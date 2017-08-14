import logging
import traceback
import warnings
from datetime import datetime
from collections import OrderedDict

import netCDF4 as nc
import numpy as np

from aggregoes.aggrelist import FillNode, InputFileNode, AggreList
from aggregoes.attributes import AttributeHandler
from aggregoes.validate_configs import Config

logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", category=RuntimeWarning)

# Nominally, this is a three step process.
#     # STEP 1. Initialize with an optional config.
#     aggregator = Aggregator()
#     # STEP 2. generate aggregation list from a list of files
#     aggregation_list = aggregator.generate_aggregation_list(files)
#     # STEP 3. finally, evaluate the aggregation list
#     aggregator.evaluate_aggregation_list(aggregation_list, filename)

timing_certainty = 0.9


def generate_aggregation_list(config, files_to_aggregate):
    # type: (Config, list) -> AggreList
    """
    Generate an aggregation list from a list of input files.

    :type files_to_aggregate: list[str]
    :param files_to_aggregate: a list of filenames to aggregate.
    :type config: dict
    :param config: dict configuring variables to index unlimited dimensions by.
    :rtype: AggreList
    :return: an aggregation list
    """
    aggregation_list = AggreList()

    if len(files_to_aggregate) == 0:
        # no files to aggregate, exit immediately, do nothing
        logger.error("No files to aggregate!")
        return aggregation_list

    logger.info("Initializing input file nodes...")
    input_files = []
    n_errors = 0.0
    for fn in sorted(files_to_aggregate):
        try:
            input_files.append(InputFileNode(config, fn))
        except Exception as e:
            n_errors += 1
            logger.warning("Error initializing InputFileNode for %s, skipping: %s" % (fn, repr(e)))
            if n_errors / len(files_to_aggregate) >= 0.5:
                logger.error("Exceeding half bad granules. Something likely wrong, but continuing."
                             "Resulting file will probably have lots of fill values. Latest error was:\n"
                             "Error initializing InputFileNode for %s, skipping: %s" % (fn, repr(e)))
                # once logger.error triggered once for input problem, make sure it won't trigger again.
                n_errors = -1.0

    if len(input_files) == 0:
        # hmmm, no files survived initialization is InputFileNode
        logger.error("No valid files found.")
        return aggregation_list

    # calculate file coverage if any unlimited dimensions are configured.
    # must have an index_by dimension configured, flatten ones don't count
    index_by = [d for d in config.dims.values() if d["index_by"] is not None and not d["flatten"]]
    if len(index_by) > 0:  # case: doing sorting
        # implication: files will be sorted according to the first indexed unlimited dimension.
        input_files = sorted(input_files, key=lambda i: i.get_first_of_index_by(index_by[0]))

        # calculate where fill value are needed between files
        fills_needed = {d["name"]: get_coverage_for(config, input_files, d) for d in index_by}

        for i in xrange(len(input_files)+1):
            fills_needed_dim_start_size = []
            for d in index_by:
                num_missing, missing_start = fills_needed[d["name"]]  # fills needed and start of missing for a dim d
                if num_missing[i] > 0:  # Any missing point along this dimension between these files?
                    fills_needed_dim_start_size.append((d, missing_start[i], num_missing[i]))
            if len(fills_needed_dim_start_size) > 0:
                # If there's anything to put in the fill node, init, fill and add to agg list.
                fill_node = FillNode(config)
                for d, start, size in fills_needed_dim_start_size:
                    fill_node.set_udim(d, size, start)
                aggregation_list.append(fill_node)
            if i < len(input_files):
                aggregation_list.append(input_files[i])
    else:  # case: no sorting, just glue files together
        aggregation_list.extend(input_files)

    return aggregation_list


