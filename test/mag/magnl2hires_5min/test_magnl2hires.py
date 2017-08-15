import unittest
import tempfile
import numpy as np
import netCDF4 as nc
from aggregoes.validate_configs import Config
from aggregoes.aggregator import generate_aggregation_list, evaluate_aggregation_list
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
        start_time = datetime(2017, 03, 05, 02, 10)
        end_time = datetime(2017, 03, 05, 02, 15)
        self.config.dims["time"].update({
            "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
            "max": end_time,
        })
        agg_list = generate_aggregation_list(self.config, self.files)
        self.assertEqual(len(agg_list), 6)

    def test_superset_front(self):
        """Test if it correctly inserts fill node to cover a gap at the start."""
        # March 5, 2017. 02:10:00 through 02:15:00
        start_time = datetime(2017, 03, 05, 02, 05)
        end_time = datetime(2017, 03, 05, 02, 15)
        self.config.dims["time"].update({
            "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
            "max": end_time,
        })
        agg_list = generate_aggregation_list(self.config, self.files)
        # with the fill Node in front... this becomes 8 elements
        self.assertEqual(len(agg_list), 8)

    def test_superset_back(self):
        """Test if it correctly inserts fill node to cover a gap at the start."""
        # March 5, 2017. 02:10:00 through 02:15:00
        start_time = datetime(2017, 03, 05, 02, 10)
        end_time = datetime(2017, 03, 05, 02, 20)
        self.config.dims["time"].update({
            "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
            "max": end_time,
        })
        agg_list = generate_aggregation_list(self.config, self.files)
        # with the fill Node in front... this becomes 8 elements
        self.assertEqual(len(agg_list), 7)

    def test_subset(self):
        """Test if it correctly chops out enough outside the time bounds."""
        # March 5, 2017. 02:10:00 through 02:15:00
        start_time = datetime(2017, 03, 05, 02, 12, 30)
        end_time = datetime(2017, 03, 05, 02, 13, 22)
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
        cls.start_time = datetime(2017, 03, 05, 02, 10)
        cls.end_time = datetime(2017, 03, 05, 02, 15)
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
        self.assertAlmostEqual(np.mean(np.diff(numeric_times)), 0.1, delta=0.002)
        self.assertAlmostEqual(np.min(np.diff(numeric_times)), 0.1, delta=0.002)
        self.assertAlmostEqual(np.max(np.diff(numeric_times)), 0.1, delta=0.002)

        datetimes = nc.num2date(numeric_times, self.output.variables["time"].units)
        self.assertLess(abs((datetimes[0]-self.start_time).total_seconds()), 0.1)
        self.assertGreaterEqual(datetimes[0], self.start_time)
        self.assertLess(abs((datetimes[-1]-self.end_time).total_seconds()), 0.1)
        self.assertLessEqual(datetimes[-1], self.end_time)

    def test_data(self):
        """Make sure there is some data in the file."""
        self.assertEqual(self.output.variables["b_gse"].shape, (3000, 3))
        b_gse = self.output.variables["b_gse"][:]
        self.assertEqual(np.ma.count(b_gse), 3000*3)


