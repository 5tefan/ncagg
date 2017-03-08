from aggregoes.aggregator import InputFileNode
from netCDF4 import num2date
from datetime import datetime
import unittest
import os

test_dir = os.path.dirname(os.path.realpath(__file__))
test_input_file = os.path.join(test_dir, "data/OR_MAG-L1b-GEOF_G16_s20170431500000_e20170431500599_c20170431501005.nc")


@unittest.skipIf(not os.path.exists(test_input_file), "Missing test input data file.")
class TestInputFileNode(unittest.TestCase):

    def test_instantiation(self):
        """Test that the most basic instantiation works."""
        InputFileNode(test_input_file)

    def test_instantiation_with_unlim_dim_primary_spec(self):
        """Test that a valid dim_configs is accepted."""
        InputFileNode(test_input_file, {
            "report_number": {
                "index_by": "OB_time",
                "other_dim_indicies": {
                    "number_samples_per_report": 0
                }
            }
        })

    def test_get_start_time(self):
            a = InputFileNode(test_input_file, {
                "report_number": {
                    "index_by": "OB_time",
                    "other_dim_indicies": {
                        "number_samples_per_report": 0
                    }
                }
            })
            start_found = num2date([a.get_index_of_unlim(0)], "seconds since 2000-01-01 12:00:00")[0]
            self.assertEqual(start_found, datetime(2017, 2, 12, 14, 59, 59, 900905))

    def test_get_end_time(self):
            a = InputFileNode(test_input_file, {
                "report_number": {
                    "index_by": "OB_time",
                    "other_dim_indicies": {
                        "number_samples_per_report": 0
                    }
                }
            })
            end_found = num2date([a.get_index_of_unlim(-1)], "seconds since 2000-01-01 12:00:00")[0]
            self.assertEqual(end_found, datetime(2017, 2, 12, 15, 0, 57, 900859))
