import unittest
from datetime import datetime
import tempfile
import netCDF4 as nc
import os

from ncagg.attributes import StratFirst, StratLast,StratUniqueList, StratIntSum, StratFloatSum, StratAssertConst
from ncagg.attributes import StratDateCreated, StratStatic, StratTimeCoverageStart, StratTimeCoverageEnd

from ncagg.attributes import datetime_format

test_dir = os.path.dirname(os.path.realpath(__file__))
test_input_file = os.path.join(test_dir, "data/OR_MAG-L1b-GEOF_G16_s20170431500000_e20170431500599_c20170431501005.nc")


class TestAttributeStrategies(unittest.TestCase):
    def setUp(self):
        # having two seconds is on purpose to test the unique list
        self.mock_str_attributes = ["first", "second", "second", "third"]
        self.mock_int_attributes = [1, 2, 2, 3]
        self.mock_float_attributes = [1.1, 2.2, 2.3, 3.3]
        self.test_nc = nc.Dataset(test_input_file)

    def test_strat_first_gives_first(self):
        process, finalize = StratFirst.setup_handler()
        for attr in self.mock_str_attributes:
            process(attr)
        self.assertEqual(finalize(self.test_nc), "first")

    def test_strat_last_gives_last(self):
        process, finalize = StratLast.setup_handler()
        for attr in self.mock_str_attributes:
            process(attr)
        self.assertEqual(finalize(self.test_nc), "third")

    def test_strat_unique_list(self):
        process, finalize = StratUniqueList.setup_handler()
        for attr in self.mock_str_attributes:
            process(attr)
        self.assertEqual(finalize(self.test_nc), "first, second, third")

    def test_int_sum(self):
        process, finalize = StratIntSum.setup_handler()
        for attr in self.mock_int_attributes:
            process(attr)
        self.assertEqual(finalize(self.test_nc), sum(self.mock_int_attributes))

    def test_float_sum(self):
        process, finalize = StratFloatSum.setup_handler()
        for attr in self.mock_float_attributes:
            process(attr)
        self.assertEqual(finalize(self.test_nc), sum(self.mock_float_attributes))

    def test_assert_const_fails_nonconst(self):
        process, finalize = StratAssertConst.setup_handler()
        with self.assertRaises(AssertionError):
            for attr in self.mock_str_attributes:
                process(attr)
        self.assertEqual(finalize(self.test_nc), "first")

    def test_assert_const_pass_consts(self):
        process, finalize = StratAssertConst.setup_handler()
        for attr in ["const", "const", "const"]:
            process(attr)
        self.assertEqual(finalize(self.test_nc), "const")

    def test_date_created_close(self):
        process, finalize = StratDateCreated.setup_handler()
        for attr in self.mock_str_attributes:
            process(attr)
        # since both of these date time strings may not be created exactly at the same time,
        # only check to make sure they are mostly the same, it's ok if there is some difference
        # in the last milliseconds piece.
        self.assertEqual(finalize(self.test_nc)[:-3], datetime_format(datetime.now())[:-3])

