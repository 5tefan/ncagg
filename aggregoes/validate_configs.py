import numpy as np
import cerberus
import netCDF4 as nc
from aggregoes.attributes import AttributeHandler
from collections import OrderedDict
from attributes import AttributeHandler
import json

"""
This file contains functions that take some configuration, generally as the first parameter, and any other necessary
argument and confirms that the configuration is understood and sensible. Each function returns a configuration which
should be used after validation. The validator may make changes to the configuration, eg. inserting inferred values
that should be explicit, for example.
"""


def validate(schema, config):
    # type: (dict, dict) -> dict
    """
    Validate a config dict against a cerberus schema. Raise ValueError if there is a problem, otherwise
    returns normalized config.

    :param schema: cerberus schema
    :param config: dict to validate
    :return: normalized config dict
    """
    v = cerberus.Validator(schema)
    if v.validate(config):
        return v.document
    else:
        raise ValueError(v.errors)


class NumpyEncoder(json.JSONEncoder):
    """
    The default json encoder is not able to serialize numpy types, thus this helper is necessary.
    """
    def default(self, obj):
        if isinstance(obj, np.generic):
            return obj.item()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return super(NumpyEncoder, self).default(obj)


class Config(object):
    def __init__(self, dims, vars, attrs):
        # type: (DimensionConfig, VariableConfig, GlobalAttributeConfig) -> None
        """
        Components to create an aggregation:
            - Dimensions: name, index_by, index_by_dim_inds, flatten.
            - Variables: name, dims, dtype, attributes, chunksize.
            - GlobalAttributes: name, strategy, value

        The individual Dimension, Variable, and GlobalAttribute handlers are in charge
        of validating their own individual schema. This Config object is in charge of validating
        interlinking requirements between the individual (mainly) Dimensions and Variables: eg
        All dimensions referenced by a variable exist in the Dimension config.
        """

        # Make sure that configured dimensions and dimensions used by variables are consistent.
        var_dims = set([d for v in vars.values() for d in v["dimensions"]])
        dims_set = set(dims.keys())
        if var_dims.issubset(dims_set) and not dims_set.issubset(var_dims):
            # Not all dimensions were used by a variable, should remove these unused dims.
            raise ValueError("Unused dimensions found in config: %s" % dims_set.difference(var_dims))
        elif not var_dims.issubset(dims_set) and dims_set.issubset(var_dims):
            # A variable used a dimensions that was not configured.
            raise ValueError("Variable depends on unconfigured dimension: %s" % var_dims.difference(dims_set))

        # Make sure that all index_by variables exist
        indexed_by_vars = set([v["index_by"] for v in vars.values() if v.get("index_by", None) is not None])
        if not indexed_by_vars.issubset(vars.keys()):
            raise ValueError("index_by variable not found: %s" % indexed_by_vars.difference(vars.keys()))

        # At the moment, anything else, we'll let fall through and error out at evaluation time.
        self.dims = dims
        self.vars = vars
        self.attrs = attrs

    @classmethod
    def from_json(cls, config):
        # type: (str) -> Config
        dims = DimensionConfig(config.get("dimensions", []))
        vars = VariableConfig(config.get("variables", []))
        attrs = GlobalAttributeConfig(config.get("attributes", []))
        return cls(dims, vars, attrs)

    def to_json(self):
        # type: () -> str
        return json.dumps({
            "dimensions": self.dims.to_list(),
            "variables": self.vars.to_list(),
            "attributes": self.attrs.to_list()
        }, sort_keys=True, indent=4, cls=NumpyEncoder)

    @classmethod
    def from_nc(cls, nc):
        with nc.Dataset(nc, "r") as nc_in:  # type: nc.Dataset
            # Configure Dimensions
            dims = DimensionConfig([{
                "name": dim.name,
                "size": None if dim.isunlimited() else dim.size
            } for dim in nc_in.dimensions.values()])

            # Configure Variables
            vars = [{
                "name": v.name,
                "dimensions": v.dimensions,
                "datatype": v.datatype,
                "attributes": {ak: v.getncattr(ak) for ak in v.ncattrs()},
                "chunksizes": v.chunking() if isinstance(v.chunking(), list) else None
            } for v in nc_in.variables.values()]
            # If the variable doesn't come with an explicit fill value, set it to the netcdf.default_fillvals value
            # https://github.com/Unidata/netcdf4-python/blob/6087ae9b77b538b9c0ab3cdde3118b4ceb6f8946/netCDF4/_netCDF4.pyx#L3359
            for v in vars:
                # convert datatype to string, use dtype attr if exists (case for VLType like str) else is
                # a basic type like np.float and just do str(np.dtype)
                # must convert datatype attribute to a string representation
                if isinstance(v["datatype"], nc._netCDF4.VLType):
                    # if it's a vlen type, grab the .dtype attribute and get the numpy name for it
                    v["datatype"] = np.dtype(v["datatype"].dtype).name
                else:
                    # otherwise it's just a regular np.dtype object already
                    # eg:  str(np.dtype(np.float32)) ==> 'float32'
                    v["datatype"] = str(v["datatype"])

                if "_FillValue" not in v["attributes"].keys() and not v["datatype"].startswith("str"):
                    # avoid AttributeError: cannot set _FillValue attribute for VLEN or compound variable
                    v["attributes"]["_FillValue"] = np.dtype(v["datatype"]).type(
                        nc.default_fillvals[np.dtype(v["datatype"]).str[1:]]
                    )
            vars = VariableConfig(vars)

            # Configure Global Attributes
            attrs = GlobalAttributeConfig([{
                "name": att,
                "strategy": "first"
            } for att in nc_in.ncattrs()])
            attrs["date_created"] = {"strategy": "date_created"}
            attrs["time_coverage_start"] = {"strategy": "time_coverage_start"}
            attrs["time_coverage_end"] = {"strategy": "time_coverage_end"}

        return cls(dims, vars, attrs)


