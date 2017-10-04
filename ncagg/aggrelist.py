import netCDF4 as nc
import numpy as np
import os
import logging
from functools import reduce

from ncagg.config import Config

logger = logging.getLogger(__name__)


def get_fill_for(variable):
    """
    Get an appropriate fill value for a NetCDF variable.
    
    :param variable: A variable config dict.
    :return: A fill value for variable.
    """
    datatype = np.dtype(variable["datatype"])
    try:
        return datatype.type(np.nan)
    except ValueError:
        # for an integer type, there is no concept of nan, this will raise
        # ValueError: cannot convert float NaN to integer, so use -9999 instead
        # main reason for this complexity is to handle exis integer datatypes
        nc_default_fill = datatype.type(nc.default_fillvals[datatype.str[1:]])
        return datatype.type(variable["attributes"].get("_FillValue", nc_default_fill))


class AbstractNode(object):
    """
    Abstract template for an AggreList node.

    At aggregation time, an AggreList expects to be able to call
    - size_along to get the size along the unlimited dimension that it will get from data_for
    - data_for to get the data corresponding to this Node
    
    This is basically the public interface implemented by Nodes (currently FillNode and InputFileNode). Anything
    that is called externally should be templated here.
    """

    def __init__(self, config):
        # type: (Config) -> None
        """
        :param config: a product config, should be what is kept by Aggregator
        """
        super(AbstractNode, self).__init__()
        self.config = config

    def __repr__(self):
        return self.__str__()

    def get_size_along(self, unlimited_dim):
        """
        Get the size of the output along some unlimited dimension. unlimited_dim must be an
        unlimited dim with a configured/known size.

        :type unlimited_dim: str
        :param unlimited_dim: name of an unlimited dim to get the size along
        :rtype: int
        :return: the size of output along unlimited_dim
        """
        raise NotImplementedError

    def data_for(self, variable):
        """
        Get the data configured by this node for the given variable. It is expected that the size
        of the output of data_for along any unlimited dimensions is consistent with the return value
        of size_along.

        :type variable: dict
        :param variable: A dict var spec for which this Node is getting data for.
        :type config: dict
        :param config: A list dimensions dicts specifying the size of dimensions, None for unlimited.
        :return: np.array
        """
        raise NotImplementedError

    def callback_with_file(self, callback=None):
        raise NotImplementedError


class FillNode(AbstractNode):
    """
    A fill node represents a segment in an AggreList which needs
    to be filled with fill values at aggregation time.
    """

    def __init__(self, config):
        super(FillNode, self).__init__(config)
        # should be a mapping between unlimited dimensions and how many elements to put in
        self.unlimited_dim_sizes = {}
        # should be a mapping between unlimited dimensions and the last valid value, so in
        # data_for, we'll want to check if the variable requested is the one that the unlim
        # dimension is indexed_by and if so, take the expected_cadences and fill according
        # to that.
        self.unlimited_dim_index_start = {}

        # reverse index to easily check if a variable indexes a dimension.
        self._reverse_index = {d["index_by"]: d for d in config.dims.values() if d.get("index_by", None) is not None}

    def __str__(self):
        return "FillNode(%s)" % self.unlimited_dim_sizes

    def set_udim(self, udim, size, start=0):
        """
        Set the number of fills along some unlimited dimension, and optionally, if it's indexed by (index_by)
        some variable, what value the fills should start at.
        """
        udim_name = udim["name"]
        self.unlimited_dim_sizes[udim_name] = size
        self.unlimited_dim_index_start[udim_name] = 0 if start is None else start

    def get_size_along(self, udim):
        # if we haven't configured a size along some unlimited dimension, it is by
        # default 0, ie... we are not inserting anything.
        return self.unlimited_dim_sizes.get(udim["name"], 0)

    def data_for(self, var):
        # check if this var indexes an unlimited dimension...
        var_indexes = self._reverse_index.get(var["name"], None)
        unlimited_dim = var_indexes["name"] if var_indexes is not None else None
        have_cadences = all((d in var_indexes["expected_cadence"].keys() for d in var["dimensions"])) \
            if var_indexes is not None else None

        linspaces = []  # these will construct the values if we return anything besides fill values.
        result_shape = []

        for index, dim in enumerate(var["dimensions"]):

            dim_size = self.config.dims[dim]["size"]
            dim_unlim = dim_size is None  # save dim_unlim because we'll set the size

            if dim_unlim:
                # do this for any unlimited dim encountered
                dim_size = self.get_size_along(self.config.dims[dim])

            result_shape.append(dim_size)

            if var_indexes is not None and have_cadences:
                expected_cadence = var_indexes["expected_cadence"][dim]
                start = 0
                stop = float(dim_size -1) / expected_cadence if expected_cadence != 0 else start
                linspaces.append(
                    np.linspace(start, stop, dim_size).reshape(
                        [1 if index != i else -1 for i in range(len(var["dimensions"]))]
                    )
                )
                if dim_unlim:
                    linspaces[-1] += 1. / expected_cadence

        if var_indexes is not None and have_cadences:
            initial_value = self.unlimited_dim_index_start.get(unlimited_dim, 0)
            return reduce(lambda x, y: x + y, linspaces) + initial_value
        else:
            return np.full(result_shape, get_fill_for(var), dtype=np.dtype(var["datatype"]))

    def callback_with_file(self, callback=None):
        """ Fill node not associated with a file, so there is nothing to do here. Ignored basically. """
        pass


