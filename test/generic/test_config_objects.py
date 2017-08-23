import unittest
from ncagg.config import ConfigDict
from ncagg.config import DimensionConfig, VariableConfig, GlobalAttributeConfig
from ncagg.config import Config

class SampleConfig(ConfigDict):
    """ A very basic config that expect fields with a something float value,
    in order to test that basic functionality works as expected. """
    def get_item_schema(self):
        default = super(SampleConfig, self).get_item_schema()
        default.update({"something": {"type": "float"}})
        return default

class TestConfigDict(unittest.TestCase):

    def test_init_valid(self):
        """ Make sure that a valid configuration is accepted and ordering
        preserved. """
        a = SampleConfig([
            {"name": "a", "something": 1},
            {"name": "b", "something": 2},
            {"name": "z", "something": 1}
        ])
        for i, k in enumerate(a.keys()):
            # check ordering
            self.assertEqual(["a", "b", "z"][i], k)

    def test_init_invalid(self):
        """ Ensure that the sample config rejects the bad string value
        since something is expected to be a float value. """
        with self.assertRaises(ValueError):
            SampleConfig([
                {"name": "a", "something": 1},
                {"name": "b", "something": "noooo"},
                {"name": "z", "something": 1}
            ])

    def test_update(self):
        """ Test that we can't insert invalid values through update either. """
        a = SampleConfig([
            {"name": "a", "something": 1},
            {"name": "z", "something": 1}
        ])
        a.update({"b": {"something": 2}})
        self.assertEqual(len(a), 3)
        with self.assertRaises(ValueError):
            a.update({"b": {"something": "noooo"}})


class TestDimVarAttrConfigs(unittest.TestCase):

    def test_dimension_config(self):
        """ Test that the DimensionConfig object behaves as expected. """
        dc = DimensionConfig([
            {"name": "a",
             "size": 5}
        ])
        self.assertIn("a", dc.keys())
        self.assertEqual(dc["a"]["size"], 5)
        self.assertTrue(dc["a"]["index_by"] is None)

        dc["b"] = {"size": None, "index_by": "c"}
        self.assertIn("b", dc.keys())
        self.assertTrue(dc["b"]["size"] is None)
        self.assertEqual(dc["b"]["index_by"], "c")

    # TODO: test Vars, and GlobalAttrs


class TestOverallConfig(unittest.TestCase):
    def test_basic(self):
        """ Make sure the configuration accepts a valid configuration. """
        dims = DimensionConfig([{"name": "a", "size": 2}, {"name": "b", "size": None}])
        vars = VariableConfig([
            {"name": "t", "dimensions": ["b"], "datatype": "float32"},
            {"name": "x", "dimensions": ["b", "a"], "datatype": "float32"},
        ])
        attrs = GlobalAttributeConfig([])
        Config(dims, vars, attrs)

    def test_basic_with_var_attrs(self):
        """ Make sure the configuration accepts a valid configuration. """
        dims = DimensionConfig([{"name": "a", "size": 2}, {"name": "b", "size": None}])
        vars = VariableConfig([
            {"name": "t", "dimensions": ["b"], "datatype": "float32", "attributes": {"_FillValue": 0}},
            {"name": "x", "dimensions": ["b", "a"], "datatype": "float32"},
        ])
        attrs = GlobalAttributeConfig([])
        Config(dims, vars, attrs)

    def test_missing_dim(self):
        """ The variable t depends on a dimension c that has not been configured.
        Make sure a ValueError is raised because of this."""
        dims = DimensionConfig([{"name": "a", "size": 2}, {"name": "b", "size": None}])
        vars = VariableConfig([
            {"name": "t", "dimensions": ["c"], "datatype": "float32"},
            {"name": "x", "dimensions": ["b", "a"], "datatype": "float32"},
        ])
        attrs = GlobalAttributeConfig([])
        with self.assertRaises(ValueError):
            Config(dims, vars, attrs)

    def test_extra_dim(self):
        """We have configured an extra dimension z that isn't used by any variables.
        Make sure a ValueError is raised. """
        dims = DimensionConfig([{"name": "a", "size": 2}, {"name": "b", "size": None}, {"name": "z", "size": None}])
        vars = VariableConfig([
            {"name": "t", "dimensions": ["a"], "datatype": "float32"},
            {"name": "x", "dimensions": ["b", "a"], "datatype": "float32"},
        ])
        attrs = GlobalAttributeConfig([])
        with self.assertRaises(ValueError):
            Config(dims, vars, attrs)

    def test_to_json(self):
        dims = DimensionConfig([{"name": "a", "size": 2}, {"name": "b", "size": None}])
        vars = VariableConfig([
            {"name": "t", "dimensions": ["b"], "datatype": "float32"},
            {"name": "x", "dimensions": ["b", "a"], "datatype": "float32"},
        ])
        attrs = GlobalAttributeConfig([])
        json = Config(dims, vars, attrs).to_dict()

