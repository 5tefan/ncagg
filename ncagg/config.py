import numpy as np
import cerberus
import netCDF4 as nc
from collections import OrderedDict

from ncagg.attributes import AttributeHandler

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
        self.dims = dims  # type: DimensionConfig
        self.vars = vars  # type: VariableConfig
        self.attrs = attrs  # type: GlobalConfig

        # At the moment, anything else, we'll let fall through and error out at evaluation time.
        self.inter_validate()


    def inter_validate(self):
        """
        While self.dims, self.vars, and self.attrs are responsible for their own basic validation,
        intervalidation between them is better done at a higher level as there is no gaurantee eg,
        dims is initialized before vars.

        Raises ValueError if an invalid configuration is detected.

        :return: None
        """
        # Make sure that configured dimensions and dimensions used by variables are consistent.
        var_dims = set([d for v in self.vars.values() for d in v["dimensions"]])
        dims_set = set(self.dims.keys())
        if var_dims.issubset(dims_set) and not dims_set.issubset(var_dims):
            # Not all dimensions were used by a variable, should remove these unused dims.
            raise ValueError("Unused dimensions found in config: %s" % dims_set.difference(var_dims))
        elif not var_dims.issubset(dims_set) and dims_set.issubset(var_dims):
            # A variable used a dimensions that was not configured.
            raise ValueError("Variable depends on unconfigured dimension: %s" % var_dims.difference(dims_set))

        # Make sure that all index_by variables exist
        indexed_by_vars = set([d["index_by"] for d in self.dims.values() if d["index_by"] is not None])
        if not indexed_by_vars.issubset(self.vars.keys()):
            raise ValueError("index_by variable not found: %s" % indexed_by_vars.difference(self.vars.keys()))

        # Make sure other_dim_inds specified are valid in range of the dimension.
        for d, v in self.dims.items():
            for od, ov in v["other_dim_inds"].items():
                if self.dims[od]["size"] is not None and np.abs(self.dims[od]["size"]) <= ov:
                    raise ValueError("dim %s's other_dim_inds %s for %s too big for size %s"
                                     % (d, ov, od, self.dims[od]["size"]))


    @classmethod
    def from_dict(cls, config):
        # type: (dict) -> Config
        dims = DimensionConfig(config.get("dimensions", []))
        vars = VariableConfig(config.get("variables", []))
        attrs = GlobalAttributeConfig(config.get("attributes", []))
        return cls(dims, vars, attrs)

    def to_dict(self):
        # type: () -> dict
        return {
            "dimensions": self.dims.to_list(),
            "variables": self.vars.to_list(),
            "attributes": self.attrs.to_list()
        }

    @classmethod
    def from_nc(cls, nc_filename):
        # type: (str) -> Config
        dims = DimensionConfig.from_nc(nc_filename)  # Configure Dimensions
        vars = VariableConfig.from_nc(nc_filename)  # Configure Variables
        attrs = GlobalAttributeConfig.from_nc(nc_filename)  # Configure Global Attributes

        return cls(dims, vars, attrs)


class ConfigDict(OrderedDict):
    def __init__(self, a_list):
        # type: (list) -> None
        # Expecting a list because that's the only way to preserve ordering serializing to/from json.
        self.schema = self.get_item_schema()

        # transform [{"name": "a", "b": "something"}, {"name": "b", "b": "else"}] into
        # [("a", {"b": "something"}), ("b", {"b": "else"})] then construct OrderedDict from that.
        super(ConfigDict, self).__init__([(e["name"], e) for e in a_list])


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
        super(ConfigDict, self).__setitem__(value["name"], value)

    def update(self, *args, **kwargs):
        for k, v in dict(*args, **kwargs).items():
            self[k] = v

    def to_list(self):
        # type: () -> list
        """
        Convert the ConfigDict to a list representation... json serializable.
        :return:
        """
        res = []
        for k, v in self.items():
            out = {}
            out.update(v)
            res.append(out)
        return res


