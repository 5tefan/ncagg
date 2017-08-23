import unittest
import tempfile
import netCDF4 as nc
import numpy as np
from ncagg.config import Config
from ncagg.aggregator import generate_aggregation_list, evaluate_aggregation_list
from datetime import datetime, timedelta
import glob
import os


class TestMag(unittest.TestCase):
    def setUp(self):
        _, self.file = tempfile.mkstemp()
        pwd = os.path.dirname(__file__)
        self.files = glob.glob(os.path.join(pwd, "data", "*.nc"))
        self.config = Config.from_nc(self.files[0])
        self.config.dims["report_number"].update({
            "index_by": "OB_time",
            "other_dim_indicies": {"samples_per_record": 0},
            "expected_cadence": {"report_number": 1, "number_samples_per_report": 10},
        })

    def tearDown(self):
        os.remove(self.file)

    def test_mag_instantiation(self):
        start_time = datetime(2017, 2, 12, 15)
        end_time = datetime(2017, 2, 12, 16)
        self.config.dims["report_number"].update({
            "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
            "max": end_time,
        })
        agg_list = generate_aggregation_list(self.config, self.files)
        self.assertEqual(len(agg_list), 60)
        evaluate_aggregation_list(self.config, agg_list, self.file)
        with nc.Dataset(self.file) as nc_out:
            time = nc_out.variables["OB_time"][:, 0]
            out_start, out_end = nc.num2date(time[[0, -1]], nc_out.variables["OB_time"].units)
            self.assertGreaterEqual(out_start, start_time-timedelta(seconds=0.25))
            self.assertLessEqual(out_end, end_time+timedelta(seconds=0.25))
            self.assertAlmostEqual(np.mean(np.diff(time)), 1, delta=0.001)
            self.assertAlmostEqual(np.max(np.diff(time)), 1, delta=0.001)
            self.assertAlmostEqual(np.min(np.diff(time)), 1, delta=0.001)
            self.assertAlmostEqual(int((end_time - start_time).total_seconds()), time.size, delta=1)

    def test_giving_extra_files(self):
        start_time = datetime(2017, 2, 12, 15, 30)
        end_time = datetime(2017, 2, 12, 16)
        self.config.dims["report_number"].update({
            "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
            "max": end_time,
        })
        agg_list = generate_aggregation_list(self.config, self.files)
        self.assertEqual(len(agg_list), 30)
        evaluate_aggregation_list(self.config, agg_list, self.file)
        with nc.Dataset(self.file) as nc_out:
            time = nc_out.variables["OB_time"][:, 0]
            out_start, out_end = nc.num2date(time[[0, -1]], nc_out.variables["OB_time"].units)
            self.assertGreaterEqual(out_start, start_time-timedelta(seconds=0.25))
            self.assertLessEqual(out_end, end_time+timedelta(seconds=0.25))
            self.assertAlmostEqual(np.mean(np.diff(time)), 1, delta=0.001)
            self.assertAlmostEqual(np.max(np.diff(time)), 1, delta=0.001)
            self.assertAlmostEqual(np.min(np.diff(time)), 1, delta=0.001)
            self.assertAlmostEqual(int((end_time - start_time).total_seconds()), time.size, delta=1)

