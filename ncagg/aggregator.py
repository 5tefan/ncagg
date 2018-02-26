import logging
import traceback
import warnings
from datetime import datetime

import netCDF4 as nc
import numpy as np

from ncagg.aggrelist import FillNode, InputFileNode
from ncagg.attributes import AttributeHandler
from ncagg.config import Config

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

def aggregate(files_to_aggregate, output_filename, config=None):
    """
    Aggregate files_to_aggregate into output_filename, with optional conifg.
    Convenience function intended to be primary external interface to aggregation.

    :type files_to_aggregate: list[str]
    :param files_to_aggregate: List of NetCDF filenames to aggregate.
    :type output_filename: str
    :param output_filename: Filename to create and write output to.
    :type config: Config
    :param config: Optional configuration, default generated from first file if not given.
    :return:
    """
    if config is None:
        config = Config.from_nc(files_to_aggregate[0])

    agg_list = generate_aggregation_list(config, files_to_aggregate)
    evaluate_aggregation_list(config, agg_list, output_filename)


def generate_aggregation_list(config, files_to_aggregate):
    # type: (Config, list) -> list
    """
    Generate an aggregation list from a list of input files.

    :type files_to_aggregate: list[str]
    :param files_to_aggregate: a list of filenames to aggregate.
    :type config: Config
    :param config: An aggregation configuration.
    :rtype: list
    :return: a list containing objects inheriting from AbstractNode describing aggregation
    """
    preliminary = []

    for f in sorted(files_to_aggregate):
        try:
            preliminary.append(InputFileNode(config, f))
        except Exception as e:
            logger.warning("Error initializing InputFileNode for %s, skipping: %s" % (f, repr(e)))
            logger.debug(traceback.format_exc())

    if len(preliminary) == 0:
        # no files in aggregation list... abort
        return preliminary

    index_by_dims = [d for d in config.dims.values() if d["index_by"] is not None and not d["flatten"]]
    if len(index_by_dims) == 0:
        # no indexing dimensions found... nothing further to do here...
        return preliminary

    # Find the primary index_by dim. First is_primary found, otherwise first index_by dim.
    primary_index_by = next((d for d in config.dims.values() if d.get("is_primary", False) == True), index_by_dims[0])

    # Transfer items from perlimiary to final. According to primary index_by dim,
    # adding fill nodes and correcting overlap.
    preliminary = sorted(preliminary, key=lambda p: p.get_first_of_index_by(primary_index_by))

    def cast_bound(bound):
        """ Cast a bound to a numerical type for use. Will not be working directly with datetime objects. """
        if isinstance(bound, datetime):
            units = config.vars[primary_index_by["index_by"]]["attributes"]["units"]
            return nc.date2num(bound, units)
        return bound

    first_along_primary = cast_bound(primary_index_by["min"])
    last_along_primary = cast_bound(primary_index_by["max"])
    cadence_hz = primary_index_by["expected_cadence"].get(primary_index_by["name"], None)

    # Can continue into the correction loop as long as we have at least cadence_hz, or min and max.
    if cadence_hz is None and first_along_primary is None and last_along_primary is None:
        return preliminary

    dt_min = (1.0 / ((2.0 - timing_certainty) * cadence_hz))
    dt_max = (1.0 / (timing_certainty * cadence_hz))  # gap is too small if less than 1 of smallest timestep

    final = []
    while len(preliminary) > 0:
        next_f = preliminary.pop(0)  # type: InputFileNode
        next_start = next_f.get_first_of_index_by(primary_index_by)
        next_end = next_f.get_last_of_index_by(primary_index_by)

        # check if this potential next file is completely outside of the time bounds...
        if ((first_along_primary is not None and first_along_primary > next_end) or
                (last_along_primary is not None and last_along_primary < next_start)):
            logger.info("File not in bounds: %s" % next_f)
            # out of bounds, doesn't get included
            continue

        # if we get here, but have no cadence_hz, nothing more to do, just add file to final and continue.
        if cadence_hz is None:
            final.append(next_f)
            continue

        # if this is the first file, there is no previous file for there to be a gap with...
        # instead, use first_along_primary (ie. min) to see if there is a gap.
        if len(final) > 0:
            # case: potential for an actual gap
            prev_end = final[-1].get_last_of_index_by(primary_index_by)
            gap_between = next_start - prev_end
        else:  # len(final) == 0  # ie. this is the first file
            # case: first file, use dim boundary
            prev_end = first_along_primary
            gap_between = next_start - prev_end
            if 0 <= gap_between < dt_min:
                # case: if record appears to be too close to the start boundary (small gap), set gap_
                # between such that the first real record will remain, even if it's less than one
                # full time step away from the bound.
                gap_between = dt_min

        # gap too big if skips 1.5 of the largest possible expected timesteps.
        if gap_between > (1.5 * dt_max):
            # if the gap is too big, insert an appropriate fill value.
            fill_node = FillNode(config)
            size = np.floor((gap_between - (1.0 / cadence_hz)) * cadence_hz)
            fill_node.set_udim(primary_index_by, size, prev_end)
            final.append(fill_node)

        # if the gap is too small, chop some off this next file to make it fit...
        if gap_between < 0.5 * dt_min:
            num_overlap = np.abs(gap_between * cadence_hz)
            num_overlap = np.ceil(num_overlap) if num_overlap < 1 else np.floor(num_overlap)
            next_f.set_dim_slice_start(primary_index_by, num_overlap)
            next_start = next_f.get_first_of_index_by(primary_index_by)  # update, it changed and is used later!

        # make sure the start of next_f isn't sticking out over the min bound
        if first_along_primary is not None and first_along_primary > next_start:
            gap_between_start = first_along_primary - next_start
            num_overlap = np.abs(np.floor((gap_between_start - (1.0 / cadence_hz)) * cadence_hz))
            next_f.set_dim_slice_start(primary_index_by, num_overlap)

        # make sure the end of the next_f isn't sticking out over the max boundary
        if last_along_primary is not None and last_along_primary < next_end:
            gap_between_end = next_end - last_along_primary
            num_overlap = np.abs(np.floor((gap_between_end + (1.0 / cadence_hz)) * cadence_hz))
            next_f.set_dim_slice_stop(primary_index_by, -num_overlap)

        # and finally, if there's anything left of this next_f, add it to the final
        if next_f.get_size_along(primary_index_by) > 0:
            final.append(next_f)

    # after looping over the input files given, check if we haven't quite reached the end point and need
    # to add a FillNode to get the final way there.
    if not isinstance(final[-1], FillNode):
        prev_end = final[-1].get_last_of_index_by(primary_index_by)
        gap_to_end = last_along_primary - prev_end
        if gap_to_end > (2.0 * dt_max):
            fill_node = FillNode(config)
            size = np.floor((gap_to_end - (1.0 / cadence_hz)) * cadence_hz)
            fill_node.set_udim(primary_index_by, size, prev_end)
            final.append(fill_node)

    return final


