import unittest
import tempfile
import netCDF4 as nc
from ncagg.config import Config
from ncagg.aggregator import generate_aggregation_list, evaluate_aggregation_list
from datetime import datetime
import glob
import os
import numpy as np
import json


class TestEuvs(unittest.TestCase):
    def setUp(self):
        # tmp file to aggregate to
        _, self.nc_out_filename = tempfile.mkstemp()

        pwd = os.path.dirname(__file__)
        self.files = sorted(glob.glob(os.path.join(pwd, "data", "type1", "*.nc")))
        with open(os.path.join(pwd, "type1_config.json")) as config_in:
            self.config = Config.from_dict(json.load(config_in))

    def tearDown(self):
        os.remove(self.nc_out_filename)

    def test_basic(self):
        """ Ok, so the files in data/type1/ don't have an unlimited dimension, report_number should be
        unlimited so I've made report_nubmer unlimited in the config template type1_config.json.
        Let's see if we can aggregate to it. """
        aggregation_list = generate_aggregation_list(self.config, self.files)
        self.assertEqual(len(aggregation_list), 3)
        evaluate_aggregation_list(self.config, aggregation_list, self.nc_out_filename)
        with nc.Dataset(self.nc_out_filename) as nc_out:  # type: nc.Dataset
            time = nc_out.variables["time"][:]
            self.assertEqual(len(time), 3)
            self.assertTrue(nc_out.dimensions["report_number"].isunlimited())
            # perffffect
