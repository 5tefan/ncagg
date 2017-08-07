import unittest
import tempfile
from aggregoes.aggregator import Aggregator
from datetime import datetime, timedelta
import glob
import os
import netCDF4 as nc
import numpy as np

class TestGenerateAggregationList(unittest.TestCase):
    def setUp(self):
        _, self.file = tempfile.mkstemp()

    def tearDown(self):
        os.remove(self.file)

    def test_main(self):
        pwd = os.path.dirname(__file__)
        files = glob.glob(os.path.join(pwd, "data", "*.nc"))[:2]
        a = Aggregator()
        start_time = datetime(2017, 07, 14, 00, 00)
        end_time = start_time + timedelta(days=1) - timedelta(milliseconds=1)
        aggregation_list = a.generate_aggregation_list(files, {
            "time": {
                "index_by": "time",
                "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
                "max": end_time,
                "expected_cadence": {"time": 1},
            }
        })
        a.evaluate_aggregation_list(aggregation_list, self.file)
        with nc.Dataset(self.file) as nc_out:
            for dt in nc.num2date(nc_out.variables["time"][:], nc_out.variables["time"].units):
                # since this is an aggregation over a day, we shouldn't have any values
                self.assertEqual(dt.year, start_time.year)
                self.assertEqual(dt.day, start_time.day)


