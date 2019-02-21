import logging
import traceback
import warnings
from datetime import datetime

import netCDF4 as nc
import numpy as np

from .aggrelist import AbstractNode, FillNode, InputFileNode, VariableNotFoundException
from .attributes import AttributeHandler
from .config import Config

logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", category=RuntimeWarning)

# WELCOME:
# A convenience wrapper is provided as  `aggregate(files, output, config=None)`
#
# Under the hood, this is a two step process.
#     # STEP 1. Create the aggregation list from a list of files.
#       aggregation_list = generate_aggregation_list(config, files)
#     # STEP 2. Evaluate the aggregation list to an output file.
#       evaluate_aggregation_list(aggregation_list, filename)
#
# -----------------------
#
# How certain is the cadence/arrival of unlim dim indicies? Most likely, real instruments
# don't produce measurements at an EXACT step... generally there will be some wiggle room.
# Should take a value between 0.0 < timing_certainty <= 1.0, where 1.0 is most certain and
# allows no deviation.  # TODO: configurable per unlim dim?
timing_certainty = 0.9


def aggregate(files_to_aggregate, output_filename, config=None):
    # type: (list[str], str, None | Config) -> None
    """
    Aggregate files_to_aggregate into output_filename, with optional conifg.
    Convenience function intended to be primary external interface to aggregation.

    :param files_to_aggregate: List of NetCDF filenames to aggregate.
    :param output_filename: Filename to create and write output to.
    :param config: Optional configuration, default generated from first file if not given.
    :return: None
    """
    if config is None:
        config = Config.from_nc(files_to_aggregate[0])

    agg_list = generate_aggregation_list(config, files_to_aggregate)
    evaluate_aggregation_list(config, agg_list, output_filename)


