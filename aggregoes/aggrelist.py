import os

import netCDF4 as nc
import numpy as np


def get_fill_for(variable):
    datatype = np.dtype(variable["datatype"])
    try:
        return datatype.type(np.nan)
    except ValueError:
        # for an integer type, there is no concept of nan, this will raise
        # ValueError: cannot convert float NaN to integer, so use -9999 instead
        # main reason for this complexity is to handle exis integer datatypes
        nc_default_fill = datatype.type( nc.default_fillvals[datatype.str[1:]] )
        return datatype.type(variable.get("attributes", {}).get("_FillValue", nc_default_fill))


class AbstractNode(object):
    """
    Abstract template for an AggreList node.

    At aggregation time, an AggreList expects to be able to call
    - size_along to get the size along the unlimited dimension that it will get from data_for
    - data_for to get the data corresponding to this Node

    """

    def __init__(self):
        super(AbstractNode, self).__init__()

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

    def data_for(self, variable, dimensions, attribute_processor=None):
        """
        Get the data configured by this node for the given variable. It is expected that the size
        of the output of data_for along any unlimited dimensions is consistent with the return value
        of size_along.

        :type variable: dict
        :param variable: A dict var spec for which this Node is getting data for.
        :type dimensions: dict
        :param dimensions: A list dimensions dicts specifying the size of dimensions, None for unlimited.
        :type attribute_processor: function
        :param attribute_processor: A callback which expects a netcdf object and handles the global attributes
        :return: np.ndarray
        """
        raise NotImplementedError


class FillNode(AbstractNode):
    """
    A fill node represents a segment in an AggreList which needs
    to be filled with fill values at aggregation time.
    """

    def __init__(self, unlimited_dim_indexed_by_time_var_map=None):
        super(FillNode, self).__init__()
        # should be a mapping between unlimited dimensions and how many elements to put in
        self.unlimited_dim_sizes = {}
        # should be a mapping between unlimited dimensions and the last valid value, so in
        # data_for, we'll want to check if the variable requested is the one that the unlim
        # dimension is indexed_by and if so, take the expected_cadences and fill according
        # to that.
        self.unlimited_dim_index_start = {}

        # assuming this has already been validated
        self.unlimited_dim_indexed_by_time_var_map = unlimited_dim_indexed_by_time_var_map or {}
        self._reverse_index = {v["index_by"]: k for k, v in self.unlimited_dim_indexed_by_time_var_map.items()}

    def __str__(self):
        return "FillNode(%s)" % self.unlimited_dim_sizes

    def set_size_along(self, unlimited_dim, size):
        """
        Set the size of the fills along some unlimited dimension.

        :param unlimited_dim:
        :param size:
        :return:
        """
        self.unlimited_dim_sizes[unlimited_dim] = size

    def set_sizes_along(self, sizes):
        """
        Set the size of the fills along some unlimited dimension.

        :type sizes: dict
        :param sizes: dict of unlim dim as keys and sizes as values
        :return: None
        """
        self.unlimited_dim_sizes.update(sizes)

    def set_unlim_dim_index_start(self, unlimited_dim, start):
        """
        For an unlimited dimensions that is indexed by some value, if the expected cadence is set, we can
        fill the index with estimated indicies based on the cadence instead of just fill values, but we have
        to know where to start. This allows that value to be configured. It is expected to be the last valid
        value of the index before the gap, ie the first value data_for(index_var) returns will be start + 1./cadence.

        :param unlimited_dim:
        :param start:
        :return:
        """
        self.unlimited_dim_index_start[unlimited_dim] = start

    def get_size_along(self, unlimited_dim):
        # if we haven't configured a size along some unlimited dimension, it is by
        # default 0, ie... we are not inserting anything.
        return self.unlimited_dim_sizes.get(unlimited_dim, 0)

    def data_for(self, variable, dimensions, attribute_processor=None):
        """

        :param variable:
        :param dimensions:
        :param attribute_processor: ignored in FillNodes
        :return:
        """

        # check if this variable indexes an unlimited dimension...
        var_indexes = self._reverse_index.get(variable["name"], None)

        linspaces = []  # these will construct the values if we return anything besides fill values.
        result_shape = []
        unlimited_dim = None  # Set to none until we know the unlimited

        for index, dim in enumerate(variable["dimensions"]):
            size_from_dimensions = next((d["size"] for d in dimensions if d["name"] == dim), None)
            dim_is_unlim = size_from_dimensions is None
            # save the unlimited dim name to lookup initial base value outside of loop
            if dim_is_unlim:
                unlimited_dim = dim
            # if size_from_dimensions is none, ie it's an unlimited dimenions, then we expect
            # to find it in self.unlimited_dim_sizes, otherwise expect an exception to be raised.
            size_from_dimensions = size_from_dimensions or self.get_size_along(dim)
            result_shape.append(size_from_dimensions)
            # only do this part if this is an index for an unlimited dim
            if var_indexes is not None:
                dim_expected_cadence = self.unlimited_dim_indexed_by_time_var_map[var_indexes]["expected_cadence"][dim]
                start = 0
                stop = float(size_from_dimensions - 1) / dim_expected_cadence if dim_expected_cadence else start
                linspaces.append(
                    np.linspace(start, stop, size_from_dimensions).reshape(
                        [1 if index != i else -1 for i in xrange(len(variable["dimensions"]))]
                    )
                )
                # if this is THE unlimited dimension, add the cadence. Since we start at 0, but the value in
                # self.unlimited_dim_index_start is the actual existing value,
                if dim_is_unlim:
                    linspaces[-1] += dim_expected_cadence

        if var_indexes is not None:
            # unfortunately, I couldn't get np.sum to work here. Keeps giving
            # ValueError('could not broadcast input array from shape (xx) into shape (x)',
            # the reduce works as I want though.
            initial_value = self.unlimited_dim_index_start.get(unlimited_dim, 0)
            return reduce(lambda x, y: x + y, linspaces) + initial_value
        # return np.full(result_shape, variable["attributes"].get("_FillValue", np.nan),
        #                dtype=np.dtype(variable["datatype"]))
        return np.full(result_shape, get_fill_for(variable), dtype=np.dtype(variable["datatype"]))


