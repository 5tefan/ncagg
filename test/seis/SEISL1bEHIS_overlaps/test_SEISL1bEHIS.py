import unittest
import netCDF4 as nc
import numpy as np
import tempfile
from ncagg.config import Config
from ncagg.aggregator import generate_aggregation_list, evaluate_aggregation_list
from datetime import datetime
import glob
import os


class TestGenerateAggregationList(unittest.TestCase):
    def setUp(self):
        _, self.file = tempfile.mkstemp()
        pwd = os.path.dirname(__file__)
        self.files = glob.glob(os.path.join(pwd, "data", "*.nc"))
        self.config = Config.from_nc(self.files[0])

    def tearDown(self):
        os.remove(self.file)

    def test_with_config(self):
        start_time = datetime(2018, 1, 17, 15, 5)
        end_time = datetime(2018, 1, 17, 15, 56)
        self.config.dims["report_number"].update({
            "index_by": "ELF_StartStopTime",
            "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
            "max": end_time,
            "expected_cadence": {"report_number": 1. / (5. * 60.), "number_of_time_bounds": 1. / ((5. * 60.)-1) },
        })
        agg_list = generate_aggregation_list(self.config, self.files)
        self.assertEqual(len(agg_list), 19)


class TestEvaluateAggregationList(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestEvaluateAggregationList, cls).setUpClass()
        pwd = os.path.dirname(__file__)


        cls.start_time = datetime(2018, 1, 17, 15, 5)
        cls.end_time = datetime(2018, 1, 17, 15, 56)
        cls.files = glob.glob(os.path.join(pwd, "data", "*.nc"))
        cls.config = Config.from_nc(cls.files[0])
        cls.config.dims["report_number"].update({
            "index_by": "ELF_StartStopTime",
            "min": cls.start_time,  # for convenience, will convert according to index_by units if this is datetime
            "max": cls.end_time,
            "expected_cadence": {"report_number": 1. / (5. * 60.), "number_of_time_bounds": 1. / ((5. * 60.)-1) },
            "size": None
        })
        _, cls.filename = tempfile.mkstemp()
        agg_list = generate_aggregation_list(cls.config, cls.files)
        print agg_list
        evaluate_aggregation_list(cls.config, agg_list, cls.filename)
        cls.output = nc.Dataset(cls.filename, "r")

    @classmethod
    def tearDownClass(cls):
        super(TestEvaluateAggregationList, cls).tearDownClass()
        print cls.filename
        #os.remove(cls.filename)

    def test_time(self):
        """Make sure the time array looks ok. Evenly spaced, bounds are correct."""
        numeric_times = self.output.variables["ELF_StartStopTime"][:, 0]
        print(numeric_times)
        print self.output.variables["ELF_StartStopTime"].shape
        self.assertAlmostEqual(np.mean(np.diff(numeric_times)), 300, delta=0.01)
        self.assertAlmostEqual(np.min(np.diff(numeric_times)), 300, delta=0.01)
        self.assertAlmostEqual(np.max(np.diff(numeric_times)), 300, delta=0.01)

        datetimes = nc.num2date(numeric_times, self.output.variables["ELF_StartStopTime"].units)
        self.assertGreater(datetimes[0], self.start_time)
        self.assertLess(datetimes[-1], self.end_time)