def generate_aggregation_list(config, files_to_aggregate):
    # type: (Config, list[str]) -> list[AbstractNode]
    """
    Generate an aggregation list from a list of input files.

    :param config: Aggregation configuration
    :param files_to_aggregate: a list of filenames to aggregate.
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
    primary_index_by = next((d for d in config.dims.values() if d.get("is_primary", False)), index_by_dims[0])

    # Transfer items from perlimiary to final. According to primary index_by dim,
    # adding fill nodes and correcting overlap.
    preliminary = sorted(preliminary, key=lambda p: p.get_first_of_index_by(primary_index_by))

    def cast_bound(bound):
        # type: (float | datetime) -> float
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

    # dt_min is minimum time between files given timing_certainty. Inflate cadence (higher hz) -> smaller time step
    # similarly, lower cadence (lower hz) -> larger time step
    dt_min = (1.0 / ((2.0 - timing_certainty) * cadence_hz))  # smallest expected time step
    dt_nom = (1.0 / cadence_hz)  # nominal expected time step
    dt_max = (1.0 / (timing_certainty * cadence_hz))  # largest expected time step

    # final list of components to aggregate, containing InputFileNodes and possibly
    # FillValueNodes. Built below going through priliminary list, adding one by one
    # while examining spacing between files and the bounds at the beginning and end.
    final = []
    while len(preliminary) > 0:
        next_f = preliminary.pop(0)  # type: InputFileNode
        next_start = next_f.get_first_of_index_by(primary_index_by)
        next_end = next_f.get_last_of_index_by(primary_index_by)

        # check if this potential next file is completely outside of the time bounds...
        if ((first_along_primary is not None and first_along_primary > next_end) or
                (last_along_primary is not None and last_along_primary < next_start)):
            logger.info("File not in bounds: %s" % next_f)
            # out of bounds, doesn't get included. Continue without adding this next_f to final.
            continue

        # if we get here, but have no cadence_hz, nothing more to do, just add file to final and continue.
        if cadence_hz is None:
            final.append(next_f)
            continue

        # subtract dt_min since first_along_primary is the bound, not a valid time point, so decrease to ensure
        # that CASE: gap-too-small isn't triggered for first point, causing first point to get chopped off.
        if len(final) > 0:
            prev_end = final[-1].get_last_of_index_by(primary_index_by)
            # the size of the gap between the previous file and the next, nominally time gap
            gap_between = next_start - prev_end
        elif first_along_primary is None:
            # don't have a bound to compare against, so just have to start by adding first file we get
            final.append(next_f)
            continue
        else:
            # CASE: first file, take the bound and subtract a min time step so that
            # the first time step greater than or equal to the bound will be included.
            # Historical: numerical issues here? What happened... was I mistaken? .. probably.
            prev_end = first_along_primary - dt_min
            gap_between = next_start - prev_end

        # gap too big if skips 1.62 of the largest possible expected dt...
        # The value 1.62 is picked somewhat artfully... just make sure all the tests pass.
        if gap_between > 1.6 * dt_max and next_start - dt_nom > first_along_primary:  # <----------- CASE: gap-too-big
            # if the gap is too big, insert an appropriate fill value.
            if len(final) > 0:  # <-------------- CASE: exists-previous-file
                size = int(max(1, np.round((gap_between-dt_nom) * cadence_hz)))  # probably correct
                # when there is a previous file, make timestamps even from end of that one
                start_from = prev_end
            else:  # <------------- CASE: no-previous-file
                size = int(max(1, np.floor((gap_between-dt_nom) * cadence_hz)))  # probably correct
                # otherwise look at the next timestamp, and go backward _size_ from there to get the start_from.
                start_from = next_start - ((size+1) * dt_nom)
                # note: start_from must be greater than first_along_primary
                try:
                    assert start_from + dt_nom >= first_along_primary, "{} + {}, {}".format(start_from,
                            dt_nom, first_along_primary)
                except Exception:
                    import ipdb; ipdb.set_trace()

            fill_node = FillNode(config)
            fill_node.set_udim(primary_index_by, size, start_from)
            final.append(fill_node)

        # if the gap is too small, chop some off this next file to make it fit...
        if gap_between < dt_min:  # <----------- CASE: gap-too-small
            # tbh, getting num_overlap correct has been mostly trial and error...
            num_overlap = np.ceil(np.abs((gap_between - dt_min) * cadence_hz))
            next_f.set_dim_slice_start(primary_index_by, num_overlap)
            # note: setting dim_slice_start effectively invalidates the previously set next_start variable

        # make sure the end of the next_f isn't sticking out after the max boundary
        if last_along_primary is not None and last_along_primary < next_end:  # <---------- CASE: hanging-over-edge
            gap_between_end = next_end - last_along_primary
            num_overlap = np.abs(np.ceil(gap_between_end * cadence_hz))
            # note: set stop to negative of overlap, ie. backwards from end since
            # there will be no following file.
            next_f.set_dim_slice_stop(primary_index_by, -num_overlap)

        # And finally, if there's anything left of this next_f, add it to the final.
        # Note: strict=False allows get_size_along to return a negative number.
        # This negative number may arise if both CASE: gap-too-small and CASE: hanging-over-edge are triggered above.
        # Example: a file with 10 records: gap-to-small sets start to 8 and hanging-over-edge sets # stop to -5,
        # then get_size_along with strict=False will return -3. Up to this point, that's fine, that means don't
        # include the file since none of it belongs!
        if next_f.get_size_along(primary_index_by, strict=False) > 0:
            final.append(next_f)

    # after looping over the input files given, check if we haven't quite reached the end point and need
    # to add a FillNode to get the final way there.
    if len(final) > 0 and not isinstance(final[-1], FillNode):
        prev_end = final[-1].get_last_of_index_by(primary_index_by)
        # add dt_min to last_along_primary again since last_along_primary isn't a real data point
        # again, gap_to_end must consider numerical issues. last and prev large magnitude, dt_min is small
        gap_to_end = (last_along_primary - prev_end) + dt_min
        if gap_to_end > dt_max:
            fill_node = FillNode(config)
            size = np.floor((gap_to_end-dt_min) * cadence_hz)
            fill_node.set_udim(primary_index_by, size, prev_end)
            final.append(fill_node)

    return final


def evaluate_aggregation_list(config, aggregation_list, to_fullpath, callback=None):
    # type: (Config, list[AbstractNode], str, None | function) -> None
    """
    Evaluate an aggregation list to a file.... ie. actually do the aggregation.

    :param config: Aggregation configuration
    :param aggregation_list: AggList specifying how to create aggregation.
    :param to_fullpath: Filename for output.
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
        with vars_once_src.get_evaluation_functions() as (data_for, _):
            for var in vars_once:   # case: do once, only for first input file node
                try:
                    nc_out.variables[var["name"]][:] = data_for(var)
                except Exception as e:
                    logger.error("Error copying component: %s, one time variable: %s" % (vars_once_src, var))
                    logger.error(traceback.format_exc())

        for component in aggregation_list:  # type: AbstractNode
            with component.get_evaluation_functions() as (data_for, callback_with_file):
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
                            # TODO: finish this...
                            # implementation will probably include ensuring that
                            # the InputFileNode and generate_aggregation_list
                            # work on multidims. Should just be copying the data here.
                            write_slices.append(slice(0, component.get_size_along(dim)))
                        else:
                            write_slices.append(slice(None))
                    try:
                        output_data = data_for(var)  # type: np.array
                        if np.issubdtype(output_data.dtype, np.floating):
                            # numpy ufunc isnan only defined for floating types.
                            nc_out.variables[var["name"]][write_slices] = np.ma.masked_where(np.isnan(output_data), output_data)
                        else:
                            nc_out.variables[var["name"]][write_slices] = output_data

                    except VariableNotFoundException:
                        # this error is fine and expected. The template may contain variables that don't
                        # exist in the inputs, just pass over them and they will come out as fill values.
                        pass
                    except Exception as e:
                        # something else... unexpected
                        logger.error("Error copying component: %s, unlim variable: %s" % (component, var))
                        logger.error(traceback.format_exc())

                # do once per component
                callback_with_file(attribute_handler.process_file)

                if callback is not None:
                    callback()

        nc_out.sync()  # write buffered data to disk

        attribute_handler.finalize_file(nc_out)  # after aggregation finished, finalize the global attributes