def get_coverage_for(config, input_files, udim):
    # type: (Config, list, dict) -> (np.array, np.array)
    """
    Mutate the actual input_files to fix overlap problems, return where the are gaps between files.

    :type config: Config
    :type input_files: list[InputFileNode]
    :param input_files:
    :type unlim_dim: str
    :param unlim_dim:
    :rtype: (np.array, np.array)
    :return: boolean array indicating where the gap sizes are too big between files
    """

    # to complete the operation of this function, the udim must be configured with an expected_cadence, min, and max
    required_keys = ["expected_cadence", "min", "max"]
    keys_to_none = [k for k in required_keys if udim.get(k, None) is None]
    if len(keys_to_none) > 0:
        raise ValueError("Cannot get coverage for unlimited dim %s, missing %s" % (udim["name"], keys_to_none))

    cadence_hz = float(udim["expected_cadence"].get(udim["name"], np.nan))  # TODO: what to do if None?

    def cast_bound(bound):
        """ Cast a bound to a numerical type for use. Will not be working directly with datetime objects. """
        if isinstance(bound, datetime):
            units = config.vars[udim["index_by"]]["attributes"]["units"]
            return nc.date2num(bound, units)
        return bound

    # turn min and max into numerical object if they come in as datetime
    last_value_before = cast_bound(udim["min"])
    first_value_after = cast_bound(udim["max"])

    # remove files that aren't between last_value_before and first_value_after
    starts = []
    ends = []
    # iterate over a copy of the list since we might be removing things while iterating over it
    for each in input_files[:]:
        try:
            start = each.get_first_of_index_by(udim)
            end = each.get_last_of_index_by(udim)
        except Exception as e:
            logger.error("Error getting start or end of %s, removing from processing: %s" % (each, repr(e)))
            input_files.remove(each)
            continue

        if (last_value_before and end < last_value_before) or (first_value_after and start > first_value_after):
            logger.info("File not in bounds: %s" % each)
            input_files.remove(each)
        else:  # case: file good to include.
            starts.append(start)
            ends.append(end)

    dt_min = (1.0 / ((2.0 - timing_certainty) * cadence_hz))
    dt_max = (1.0 / (timing_certainty * cadence_hz))
    assert dt_min <= dt_max
    # turn starts and ends into np.ndarray with last_value_before and first_value_after in approriate spots
    starts = np.hstack((starts, [(first_value_after or ends[-1])]))
    ends = np.hstack(([(last_value_before or starts[0])], ends))

    # stagger and take diff so that eg. coverage_diff[1] is gap between first and second file...
    coverage = np.empty((starts.size + ends.size), dtype=starts.dtype)
    coverage[0::2] = ends
    coverage[1::2] = starts
    coverage_diff = np.diff(coverage)[::2]

    # if the gap is larger than 2 nominal steps, we'll need to fill (if the expected cadence is known)
    # number of filles needed is insert coverage_diff[gap_too_big] * cadence_hz fill values
    gap_too_big = coverage_diff > (2.0 * dt_min)  # type: np.ndarray
    num_missing = np.zeros_like(gap_too_big, dtype=int)
    for index in gap_too_big.nonzero()[0]:
        num_missing[index] = np.floor((coverage_diff[index] - (1.0 / cadence_hz)) * cadence_hz)

    # if the gap is less than 0, we'll need to trim something, ie two files overlap and
    # we'll need to pick one of the overlapping
    gap_too_small_upper_bound_seconds = dt_min if cadence_hz > 0 else 0
    where_gap_too_small = np.where(coverage_diff <= gap_too_small_upper_bound_seconds)[0]
    for problem_index in where_gap_too_small:
        # TODO: do we need both ceil and floor in there?
        num_overlap = int(np.ceil(np.abs(np.floor(coverage_diff[problem_index] * cadence_hz))))
        if num_overlap == 0:
            continue  # skip if num overlap == 0, nothing to do!
        # Take the gap off from front of following file, ie. bias towards first values that arrived.
        # On the end, when there is no following file, instead chop the end from the last file. Check
        # also num_missing just in case there's a FillNode after in which case don't take it off of
        # the end even if it's the last file.
        if problem_index < len(input_files) - 1 or num_missing[problem_index-1] > 0:
            # this np.floor is consistent with np.ceil (pretty sure, bias towards keeping data
            # with the previous agg interval if a record falls over? Shouldn't really matter as long
            # as we're consistent.
            input_files[problem_index].set_dim_slice_start(udim, num_overlap)
        else:
            # if it's the last file, have to take it off the end of the previous instead of beginning of next.
            input_files[problem_index - 1].set_dim_slice_stop(udim, -num_overlap)

    return num_missing, np.where(num_missing, ends, np.zeros_like(num_missing))
    return num_missing, np.where(num_missing, ends + (1.0 / cadence_hz), np.zeros_like(num_missing))

