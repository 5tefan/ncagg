from aggregoes.ncei.ncei_l2_cli import reduce_version
import unittest


class TestReduceVersion(unittest.TestCase):
    """Check that versioning for l2+ works as expected."""
    def test_nominal_all_same(self):
        versions = ["1_0_0"] * 4
        self.assertEqual(reduce_version(versions), "1_0_0")

    def test_one_different_major(self):
        versions = ["1_0_0"] * 4 + ["2_0_0"]
        self.assertEqual(reduce_version(versions), "1-2_0_0")

    def test_three_different_major(self):
        versions = ["1_0_0"] * 4 + ["2_0_0"] * 2 + ["3_0_0"] * 2
        self.assertEqual(reduce_version(versions), "1-2-3_0_0")

    def test_one_different_major_and_patch(self):
        versions = ["1_0_0"] * 4 + ["2_0_0"] * 2 + ["1_0_1"] * 2
        self.assertEqual(reduce_version(versions), "1-2_0_x")

    def test_one_different_patch(self):
        versions = ["1_0_0"] * 4 + ["1_0_1"]
        self.assertEqual(reduce_version(versions), "1_0_0-1")

    def test_one_different_minor_and_path(self):
        versions = ["1_0_0"] * 4 + ["1_0_1"] + ["2_0_0"]
        self.assertEqual(reduce_version(versions), "1-2_0_x")