def initialize_aggregation_file(config, fullpath):
    # type: (Config, str) -> None
    """
    Based on the configuration, initialize a file in which to write the aggregated output. 
    
    In other words, resurrect a netcdf file that would result in config.

    :param config: Aggregation configuration
    :param fullpath: filename of output to initialize.
    :return: None
    """
    with nc.Dataset(fullpath, 'w') as nc_out:
        for dim in config.dims.values():
            # note: dim["size"] will be None for unlimited dimensions.
            nc_out.createDimension(dim["name"], dim["size"])
        for var in config.vars.values():
            var_name = var.get("map_to", var["name"])
            var_type = np.dtype(var["datatype"])
            fill_value = var["attributes"].pop("_FillValue", None)
            if fill_value is not None:
                # fill_value is None by default, but if there is a value specified,
                # explicitly cast it to the same type as the data.
                fill_value = var_type.type(fill_value)
            var_out = nc_out.createVariable(var_name, var_type, var["dimensions"],
                                            chunksizes=var["chunksizes"], zlib=True,
                                            complevel=7, fill_value=fill_value)
            for k, v in var["attributes"].items():
                if k in ["valid_min", "valid_max"]:
                    # cast scalar attributes to datatype of variable
                    # smc@20181206: moved hanldling of _FillValue to createVariable, seems
                    # to matter for netcdf vlen datatypes (eg. string types)
                    var["attributes"][k] = var_type.type(v)
                if k in ["valid_range", "flag_masks", "flag_values"]:
                    # cast array attributes to datatype of variable
                    # Note: two ways to specify an array attribute in Config, either CSV or as actual array.
                    if isinstance(v, str):
                        var["attributes"][k] = np.array(map(var_type.type, v.split(", ")), dtype=var_type)
                    else:
                        var["attributes"][k] = np.array(v, dtype=var_type)

            var_out.setncatts(var["attributes"])

