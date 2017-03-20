import unittest
import numpy as np
import netCDF4 as nc
import tempfile
from aggregoes.aggregator import Aggregator
from datetime import datetime
import glob
import os


class TestGenerateAggregationList(unittest.TestCase):
    def setUp(self):
        _, self.file = tempfile.mkstemp()

    def tearDown(self):
        os.remove(self.file)

    def test_with_config(self):
        pwd = os.path.dirname(__file__)
        # March 5th 00:30 through 00:35
        start_time = datetime(2017, 03, 04, 00, 12, 35)
        end_time = datetime(2017, 03, 04, 00, 14, 22)
        files = glob.glob(os.path.join(pwd, "data", "*.nc"))
        a = Aggregator()
        aggregation_list = a.generate_aggregation_list(files, {
            "report_number": {
                "index_by": "L1a_SciData_TimeStamp",
                "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
                "max": end_time,
                "expected_cadence": {"report_number": 1},
            }
        })

class TestEvaluateAggregationList(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestEvaluateAggregationList, cls).setUpClass()
        pwd = os.path.dirname(__file__)
        # March 5, 2017. 02:10:00 through 02:15:00
        cls.start_time = datetime(2017, 01, 18, 00, 37)
        cls.end_time = datetime(2017, 01, 18, 00, 38)
        cls.files = glob.glob(os.path.join(pwd, "data", "*.nc"))
        a = Aggregator()
        aggregation_list = a.generate_aggregation_list(cls.files, {
            "report_number": {
                "index_by": "L1a_SciData_TimeStamp",
                "expected_cadence": {"report_number": 1},
            }
        })
        _, cls.filename = tempfile.mkstemp()
        a.evaluate_aggregation_list(aggregation_list, cls.filename)
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

