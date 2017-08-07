import unittest
from aggregoes.validate_configs import ConfigDict

class SampleConfig(ConfigDict):
    def get_item_schema(self):
        default = super(SampleConfig, SampleConfig).get_item_schema(self)
        default.update({"something": {"type": "float"}})
        return default

class TestConfigDict(unittest.TestCase):

    def test_init_valid(self):
        a = SampleConfig([
            {"name": "a", "something": 1},
            {"name": "b", "something": 2},
            {"name": "z", "something": 1}
        ])
        for i, k in enumerate(a.keys()):
            # check ordering
            self.assertEqual(["a", "b", "z"][i], k)

    def test_init_invalid(self):
        with self.assertRaises(ValueError):
            a = SampleConfig([
                {"name": "a", "something": 1},
                {"name": "b", "something": "noooo"},
                {"name": "z", "something": 1}
            ])

    def test_update(self):
        a = SampleConfig([
            {"name": "a", "something": 1},
            {"name": "z", "something": 1}
        ])
        a.update({"b": {"something": 2}})
        self.assertEqual(len(a), 3)
        with self.assertRaises(ValueError):
            a.update({"b": {"something": "noooo"}})

