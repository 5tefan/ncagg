import os
import cerberus
import numpy as np
import netCDF4 as nc
from datetime import datetime, timedelta
from utils.init_config_template import generate_default_variables_config, \
    generate_default_global_attributes_config, generate_default_dimensions_config
from utils.validate_configs import validate_unlimited_dim_indexed_by_time_var_map as validate_unlim_config

import logging, traceback

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
logging.getLogger().addHandler(console)


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

    def data_for(self, variable, dimensions):
        """
        Get the data configured by this node for the given variable. It is expected that the size
        of the output of data_for along any unlimited dimensions is consistent with the return value
        of size_along.

        :type dimensions: dict
        :param dimensions: A list dimensions dicts specifying the size of dimensions, None for unlimited.
        :type variable: dict
        :param variable: A dict var spec for which this Node is getting data for.
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
        return self.unlimited_dim_sizes.get(unlimited_dim, None)

    def data_for(self, variable, dimensions):

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
            size_from_dimensions = size_from_dimensions or self.unlimited_dim_sizes[dim]
            result_shape.append(size_from_dimensions)
            # only do this part if this is an index for an unlimited dim
            if var_indexes is not None:
                dim_expected_cadence = self.unlimited_dim_indexed_by_time_var_map[var_indexes]["expected_cadence"][dim]
                start = 0
                stop = float(size_from_dimensions - 1)/dim_expected_cadence if dim_expected_cadence else start
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
        return np.full(result_shape, np.nan, dtype=np.dtype(variable["datatype"]))


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

    def get_index_of_unlim(self, index, unlim_dim=None):
        """
        Get the value from an index along an unlimited dimension of the file as specified by
        self.unlimited_dim_indexed_by_time_var_map.

        :param index:
        :return:
        """
        if unlim_dim is None and len(self.unlimited_dim_indexed_by_time_var_map) > 0:
            # if there's more than one, we're simply going by the first in .values(),
            # could make this configurable later, possibly add a "primary": True flag
            # in one of the mappings.
            unlim_dim = self.unlimited_dim_indexed_by_time_var_map.keys()[0]

        unlim_mapping = self.unlimited_dim_indexed_by_time_var_map[unlim_dim]

        with nc.Dataset(self.filename) as nc_in:  # type: nc.Dataset
            time_var = nc_in.variables[unlim_mapping["index_by"]]  # type: nc.Variable
            # get the slices we need to fetch the start time of the file, note that the
            # .get will fail to find a mapping for the unlimited dim and so will default to
            # 0, which should be the first record, and thus what we're after
            slices = tuple([index if d == unlim_dim else unlim_mapping["other_dim_indicies"].get(d, index)
                            for d in time_var.dimensions])

            # flatten the variable just in case,
            return time_var[slices].flatten()[0]

    def get_units_of_unlim_index(self, unlim_dim):
        """
        Get the units of of the variable by which unlim_dim is indexed. (implemented for convenience so
        that unlim_dim/expected_cadence/(min|max) can be given as datetime
        :param unlim_dim:
        :return:
        """
        if unlim_dim is None and len(self.unlimited_dim_indexed_by_time_var_map) > 0:
            # if there's more than one, we're simply going by the first in .values(),
            # could make this configurable later, possibly add a "primary": True flag
            # in one of the mappings.
            unlim_dim = self.unlimited_dim_indexed_by_time_var_map.keys()[0]

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
            raise ValueError("Invalid start index")

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
            raise ValueError("Invalid stop index")

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
                if dim in nc_in.dimensions.keys() and nc_in:
                    # it's ok if dim is unlimited here, will still have a size.
                    return slice(nc_in.dimensions[dim].size)
                else:
                    raise ValueError("Dimension does not exist: %s" % dim)

    def get_size_along(self, unlimited_dim):
        """
        For an InputFileNode instance, the unlimited_dim arguemnt doesn't actually
        have to be an unlimited dimension, the correct value will be returned for any
        valid dimension in the input file.

        :param unlimited_dim: A variable in the input netcdf
        :return: The size of the variable unlimited_dim
        """
        # check if it's overridden in self.dim_slices
        dim_slice = self.get_dim_slice(unlimited_dim)
        if isinstance(dim_slice, int):
            # if the dim_slice is just an integer index, then it's length will just be 1
            return 1

        # otherwise, if it's a slice, this gets a little more complicated. Remember, we have to handle
        # the following kinds of slices: slice(None), slice(None, -3), etc...

        # so first, lets figure out the size of the dimension from the file and try to convert everything
        # to real indicies so we can just return (start - end)
        with nc.Dataset(self.filename) as nc_in:
            dim_length = nc_in.dimensions[unlimited_dim].size

        dim_start_i = (
            (dim_length - dim_slice.start if dim_slice.start is not None and dim_slice.start < 0 else dim_slice.start)
            or 0
        )

        dim_end_i = (
            (dim_length + dim_slice.stop if dim_slice.stop is not None and dim_slice.stop < 0 else dim_slice.stop)
            or dim_length
        )

        assert dim_start_i <= dim_end_i, "dim size can't be negative"
        return dim_end_i - dim_start_i

    def data_for(self, variable, dimensions):
        """
        Get the data configured by this Node for the variable given.
        :type variable: dict
        :param variable: a dict specification of the variable to get
        :type dimensions: list
        :param dimensions: list of dimensions in the output.
        :return:
        """
        with nc.Dataset(self.filename) as nc_in:
            # get the ordering and slicing of dimenisons
            var_slices = []
            for dim in nc_in.variables[variable["name"]].dimensions:
                var_slices.append(self.get_dim_slice(dim))

            # there are some variables that have no dimensions, ie. they are just a
            # scalar value (seems odd to me, but these are values like "number_samples_per_report" in mag
            # L1b.
            try:
                return np.ma.filled(nc_in.variables[variable["name"]][var_slices or slice(None)], fill_value=np.nan)
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


class Aggregator(object):
    """
    Nominally, this is a three step process.
        # STEP 1. input files and config
        self.config = config
        # STEP 2. generate aggregation list
        aggregation_list = self.generate_aggregation_list()
        # STEP 3. finally, evaluate the aggregation list
        self.evaluate_aggregation_list(aggregation_list)


    Ways to run:

    These will automatically go to the /nfs/... archive and get the required data.
        Aggregator.doDay("YYYYMMDD", "data-short-name")
        Aggregator.doWeek("YYYYMM", "data-short-name")
        Aggregator.doYear("YYYY", "data-short-name")

    Aggregator.doCustom(file_list, start_date, end_date)
    """

    def __init__(self, config=None):
        super(Aggregator, self).__init__()
        self.config = config or {}
        self.last_value_before = None
        self.first_value_after = None
        self.timing_certainty = 0.9
        # if config doesn't come with either a "global attributes" or a "data variables" key,
        # they will be automatically configured when generate_aggregation_list is called based
        # on the first file in the list to aggregate as a template.

    def generate_aggregation_list(self, files_to_aggregate, config=None):
        # if global attributes and data variables are not configured, set them to defaults based on the first
        # file in files_to_aggregate
        if "global attributes" not in self.config.keys():
            self.config["global attributes"] = generate_default_global_attributes_config(files_to_aggregate[0])
        if "dimensions" not in self.config.keys():
            self.config["dimensions"] = generate_default_dimensions_config(files_to_aggregate[0])
        if "variables" not in self.config.keys():
            self.config["variables"] = generate_default_variables_config(files_to_aggregate[0])

        self.config["config"] = config

        # auto detect the unlimited dimensions, it is along these that we need to aggregate
        # unlimited_dims = [dim for dim in self.config["dimensions"] if dim["size"] is None]

        aggregation_list = AggreList()

        unlim_config = validate_unlim_config(self.config.get("config"), files_to_aggregate[0]) if \
            len(files_to_aggregate) > 0 else None
        input_files = [InputFileNode(fn, unlim_config) for fn in sorted(files_to_aggregate)]
        if unlim_config is not None:
            unlim_fills_needed = {
                unlim_dim: self.get_coverage_for(input_files, unlim_dim) for unlim_dim in unlim_config.keys()
            }

        for index, file_node in enumerate(input_files):

            # noinspection PyUnboundLocalVariable
            if unlim_config is not None and len(unlim_fills_needed) > 0:
                fill_node = FillNode(unlim_config)  # init, may not be used though
                for unlim_dim in unlim_config.keys():
                    # this element is tuple, first is np.ndarray of number missing between each
                    # file, and second np.ndarray of last present value before missing if there is a gap
                    num_missing, missing_start = unlim_fills_needed[unlim_dim]
                    if num_missing[index] > 0:
                        fill_node.set_size_along(unlim_dim, num_missing[index])
                        fill_node.set_unlim_dim_index_start(unlim_dim, missing_start[index])
                if len(fill_node.unlimited_dim_sizes) > 0:
                    aggregation_list.append(fill_node)

            aggregation_list.append(file_node)

        return aggregation_list

    def get_coverage_for(self, input_files, unlim_dim):
        """
        Mutate the actual input_files to fix overlap problems, return where the are gaps between files.

        :type input_files: list[InputFileNode]
        :param input_files:
        :type unlim_dim: str
        :param unlim_dim:
        :rtype: np.ndarray
        :return: boolean array indicating where the gap sizes are too big between files
        """
        # cadence_hz = next((d["expected_cadence"] for d in self.config["dimensions"] if d["name"] == unlim_dim), None)
        cadence_hz = self.config["config"][unlim_dim]["expected_cadence"][unlim_dim]


        def cast_bound(bound):
            """
            Cast a bound to a numerical type for use. Will not be working directly with datetime objects.

            :param bound: a min or max value read from a config
            :return: the bound value converted to it's numerical representation
            """
            if isinstance(bound, datetime):
                return nc.date2num([bound], input_files[0].get_units_of_unlim_index(unlim_dim))[0]
            return bound

        last_value_before = None
        first_value_after = None

        try:
            last_value_before = cast_bound(self.config["config"][unlim_dim]["min"])
            first_value_after = cast_bound(self.config["config"][unlim_dim]["max"])
        except KeyError:
            # ignore, likely just wasn't configured in which case, we don't have
            # any bounds and will just use whatever data is in the input files.
            pass

        # remove files that aren't between last_value_before and first_value_after
        starts = []
        ends = []
        # iterate over a copy of the list since we might be removing things while iterating over it
        for each in input_files[:]:
            start = each.get_index_of_unlim(0, unlim_dim)
            end = each.get_index_of_unlim(-1, unlim_dim)
            if (last_value_before and end < last_value_before) or (first_value_after and start > first_value_after):
                input_files.remove(each)
            else:
                starts.append(start)
                ends.append(end)

        # turn starts and ends into np.ndarray with last_value_before and first_value_after in approriate spots
        starts = np.hstack((starts, [first_value_after or ends[-1] + (1.0/cadence_hz)]))
        ends = np.hstack(([last_value_before or starts[0] - (1.0/cadence_hz)], ends))

        # stagger and dake diff so that eg. coverage_diff[1] is gap between first and second file...
        coverage = np.empty((starts.size + ends.size), dtype=starts.dtype)
        coverage[0::2] = ends
        coverage[1::2] = starts
        coverage_diff = np.diff(coverage)[::2]

        # if the gap is less than 0, we'll need to trim something, ie two files overlap and
        # we'll need to pick one of the overlapping
        gap_too_small_upper_bound_seconds = 1.0 / ((2.0 - self.timing_certainty) * cadence_hz) if cadence_hz else 0
        gap_too_small = coverage_diff <= gap_too_small_upper_bound_seconds
        where_gap_too_small = np.where(gap_too_small)[0]
        for problem_index in where_gap_too_small:
            num_overlap = np.abs(np.round(coverage_diff[problem_index] * cadence_hz))
            # if gap at beginning of the agg period, take off from front of first file, otherwise chop
            # the end from the previous file
            if problem_index == 0:
                input_files[0].set_dim_slice_start(unlim_dim, int(np.ceil(num_overlap)))
            else:
                # this np.floor is consistent with np.ceil (pretty sure, bias towards keeping data
                # with the previous agg interval if a record falls over?
                input_files[problem_index - 1].set_dim_slice_stop(unlim_dim, -int(np.floor(num_overlap)))

        # if the gap is larger than 2 nominal steps, we'll need to fill (if the expected cadence is known)
        # number of filles needed is insert coverage_diff[gap_too_big] * cadence_hz fill values
        gap_too_big = coverage_diff > 2.0 / ((2.0 - self.timing_certainty) * cadence_hz)  # type: np.ndarray
        insert_fills = np.zeros_like(gap_too_big, dtype=int)
        for index in gap_too_big.nonzero()[0]:
            insert_fills[index] = np.round((coverage_diff[index] - (1.0 / cadence_hz)) * cadence_hz)

        return insert_fills, np.where(insert_fills, ends, np.zeros_like(insert_fills))

    def evaluate_aggregation_list(self, aggregation_list, to_fullpath):
        """
        Evaluate an aggregation list to a file.... ie. actually do the aggregation.

        :param aggregation_list:
        :param to_fullpath:
        :return:
        """
        self.initialize_aggregation_file(to_fullpath)
        with nc.Dataset(to_fullpath, 'r+') as nc_out:  # type: nc.Dataset
            # get a list of variables that depend on an unlimited dimension
            vars_with_unlim = [
                v
                for d in [di["name"] for di in self.config["dimensions"] if di["size"] is None]
                for v in self.config["variables"]
                if d in v["dimensions"]
            ]
            for index, component in enumerate(aggregation_list):
                # make a mapping between unlim dimensions and their initial length because even after we append
                # only one variable that depends on the unlimited dimension, getting the size of it will return
                # the new appended size, which doesn't help us index the rest of the variables to fill in
                unlim_dim_start_lens = {d.name: d.size for d in nc_out.dimensions.values() if d.isunlimited()}

                for var in (self.config["variables"] if index == 0 else vars_with_unlim):
                    write_slices = []
                    for dim in nc_out.variables[var["name"]].dimensions:
                        if nc_out.dimensions[dim].isunlimited():
                            d_start = unlim_dim_start_lens[dim]
                            write_slices.append(slice(d_start, d_start + component.get_size_along(dim)))
                        else:
                            write_slices.append(slice(None))

                    # if there were no dimensions... write_slices will still be []
                    write_slices = write_slices or slice(None)
                    try:
                        var_name = var.get("map_to", var["name"])
                        nc_out.variables[var_name][write_slices] = component.data_for(var, self.config["dimensions"])
                    except IndexError as e:
                        print component.data_for(var, self.config["dimensions"])
                        print component.data_for(var, self.config["dimensions"]).shape
                        print write_slices
                        print var["name"]
                        logger.error(traceback.format_exc())
                        logger.error("For var %s: %s" % (var, repr(e)))

    def initialize_aggregation_file(self, fullpath):
        """
        Based on the configuration in self.config, initialize a file in which to write the aggregated output.

        :param fullpath: filename of output to initialize.
        :return: None
        """
        with nc.Dataset(fullpath, 'w') as nc_out:
            for dim in self.config["dimensions"]:
                nc_out.createDimension(dim["name"], dim["size"])
            for var in self.config["variables"]:
                var_name = var.get("map_to", var["name"])
                var_out = nc_out.createVariable(var_name, np.dtype(var["datatype"]), var["dimensions"])
                var_out.setncatts(var["attributes"])

    def handle_unexpected_condition(self, message, fatal=False, email=None):
        """
        Do something when unexpected conditions are found. This may include actions
        like emailing the DM, for example

        :param email:
        :param fatal:
        :param message:
        :return:
        """
        if fatal:
            raise Exception(message)
        else:
            logger.warning(message)
