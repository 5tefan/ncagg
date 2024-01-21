import unittest
import numpy as np
import netCDF4 as nc
from ncagg.aggregator import initialize_aggregation_file
import os
import tempfile
from ncagg.config import Config


class TestFileInitialization(unittest.TestCase):
    def setUp(self):
        _, self.filename = tempfile.mkstemp()

    def tearDown(self):
        os.remove(self.filename)

    def test_initialize_basic(self):
        """Ensure aggregation file is created with proper dimensions according to the config."""
        config = Config.from_dict(
            {
                "dimensions": [{"name": "x", "size": None}, {"name": "y", "size": 10}],
                "variables": [
                    {
                        "name": "x",
                        "dimensions": ["x", "y"],
                        "datatype": "int8",
                        "attributes": {
                            "_FillValue": 1,
                        },
                    }
                ],
                "global attributes": [],
            }
        )
        initialize_aggregation_file(config, self.filename)
        with nc.Dataset(self.filename) as nc_check:
            self.assertEqual(len(nc_check.dimensions), 2)
            self.assertEqual(nc_check.dimensions["y"].size, 10)
            self.assertFalse(nc_check.dimensions["y"].isunlimited())
            self.assertTrue(nc_check.dimensions["x"].isunlimited())
            self.assertEqual(nc_check.variables["x"]._FillValue, 1)

    def test_initialize_several_variables(self):
        """Ensure aggregation file is created correctly according to the variable config."""
        config = Config.from_dict(
            {
                "dimensions": [{"name": "x", "size": None}, {"name": "y", "size": 10}],
                "variables": [
                    {
                        "name": "foo",
                        "dimensions": ["x", "y"],
                        "datatype": "float32",
                        "attributes": {"units": "seconds"},
                    },
                    {
                        "name": "foo_x",
                        "dimensions": ["x"],
                        "datatype": "float64",
                        "attributes": {"units": "floops", "created_by": "the flooper"},
                    },
                ],
                "global attributes": [],
            }
        )
        initialize_aggregation_file(config, self.filename)
        with nc.Dataset(self.filename) as nc_check:
            self.assertEqual(len(nc_check.variables), 2)
            self.assertEqual(nc_check.variables["foo"].dimensions, ("x", "y"))
            self.assertEqual(nc_check.variables["foo"].datatype, np.dtype(np.float32))
            self.assertEqual(nc_check.variables["foo"].units, "seconds")
            self.assertEqual(nc_check.variables["foo_x"].dimensions, ("x",))
            self.assertEqual(nc_check.variables["foo_x"].datatype, np.dtype(np.float64))
            self.assertEqual(nc_check.variables["foo_x"].units, "floops")
            self.assertEqual(
                nc_check.variables["foo_x"].getncattr("created_by"), "the flooper"
            )

    def test_initialize_with_list_attribute(self):
        """Ensure aggregation file is created with proper dimensions according to the config."""
        config = Config.from_dict(
            {
                "dimensions": [{"name": "x", "size": None}, {"name": "y", "size": 10}],
                "variables": [
                    {
                        "name": "x",
                        "dimensions": ["x", "y"],
                        "datatype": "int8",
                        "attributes": {"valid_range": [0, 10]},
                    }
                ],
                "global attributes": [],
            }
        )
        initialize_aggregation_file(config, self.filename)
        with nc.Dataset(self.filename) as nc_check:
            self.assertEqual(len(nc_check.dimensions), 2)
            self.assertEqual(nc_check.variables["x"].valid_range[0], 0)
            self.assertEqual(nc_check.variables["x"].valid_range[1], 10)
