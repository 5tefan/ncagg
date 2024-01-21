import unittest
import tempfile
from ncagg.config import Config
from ncagg.aggregator import generate_aggregation_list, evaluate_aggregation_list
import glob
import os
import netCDF4 as nc
import numpy as np


class TestAggregate(unittest.TestCase):
    def setUp(self):
        _, self.file = tempfile.mkstemp()

        pwd = os.path.dirname(__file__)
        self.files = glob.glob(os.path.join(pwd, "data", "*.nc"))
        self.config = Config.from_nc(self.files[0])

    def tearDown(self):
        os.remove(self.file)

    def test_main(self):
        agg_list = generate_aggregation_list(self.config, self.files)
        evaluate_aggregation_list(self.config, agg_list, self.file)

        with nc.Dataset(self.file) as nc_in:
            # there should be no fill values in the status variable
            # before ncagg v0.8.5 vlen types like string incorrectly aggregated to fills
            status = nc_in.variables["status"][:]
            self.assertFalse(np.ma.is_masked(status))

            # prior to ncagg v0.8.18, there was a bug that converted string fills 
            # to the string "nan"
            flare_class = nc_in.variables["flare_class"][:]
            self.assertFalse("nan" in flare_class)
            self.assertTrue("" in flare_class)
            self.assertTrue("B1.0" in flare_class)

