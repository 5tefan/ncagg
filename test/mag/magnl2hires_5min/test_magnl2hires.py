import unittest
import tempfile
import numpy as np
import netCDF4 as nc
from ncagg.config import Config
from ncagg.aggregator import generate_aggregation_list, evaluate_aggregation_list
from ncagg.aggrelist import FillNode
from datetime import datetime
import glob
import os


class TestGenerateAggregationList(unittest.TestCase):
    def setUp(self):
        _, self.file = tempfile.mkstemp()
        pwd = os.path.dirname(__file__)
        self.files = glob.glob(os.path.join(pwd, "data", "*.nc"))
        self.config = Config.from_nc(self.files[0])
        self.config.dims["time"].update({
            "index_by": "time",
            "expected_cadence": {"time": 10},
        })

    def tearDown(self):
        os.remove(self.file)

    def test_5min(self):
        # March 5, 2017. 02:10:00 through 02:15:00
        start_time = datetime(2017, 3, 5, 2, 10)
        end_time = datetime(2017, 3, 5, 2, 15)
        self.config.dims["time"].update({
            "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
            "max": end_time,
        })
        agg_list = generate_aggregation_list(self.config, self.files)
        self.assertEqual(len(agg_list), 6)

    def test_superset_front(self):
        """Test if it correctly inserts fill node to cover a gap at the start."""
        # March 5, 2017. 02:10:00 through 02:15:00
        start_time = datetime(2017, 3, 5, 2, 5)
        end_time = datetime(2017, 3, 5, 2, 15)
        self.config.dims["time"].update({
            "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
            "max": end_time,
        })
        agg_list = generate_aggregation_list(self.config, self.files)
        # with the fill Node in front... this becomes 8 elements
        self.assertEqual(len(agg_list), 8)

    def test_superset_back(self):
        """Test if it correctly inserts fill node to cover a gap at end."""
        # March 5, 2017. 02:10:00 through 02:15:00
        start_time = datetime(2017, 3, 5, 2, 10)
        end_time = datetime(2017, 3, 5, 2, 20)
        self.config.dims["time"].update({
            "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
            "max": end_time,
        })
        agg_list = generate_aggregation_list(self.config, self.files)
        self.assertTrue(isinstance(agg_list[-1], FillNode))

    def test_subset(self):
        """Test if it correctly chops out enough outside the time bounds."""
        # March 5, 2017. 02:10:00 through 02:15:00
        start_time = datetime(2017, 3, 5, 2, 12, 30)
        end_time = datetime(2017, 3, 5, 2, 13, 22)
        self.config.dims["time"].update({
            "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
            "max": end_time,
        })
        agg_list = generate_aggregation_list(self.config, self.files)
        self.assertEqual(len(agg_list), 2)


class TestEvaluateAggregationList(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestEvaluateAggregationList, cls).setUpClass()
        pwd = os.path.dirname(__file__)
        # March 5, 2017. 02:10:00 through 02:15:00
        cls.start_time = datetime(2017, 3, 5, 2, 10)
        cls.end_time = datetime(2017, 3, 5, 2, 15)
        cls.files = glob.glob(os.path.join(pwd, "data", "*.nc"))
        cls.config = Config.from_nc(cls.files[0])
        cls.config.dims["time"].update({
            "index_by": "time",
            "min": cls.start_time,  # for convenience, will convert according to index_by units if this is datetime
            "max": cls.end_time,
            "expected_cadence": {"time": 10},
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
        numeric_times = self.output.variables["time"][:]

        self.assertGreater(numeric_times.size, 0)

        self.assertAlmostEqual(np.mean(np.diff(numeric_times)), 0.1, delta=0.002)
        self.assertAlmostEqual(np.min(np.diff(numeric_times)), 0.1, delta=0.002)
        self.assertAlmostEqual(np.max(np.diff(numeric_times)), 0.1, delta=0.002)

        datetimes = nc.num2date(numeric_times, self.output.variables["time"].units)

        self.assertGreaterEqual(datetimes[0], self.start_time)
        self.assertLessEqual(datetimes[-1], self.end_time)

        self.assertLess(abs((datetimes[0] - self.start_time).total_seconds()), 0.1)
        self.assertLess(abs((datetimes[-1] - self.end_time).total_seconds()), 0.1)

