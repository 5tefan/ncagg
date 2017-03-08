import netCDF4 as nc

"""
This file contains functions that take some configuration, generally as the first parameter, and any other necessary
argument and confirms that the configuration is understood and sensible. Each function returns a configuration which
should be used after validation. The validator may make changes to the configuration, eg. inserting inferred values
that should be explicit, for example.
"""


def validate_unlimited_dim_indexed_by_time_var_map(mapping, input_file):
    """
    Validate that a mapping between an unlimited dimension and some variable indexing it (like time)
    is a valid relationship and properly specified.

    This config mapping should look something like this:
    {
        "record_number": { "index_by": "time_variable", "other_dim_indicies": { "samples_per_record": 0 }
                            "min": value, "max": value, "expected_cadence": { "each_dim": cadence }
                          }
    }
    This config indicates that the unlimited dimension record_number is indexed in time by time_variable. Though
    time_variable is not flat, we specify to take the first record from the other dimension besides record_number.


    :type mapping: dict
    :param mapping: specification of mapping between unlim dimension and a variable indexing it
    :type input_file: str
    :param input_file: a sample input file to check the mapping against
    :rtype: dict
    :return: a validated mapping
    """

    # the do nothing/pass through case
    if mapping is None or len(mapping) == 0:
        return {}

    # otherwise there are actaully keys to validate
    with nc.Dataset(input_file) as nc_in:
        # the keys in mapping should be dimensions in the file
        check_keys_are_dims = all((k in nc_in.dimensions.keys() for k in mapping.keys()))
        if not check_keys_are_dims:
            raise ValueError("Keys must be dimensions in the input file.")

        # those dimensions should be unlimited
        check_keys_are_unlimited = all(
            (nc_in.dimensions[k].isunlimited() if k in nc_in.dimensions.keys() else False for k in mapping.keys())
        )
        if not check_keys_are_unlimited:
            raise ValueError("Keys must be unlimited dimensions.")

        for key, value in mapping.items():
            if not value["index_by"] in nc_in.variables.keys():
                raise ValueError("Key index_by must map to a variable name.")
            # default other_dim_indicies to 0 if they aren't specified, this seems most reasonable thing to do.
            # is ok even if entire other_dim_indicies is missing.
            value["other_dim_indicies"] = value.get("other_dim_indicies", {})
            if not isinstance(value["other_dim_indicies"], dict):
                raise TypeError("Key other_dim_indicies must be a dict.")
            checked_other_dim_indicies = {
                d: value["other_dim_indicies"].get(d, 0) for d in nc_in.variables[value["index_by"]].dimensions
            }

            # check that the specified dimension index is in range of the size of the dimension
            # note the abs(v) as the index could be eg. -1 to go by the last one.
            check_other_dim_indicies_in_range = all(
                (abs(v) < nc_in.dimensions[k].size for k, v in checked_other_dim_indicies.items())
            )
            if not check_other_dim_indicies_in_range:
                raise ValueError("Specified other_dim_indicies value not in range of dimension.")

            value["other_dim_indicies"] = checked_other_dim_indicies

        return mapping

