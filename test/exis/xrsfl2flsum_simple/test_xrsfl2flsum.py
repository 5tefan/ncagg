import unittest
import tempfile
from ncagg.config import Config
from ncagg.aggregator import generate_aggregation_list, evaluate_aggregation_list
import glob
import os
import netCDF4 as nc


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
        Nothing too fancy here, but just making sure that aggregating
        a variable of strings works properly.

        Previous to version 0.8.5 we had trouble with vlen datatypes.
        """
        agg_list = generate_aggregation_list(self.config, self.files)
        evaluate_aggregation_list(self.config, agg_list, self.file)

        with nc.Dataset(self.file) as nc_in:
            status = nc_in.variables["status"]
            # there should be no fill values...
            # before ncagg v0.8.5 vlen types like string incorrectly aggregated to all fill values.
            self.assertFalse(any(status[:] == status._FillValue))