def evaluate_aggregation_list(config, aggregation_list, to_fullpath, callback=None):
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

    initialize_aggregation_file(config, to_fullpath)

    attribute_handler = AttributeHandler(config, filename=to_fullpath)

    vars_unlim_append = []
    vars_once = []
    vars_simple_flatten = []
    vars_index_flatten = []

    # Each of lists above is treated differently, figure out treatment for each variable ahead of time, once.
    for v in config.vars.values():
        var_dims = [config.dims[d] for d in v["dimensions"]]

        depends_on_unlimited = any((d["size"] is None for d in var_dims))
        if not depends_on_unlimited:
            # variables that don't depend on an unlimited dimension, we'll only need to copy once.
            vars_once.append(v)
            continue

        is_flatten = any((d.get("flatten", False) for d in var_dims))
        if not is_flatten:  # case: simple unlim, just append (raw or index, doesn't matter)
            vars_unlim_append.append(v)
            continue

        is_indexed = any((d.get("index_by", None) is not None for d in var_dims))
        if is_flatten and is_indexed:
            vars_index_flatten.append(v)
        else:  # case: just simple flattening, don't care about indexing
            vars_simple_flatten.append(v)

    with nc.Dataset(to_fullpath, 'r+') as nc_out:  # type: nc.Dataset

        # the vars once don't depend on an unlimited dim so only need to be copied once. Find the first
        # InputFileNode to copy from so we don't get fill values. Otherwise, if none exists, which shouldn't
        # happen, but oh well, use a fill node.
        vars_once_src = next((i for i in aggregation_list if isinstance(i, InputFileNode)), aggregation_list[0])
        for var in vars_once:   # case: do once, only for first input file node
            nc_out.variables[var["name"]][:] = vars_once_src.data_for(var)

        for component in aggregation_list:

            unlim_starts = {k: nc_out.dimensions[k].size for k, v in config.dims.items() if v["size"] is None}

            # case: regular concat var along unlim dim
            logger.debug("vars_unlim_append: %s" % [v["name"] for v in vars_unlim_append])
            for var in vars_unlim_append:
                write_slices = []
                for dim in [config.dims[d] for d in var["dimensions"]]:
                    if dim["size"] is None:  # it's unlimited
                        d_start = unlim_starts[dim["name"]]
                        write_slices.append(slice(d_start, d_start + component.get_size_along(dim)))
                    else:
                        write_slices.append(slice(None))
                nc_out.variables[var["name"]][write_slices] = component.data_for(var)

            # case: simple flatten unlim
            logger.debug("vars_simple_flatten: %s" % [v["name"] for v in vars_simple_flatten])
            for var in vars_simple_flatten:
                write_slices = []
                for dim in [config.dims[d] for d in var["dimensions"]]:
                    if dim["size"] is None and not dim["flatten"]:  # it's unlimited
                        d_start = unlim_starts[dim["name"]]
                        write_slices.append(slice(d_start, d_start + component.get_size_along(dim)))
                    elif dim["size"] is None and dim["flatten"]:
                        write_slices.append(slice(0, component.get_size_along(dim)))
                    else:
                        write_slices.append(slice(None))
                nc_out.variables[var["name"]][write_slices] = component.data_for(var)


            # case: flattening according to an index
            logger.debug("vars_index_flatten: %s" % [v["name"] for v in vars_index_flatten])
            for var in vars_index_flatten:
                write_slices = []
                for dim in [config.dims[d] for d in var["dimensions"]]:
                    if dim["size"] is None and not dim["flatten"]:  # it's unlimited
                        d_start = unlim_starts[dim["name"]]
                        write_slices.append(slice(d_start, d_start + component.get_size_along(dim)))
                    elif dim["size"] is None and dim["flatten"] and dim["index_by"] is None:
                        write_slices.append(slice(0, component.get_size_along(dim)))
                    elif dim["size"] is None and dim["flatten"] and dim["index_by"] is not None:
                        index_by = dim["index_by"]
                        index_by_incoming_values = component.data_for(config.vars[index_by])
                        index_by_existing_values = nc_out.variables[index_by][:]
                        # TODO: finish this
                        write_slices.append(slice(0, component.get_size_along(dim)))
                    else:
                        write_slices.append(slice(None))
                nc_out.variables[var["name"]][write_slices] = component.data_for(var)


            # do once per component
            component.callback_with_file(attribute_handler.process_file)

            if callback is not None:
                callback()

        # write buffered data to disk
        nc_out.sync()

        # after aggregation finished, finalize the global attributes
        attribute_handler.finalize_file(nc_out)


def initialize_aggregation_file(config, fullpath):
    """
    Based on the configuration in self.config, initialize a file in which to write the aggregated output.

    :param fullpath: filename of output to initialize.
    :return: None
    """
    with nc.Dataset(fullpath, 'w') as nc_out:
        for dim in config.dims.values():
            nc_out.createDimension(dim["name"], dim["size"])
        for var in config.vars.values():
            var_name = var.get("map_to", var["name"])
            var_type = np.dtype(var["datatype"])
            var_out = nc_out.createVariable(var_name, var_type, var["dimensions"],
                                            chunksizes=var["chunksizes"], zlib=True,
                                            complevel=7)
            for k, v in var["attributes"].items():
                if k in ["_FillValue", "valid_min", "valid_max"]:
                    var["attributes"][k] = var_type.type(v)
                if k in ["valid_range", "flag_masks", "flag_values"]:
                    if isinstance(v, basestring):
                        var["attributes"][k] = np.array(map(var_type.type, v.split(", ")), dtype=var_type)
                    else:
                        var["attributes"][k] = np.array(v, dtype=var_type)

            var_out.setncatts(var["attributes"])

