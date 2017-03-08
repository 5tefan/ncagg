from aggregoes.utils.validate_configs import validate_unlimited_dim_indexed_by_time_var_map
from datetime import datetime
import unittest
import os

test_dir = os.path.dirname(os.path.realpath(__file__))
test_input_file = os.path.join(test_dir, "data/OR_MAG-L1b-GEOF_G16_s20170431500000_e20170431500599_c20170431501005.nc")


@unittest.skipIf(not os.path.exists(test_input_file), "Missing test input data file.")
class TestInputFileNode(unittest.TestCase):


    def test_plain_valid_config(self):
        """Test that a valid dim_configs is accepted."""
        validate_unlimited_dim_indexed_by_time_var_map({
            "report_number": {
                "index_by": "OB_time",
                "other_dim_indicies": {
                    "number_samples_per_report": 0
                }
            }
        }, test_input_file)

    def test_with_invalid_unlim_dim_fails(self):
        """Test that an exception is raised when an invalid dimension is used."""
        with self.assertRaises(ValueError):
            validate_unlimited_dim_indexed_by_time_var_map({
                "not existing unlim dim": {
                    "index_by": "OB_time",
                    "other_dim_indicies": {
                        "number_samples_per_report": 0
                    }
                }
            }, test_input_file)

    def test_with_invalid_index_by(self):
        """Test that an excpetion is raised when an invalid index_by value is given."""
        with self.assertRaises(ValueError):
            validate_unlimited_dim_indexed_by_time_var_map({
                "report_number": {
                    "index_by": "not existing variable",
                    "other_dim_indicies": {
                        "number_samples_per_report": 0
                    }
                }
            }, test_input_file)

    def test_for_default_other_dim_indicies(self):
        """Test that other_dim_indicies are filled to the correct default (0) if not given initially."""
        a = validate_unlimited_dim_indexed_by_time_var_map({
            "report_number": {
                "index_by": "OB_time"
            }
        }, test_input_file)
        self.assertEqual(
            a["report_number"]["other_dim_indicies"]["number_samples_per_report"],
            0
        )

    def test_with_out_of_range_other_dim(self):
        """Test that an exception is raised if an other_dim_indicies value is out of possible range."""
        with self.assertRaises(ValueError):
            validate_unlimited_dim_indexed_by_time_var_map({
                "report_number": {
                    "index_by": "not existing variable",
                    "other_dim_indicies": {
                        "number_samples_per_report": 12
                    }
                }
        }, test_input_file)