def evaluate_aggregation_list(config, aggregation_list, to_fullpath, callback=None):
    """
    Evaluate an aggregation list to a file.... ie. actually do the aggregation.

    :param aggregation_list: AggList specifying how to create aggregation.
    :param to_fullpath: Filename for output.
    :type callback: None | function
    :param callback: called every time an aggregation_list element is processed.
    :return: None
    """
    if aggregation_list is None or len(aggregation_list) == 0:
        logger.warn("No files in aggregation list, nothing to do.")
        return  # bail early

    initialize_aggregation_file(config, to_fullpath)

    attribute_handler = AttributeHandler(config, filename=to_fullpath)

    vars_once = []
    vars_unlim = []

    # Each of lists above is treated differently, figure out treatment for each variable ahead of time, once.
    for v in config.vars.values():
        var_dims = [config.dims[d] for d in v["dimensions"]]

        depends_on_unlimited = any((d["size"] is None for d in var_dims))
        if not depends_on_unlimited:
            # variables that don't depend on an unlimited dimension, we'll only need to copy once.
            vars_once.append(v)
        else:
            vars_unlim.append(v)

    with nc.Dataset(to_fullpath, 'r+') as nc_out:  # type: nc.Dataset

        # the vars once don't depend on an unlimited dim so only need to be copied once. Find the first
        # InputFileNode to copy from so we don't get fill values. Otherwise, if none exists, which shouldn't
        # happen, but oh well, use a fill node.
        vars_once_src = next((i for i in aggregation_list if isinstance(i, InputFileNode)), aggregation_list[0])
        for var in vars_once:   # case: do once, only for first input file node
            nc_out.variables[var["name"]][:] = vars_once_src.data_for(var)

        for component in aggregation_list:
            
            unlim_starts = {k: nc_out.dimensions[k].size for k, v in config.dims.items() if v["size"] is None}

            for var in vars_unlim:
                write_slices = []
                for dim in [config.dims[d] for d in var["dimensions"]]:
                    if dim["size"] is None and not dim["flatten"]:
                        # case: regular concat var along unlim dim
                        d_start = unlim_starts[dim["name"]]
                        write_slices.append(slice(d_start, d_start + component.get_size_along(dim)))
                    elif dim["size"] is None and dim["flatten"] and dim["index_by"] is None:
                        # case: simple flatten unlim
                        write_slices.append(slice(0, component.get_size_along(dim)))
                    elif dim["size"] is None and dim["flatten"] and dim["index_by"] is not None:
                        # case: flattening according to an index
                        index_by = dim["index_by"]
                        index_by_incoming_values = component.data_for(config.vars[index_by])
                        index_by_existing_values = nc_out.variables[index_by][:]
                        # TODO: finish this
                        write_slices.append(slice(0, component.get_size_along(dim)))
                    else:
                        write_slices.append(slice(None))
                try:
                    output_data = component.data_for(var)
                    nc_out.variables[var["name"]][write_slices] = np.ma.masked_where(np.isnan(output_data), output_data)
                except Exception as e:
                    logger.error("Unexpected error copying from component into output: %s" % component)
                    logger.error(traceback.format_exc())

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
    Based on the configuration, initialize a file in which to write the aggregated output.

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
                    if isinstance(v, str):
                        var["attributes"][k] = np.array(map(var_type.type, v.split(", ")), dtype=var_type)
                    else:
                        var["attributes"][k] = np.array(v, dtype=var_type)

            var_out.setncatts(var["attributes"])

