import unittest
import numpy as np
import netCDF4 as nc
from aggregoes.aggre_list import Aggregator
import os
import tempfile


class TestFileInitialization(unittest.TestCase):

    def setUp(self):
        _, self.filename = tempfile.mkstemp()

    def tearDown(self):
        os.remove(self.filename)

    def test_initialize_dimensions(self):
        """Ensure aggregation file is created with proper dimensions according to the config."""
        a = Aggregator({
            "dimensions": [
                {"name": "x", "size": None},
                {"name": "y", "size": 10}
            ],
            "variables": [],
            "global attributes": []
        })
        a.initialize_aggregation_file(self.filename)
        with nc.Dataset(self.filename) as nc_check:
            self.assertEqual(len(nc_check.dimensions), 2)
            self.assertEqual(nc_check.dimensions["y"].size, 10)
            self.assertFalse(nc_check.dimensions["y"].isunlimited())
            self.assertTrue(nc_check.dimensions["x"].isunlimited())

    def test_initialize_single_variable(self):
        """Ensure aggregation file is created correctly according to the variable config."""
        a = Aggregator({
            "dimensions": [
                {"name": "x", "size": None},
                {"name": "y", "size": 10}
            ],
            "variables": [
                {
                    "name": "foo",
                    "dimensions": ["x", "y"],
                    "datatype": "float32",
                    "attributes": {"units": "seconds"}
                },
            ],
            "global attributes": []
        })
        a.initialize_aggregation_file(self.filename)
        with nc.Dataset(self.filename) as nc_check:
            self.assertEqual(len(nc_check.variables), 1)
            self.assertEqual(nc_check.variables["foo"].dimensions, ("x", "y"))
            self.assertEqual(nc_check.variables["foo"].datatype, np.dtype(np.float32))
            self.assertEqual(nc_check.variables["foo"].units, "seconds")

    def test_initialize_several_variables(self):
        """Ensure aggregation file is created correctly according to the variable config."""
        a = Aggregator({
            "dimensions": [
                {"name": "x", "size": None},
                {"name": "y", "size": 10}
            ],
            "variables": [
                {
                    "name": "foo",
                    "dimensions": ["x", "y"],
                    "datatype": "float32",
                    "attributes": {"units": "seconds"}
                }, {
                    "name": "foo_x",
                    "dimensions": ["x"],
                    "datatype": "float64",
                    "attributes": {"units": "floops",
                                   "created_by": "the flooper"}
                },
            ],
            "global attributes": []
        })
        a.initialize_aggregation_file(self.filename)
        with nc.Dataset(self.filename) as nc_check:
            self.assertEqual(len(nc_check.variables), 2)
            self.assertEqual(nc_check.variables["foo"].dimensions, ("x", "y"))
            self.assertEqual(nc_check.variables["foo"].datatype, np.dtype(np.float32))
            self.assertEqual(nc_check.variables["foo"].units, "seconds")
            self.assertEqual(nc_check.variables["foo_x"].dimensions, ("x",))
            self.assertEqual(nc_check.variables["foo_x"].datatype, np.dtype(np.float64))
            self.assertEqual(nc_check.variables["foo_x"].units, "floops")
            self.assertEqual(nc_check.variables["foo_x"].getncattr("created_by"), "the flooper")

