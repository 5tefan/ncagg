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
        self.files = sorted(glob.glob(os.path.join(pwd, "data", "type3", "*.nc")))
        with open(os.path.join(pwd, "type3_config.json")) as config_in:
            self.config = Config.from_dict(json.load(config_in))

    def tearDown(self):
        os.remove(self.nc_out_filename)

    def test_using_product_bounds(self):
        """ Ok, so the files in data/type3/ don't have an unlimited report_number dimension.
        Also, euvsCQualityFlags is missing a report_number dimension, can we create an explicit
        dependence on this? """
        start_time = datetime(2017, 8, 25, 0, 3, 30)  # 2017-08-25T00:03:29.6Z
        end_time = datetime(2017, 8, 25, 0, 5, 0)  # 2017-08-25T00:04:29.6Z

        self.config.dims["report_number"].update(
            {
                "index_by": "time",
                "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
                "max": end_time,
                "expected_cadence": {"report_number": 1.0 / 30.0},
            }
        )
        self.config.inter_validate()
        aggregation_list = generate_aggregation_list(self.config, self.files)
        self.assertGreater(len(aggregation_list), 2)
        evaluate_aggregation_list(self.config, aggregation_list, self.nc_out_filename)
        with nc.Dataset(self.nc_out_filename) as nc_out:  # type: nc.Dataset
            self.assertTrue(nc_out.dimensions["report_number"].isunlimited())

            time = nc_out.variables["time"][:]

            self.assertAlmostEqual(np.min(np.diff(time)), 30.0, delta=0.001)
            self.assertAlmostEqual(np.max(np.diff(time)), 30.0, delta=0.001)
