import unittest
from aggregoes.aggregator import AggreList
from aggregoes.aggregator import FillNode


class TestAggreList(unittest.TestCase):

    def test_initialization(self):
        a = AggreList()

    def test_append_one_element(self):
        """Make sure the AggreList can append an item."""
        a = AggreList()
        a.append(FillNode())
        self.assertEqual(len(a), 1)

    def test_append_several_elements(self):
        """Make sure the AggreList can append several items."""
        a = AggreList()
        a.append(FillNode())
        a.append(FillNode())
        a.append(FillNode())
        self.assertEqual(len(a), 3)

    def test_append_non_aggrenode_type(self):
        """AggreList should not append a non AggreNode type object."""
        a = AggreList()
        a.append("hello")
        self.assertEqual(len(a), 0)

    def test_append_and_remove(self):
        """Can we remove items from the AggreList?"""
        a = AggreList()
        self.assertEqual(len(a), 0)
        b = FillNode()
        a.append(b)
        self.assertEqual(len(a), 1)
        a.remove(b)
        self.assertEqual(len(a), 0)
