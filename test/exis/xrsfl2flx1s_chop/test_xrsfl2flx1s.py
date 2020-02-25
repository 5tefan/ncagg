import unittest
import tempfile
import netCDF4 as nc
import numpy as np
from ncagg.config import Config
from ncagg.aggregator import generate_aggregation_list, evaluate_aggregation_list
from datetime import datetime, timedelta
import glob
import os
import netCDF4 as nc
import numpy as np


class TestGenerateAggregationList(unittest.TestCase):
    def setUp(self):
        _, self.file = tempfile.mkstemp()

        pwd = os.path.dirname(__file__)
        self.files = glob.glob(os.path.join(pwd, "data", "*.nc"))[:2]
        self.config = Config.from_nc(self.files[0])

    def tearDown(self):
        os.remove(self.file)

    def test_main(self):
        start_time = datetime(2017, 7, 14, 0, 0)
        end_time = start_time + timedelta(days=1) - timedelta(milliseconds=1)
        self.config.dims["time"].update(
            {
                "index_by": "time",
                "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
                "max": end_time,
                "expected_cadence": {"time": 1},
            }
        )
        agg_list = generate_aggregation_list(self.config, self.files)
        evaluate_aggregation_list(self.config, agg_list, self.file)
        with nc.Dataset(self.file) as nc_out:
            start_time_num, end_time_num = nc.date2num(
                [start_time, end_time], nc_out["time"].units
            )
            time = nc_out.variables["time"][:]
            out_start, out_end = nc.num2date(
                time[[0, -1]], nc_out.variables["time"].units
            )
            self.assertGreaterEqual(out_start, start_time)
            self.assertLessEqual(out_end, end_time)
            self.assertAlmostEqual(np.mean(np.diff(time)), 1, delta=0.001)
            self.assertAlmostEqual(np.max(np.diff(time)), 1, delta=0.001)
            self.assertAlmostEqual(np.min(np.diff(time)), 1, delta=0.001)
            self.assertAlmostEqual(
                int((end_time - start_time).total_seconds()), time.size, delta=1
            )
            self.assertGreaterEqual(time[0], start_time_num)
            self.assertLess(time[-1], end_time_num)
