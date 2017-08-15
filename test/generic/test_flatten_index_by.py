import numpy as np
import unittest


class TestFlattenIndexBy(unittest.TestCase):
    def test_first(self):
        a = np.array(["g16", "g17", "g18"])
        b = np.array(["g17", "g19"])

        # existing piece
        overlap_a = np.where(np.in1d(a, b))
        overlap_b = np.where(np.in1d(b, a))
        self.assertTrue(a[overlap_a] == b[overlap_b])

        new = np.where(~np.in1d(b, a))
        new_i = np.linspace(len(a), len(a)+len(new), 1, dtype=np.int)
        print new_i

        target = np.array(["g16", "g17", "g18", "g19"])


