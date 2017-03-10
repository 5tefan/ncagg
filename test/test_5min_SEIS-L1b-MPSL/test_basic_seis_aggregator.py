import unittest
import tempfile
from aggregoes.aggregator import Aggregator
from datetime import datetime
import glob
import os


class TestExis(unittest.TestCase):
    def setUp(self):
        _, self.file = tempfile.mkstemp()

    def tearDown(self):
        # os.remove(self.file)
        print self.file

    # def test_exis_instantiation(self):
    #     """Create just the most basic aggregation list for SEIS."""
    #     pwd = os.path.dirname(__file__)
    #     files = glob.glob(os.path.join(pwd, "data", "*.nc"))[:]
    #     a = Aggregator()
    #     aggregation_list = a.generate_aggregation_list(files)
    #     a.evaluate_aggregation_list(aggregation_list, self.file)

    def test_exis_with_config(self):
        """Test an EXIS-L1b-SFXR aggregation with dimensions specified."""
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
        print aggregation_list
        a.evaluate_aggregation_list(aggregation_list, self.file)