class InputFileNode(AbstractNode):
    def __init__(self, filename, unlimited_dim_indexed_by_time_var_map=None):
        """
        For sake of optimization, we're going to assume that the unlimited_dim map has been
        validated before being passed here.

        :param filename:
        :param unlimited_dim_indexed_by_time_var_map:
        """
        super(InputFileNode, self).__init__()
        self.filename = filename
        # along the unlimited dimensions of the file, we'll need to potentially trim, so keep a lookup dict
        # with "dim name": [None: None] -> slice(*[None, None]) -> [:], or "dim name": [3:None] -> [3:], or
        # even "dim name": [None, -3] -> slice(*[None, 3]) -> [:-3]
        self.dim_slices = {}  # type: dict

        # if this isn't set, then can't get self.first_time or self.last_time and instead we'll fall
        # back on the filename start and end, this should be a mapping between an unlimited dimension
        # and a variable containing corresponding time stamps.
        # it should handle multi dimensional time stamps,
        # "record_number": { "index_by": "time_variable", "other_dim_indicies": { "samples_per_record": 0 }}
        # assuming this has already been validated.
        self.unlimited_dim_indexed_by_time_var_map = unlimited_dim_indexed_by_time_var_map or {}
        # The exclusions and inclusions are applied to the raw data from the netcdf in the following order
        # 1. sort with self.sort_unlim_dim argsort
        # -- removed 2. exclude indicides from unlim with a = np.ma.array(v, mask=False), a.mask[self.exclude[dim]] = True
        # 3. go through file internal aggregation list, start and stop according to self.dim_slices
        # 4. go through aggregation list
        self.sort_unlim = {}  # argsort along each unlim dim
        self.file_internal_aggregation_list = {}  # will be one aggregation list per dim

        # TODO: break this out into a function
        if self.unlimited_dim_indexed_by_time_var_map:
            for unlim_dim in self.unlimited_dim_indexed_by_time_var_map.keys():

                # cadence_hz may be None in which case we'll simply look for fill or invalid values in the index_by
                # variable. At the moment, this is hard coded to seek 0's since our main use case is index_by time
                # and we don't expect our spacecraft to teleport back to the epoch value :)
                cadence_hz = self.unlimited_dim_indexed_by_time_var_map[unlim_dim].get("expected_cadence", {}).get(unlim_dim, None)

                # big picture, if cadence_hz is None, then we'll go through np.where(times==0) and put slices in
                # the gaps
                # if no cadence, np.where(times == 0) for each insert slice between
                times = self.get_index_of_index_by(slice(None), unlim_dim)
                self.sort_unlim[unlim_dim] = aggsort = np.argsort(times)
                cadence_uncert = 0.9

                # find the first good value, ie value is not zero
                slice_start = 0
                while times[aggsort[slice_start]] == 0 and slice_start < times.size:
                    slice_start += 1

                dim_agg_list = []
                in_slice = True

                to_iter = xrange(slice_start + 1, times.size) if cadence_hz else np.where(times == 0)[0]

                for i in to_iter:
                    # cut off conditions first,
                    if times[aggsort[i]] == 0:
                        if in_slice and i - slice_start > 1:
                            # only if there is content (len > 1) in the slice and we are actually in a slice...
                            # cut off slice and insert a fill
                            dim_agg_list.append(slice(slice_start, i))
                        if cadence_hz is None:
                            # keep in_slice == True
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
                        dim_agg_list.append(slice(slice_start, i - 1))
                        in_slice = False
                    elif stepdiff > (2 / ((2 - cadence_uncert) * cadence_hz)):
                        # too big a time step, cutoff slice and insert fill
                        dim_agg_list.append(slice(slice_start, i))

                        num_missing = int(np.abs(np.floor(stepdiff * cadence_hz)))-1
                        f = FillNode(self.unlimited_dim_indexed_by_time_var_map)
                        f.set_size_along(unlim_dim, num_missing)
                        f.set_unlim_dim_index_start(unlim_dim, times[aggsort[i-1]])
                        dim_agg_list.append(f)

                        # jump right back into a slice.
                        slice_start = i
                        in_slice = True
                        # else:
                        #    # otherwise if distance from last is within tolerance, continue
                        #    pass

                # when loop terminates, if still in_slice, add that final slice.
                # EXCEPT, check for the edge case where cadence_hz is none and the time is a 0
                # in which case slice_start would == times.size
                if in_slice and slice_start < times.size:
                    dim_agg_list.append(slice(slice_start, times.size))

                self.file_internal_aggregation_list[unlim_dim] = dim_agg_list

    def get_first_of_index_by(self, unlim_dim):
        assert unlim_dim in self.unlimited_dim_indexed_by_time_var_map.keys(), "Node init w/o unlim_config?"
        # if any of the lines below raises a KeyError, it's likely that self was initialized without an
        # unlimited index_by mapping.
        first_slice = self.file_internal_aggregation_list[unlim_dim][0]
        assert isinstance(first_slice, slice), "Must be a slice!"
        assert isinstance(first_slice.start, int), "Must be an int!"
        return self.get_index_of_index_by(first_slice.start, unlim_dim)

    def get_last_of_index_by(self, unlim_dim):
        assert unlim_dim in self.unlimited_dim_indexed_by_time_var_map.keys(), "Node init w/o unlim_config?"
        # if any of the lines below raises a KeyError, it's likely that self was initialized without an
        # unlimited index_by mapping.
        last_slice = self.file_internal_aggregation_list[unlim_dim][-1]
        assert isinstance(last_slice, slice), "Must be a slice!"
        assert isinstance(last_slice.start, int), "Must be an int!"
        return self.get_index_of_index_by(last_slice.stop-1, unlim_dim)

    def get_index_of_index_by(self, index, unlim_dim):
        unlim_mapping = self.unlimited_dim_indexed_by_time_var_map[unlim_dim]
        with nc.Dataset(self.filename) as nc_in:  # type: nc.Dataset
            index_by = nc_in.variables[unlim_mapping["index_by"]]  # type: nc.Variable
            # get the slices we need to fetch the index according to the config, note that the
            # .get may fail to find a mapping for the unlimited dim and so will default to
            # 0, which should be the first record, and thus what we're after
            index = self.sort_unlim[unlim_dim][index] if unlim_dim in self.sort_unlim.keys() else index
            slices = tuple([
                               index if d == unlim_dim
                               else unlim_mapping.get("other_dim_indicies", {}).get(d, 0)
                               for d in index_by.dimensions
                               ])

            return index_by[slices]

    def get_units_of_index_by(self, unlim_dim):
        """
        Get the units of of the variable by which unlim_dim is indexed. (implemented for convenience so
        that unlim_dim/expected_cadence/(min|max) can be given as datetime
        :param unlim_dim:
        :return:
        """
        unlim_mapping = self.unlimited_dim_indexed_by_time_var_map[unlim_dim]

        with nc.Dataset(self.filename) as nc_in:  # type: nc.Dataset
            time_var = nc_in.variables[unlim_mapping["index_by"]]  # type: nc.Variable
            return time_var.units

    def __str__(self):
        dim_strs = []
        for dim, val in self.dim_slices.items():
            slice_first = val.start or ''
            slice_last = val.stop or ''
            dim_strs.append("%s[%s:%s]" % (dim, slice_first, slice_last))
        return "%s[%s]" % (os.path.basename(self.filename), ",".join(dim_strs))

    def set_dim_slice(self, dim, dim_slice=slice(None)):
        """
        Explicitly set the slice that's taken from the input file for a certain dimension.
        This slice is an *external interface*, ie this slice is applied to the output view
        of the data, taking into account fill values to be inserted.

        For a simple illustration:
        If the internal slice of netcdf data is slice(10, None=100) and a self.set_dim_slice(dim, slice(10, None))
        is applied, that translates to a netcdf slice of slice(20, None=100).

        :type dim_slice: slice | int
        :param dim: dimension to set slice for
        :param dim_slice: the slice by which to slice dimension
        :rtype: None
        :return: None
        """
        if isinstance(dim_slice, (int, slice)):
            self.dim_slices[dim] = dim_slice
        else:
            raise ValueError("Invalid slice or index")

    # REMOVED: excluded inidicies are implicitly included in the slicing via file_internal_aggregation_list
    # if there is a strong use case to add this, it should likely be added as another transform layer on top
    # using masked arrays: a = np.ma.array(v, mask=False), a.mask[self.exclude[dim]] = True, and so will be
    # somewhat independent of the other transforms. Would need to consider impacts to calculation of size
    # something like (prev layers - len(self.exclude[dim])
    # def add_unlim_dim_exclude_index(self, unlim_dim, index):
    #     """
    #     Specify to exclude a certain index from an unlimited dimensions during aggregation.
    #     This should be useful in removing, eg 0 timestamps within a file.
    #     :param unlim_dim:
    #     :param index:
    #     :return:
    #     """
    #     self.exclude_index_from_unlim[unlim_dim] = self.exclude_index_from_unlim.get(unlim_dim, []).append(index)

    def set_dim_slice_start(self, dim, start):
        """
        Explicitly set the start of the slice for dimension dim.

        :param dim: dimension to set slice for
        :type start: int
        :param start: where the slice for dim should start
        :rtype: None
        :return: None
        """
        if isinstance(start, int):
            old_slice = self.dim_slices.get(dim, slice(None))
            self.dim_slices[dim] = slice(start, old_slice.stop)
        else:
            raise ValueError("Expected integer index, got %s" % type(start))

    def set_dim_slice_stop(self, dim, stop):
        """
        Explicitly set the stop of the slice for dimension dim.

        :param dim: dimension to set slice for
        :type stop: int
        :param stop: where the slice for dim should stop
        :rtype: None
        :return: None
        """
        if isinstance(stop, int):
            old_slice = self.dim_slices.get(dim, slice(None))
            self.dim_slices[dim] = slice(old_slice.start, stop)
        else:
            raise ValueError("Expected integer index, got %s" % type(stop))

    def get_dim_slice(self, dim):
        """
        Get the slice for some dimension dim. First taken from self.dim_slices if it's been
        explicitly set or overridden, falling back on getting the actual value out of the
        file if it hasn't been overridden.

        :type dim: str
        :param dim: dimension to get slice for
        :rtype: slice | int
        :return: slice for dimension dim
        """
        if dim in self.dim_slices.keys():
            return self.dim_slices[dim]
        else:
            with nc.Dataset(self.filename) as nc_in:
                if dim in nc_in.dimensions.keys() and nc_in.dimensions[dim].isunlimited():
                    # must return none if unlimited so that get_size_along uses length from
                    # get_file_internal_aggregation_size - which takes into account the internal agg list
                    # and then falls back on nc_in.dimesionse[dim].size if there is no agg list
                    return slice(None)
                elif dim in nc_in.dimensions.keys():
                    # it's ok if dim is unlimited here, will still have a size.
                    return slice(nc_in.dimensions[dim].size)
                else:
                    raise ValueError("Dimension does not exist: %s" % dim)

    def get_file_internal_aggregation_size(self, unlim_dim):
        """
        This size is the size of the file_internal_aggregation_list (ie. including fill)
        or falling back on
        :param unlim_dim:
        :return:
        """
        internal_aggregation_list = self.file_internal_aggregation_list.get(unlim_dim, None)
        if internal_aggregation_list is None:
            with nc.Dataset(self.filename) as nc_in:
                return nc_in.dimensions[unlim_dim].size

        # Otherwise we'll need to go through and sum:
        dim_length = 0
        for each in internal_aggregation_list:
            if isinstance(each, FillNode):
                dim_length += each.get_size_along(unlim_dim)
            else:
                assert isinstance(each, slice)
                dim_length += (each.stop - each.start)

        return dim_length

    def get_size_along(self, unlim_dim):
        """
        For an InputFileNode instance, the unlimited_dim arguemnt doesn't actually
        have to be an unlimited dimension, the correct value will be returned for any
        valid dimension in the input file.

        :param unlim_dim: A variable in the input netcdf
        :return: The size of the variable unlimited_dim
        """
        # check if it's overridden in self.dim_slices
        dim_slice = self.get_dim_slice(unlim_dim)
        if isinstance(dim_slice, int):
            # if the dim_slice is just an integer index, then it's length will just be 1
            return 1

        # otherwise, if it's a slice, this gets a little more complicated. Remember, we have to handle
        # the following kinds of slices: slice(None), slice(None, -3), etc...

        # so first, lets figure out the size of the dimension from the file and try to convert everything
        # to real indicies so we can just return (start - end)
        dim_length = self.get_file_internal_aggregation_size(unlim_dim)

        dim_start_i = (
            (dim_length + dim_slice.start if dim_slice.start is not None and dim_slice.start < 0 else dim_slice.start)
            or 0
        )

        if dim_slice.stop is None:
            dim_end_i = dim_length
        else:
            assert dim_slice.stop is not None
            if dim_slice.stop < 0:
                dim_end_i = dim_length + dim_slice.stop
            else:
                dim_end_i = dim_slice.stop

        assert dim_start_i <= dim_end_i, "dim size can't be negative"
        return dim_end_i - dim_start_i

    def data_for(self, variable, dimensions, attribute_processor=None):
        """
        Get the data configured by this Node for the variable given.
        :type variable: dict
        :param variable: a dict specification of the variable to get
        :type dimensions: list
        :param dimensions: list of dimensions in the output.
        :type attribute_processor: function
        :param attribute_processor: global attribute processor
        :return:
        """

        with nc.Dataset(self.filename) as nc_in:
            if attribute_processor is not None:
                attribute_processor(nc_in)

            fill = get_fill_for(variable)  # get the fill value, needed in both branches below

            # Sorry, there's a limitation here, can only handle 1 unlimited dimension with internal aggregation
            # figure out if we have an internal aggregation list for the unlimited dim of this variable
            internal_agg_dim = next(
                (dim for dim in variable["dimensions"] if dim in self.file_internal_aggregation_list.keys()),
                None
            )
            if internal_agg_dim is not None:
                growing = None  # will become an np.ndarray
                for internal_agg_segment in self.file_internal_aggregation_list[internal_agg_dim]:

                    if isinstance(internal_agg_segment, slice):
                        # if the agg segment is a slice, get it directly out of the nc and add to growing
                        var_slices = []
                        for dim in nc_in.variables[variable["name"]].dimensions:
                            if dim == internal_agg_dim:
                                aggsort = self.sort_unlim[dim]
                                var_slices.append(aggsort[internal_agg_segment])
                            else:
                                var_slices.append(self.get_dim_slice(dim))
                        var_slices = tuple(var_slices)
                        from_file = np.ma.filled(nc_in.variables[variable["name"]][var_slices], fill_value=fill)
                        if growing is None:
                            # initialize growing, this is done here since further concatenations must
                            # have the same shape
                            # assumption: the first internal_agg_segment is NOT a FillNode
                            growing = from_file
                        else:
                            growing = np.concatenate((growing, from_file))

                    else:
                        # if not a slice, it must be a FillNode, assert so and handle accordingly
                        assert isinstance(internal_agg_segment, FillNode)
                        growing = np.concatenate((growing, internal_agg_segment.data_for(
                            variable, dimensions
                        )))

                return growing[[self.get_dim_slice(dim) for dim in variable["dimensions"]]]

            # if there's no internal_aggregation_list set up, it's just a regular pull the data from the file
            # get the ordering and slicing of dimenisons
            var_slices = []
            for dim in nc_in.variables[variable["name"]].dimensions:
                aggsort = self.sort_unlim.get(dim, None)
                if aggsort is not None:
                    var_slices.append(aggsort[self.get_dim_slice(dim)])
                else:
                    var_slices.append(self.get_dim_slice(dim))

            # there are some variables that have no dimensions, ie. they are just a
            # scalar value (seems odd to me, but these are values like "number_samples_per_report" in mag
            # L1b.
            try:
                return np.ma.filled(nc_in.variables[variable["name"]][var_slices or slice(None)], fill_value=fill)
            except ValueError:
                return nc_in.variables[variable["name"]][var_slices or slice(None)]


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