class InputFileNode(AbstractNode):
    def __init__(self, config, filename):
        super(InputFileNode, self).__init__(config)
        self.filename = filename
        # along the unlimited dimensions of the file, we'll need to potentially trim, so keep a lookup dict
        # with "dim name": [None: None] -> slice(*[None, None]) -> [:], or "dim name": [3:None] -> [3:], or
        # even "dim name": [None, -3] -> slice(*[None, 3]) -> [:-3]
        self.dim_slices = {}  # type: dict

        # The exclusions and inclusions are applied to the raw data from the netcdf in the following order
        # 1. sort with self.sort_unlim_dim argsort
        # 2. go through file internal aggregation list, start and stop according to self.dim_slices
        self.sort_unlim = {}  # argsort along each unlim dim
        self.file_internal_aggregation_list = {}  # will be one aggregation list per dim
        self.get_coverage()


    def get_coverage(self):
        """
        Similar to calculating coverage between files in aggregator, here, we calculate
        coverage within the file, filling in the self.file_internal_aggregation_list with
        slice and FillNode objects as needed.

        :return: None
        """
        index_by = [d for d in self.config.dims.values() if d["index_by"] is not None and not d["flatten"]]
        for udim in index_by:

            # cadence_hz may be None in which case we'll simply look for fill or invalid values in the index_by
            # variable. At the moment, this is hard coded to seek 0's since our main use case is index_by time
            # and we don't expect our spacecraft to teleport back to the epoch value :)
            cadence_hz = udim["expected_cadence"].get(udim["name"], None)  # what to do if None?

            # big picture, if cadence_hz is None, then we'll go through np.where(times==0) and put slices in
            # the gaps. If we DO have a cadence, then go through and look at the spacing between each.
            times = self.get_index_of_index_by(slice(None), udim)  # ok if time is multidim -> see fn for usage of
            self.sort_unlim[udim["name"]] = aggsort = np.argsort(times)
            cadence_uncert = 0.9

            # find the first good value, ie value is not zero
            slice_start = 0
            while times[aggsort[slice_start]] <= 0 and slice_start < times.size:
                slice_start += 1

            dim_agg_list = []
            in_slice = True

            to_iter = range(slice_start + 1, times.size) if cadence_hz else np.where(times <= 0)[0]

            for i in to_iter:
                # cut off conditions first,
                if times[aggsort[i]] <= 0 or np.isnan(times[aggsort[i]]):
                    if in_slice:
                        # only if we are actually in a slice... cut off slice and insert a fill
                        dim_agg_list.append(slice(slice_start, i))
                    if cadence_hz is None:
                        # when cadence_hz is none, that means we're going though np.where(times==0)
                        # instead of every value, so in that case, we jump right back into the slice
                        # because next time around though this loop will again be a time == 0, and we'll
                        # slice again. No intermediate loop to hit the if not in_slice below to reset back
                        # in, so keep in_slice == True
                        slice_start = i + 1
                    else:
                        in_slice = False

                    continue  # skip the rest of the loop

                stepdiff = times[aggsort[i]] - times[aggsort[i - 1]]
                # fall through to slice continuation
                if not in_slice:
                    slice_start = i
                    in_slice = True
                elif stepdiff < (0.5 / ((2 - cadence_uncert) * cadence_hz)):
                    # if significantly less than tolerance of cadence, remove value, ie cutoff and restart
                    dim_agg_list.append(slice(slice_start, i))
                    in_slice = False
                elif stepdiff > (2 / ((2 - cadence_uncert) * cadence_hz)):
                    # too big a time step, cutoff slice and insert fill
                    dim_agg_list.append(slice(slice_start, i))

                    num_missing = int(np.abs(np.floor(stepdiff * cadence_hz)))-1
                    f = FillNode(self.config)
                    f.set_udim(udim, num_missing, times[aggsort[i-1]])
                    dim_agg_list.append(f)

                    # jump right back into a slice.
                    slice_start = i
                    in_slice = True
                # else:  # implicit fall through, OK to be commented out, not sure there's really any perf diff
                #    pass  # otherwise if distance from last is within tolerance, continue

            # when loop terminates, if still in_slice, add that final slice.
            if in_slice and slice_start < times.size:
                dim_agg_list.append(slice(slice_start, times.size))

            self.file_internal_aggregation_list[udim["name"]] = dim_agg_list

    def get_first_of_index_by(self, udim):
        """ Get the first value along udim. """
        first_slice = self.file_internal_aggregation_list[udim["name"]][0]
        assert isinstance(first_slice, slice), "Must be a slice!"
        assert isinstance(first_slice.start, int), "Must be an int!"
        return self.get_index_of_index_by(first_slice.start, udim)

    def get_last_of_index_by(self, udim):
        """ Get the last value along udim. """
        last_slice = self.file_internal_aggregation_list[udim["name"]][-1]
        assert isinstance(last_slice, slice), "Must be a slice!"
        assert isinstance(last_slice.start, int), "Must be an int!"
        return self.get_index_of_index_by(last_slice.stop - 1, udim)

    def get_index_of_index_by(self, index, udim):
        """
        Get index (being element or slice) from the variable udim is indexed by (index_by).
        :type index: int | np.array | Slice
        :param index: element or slice
        :type udim: dict
        :param udim: unlimited dim dict config
        :rtype: np.array
        :return: values requested from variable that indexes udim
        """
        with nc.Dataset(self.filename) as nc_in:  # type: nc.Dataset
            index_by = nc_in.variables[udim["index_by"]]  # type: nc.Variable
            # The index argument is the desired index from the _external_ view. Internally, since the records have
            #  been sorted, it may actually be a different index internally. To find out, try to retrieve the
            # _internal_ index from sorted.
            internal_index = self.sort_unlim[udim["name"]][index] if udim["name"] in self.sort_unlim.keys() else index

            # If the index_by variable has multiple dimensions and an index isn't specified in other_dim_inds,
            # then default to 0
            slices = tuple([internal_index if d == udim["name"] else udim["other_dim_inds"].get(d, 0)
                            for d in index_by.dimensions ])

            try:
                # Safer to do np.nan, but this block could be simplified to always make the fill value 0.
                return np.ma.filled(index_by[slices], fill_value=np.nan)
            except ValueError:
                # Trying to fill with np.nan for an interger type will raise ValueError, so fill with 0 instead.
                # Filling with 0 is fine since 0's will be taken out by the slices. IMPORTANT: some major changes
                # needed throughout if this is ever used for data that's regularly indexed at 0
                return np.ma.filled(index_by[slices], fill_value=0)

    def __str__(self):
        dim_strs = []
        for dim, val in self.dim_slices.items():
            slice_first = val.start if val.start is not None else ''
            slice_last = val.stop if val.stop is not None else ''
            dim_strs.append("%s[%s:%s]" % (dim, slice_first, slice_last))
        return "%s[%s]" % (os.path.basename(self.filename), ",".join(dim_strs))

    def set_dim_slice_start(self, dim, start):
        """
        Explicitly set the start of the slice for dimension dim.

        :param dim: dimension to set slice for
        :type start: int
        :param start: where the slice for dim should start
        :rtype: None
        :return: None
        """
        old_slice = self.dim_slices.get(dim["name"], slice(None))
        self.dim_slices[dim["name"]] = slice(int(start), old_slice.stop)

    def set_dim_slice_stop(self, dim, stop):
        """
        Explicitly set the stop of the slice for dimension dim.

        :param dim: dimension to set slice for
        :type stop: int
        :param stop: where the slice for dim should stop
        :rtype: None
        :return: None
        """
        old_slice = self.dim_slices.get(dim["name"], slice(None))
        self.dim_slices[dim["name"]] = slice(old_slice.start, int(stop))

    def get_dim_slice(self, dim):
        """
        Get the slice for some dimension dim. First taken from self.dim_slices if it's been
        explicitly set or overridden, falling back on getting the actual size out of the
        file if it hasn't been overridden.

        :type dim: str
        :param dim: dimension to get slice for
        :rtype: slice | int
        :return: slice for dimension dim
        """
        if dim["name"] in self.dim_slices.keys():  # case: dimension has been sliced!
            return self.dim_slices[dim["name"]]
        else:  # case: no slice set, is default slice(None), ok to return slice(None) for a udim here.
            return slice(dim["size"])

    def get_file_internal_aggregation_size(self, dim):
        """
        This size is the size of the file_internal_aggregation_list (including fill) or falling back on true size.
        """
        internal_aggregation_list = self.file_internal_aggregation_list.get(dim["name"], None)
        if internal_aggregation_list is None:
            if dim["size"] is None:
                with nc.Dataset(self.filename) as nc_in:
                    if dim["name"] in nc_in.dimensions.keys():
                        return nc_in.dimensions[dim["name"]].size
                    else:
                        # CASE: new dim... handle a new dimension in output that doesn't
                        # exist in the input. It will always have size one, since it implicitly
                        # depends on file, and inside this InputFileNode, we're representing 1 file.
                        return 1
            else:
                return dim["size"]

        # Otherwise we'll need to go through and sum:
        dim_length = 0
        for each in internal_aggregation_list:
            if isinstance(each, FillNode):
                dim_length += each.get_size_along(dim)
            else:
                assert isinstance(each, slice) and each.start is not None and each.stop is not None
                dim_length += (each.stop - each.start)

        return dim_length

    def get_size_along(self, dim):
        """
        For an InputFileNode instance, the unlimited_dim arguemnt doesn't actually have to be an unlimited dimension,
        the correct value will be returned for any valid dimension in the input file.

        :return: The size of the dim
        """
        dim_slice = self.get_dim_slice(dim)  # check if it's overridden in self.dim_slices
        if isinstance(dim_slice, int):
            return 1  # if the dim_slice is just an integer index, then it's length will just be 1

        # otherwise, if it's a slice, this gets a little more complicated. Remember, we have to handle
        # the following kinds of slices: slice(None), slice(None, -3), etc...

        # so first, lets figure out the size of the dimension from the file and try to convert everything
        # to real indicies so we can just return (start - end)
        dim_length = self.get_file_internal_aggregation_size(dim)

        # find numeric start index
        if dim_slice.start is not None and dim_slice.start < 0:
            dim_start_i = dim_length + dim_slice.start  # start negative indicates indexing from end
        else:
            dim_start_i = 0 if dim_slice.start is None else dim_slice.start

        # find numeric end index
        if dim_slice.stop is not None and dim_slice.stop < 0:
            dim_end_i = dim_length + dim_slice.stop
        else:
            dim_end_i = dim_length if dim_slice.stop is None else dim_slice.stop

        assert dim_start_i <= dim_end_i, "dim size can't be neg, got [%s:%s] for %s" % (dim_start_i, dim_end_i, self)
        return dim_end_i - dim_start_i

    def data_for(self, var):
        """
        Get the data configured by this Node for the variable given.
        :type var: dict
        :param variable: a dict specification of the variable to get
        :return: array of data for variable
        """
        with nc.Dataset(self.filename) as nc_in:
            fill_value = get_fill_for(var)
            dims = [self.config.dims[d] for d in var["dimensions"]
                    if d in nc_in.variables[var["name"]].dimensions]

            # step 1: get the sorted data
            dim_slices = tuple([self.sort_unlim.get(d["name"], slice(None)) for d in dims]) or slice(None)
            prelim_data = np.ma.filled(nc_in.variables[var["name"]][dim_slices], fill_value=fill_value)

            if len(dims) == 0:
                # if this is just a scalar value, return
                return prelim_data

            # step 2: if there's an aggregation list for it, transform prelim_data according to it
            internal_agg_dims = [d["name"] for d in dims if d["name"] in self.file_internal_aggregation_list.keys()]
            if len(internal_agg_dims) > 0:
                out_shape = tuple([self.get_file_internal_aggregation_size(d) for d in dims])
                transformed_data = np.full(out_shape, fill_value, dtype=prelim_data.dtype)
                dim_along = internal_agg_dims[0]
                loc_along_dim = 0
                dim_i = next((i for i in range(len(dims)) if dims[i]["name"] == dim_along))
                for agg_seg in self.file_internal_aggregation_list[dim_along]:
                    if isinstance(agg_seg, FillNode):
                        data_in_transit = agg_seg.data_for(var)
                    else:
                        assert isinstance(agg_seg, slice), "Found %s" % agg_seg
                        data_in_transit = prelim_data[[agg_seg if d["name"] == dim_along else slice(None)
                                                       for d in dims]]


                    size_along_dim = np.shape(data_in_transit)[dim_i]
                    transformed_data[[slice(loc_along_dim, loc_along_dim + size_along_dim) if i == dim_i else slice(None)
                                      for i in range(len(dims))]] = data_in_transit

                    loc_along_dim += size_along_dim

                # this doesn't work, but was a first attempt at how to solve internal agg lists for a variable
                # that depended on multiple unliited dimensions
                # for i, d in enumerate(dims):
                #     # loop over dimensions, outter to inner, gradually replacing them according to the internal
                #     # agg list if one exists for the dimension.
                #     dst_slices = [slice(None) for _ in range(i)] or [slice(None)]
                #     src_slices = [slice(None) for _ in range(i)] or [slice(None)]
                #     if d["name"] in internal_agg_dims:
                #         loc_along_dim = 0
                #         for agg_seg in self.file_internal_aggregation_list[d["name"]]:
                #             if isinstance(agg_seg, FillNode):
                #                 data_in_transit = agg_seg.data_for(var)
                #             else:
                #                 assert isinstance(agg_seg, slice), "Found %s" % agg_seg
                #                 src_slices[-1] = agg_seg  # here's the slice we'll get
                #                 data_in_transit = prelim_data[src_slices]  # pull it from prelim, get the shape
                #
                #             size_along_dim = np.shape(data_in_transit)[i]
                #             dst_slices[-1] = slice(loc_along_dim, loc_along_dim + size_along_dim)
                #             src_slices[-1] = slice(size_along_dim)
                #             transformed_data[dst_slices] = data_in_transit[src_slices]
                #             loc_along_dim += size_along_dim
                #
                #     else:  # just copy across
                #         transformed_data[dst_slices] = prelim_data[src_slices]
                prelim_data = transformed_data

            # step 3: slice to external view
            return prelim_data[[self.get_dim_slice(d) for d in dims]]

    def callback_with_file(self, callback=None):
        """
        Callback for anything that needs access to the file object stored in the node. Intended
        mainly for attribute handling.

        :param callback: function to call with represented NetCDF Dataset handle as argument.
        :return: None
        """
        if callback is not None:
            with nc.Dataset(self.filename) as nc_in:
                callback(nc_in)


class AggreList(list):
    """
    An AggreList instance is a list like object which contains data structures which can
    be evalutated to produce an aggregated output file.

    It is recommended to use the Aggregator class to construct the AggreList object.
    """

    def __init__(self):
        super(AggreList, self).__init__()

    def append(self, p_object):
        """
        Only insert valid aggregation Node type object.
        :param p_object:
        :return:
        """
        if isinstance(p_object, AbstractNode):
            super(AggreList, self).append(p_object)
