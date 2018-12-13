import unittest
import tempfile
from ncagg.config import Config
from ncagg.aggregator import generate_aggregation_list, evaluate_aggregation_list
import glob
import os

class TestAggregate(unittest.TestCase):
    def setUp(self):
        _, self.file = tempfile.mkstemp()

        pwd = os.path.dirname(__file__)
        self.files = glob.glob(os.path.join(pwd, "data", "*.nc"))
        self.config = Config.from_nc(self.files[0])

    def tearDown(self):
        os.remove(self.file)

    def test_main(self):
        """
        Just make sure this completes without error.

        Nothing too fancy here, but just making sure that aggregating
        a variable of strings works properly.

        Previously, we've had trouble with vlen datatypes.
        """
        agg_list = generate_aggregation_list(self.config, self.files)
        evaluate_aggregation_list(self.config, agg_list, self.file)

        # TODO: look at the output _FIllValue for the vlen datatype
        # make sure that's correct.


