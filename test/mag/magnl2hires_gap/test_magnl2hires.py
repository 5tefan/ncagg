import unittest
import tempfile
import numpy as np
import netCDF4 as nc
from ncagg.config import Config
from ncagg.aggregator import generate_aggregation_list, evaluate_aggregation_list
from ncagg.aggregator import FillNode
from datetime import datetime
import glob
import os


class TestGenerateAggregationList(unittest.TestCase):
    def setUp(self):
        _, self.file = tempfile.mkstemp()
        pwd = os.path.dirname(__file__)
        self.files = glob.glob(os.path.join(pwd, "data", "*.nc"))
        self.config = Config.from_nc(self.files[0])
        self.config.dims["time"].update(
            {
                "index_by": "time",
                "expected_cadence": {"time": 10},
            }
        )

    def tearDown(self):
        os.remove(self.file)

    def test_main(self):
        start_time = datetime(2017, 4, 14, 19, 23)
        end_time = datetime(2017, 4, 14, 20, 30)
        self.config.dims["time"].update(
            {
                "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
                "max": end_time,
            }
        )
        agg_list = generate_aggregation_list(self.config, self.files)
        self.assertEqual(len(agg_list), 8)

    def test_superset_front(self):
        """Test if it correctly inserts fill node to cover a gap at the start."""
        start_time = datetime(2017, 4, 14, 19, 20)
        end_time = datetime(2017, 4, 14, 20, 30)
        self.config.dims["time"].update(
            {
                "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
                "max": end_time,
            }
        )
        agg_list = generate_aggregation_list(self.config, self.files)
        self.assertEqual(len(agg_list), 8)

    def test_superset_back(self):
        """Test if it correctly inserts fill node to cover a gap at the end."""
        start_time = datetime(2017, 4, 14, 19, 23)
        end_time = datetime(2017, 4, 14, 20, 35)
        self.config.dims["time"].update(
            {
                "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
                "max": end_time,
            }
        )
        agg_list = generate_aggregation_list(self.config, self.files)
        self.assertTrue(isinstance(agg_list[-1], FillNode))

    def test_subset(self):
        """Test if it correctly chops out enough outside the time bounds."""
        start_time = datetime(2017, 4, 14, 19, 26)
        end_time = datetime(2017, 4, 14, 20, 28)
        self.config.dims["time"].update(
            {
                "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
                "max": end_time,
            }
        )
        agg_list = generate_aggregation_list(self.config, self.files)
        self.assertEqual(len(agg_list), 3)


class TestEvaluateAggregationList(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestEvaluateAggregationList, cls).setUpClass()
        pwd = os.path.dirname(__file__)
        cls.start_time = datetime(2017, 4, 14, 19, 23)
        cls.end_time = datetime(2017, 4, 14, 20, 30)
        cls.files = glob.glob(os.path.join(pwd, "data", "*.nc"))
        cls.files = glob.glob(os.path.join(pwd, "data", "*.nc"))
        cls.config = Config.from_nc(cls.files[0])
        cls.config.dims["time"].update(
            {
                "index_by": "time",
                "min": cls.start_time,  # for convenience, will convert according to index_by units if this is datetime
                "max": cls.end_time,
                "expected_cadence": {"time": 10},
            }
        )
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
        numeric_times = self.output.variables["time"][:]

        self.assertGreater(numeric_times.size, 0)

        self.assertAlmostEqual(np.mean(np.diff(numeric_times)), 0.1, delta=0.01)
        self.assertAlmostEqual(np.min(np.diff(numeric_times)), 0.1, delta=0.01)
        self.assertAlmostEqual(np.max(np.diff(numeric_times)), 0.1, delta=0.01)

        datetimes = nc.num2date(numeric_times, self.output.variables["time"].units)

        self.assertGreaterEqual(datetimes[0], self.start_time)
        self.assertLessEqual(datetimes[-1], self.end_time)

        self.assertLess(abs((datetimes[0] - self.start_time).total_seconds()), 0.1)
        # verified, this difference should be ~0.000825, first timestamp after
        # start_time is datetime(2017, 4, 14, 19, 23, 0, 825)
        self.assertTrue(0.0 <= (datetimes[0] - self.start_time).total_seconds() < 0.1)

        # the end timestamp should be at most 1 cadence before the end_time
        self.assertTrue(0.0 <= (self.end_time - datetimes[-1]).total_seconds() < 0.1)
