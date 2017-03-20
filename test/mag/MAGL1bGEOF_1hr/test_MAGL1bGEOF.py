import unittest
import tempfile
from aggregoes.aggregator import Aggregator
from datetime import datetime
import glob
import os


class TestMag(unittest.TestCase):
    def setUp(self):
        _, self.file = tempfile.mkstemp()

    def tearDown(self):
        os.remove(self.file)

    def test_mag_instantiation(self):
        pwd = os.path.dirname(__file__)
        start_time = datetime(2017, 02, 12, 15)
        end_time = datetime(2017, 02, 12, 16)
        files = glob.glob(os.path.join(pwd, "data", "*.nc"))
        a = Aggregator()
        aggregation_list = a.generate_aggregation_list(files, {
            "report_number": {
                "index_by": "OB_time",
                "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
                "max": end_time,
                "other_dim_indicies": {"samples_per_record": 0},
                "expected_cadence": {"report_number": 1, "number_samples_per_report": 10}
            }
        })
        self.assertEqual(len(aggregation_list), 60)

    def test_giving_extra_files(self):
        pwd = os.path.dirname(__file__)
        start_time = datetime(2017, 02, 12, 15, 30)
        end_time = datetime(2017, 02, 12, 16)
        files = glob.glob(os.path.join(pwd, "data", "*.nc"))
        a = Aggregator()
        aggregation_list = a.generate_aggregation_list(files, {
            "report_number": {
                "index_by": "OB_time",
                "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
                "max": end_time,
                "other_dim_indicies": {"samples_per_record": 0},
                "expected_cadence": {"report_number": 1, "number_samples_per_report": 10}
            }
        })
        self.assertEqual(len(aggregation_list), 30)
