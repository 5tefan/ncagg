import unittest
import netCDF4 as nc
import numpy as np
import tempfile
from aggregoes.aggregator import Aggregator
from datetime import datetime
import glob
import os
import json


class TestGenerateAggregationList(unittest.TestCase):
    def setUp(self):
        _, self.file = tempfile.mkstemp()

    def tearDown(self):
        os.remove(self.file)

    def test_with_config(self):
        pwd = os.path.dirname(__file__)
        start_time = datetime(2017, 06, 8, 16, 45)
        end_time = datetime(2017, 06, 8, 16, 50)
        files = glob.glob(os.path.join(pwd, "data", "*.nc"))

        with open(os.path.join(pwd, "seis-l1b-sgps-east.json")) as product_config_file:
            product_config = json.load(product_config_file)

        a = Aggregator(product_config)
        aggregation_list = a.generate_aggregation_list(files, {
            "report_number": {
                "index_by": "L1a_SciData_TimeStamp",
                "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
                "max": end_time,
                "expected_cadence": {"report_number": 1, "sensor_unit": 0},
            }
        })
        self.assertEqual(len(aggregation_list), 6)


class TestEvaluateAggregationList(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestEvaluateAggregationList, cls).setUpClass()
        pwd = os.path.dirname(__file__)
        cls.start_time = datetime(2017, 06, 8, 16, 45)
        cls.end_time = datetime(2017, 06, 8, 16, 50)
        cls.files = glob.glob(os.path.join(pwd, "data", "*.nc"))
        with open(os.path.join(pwd, "seis-l1b-sgps-east.json")) as product_config_file:
            product_config = json.load(product_config_file)

        a = Aggregator(product_config)
        aggregation_list = a.generate_aggregation_list(cls.files, {
            "report_number": {
                "index_by": "L1a_SciData_TimeStamp",
                "min": cls.start_time,  # for convenience, will convert according to index_by units if this is datetime
                "max": cls.end_time,
                "expected_cadence": {"report_number": 1, "sensor_unit": 0},
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
        self.assertAlmostEqual(np.mean(np.diff(numeric_times)), 1, delta=0.01)
        self.assertAlmostEqual(np.min(np.diff(numeric_times)), 1, delta=0.01)
        self.assertAlmostEqual(np.max(np.diff(numeric_times)), 1, delta=0.01)

        datetimes = nc.num2date(numeric_times, self.output.variables["L1a_SciData_TimeStamp"].units)
        self.assertLess(abs((datetimes[0]-self.start_time).total_seconds()), 0.1)
        self.assertLess(abs((datetimes[-1]-self.end_time).total_seconds()), 0.1)


