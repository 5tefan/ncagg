import unittest
import numpy as np
import netCDF4 as nc
import tempfile
from ncagg.config import Config
from ncagg.aggregator import generate_aggregation_list, evaluate_aggregation_list
from datetime import datetime
import glob
import os


class TestEvaluateAggregationList(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestEvaluateAggregationList, cls).setUpClass()
        pwd = os.path.dirname(__file__)
        # March 5, 2017. 02:10:00 through 02:15:00
        cls.start_time = datetime(2017, 1, 18, 0, 37)
        cls.end_time = datetime(2017, 1, 18, 0, 38)
        cls.files = glob.glob(os.path.join(pwd, "data", "*.nc"))
        cls.config = Config.from_nc(cls.files[0])
        cls.config.dims["report_number"].update({
            "index_by": "L1a_SciData_TimeStamp",
            "min": cls.start_time,  # for convenience, will convert according to index_by units if this is datetime
            "max": cls.end_time,
            "expected_cadence": {"report_number": 1},
        })
        _, cls.filename = tempfile.mkstemp()
        agg_list = generate_aggregation_list(cls.config, cls.files)
        evaluate_aggregation_list(cls.config, agg_list, cls.filename)
        cls.output = nc.Dataset(cls.filename, "r")

    @classmethod
    def tearDownClass(cls):
        super(TestEvaluateAggregationList, cls).tearDownClass()
        os.remove(cls.filename)

    def test_time(self):
        """Make sure the time array looks ok. Evenly spaced, bounds are correct."""
        numeric_times = self.output.variables["L1a_SciData_TimeStamp"][:]
        # timestamps on SEIS seem pretty well behaved, these are small delta's but
        # the timestamps are almost absolutely regular
        self.assertAlmostEqual(np.mean(np.diff(numeric_times)), 1, delta=0.001)
        self.assertAlmostEqual(np.min(np.diff(numeric_times)), 1, delta=0.001)
        self.assertAlmostEqual(np.max(np.diff(numeric_times)), 1, delta=0.001)

        datetimes = nc.num2date(numeric_times, self.output.variables["L1a_SciData_TimeStamp"].units)
        self.assertLessEqual(abs((datetimes[0]-self.start_time).total_seconds()), 1)
        self.assertLessEqual(abs((datetimes[-1]-self.end_time).total_seconds()), 1)

