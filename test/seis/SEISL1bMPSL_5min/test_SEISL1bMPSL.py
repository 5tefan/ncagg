import unittest
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