class ConfigDict(OrderedDict):
    def __init__(self, a_list):
        # type: (list) -> None
        # Expecting a list because that's the only way to preserve ordering serializing to/from json.
        self.schema = self.get_item_schema()
        # transform [{"name": "a", "b": "something"}, {"name": "b", "b": "else"}] into
        # [("a", {"b": "something"}), ("b", {"b": "else"})] then construct OrderedDict from that.
        super(ConfigDict, self).__init__([(e.pop("name"), e) for e in a_list])

    def get_item_schema(self):
        # type: () -> dict
        """
        Each config item must have at least a name. Add more in subclass.
        :return: common schema, containing name field.
        """
        return {"name": {"type": "string", "required": True}}

    def __setitem__(self, key, value):
        # type: (str, dict) -> None
        value.update({"name": key})
        value = validate(self.schema, value)
        super(ConfigDict, self).__setitem__(value.pop("name"), value)

    def to_list(self):
        # type: () -> list
        """
        Convert the ConfigDict to a list representation... json serializable.
        :return:
        """
        res = []
        for k, v in self.iteritems():
            out = {"name": k}.update(v)
            res.append(out)
        return res


# DimensionConfig, VariableConfig, AttributeConfig, ...
class DimensionConfig(ConfigDict):
    def get_item_schema(self):
        default = super(DimensionConfig, self).get_item_schema()
        default.update({
            "size": {"type": "integer", "nullable": True},
            "flatten": {"type": "boolean", "default": False},
            "index_by": {"type": "string", "default": None, "nullable": True},
            "min": {"type": "number", "default": None, "nullable": True},  # lower bound via index_by
            "max": {"type": "number", "default": None, "nullable": True},  # upper bound via index_by
            "other_dim_inds": {"type": "dict", "valueschema": {"type": "integer"}, "default": {}},
            "expected_cadence": {"type": "dict", "valueschema": {"type": "number"}, "default": {}}
        })
        return default

    def __setitem__(self, key, value):
        if value.get("size", None) is not None and value.get("index_by", None) is not None:
            raise ValueError("%s: %s: can only index_by for unlimited dimensions" % (self.__class__.__name__, key))
        if value.get("index_by", None) is None:
            # if index_by is not set, can't have any of these.
            value.update({
                "min": None,
                "max": None,
                "other_dim_inds": {},
                "expected_cadence": {}
            })
        super(DimensionConfig, self).__setitem__(key, value)


class VariableConfig(ConfigDict):
    def get_item_schema(self):
        default = super(VariableConfig, self).get_item_schema()
        default.update({
            "dimensions": {"type": "list", "schema": {"type": "string"}},
            "datatype": {"type": "string", "allowed": ["int8", "int16", "int32", "int64",
                                                       "uint8", "uint16", "uint32", "uint64",
                                                       "float16", "float32", "float64",
                                                       "string"]},
            "attributes": {"type": "dict", "valueschema": {"oneof_type": ["string", "number"]}, "default": {}},
            "chunksizes": {"type": "list", "schema": {"type": "integer"}, "default": []}
        })
        return default

    def __setitem__(self, key, value):
        len_chunks = len(value.get("chunksizes", []))
        if len_chunks > 0 and len(value.get("dimensions", [])) != len_chunks:
            # if chunksizes are given, chunksizes and dimensions must be lists of the same size
            raise ValueError("%s: %s: required: len(dims) == len(chunksizes)" % (self.__class__.__name__, key) )
        super(VariableConfig, self).__setitem__(key, value)


class GlobalAttributeConfig(ConfigDict):
    def get_item_schema(self):
        default = super(GlobalAttributeConfig, self).get_item_schema()
        default.update({
            "strategy": {"type": "string", "allowed": AttributeHandler.strategy_handlers.keys()},
            "value": {"oneof_type": ["string", "float", "int"], "nullable": True, "default": None}
        })
        return default


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
            if value == "flatten":
                continue  # don't need to do anything else. Flatten is valid.

            # otherwise, check index_by syntax
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

