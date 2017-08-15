import unittest
import tempfile
import netCDF4 as nc
import numpy as np
from aggregoes.validate_configs import Config
from aggregoes.aggregator import generate_aggregation_list, evaluate_aggregation_list
from datetime import datetime
import glob
import os


class TestMag(unittest.TestCase):
    def setUp(self):
        _, self.file = tempfile.mkstemp()
        pwd = os.path.dirname(__file__)
        self.files = glob.glob(os.path.join(pwd, "data", "*.nc"))
        self.config = Config.from_nc(self.files[0])

    def tearDown(self):
        os.remove(self.file)

    def test_mag_instantiation(self):
        start_time = datetime(2017, 02, 12, 15)
        end_time = datetime(2017, 02, 12, 15, 02)
        self.config.dims["report_number"].update({
            "index_by": "OB_time",
            "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
            "max": end_time,
            "other_dim_indicies": {"samples_per_record": 0},
            "expected_cadence": {"report_number": 1, "number_samples_per_report": 10},
        })
        agg_list = generate_aggregation_list(self.config, self.files)
        evaluate_aggregation_list(self.config, agg_list, self.file)
        with nc.Dataset(self.file) as nc_out:
            time = nc_out.variables["OB_time"][:, 0]
            out_start, out_end = nc.num2date(time[[0, -1]], nc_out.variables["OB_time"].units)
            self.assertGreaterEqual(out_start, start_time)
            self.assertLessEqual(out_end, end_time)
            self.assertAlmostEqual(np.mean(np.diff(time)), 1, delta=0.001)
            self.assertAlmostEqual(np.max(np.diff(time)), 1, delta=0.001)
            self.assertAlmostEqual(np.min(np.diff(time)), 1, delta=0.001)
            self.assertAlmostEqual(int((end_time - start_time).total_seconds()), time.size, delta=1)

