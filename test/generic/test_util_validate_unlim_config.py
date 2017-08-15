import os
import unittest

from ncagg.config import Config

test_dir = os.path.dirname(os.path.realpath(__file__))
test_input_file = os.path.join(test_dir, "data/OR_MAG-L1b-GEOF_G16_s20170431500000_e20170431500599_c20170431501005.nc")


@unittest.skipIf(not os.path.exists(test_input_file), "Missing test input data file.")
class TestInputFileNode(unittest.TestCase):

    def setUp(self):
        self.config = Config.from_nc(test_input_file)

    def test_plain_valid_config(self):
        """Test that a valid dim_configs is accepted."""
        self.config.dims["report_number"].update({
            "index_by": "OB_time",
            "other_dim_indicies": {
                "number_samples_per_report": 0
            }
        })

    def test_with_invalid_unlim_dim_fails(self):
        """Test that an exception is raised when an invalid dimension is used."""
        with self.assertRaises(KeyError):
            self.config.dims["not existing unlim dim"].update({
                "index_by": "OB_time",
                "other_dim_indicies": {
                    "number_samples_per_report": 0
                }
            })

    def test_with_invalid_index_by(self):
        """Test that an excpetion is raised when an invalid index_by value is given."""
        self.config.dims["report_number"].update({
            "index_by": "not existing variable",
            "other_dim_indicies": {
                "number_samples_per_report": 0
            }
        })
        with self.assertRaises(ValueError):
            self.config.inter_validate()

    def test_with_out_of_range_other_dim(self):
        """Test that an exception is raised if an other_dim_indicies value is out of possible range."""
        self.config.dims["report_number"].update({
            "index_by": "not existing variable",
            "other_dim_indicies": {
                "number_samples_per_report": 12
            }
        })
        with self.assertRaises(ValueError):
            self.config.inter_validate()

