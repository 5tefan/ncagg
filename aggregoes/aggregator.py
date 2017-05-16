import logging
import warnings
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

warnings.filterwarnings("ignore", category=RuntimeWarning)


class Aggregator(object):
    """
    Nominally, this is a three step process.
        # STEP 1. Initialize with an optional config.
        aggregator = Aggregator()
        # STEP 2. generate aggregation list from a list of files
        aggregation_list = aggregator.generate_aggregation_list(files)
        # STEP 3. finally, evaluate the aggregation list
        aggregator.evaluate_aggregation_list(aggregation_list, filename)
    """

    def __init__(self, config=None):
        """
        Initialize an aggregator, taking an optional config dict which can contain the keys ["variables",
        "dimensions", "global attributes"].
        
        If the config is missing any of the expected keys, they will be automatically configured 
        when generate_aggregation_list is called based on the first file in the list to aggregate
        as a template.
        
        :type config: dict
        :param config: Optional config
        """
        super(Aggregator, self).__init__()
        self.config = config or {}

        # Validate each component of the config. Failing validation, an exception will be raised.
        # TODO: user cerberus to validate these instead.
        [validate_a_variable_block(b) for b in self.config.get("variables", [])]
        [validate_a_dimension_block(b) for b in self.config.get("dimensions", [])]
        [validate_a_global_attribute_block(b) for b in self.config.get("global attributes", [])]

        self.timing_certainty = 0.9

    def generate_aggregation_list(self, files_to_aggregate, index_config=None):
        """
        Generate an aggregation list from a list of input files.

        :type files_to_aggregate: list[str]
        :param files_to_aggregate: a list of filenames to aggregate.
        :type index_config: dict
        :param index_config: dict configuring variables to index unlimited dimensions by.
        :rtype: AggreList
        :return: an aggregation list
        """
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

        self.config["config"] = unlim_config = validate_unlim_config(index_config, files_to_aggregate[0])

        logger.info("Initializing input file nodes...")
        input_files = []
        for fn in sorted(files_to_aggregate):
            try:
                input_files.append(InputFileNode(fn, unlim_config))
            except Exception as e:
                logger.error("Error initializing InputFileNode for %s, skipping: %s" % (fn, repr(e)))

        # calculate file coverage if any unlimited dimensions are configured.
        if unlim_config is not None:
            logger.info("\tFound config for unlimited dim indexing, calculating coverage.")
            unlim_fills_needed = {
                unlim_dim: self.get_coverage_for(input_files, unlim_dim) for unlim_dim in unlim_config.keys()
            }

        logger.info("Building aggregation list...")
        for index in xrange(len(input_files) + 1):
            # + 1 since by taking into account the diff between last_value_before and first_value_after while
            # calculating calculate, the length of num_missing and missing_start == len(input_files) + 1

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
                # if anything was filled out in the fill_node, add it to the aggregation list
                if len(fill_node.unlimited_dim_sizes) > 0:
                    aggregation_list.append(fill_node)

            if index < len(input_files):
                aggregation_list.append(input_files[index])

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
                return nc.date2num([bound], input_files[0].get_units_of_index_by(unlim_dim))[0]
            return bound

        # turn min and max into numerical object if they come in as datetime
        last_value_before = cast_bound(self.config["config"][unlim_dim].get("min"))
        first_value_after = cast_bound(self.config["config"][unlim_dim].get("max"))

        # remove files that aren't between last_value_before and first_value_after
        starts = []
        ends = []
        # iterate over a copy of the list since we might be removing things while iterating over it
        for each in input_files[:]:
            try:
                start = each.get_first_of_index_by(unlim_dim)
                end = each.get_last_of_index_by(unlim_dim)
            except Exception as e:
                logger.error("Error getting start or end of %s, removing from processing: %s" % (each, repr(e)))
                input_files.remove(each)
                continue

            if (last_value_before and end < last_value_before) or (first_value_after and start > first_value_after):
                logger.info("File not in bounds: %s" % each)
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
        where_gap_too_small = np.where(coverage_diff <= gap_too_small_upper_bound_seconds)[0]
        for problem_index in where_gap_too_small:
            num_overlap = np.abs(np.floor(coverage_diff[problem_index] * cadence_hz))
            # Take the gap off from front of following file, ie. bias towards first values that arrived.
            # On the end, when there is no following file, instead chop the end from the last file.
            if problem_index < len(input_files) - 1:
                # this np.floor is consistent with np.ceil (pretty sure, bias towards keeping data
                # with the previous agg interval if a record falls over?
                input_files[problem_index].set_dim_slice_start(unlim_dim, int(np.ceil(num_overlap)))
            else:
                input_files[problem_index - 1].set_dim_slice_stop(unlim_dim, -int(np.ceil(num_overlap)))

        # if the gap is larger than 2 nominal steps, we'll need to fill (if the expected cadence is known)
        # number of filles needed is insert coverage_diff[gap_too_big] * cadence_hz fill values
        gap_too_big = coverage_diff > 2.0 / ((2.0 - self.timing_certainty) * cadence_hz)  # type: np.ndarray
        insert_fills = np.zeros_like(gap_too_big, dtype=int)
        for index in gap_too_big.nonzero()[0]:
            insert_fills[index] = np.floor((coverage_diff[index] - (1.0 / cadence_hz)) * cadence_hz)

        return insert_fills, np.where(insert_fills, ends, np.zeros_like(insert_fills))

    def evaluate_aggregation_list(self, aggregation_list, to_fullpath, callback=None):
        """
        Evaluate an aggregation list to a file.... ie. actually do the aggregation.

        :param aggregation_list:
        :param to_fullpath:
        :type callback: None | function
        :param callback: called every time an aggregation_list element is processed.
        :return:
        """
        if len(aggregation_list) == 0:
            logger.warn("No files in aggregation list, nothing to do.")
            return  # bail early
        self.initialize_aggregation_file(to_fullpath)
        attribute_handler = AttributeHandler(
            global_attr_config=self.config["global attributes"],
            runtime_config=self.config["config"],
            filename=to_fullpath
        )

        vars_with_unlim = [
            v
            for d in [di["name"] for di in self.config["dimensions"] if di["size"] is None]
            for v in self.config["variables"]
            if d in v["dimensions"]
        ]
        with nc.Dataset(to_fullpath, 'r+') as nc_out:  # type: nc.Dataset
            # get a list of variables that depend on an unlimited dimension, after the first file is
            # processed, we'll only need to go through these.
            for index, component in enumerate(aggregation_list):
                # make a mapping between unlim dimensions and their initial length because even after we append
                # only one variable that depends on the unlimited dimension, getting the size of it will return
                # the new appended size, which doesn't help us index the rest of the variables to fill in
                unlim_dim_start_lens = {d.name: d.size for d in nc_out.dimensions.values() if d.isunlimited()}

                for var in (self.config["variables"] if index == 0 else vars_with_unlim):
                    var_out_name = var.get("map_to", var["name"])
                    write_slices = []
                    for dim in nc_out.variables[var_out_name].dimensions:
                        if nc_out.dimensions[dim].isunlimited():
                            d_start = unlim_dim_start_lens[dim]
                            write_slices.append(slice(d_start, d_start + component.get_size_along(dim)))
                        else:
                            write_slices.append(slice(None))

                    # if there were no dimensions... write_slices will still be []
                    write_slices = write_slices or slice(None)
                    try:
                        nc_out.variables[var_out_name][write_slices] = component.data_for(var,
                                                                                          self.config["dimensions"],
                                                                                          attribute_handler.process_file)
                    except Exception as e:
                        logger.debug(component.data_for(var, self.config["dimensions"]).shape)
                        logger.debug(write_slices)
                        logger.debug(traceback.format_exc())
                        logger.error("For var %s: %s, continuing" % (var["name"], repr(e)))

                if callback is not None:
                    callback()

            # write buffered data to disk
            nc_out.sync()

            # after aggregation finished, finalize the global attributes
            attribute_handler.finalize_file(nc_out)

        unlim_config = self.config.get("config", None)

        if unlim_config is None:
            # nothing left to do if no unlimited conifg
            return
        # otherwise sort all records, seems we occasionally get out of order records
        # close and re-open file just to be safe
        with nc.Dataset(to_fullpath, 'r+') as nc_out:  # type: nc.Dataset
            # get argsort along the configured unlimited dims
            unlim_argsorts = {
                unlim_dim: self.argsort_for_unlim(nc_out, unlim_dim) for unlim_dim in unlim_config.keys()
            }
            for var in vars_with_unlim:
                var_out_name = var.get("map_to", var["name"])
                slices = [unlim_argsorts.get(dim, slice(None)) for dim in nc_out.variables[var_out_name].dimensions]
                nc_out.variables[var_out_name][:] = nc_out.variables[var_out_name][slices]

    def argsort_for_unlim(self, nc_out, unlim_dim):
        """

        :type nc_out: nc.Dataset
        :param nc_out: netcdf out to argsort against
        :param unlim_dim:
        :return:
        """
        unlim_mapping = self.config["config"][unlim_dim]
        index_by = unlim_mapping["index_by"]
        slices = tuple([slice(None) if d == unlim_dim else unlim_mapping.get("other_dim_indicies", {}).get(d, 0)
                        for d in nc_out[index_by].dimensions])
        return np.argsort(nc_out.variables[index_by][slices])


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
                var_type = np.dtype(var["datatype"])
                var_out = nc_out.createVariable(var_name, var_type, var["dimensions"],
                                                chunksizes=var.get("chunksizes", None), zlib=True,
                                                complevel=7)
                for k, v in var["attributes"].items():
                    if k in ["_FillValue", "valid_min", "valid_max"]:
                        var["attributes"][k] = var_type.type(v)
                    if k in ["valid_range", "flag_masks", "flag_values"]:
                        var["attributes"][k] = np.array(v, dtype=var_type)

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
