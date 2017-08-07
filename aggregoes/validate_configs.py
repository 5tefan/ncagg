import numpy as np
import netCDF4 as nc
from aggregoes.attributes import AttributeHandler

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


    :type mapping: dict | None
    :param mapping: specification of mapping between unlim dimension and a variable indexing it
    :type input_file: basestring
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

            # Check that the specified dimension index is in range of the size of the dimension. Note the abs(v) as the index
            # could be eg. -1 to go by the last one. Also, check if size is 0, in which case let this through. By now, we've 
            # validated that the dimension exists - say we're unlucky and the input_file we're checking against is empty but
            # one later in the list has data, don't fail validation here.
            check_other_dim_indicies_in_range = all(
                (nc_in.dimensions[k].size == 0 or abs(v) < nc_in.dimensions[k].size for k, v in checked_other_dim_indicies.items())
            )
            if not check_other_dim_indicies_in_range:
                raise ValueError("Specified other_dim_indicies value not in range of dimension.")

            value["other_dim_indicies"] = checked_other_dim_indicies

        return mapping


def validate_a_global_attribute_block(block):
    """
    Validate a global attribute configuration.
     - checks that the block has a name field
     - strategy is valid, if strategy given otherwise default to "first"
     - if strategy is static, make sure value is given
    :type block: dict
    :param block: a dict bock configuring a global attribute
    :return: None
    """
    if block is None or len(block) == 0:
        return None

    if "name" not in block.keys():
        raise ValueError("Name of attribute not set in attribute config block.")

    if "strategy" in block.keys():
        strategy = block["strategy"]
        if AttributeHandler.strategy_handlers.get(strategy, None) is None:
            raise ValueError("Strategy %s does not exist, found for attribute: %s" % (strategy, block["name"]))

        if strategy == "static" and block.get("value", None) is None:
            raise ValueError("No value key set for attribute %s with strategy static" % block["name"])
    else:
        block["strategy"] = "first"


def validate_a_dimension_block(block):
    """
    Validate that a block (dict) configuring a dimension is valid.
    :type block: dict
    :param block: a dimension configuration block to validate.
    :return: None
    """
    if block is None or len(block) == 0:
        return None

    for required_key in ["name", "size"]:
        if required_key not in block.keys():
            raise ValueError(
                "Dimension configuration missing key %s for %s" % (required_key, block.get("name", "unknown"))
            )


def validate_a_variable_block(block):
    """
    Validate that a block (dict) configuring a variable is valid.
    :param block:
    :return:
    """
    if block is None or len(block) == 0:
        return None

    block_keys = block.keys()
    if "name" not in block_keys or not isinstance(block["name"], basestring):
        raise ValueError("Variable block does not name (basestring) the variable it configures!")

    if "dimensions" not in block_keys:
        raise ValueError("Variable configuration for %s must be a list of dimensions." % block["name"])

    if not hasattr(block["dimensions"], "__iter__"):
        raise ValueError("Expected dimensions to be a list that variable %s depends on" % block["name"])

    if "datatype" not in block_keys:
        raise ValueError("datatype not configured for variable %s" % block["name"])

    # make sure the datatype is understood
    np.dtype(block["datatype"])

    if "attributes" not in block_keys:
        block["attributes"] = {}
    else:
        if not isinstance(block["attributes"], dict):
            raise ValueError("Variable %s attributes configuration should be a dict" % block["name"])



def validate_take_dim_indicies_block(block, dim_config):
    if block is None or len(block) == 0:
        return None

    # the validity of take_dim_indicies depends on the dimension configuration...
    # not valid to collapse a dimension and still have it in the dim_config
    block_keys = block.keys()
    dim_config_keys = [d["name"] for d in dim_config]
    for key in block_keys:
        if key in dim_config_keys:
            raise ValueError("Cannot have a dimension that gets collapsed! Don't collapse or remove dim: %s" % key)

