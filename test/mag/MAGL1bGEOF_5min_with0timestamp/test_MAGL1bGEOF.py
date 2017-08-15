import unittest
import tempfile
import netCDF4 as nc
import numpy as np
from ncagg.config import Config
from ncagg.aggregator import generate_aggregation_list, evaluate_aggregation_list
from datetime import datetime, timedelta
import glob
import os

import logging
logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)


class TestGenerateAggregationList(unittest.TestCase):
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

    def test_5min(self):
        start_time = datetime(2017, 03, 16, 15, 25)
        end_time = datetime(2017, 03, 16, 15, 30)
        self.config.dims["report_number"].update({
            "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
            "max": end_time,
        })
        agg_list = generate_aggregation_list(self.config, self.files)
        self.assertEqual(len(agg_list), 6)

    def test_superset_front(self):
        start_time = datetime(2017, 03, 16, 15, 15)
        end_time = datetime(2017, 03, 16, 15, 30)
        self.config.dims["report_number"].update({
            "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
            "max": end_time,
        })
        agg_list = generate_aggregation_list(self.config, self.files)
        # with the fill Node in front... this becomes 8 elements
        self.assertEqual(len(agg_list), 8)

    def test_superset_back(self):
        """Test if it correctly inserts fill node to cover a gap at the start."""
        start_time = datetime(2017, 03, 16, 15, 25)
        end_time = datetime(2017, 03, 16, 15, 35)
        self.config.dims["report_number"].update({
            "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
            "max": end_time,
        })
        agg_list = generate_aggregation_list(self.config, self.files)
        self.assertEqual(len(agg_list), 7)

    def test_subset(self):
        """Test if it correctly chops out enough outside the time bounds."""
        start_time = datetime(2017, 03, 16, 15, 25)
        end_time = datetime(2017, 03, 16, 15, 27)
        self.config.dims["report_number"].update({
            "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
            "max": end_time,
        })
        agg_list = generate_aggregation_list(self.config, self.files)
        self.assertEqual(len(agg_list), 3)


class TestEvaluateAggregationList(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestEvaluateAggregationList, cls).setUpClass()
        pwd = os.path.dirname(__file__)
        cls.start_time = datetime(2017, 03, 16, 15, 27)
        cls.end_time = datetime(2017, 03, 16, 15, 28)
        cls.files = glob.glob(os.path.join(pwd, "data", "*.nc"))

        cls.config = Config.from_nc(cls.files[0])
        cls.config.dims["report_number"].update({
            "index_by": "OB_time",
            "min": cls.start_time,  # for convenience, will convert according to index_by units if this is datetime
            "max": cls.end_time,
            "other_dim_indicies": {"samples_per_record": 0},
            "expected_cadence": {"report_number": 1, "number_samples_per_report": 10},
        })
        _, cls.filename = tempfile.mkstemp()
        agg_list = generate_aggregation_list(cls.config, cls.files)
        logger.info(agg_list)
        evaluate_aggregation_list(cls.config, agg_list, cls.filename)
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
        np.set_printoptions(threshold=np.inf)
        # logger.debug(numeric_times)
        # logger.debug(np.diff(numeric_times)[9:].reshape(-1, 10))
        self.assertAlmostEqual(np.mean(np.diff(numeric_times)), 0.1, delta=0.002)
        self.assertAlmostEqual(np.min(np.diff(numeric_times)), 0.1, delta=0.002)
        self.assertAlmostEqual(np.max(np.diff(numeric_times)), 0.1, delta=0.002)

        datetimes = nc.num2date(numeric_times, self.output.variables["OB_time"].units)
        # since we have records of size 10 and we don't want any coming in before start time
        # the start time may be up to 0.9 after the aggregation start time,
        self.assertLess(abs((datetimes[0]-self.start_time).total_seconds()), 0.91)

        # similarly for the aggregation end, we aren't chopping off in the middle of a records,
        # so even if the first one is before the end, up to 0.91 may be after.
        self.assertLess(abs((datetimes[-10]-self.end_time).total_seconds()), 0.91)
