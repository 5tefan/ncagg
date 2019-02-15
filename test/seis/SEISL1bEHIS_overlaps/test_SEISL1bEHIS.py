import unittest
import netCDF4 as nc
import numpy as np
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
        evaluate_aggregation_list(cls.config, agg_list, cls.filename)
        cls.output = nc.Dataset(cls.filename, "r")

    @classmethod
    def tearDownClass(cls):
        super(TestEvaluateAggregationList, cls).tearDownClass()
        os.remove(cls.filename)

    def test_time(self):
        """Make sure the time array looks ok. Evenly spaced, bounds are correct."""
        numeric_times = self.output.variables["ELF_StartStopTime"][:]

        self.assertAlmostEqual(np.mean(np.diff(numeric_times)), 299, delta=0.01)
        self.assertAlmostEqual(np.min(np.diff(numeric_times)), 299, delta=0.01)
        self.assertAlmostEqual(np.max(np.diff(numeric_times)), 299, delta=0.01)

        # Previously, when we were flooring the FillNode size, there would be no
        # fill node inserted here and we would have a gap of size 540. The mean
        # diff was 326ish. I've decided that it's better to turn the 540 step into
        # a 300 and a 240 second step. The "evidence" I'm using to say this is better is
        # that this bring the mean time diff to 294, which is much closer to
        # the nominal 300 than the previous 326 was.
        self.assertAlmostEqual(np.mean(np.diff(numeric_times[:, 0])), 294, delta=1)
        self.assertAlmostEqual(np.min(np.diff(numeric_times[:, 0])), 240, delta=0.01)
        self.assertAlmostEqual(np.max(np.diff(numeric_times[:, 0])), 300, delta=0.01)

        datetimes = nc.num2date(numeric_times, self.output.variables["ELF_StartStopTime"].units)

        self.assertGreaterEqual(datetimes[0, 0], self.start_time)
        self.assertLessEqual(datetimes[-1, 0], self.end_time)


