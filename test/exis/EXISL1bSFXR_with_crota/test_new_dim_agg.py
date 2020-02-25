import unittest
import tempfile
import netCDF4 as nc
from ncagg.config import Config
from ncagg.aggregator import generate_aggregation_list, evaluate_aggregation_list
import glob
import os
import numpy as np
import json


class TestEuvs(unittest.TestCase):
    def setUp(self):
        # tmp file to aggregate to
        _, self.nc_out_filename = tempfile.mkstemp()

        pwd = os.path.dirname(__file__)
        self.files = sorted(glob.glob(os.path.join(pwd, "data", "*.nc")))
        with open(os.path.join(pwd, "new_dim_config.json")) as config_in:
            self.config = Config.from_dict(json.load(config_in))

    def tearDown(self):
        os.remove(self.nc_out_filename)

    def test_basic_create_new_dim(self):
        """
        Files in data have SUVI_CROTA dimensionless variables. The config has been
        modified from the default to give crota variables a dependence on the unlim
        dimension crota_report_number.

        Here, make sure this transformation is done correctly.
        """
        aggregation_list = generate_aggregation_list(self.config, self.files)
        self.assertEqual(len(aggregation_list), 5)
        evaluate_aggregation_list(self.config, aggregation_list, self.nc_out_filename)
        with nc.Dataset(self.nc_out_filename) as nc_out:  # type: nc.Dataset
            crota_time = nc_out.variables["SUVI_CROTA_time"][:]
            self.assertEqual(len(crota_time), 5)
            self.assertTrue(nc_out.dimensions["crota_report_number"].isunlimited())
            # make sure each crota_time value isn't the same, they should be increasing
            # but there isn't necessarily a unique crota value in each file (it's given
            # about once a minute), so it's expected that there are cases where two
            # consecutive files have the same crota data. Hence, on average, it's
            # increasing.
            self.assertGreater(np.mean(np.diff(crota_time)), 0)
            # perffffect
