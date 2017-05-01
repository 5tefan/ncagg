from aggregoes.aggrelist import InputFileNode
from netCDF4 import num2date
from datetime import datetime
import unittest
import os

test_dir = os.path.dirname(os.path.realpath(__file__))
test_input_file = os.path.join(test_dir, "data/OR_MAG-L1b-GEOF_G16_s20170431500000_e20170431500599_c20170431501005.nc")
another_input_file = os.path.join(test_dir, "data/dn_magn-l2-hires_g16_s20170414T202800Z_e20170414T202859Z_v2_0_0.nc")

@unittest.skipIf(not os.path.exists(test_input_file), "Missing test input data file.")
class TestInputFileNode(unittest.TestCase):
    def test_instantiation_basic(self):
        """Test that the most basic instantiation works."""
        InputFileNode(test_input_file)

    def test_instantiation_with_config(self):
        """Test that a valid dim_configs is accepted."""
        InputFileNode(test_input_file, {
            "report_number": {
                "index_by": "OB_time",
                "other_dim_indicies": {"number_samples_per_report": 0}
            }
        })

    def test_get_start_time(self):
        a = InputFileNode(test_input_file, {
            "report_number": {
                "index_by": "OB_time",
                "other_dim_indicies": {"number_samples_per_report": 0}
            }
        })
        start_found = num2date([a.get_first_of_index_by("report_number")], "seconds since 2000-01-01 12:00:00")[0]
        self.assertEqual(start_found, datetime(2017, 2, 12, 14, 59, 59, 900905))

    def test_get_end_time(self):
        a = InputFileNode(test_input_file, {
            "report_number": {
                "index_by": "OB_time",
                "other_dim_indicies": {"number_samples_per_report": 0}
            }
        })
        end_found = num2date([a.get_last_of_index_by("report_number")], "seconds since 2000-01-01 12:00:00")[0]
        self.assertEqual(end_found, datetime(2017, 2, 12, 15, 0, 58, 900926))

    def test_get_start_time_with_cadence(self):
        a = InputFileNode(test_input_file, {
            "report_number": {
                "index_by": "OB_time",
                "other_dim_indicies": {"number_samples_per_report": 0},
                "expected_cadence": {"report_number": 1, "number_samples_per_report": 10}
            }
        })
        start_found = num2date([a.get_first_of_index_by("report_number")], "seconds since 2000-01-01 12:00:00")[0]
        self.assertEqual(start_found, datetime(2017, 2, 12, 14, 59, 59, 900905))

    def test_get_end_time_with_cadence(self):
        a = InputFileNode(test_input_file, {
            "report_number": {
                "index_by": "OB_time",
                "other_dim_indicies": {"number_samples_per_report": 0},
                "expected_cadence": {"report_number": 1, "number_samples_per_report": 10}
            }
        })
        end_found = num2date([a.get_last_of_index_by("report_number")], "seconds since 2000-01-01 12:00:00")[0]
        self.assertEqual(end_found, datetime(2017, 2, 12, 15, 0, 58, 900926))


@unittest.skipIf(not os.path.exists(another_input_file), "Missing test input data file.")
class TestAnotherInputFileNode(unittest.TestCase):
    """Test another input file. This is a 1d time file. Even if the more complicated 2d stuff above
    works, still check that the simpler stuff works as well!"""
    def test_instantiation_basic(self):
        """Test that the most basic instantiation works."""
        InputFileNode(another_input_file)

    def test_instantiation_with_config(self):
        """Test that a valid dim_configs is accepted."""
        InputFileNode(another_input_file, {
            "time": {
                "index_by": "time"
            }
        })

    def test_get_start_time(self):
        """Test that a valid dim_configs is accepted."""
        a = InputFileNode(another_input_file, {
            "time": {
                "index_by": "time"
            }
        })
        start_found = num2date([a.get_first_of_index_by("time")], "seconds since 2000-01-01 12:00:00")[0]
        self.assertEqual(start_found, datetime(2017, 04, 14, 20, 27, 59, 900871))

    def test_get_end_time(self):
        """Test that a valid dim_configs is accepted."""
        a = InputFileNode(another_input_file, {
            "time": {
                "index_by": "time"
            }
        })
        start_found = num2date([a.get_last_of_index_by("time")], "seconds since 2000-01-01 12:00:00")[0]
        self.assertEqual(start_found, datetime(2017, 4, 14, 20, 28, 59, 800611))

