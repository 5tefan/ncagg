import logging
import traceback
from datetime import datetime

import netCDF4 as nc
import numpy as np

from aggregoes.aggrelist import FillNode, InputFileNode, AggreList
from aggregoes.attributes import AttributeHandler
from utils.init_config_template import generate_default_variables_config, \
    generate_default_global_attributes_config, generate_default_dimensions_config
from utils.validate_configs import validate_unlimited_dim_indexed_by_time_var_map as validate_unlim_config
from utils.validate_configs import validate_a_dimension_block, validate_a_global_attribute_block, \
    validate_a_variable_block

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
logging.getLogger().addHandler(console)


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
        Aggregator.doMonth("YYYYMM", "data-short-name")
        Aggregator.doYear("YYYY", "data-short-name")

    Aggregator.doCustom(file_list, start_date, end_date)
    """

    def __init__(self, config=None):
        super(Aggregator, self).__init__()
        self.config = config or {}
        [validate_a_variable_block(b) for b in self.config.get("variables", [])]
        [validate_a_dimension_block(b) for b in self.config.get("dimensions", [])]
        [validate_a_global_attribute_block(b) for b in self.config.get("global attributes", [])]

        self.timing_certainty = 0.9
        # if config doesn't come with either a "global attributes" or a "data variables" key,
        # they will be automatically configured when generate_aggregation_list is called based
        # on the first file in the list to aggregate as a template.

    def generate_aggregation_list(self, files_to_aggregate, config=None):
        aggregation_list = AggreList()

        if len(files_to_aggregate) == 0:
            # no files to aggregate, exit immediately, do nothing
            logger.warn("No files to aggregate!")
            return aggregation_list

        # if global attributes and data variables are not configured, set them to defaults based on the first
        # file in files_to_aggregate
        logger.info("Validating configurations...")
        if "global attributes" not in self.config.keys():
            logger.debug("\tglobal attributes configuration not found, creating default.")
            self.config["global attributes"] = generate_default_global_attributes_config(files_to_aggregate[0])
        if "dimensions" not in self.config.keys():
            logger.debug("\tdimensions configuration not found, creating default")
            self.config["dimensions"] = generate_default_dimensions_config(files_to_aggregate[0])
        if "variables" not in self.config.keys():
            logger.debug("\tvariables configuration not found, creating default")
            self.config["variables"] = generate_default_variables_config(files_to_aggregate[0])

        self.config["config"] = config

        # auto detect the unlimited dimensions, it is along these that we need to aggregate
        # unlimited_dims = [dim for dim in self.config["dimensions"] if dim["size"] is None]

        logger.info("Initializing input file nodes...")
        unlim_config = validate_unlim_config(self.config.get("config", None), files_to_aggregate[0])
        input_files = [InputFileNode(fn, unlim_config) for fn in sorted(files_to_aggregate)]
        if unlim_config is not None:
            logger.info("\tFound config for unlimited dim indexing, calculating coverage.")
            unlim_fills_needed = {
                unlim_dim: self.get_coverage_for(input_files, unlim_dim) for unlim_dim in unlim_config.keys()
            }

        logger.info("Building aggregation list...")
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
        starts = np.hstack((starts, [first_value_after or ends[-1] + (1.0 / cadence_hz)]))
        ends = np.hstack(([last_value_before or starts[0] - (1.0 / cadence_hz)], ends))

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
        attribute_handler = AttributeHandler(
            global_attr_config=self.config["global attributes"],
            runtime_config=self.config["config"]
        )

        with nc.Dataset(to_fullpath, 'r+') as nc_out:  # type: nc.Dataset
            # get a list of variables that depend on an unlimited dimension, after the first file is
            # processed, we'll only need to go through these.
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
                        nc_out.variables[var_name][write_slices] = component.data_for(
                            var, self.config["dimensions"], attribute_handler.process_file
                        )
                    except IndexError as e:
                        logger.debug(component.data_for(var, self.config["dimensions"]))
                        logger.debug(component.data_for(var, self.config["dimensions"]).shape)
                        logger.debug(write_slices)
                        logger.debug(var["name"])
                        logger.error(traceback.format_exc())
                        logger.error("For var %s: %s" % (var, repr(e)))

            # after aggregation finished, finalize the global attributes
            attribute_handler.finalize_file(nc_out)

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
