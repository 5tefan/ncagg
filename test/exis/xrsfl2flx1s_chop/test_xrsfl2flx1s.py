import unittest
import tempfile
from aggregoes.aggregator import Aggregator
from datetime import datetime, timedelta
import glob
import os

class TestGenerateAggregationList(unittest.TestCase):
    def setUp(self):
        _, self.file = tempfile.mkstemp()

    def tearDown(self):
        os.remove(self.file)

    def test_main(self):
        pwd = os.path.dirname(__file__)
        files = glob.glob(os.path.join(pwd, "data", "*.nc"))[:2]
        a = Aggregator()
        start_time = datetime(2017, 07, 14, 00, 00)
        end_time = start_time + timedelta(days=1) - timedelta(milliseconds=1)
        aggregation_list = a.generate_aggregation_list(files, {
            "time": {
                "index_by": "time",
                "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
                "max": end_time,
                "expected_cadence": {"time": 1},
            }
        })
        self.assertEqual(len(aggregation_list), 1)


