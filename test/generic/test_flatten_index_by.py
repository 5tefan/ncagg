import numpy as np
import unittest


class TestFlattenIndexBy(unittest.TestCase):
    @unittest.expectedFailure
    def test_first(self):
        a = np.array(["g16", "g17", "g18"])
        b = np.array(["g17", "g19"])

        # existing piece
        overlap_a = np.where(np.in1d(a, b))
        overlap_b = np.where(np.in1d(b, a))
        self.assertTrue(a[overlap_a] == b[overlap_b])

        new = np.where(~np.in1d(b, a))
        np.linspace(len(a), len(a) + len(new), 1, dtype=int)

        np.array(["g16", "g17", "g18", "g19"])
        self.assertTrue(False)  # this is not implemented....
