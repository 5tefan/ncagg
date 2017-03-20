import unittest
import tempfile
import numpy as np
import netCDF4 as nc
from aggregoes.aggregator import Aggregator
from datetime import datetime
import glob
import os


class TestGenerateAggregationList(unittest.TestCase):
    def setUp(self):
        _, self.file = tempfile.mkstemp()

    def tearDown(self):
        os.remove(self.file)

    def test_5min(self):
        pwd = os.path.dirname(__file__)
        start_time = datetime(2017, 03, 16, 15, 25)
        end_time = datetime(2017, 03, 16, 15, 30)
        files = glob.glob(os.path.join(pwd, "data", "*.nc"))
        a = Aggregator()
        aggregation_list = a.generate_aggregation_list(files, {
            "report_number": {
                "index_by": "OB_time",
                "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
                "max": end_time,
                "other_dim_indicies": {"samples_per_record": 0},
                "expected_cadence": {"report_number": 1, "number_samples_per_report": 10},
            }
        })
        # self.assertEqual(len(aggregation_list), 6)

    def test_superset_front(self):
        """Test if it correctly inserts fill node to cover a gap at the start."""
        pwd = os.path.dirname(__file__)
        start_time = datetime(2017, 03, 16, 15, 25)
        end_time = datetime(2017, 03, 16, 15, 30)
        files = glob.glob(os.path.join(pwd, "data", "*.nc"))
        a = Aggregator()
        aggregation_list = a.generate_aggregation_list(files, {
            "report_number": {
                "index_by": "OB_time",
                "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
                "max": end_time,
                "other_dim_indicies": {"samples_per_record": 0},
                "expected_cadence": {"report_number": 1, "number_samples_per_report": 10},
            }
        })
        # with the fill Node in front... this becomes 8 elements
        # self.assertEqual(len(aggregation_list), 8)

    def test_superset_back(self):
        """Test if it correctly inserts fill node to cover a gap at the start."""
        pwd = os.path.dirname(__file__)
        start_time = datetime(2017, 03, 16, 15, 25)
        end_time = datetime(2017, 03, 16, 15, 30)
        files = glob.glob(os.path.join(pwd, "data", "*.nc"))
        a = Aggregator()
        aggregation_list = a.generate_aggregation_list(files, {
            "report_number": {
                "index_by": "OB_time",
                "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
                "max": end_time,
                "other_dim_indicies": {"samples_per_record": 0},
                "expected_cadence": {"report_number": 1, "number_samples_per_report": 10},
            }
        })
        # self.assertEqual(len(aggregation_list), 7)

    def test_subset(self):
        """Test if it correctly chops out enough outside the time bounds."""
        pwd = os.path.dirname(__file__)
        start_time = datetime(2017, 03, 16, 15, 25)
        end_time = datetime(2017, 03, 16, 15, 30)
        files = glob.glob(os.path.join(pwd, "data", "*.nc"))
        a = Aggregator()
        aggregation_list = a.generate_aggregation_list(files, {
            "report_number": {
                "index_by": "OB_time",
                "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
                "max": end_time,
                "other_dim_indicies": {"samples_per_record": 0},
                "expected_cadence": {"report_number": 1, "number_samples_per_report": 10},
            }
        })
        # self.assertEqual(len(aggregation_list), 2)


class TestEvaluateAggregationList(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestEvaluateAggregationList, cls).setUpClass()
        pwd = os.path.dirname(__file__)
        cls.start_time = datetime(2017, 03, 16, 15, 27)
        cls.end_time = datetime(2017, 03, 16, 15, 28)
        cls.files = glob.glob(os.path.join(pwd, "data", "*.nc"))
        a = Aggregator()
        aggregation_list = a.generate_aggregation_list(cls.files, {
            "report_number": {
                "index_by": "OB_time",
                "min": cls.start_time,  # for convenience, will convert according to index_by units if this is datetime
                "max": cls.end_time,
                "other_dim_indicies": {"samples_per_record": 0},
                "expected_cadence": {"report_number": 1, "number_samples_per_report": 10},
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
        numeric_times = self.output.variables["OB_time"][:, 0].flatten()
        self.assertAlmostEqual(np.mean(np.diff(numeric_times)), 1, delta=0.02)
        self.assertAlmostEqual(np.min(np.diff(numeric_times)), 1, delta=0.02)
        self.assertAlmostEqual(np.max(np.diff(numeric_times)), 1, delta=0.02)

        datetimes = nc.num2date(numeric_times, self.output.variables["OB_time"].units)
        self.assertLess(abs((datetimes[0]-self.start_time).total_seconds()), 1)
        self.assertLess(abs((datetimes[-1]-self.end_time).total_seconds()), 1)


    def test_strict_time(self):
        """Make sure the time array looks ok. Evenly spaced, bounds are correct."""
        numeric_times = self.output.variables["OB_time"][:].flatten()
        self.assertAlmostEqual(np.mean(np.diff(numeric_times)), 0.1, delta=0.02)
        self.assertAlmostEqual(np.min(np.diff(numeric_times)), 0.1, delta=0.02)
        self.assertAlmostEqual(np.max(np.diff(numeric_times)), 0.1, delta=0.02)

        datetimes = nc.num2date(numeric_times, self.output.variables["OB_time"].units)
        # since we have records of size 10 and we don't want any coming in before start time
        # the start time may be up to 0.9 after the aggregation start time,
        self.assertLess(abs((datetimes[0]-self.start_time).total_seconds()), 0.91)

        # similarly for the aggregation end, we aren't chopping off in the middle of a records,
        # so even if the first one is before the end, up to 0.91 may be after.
        self.assertLess(abs((datetimes[-1]-self.end_time).total_seconds()), 0.91)