# DimensionConfig, VariableConfig, AttributeConfig, ...
class DimensionConfig(ConfigDict):
    def get_item_schema(self):
        default = super(DimensionConfig, self).get_item_schema()
        default.update({
            "size": {"type": "integer", "nullable": True, "min": 1},
            "flatten": {"type": "boolean", "default": False},
            "index_by": {"type": "string", "default": None, "nullable": True},
            "min": {"oneof_type": ["number", "datetime"], "default": None, "nullable": True},  # lower bound via index_by
            "max": {"oneof_type": ["number", "datetime"], "default": None, "nullable": True},  # upper bound via index_by
            "other_dim_inds": {"type": "dict", "valueschema": {"type": "integer"}, "default": dict()},
            "expected_cadence": {"type": "dict", "valueschema": {"type": "float"}, "default": dict()}
        })
        return default

    def __setitem__(self, key, value):
        # if value.get("size", None) is not None and value.get("index_by", None) is not None:
        #     raise ValueError("%s: %s: can only index_by for unlimited dimensions" % (self.__class__.__name__, key))
        if value.get("index_by", None) is None:
            # if index_by is not set, can't have any of these.
            value.update({
                "min": None,
                "max": None,
                "other_dim_inds": {},
                "expected_cadence": {}
            })
        super(DimensionConfig, self).__setitem__(key, value)

    @classmethod
    def from_nc(cls, nc_filename):
        with nc.Dataset(nc_filename, "r") as nc_in:  # type: nc.Dataset
            return cls([{
                "name": dim.name,
                "size": None if dim.isunlimited() else dim.size
            } for dim in nc_in.dimensions.values()])



class VariableConfig(ConfigDict):
    def get_item_schema(self):
        default = super(VariableConfig, self).get_item_schema()
        default.update({
            "dimensions": {"type": "list", "schema": {"type": "string"}},
            "datatype": {"type": "string"}, # "allowed": np.sctypeDict.keys()},  # TODO: how to validate this?
            "attributes": {"type": "dict", "valueschema": {"oneof_type": ["string", "number", "list"]}, "default": {}},
            "chunksizes": {"type": "list", "schema": {"type": "integer"}, "default": None, "nullable": True}
        })
        return default

    def __setitem__(self, key, value):
        if value.get("chunksizes", None) is not None and len(value.get("dimensions", [])) != len(value["chunksizes"]):
            # if chunksizes are given, chunksizes and dimensions must be lists of the same size
            raise ValueError("%s: %s: required: len(dims) == len(chunksizes)" % (self.__class__.__name__, key) )
        super(VariableConfig, self).__setitem__(key, value)

    @classmethod
    def from_nc(cls, nc_filename):
        with nc.Dataset(nc_filename, "r") as nc_in:  # type: nc.Dataset
            vars = [{
                "name": v.name,
                "dimensions": list(v.dimensions),
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
                    dt = np.dtype(v["datatype"].dtype)
                else:
                    # otherwise it's just a regular np.dtype object already
                    # eg:  str(np.dtype(np.float32)) ==> 'float32'
                    dt = v["datatype"]

                v["datatype"] = str(dt)

                if "_FillValue" not in v["attributes"].keys() and not dt.kind in ["U", "S"]:  # not string type
                    # avoid AttributeError: cannot set _FillValue attribute for VLEN or compound variable
                    v["attributes"]["_FillValue"] = dt.type(nc.default_fillvals[dt.str[1:]])

                # make sure we only have builtin types here...
                for k, a in v["attributes"].items():
                    if isinstance(a, np.ndarray):
                        v["attributes"][k] = a.tolist()
                    elif isinstance(a, np.generic):
                        v["attributes"][k] = a.item()

        return cls(vars)

class GlobalAttributeConfig(ConfigDict):
    def get_item_schema(self):
        default = super(GlobalAttributeConfig, self).get_item_schema()
        default.update({
            "strategy": {"type": "string", "allowed": list(AttributeHandler.strategy_handlers.keys())},
            "value": {"oneof_type": ["string", "float", "integer"], "nullable": True, "default": None}
        })
        return default

    @classmethod
    def from_nc(cls, nc_filename):
        with nc.Dataset(nc_filename, "r") as nc_in:  # type: nc.Dataset
            attrs = cls([{
                "name": att,
                "strategy": "first"
            } for att in nc_in.ncattrs()])
            attrs.get("date_created", {}).update({"strategy": "date_created"})
            attrs.get("time_coverage_start", {}).update({"strategy": "time_coverage_start"})
            attrs.get("time_coverage_end", {}).update({"strategy": "time_coverage_end"})
        return attrs



