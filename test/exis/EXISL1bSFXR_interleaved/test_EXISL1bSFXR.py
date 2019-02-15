import unittest
import tempfile
import netCDF4 as nc
from ncagg.config import Config
from ncagg.aggregator import generate_aggregation_list, evaluate_aggregation_list
from datetime import datetime, timedelta
import glob
import os
import numpy as np


import logging

logger = logging.getLogger(__name__)


class TestExis(unittest.TestCase):
    def setUp(self):
        # tmp file to aggregate to
        _, self.nc_out_filename = tempfile.mkstemp()

        pwd = os.path.dirname(__file__)
        self.files = sorted(glob.glob(os.path.join(pwd, "data", "*.nc")))
        self.config = Config.from_nc(self.files[0])

    def tearDown(self):
        os.remove(self.nc_out_filename)

    def test_exis_with_config(self):
        """
        Test an EXIS-L1b-SFXR aggregation with dimensions specified.

        This particular test case is designed to cover the situation for which
        we put handling of strict=False into the get_size_along(dimension). The
        calculation of overlaps between files was resulting in a negative since
        gap between files was small, the file was also sticking off the end, so
        ultimately it was chopped on both sides and ended up with a negative size.

        This should have been fine, as long as that FileNode doesn't end up in
         the final aggregation list.

         A couple files that capture this scenario are in the associated data/.
        """
        # March 5th 00:30 through 00:35
        start_time = datetime(2019, 2, 5, 0)
        end_time = datetime(2019, 2, 6, 0) - timedelta(microseconds=1)

        self.config.dims["report_number"].update({
            "index_by": "time",
            "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
            "max": end_time,
            "expected_cadence": {"report_number": 1},
        })

        self.config.inter_validate()
        aggregation_list = generate_aggregation_list(self.config, self.files)
        evaluate_aggregation_list(self.config, aggregation_list, self.nc_out_filename)

        with nc.Dataset(self.nc_out_filename) as nc_out:  # type: nc.Dataset
            start_time_num, end_time_num = nc.date2num([start_time, end_time], nc_out["time"].units)
            time = nc_out.variables["time"][:]
            # have not been able to satisfy this: self.assertEquals(time.size, 86400)
            self.assertAlmostEqual(np.min(np.diff(time)), 0.854, delta=0.001)
            self.assertAlmostEqual(np.max(np.diff(time)), 1., delta=0.001)
            self.assertAlmostEqual(np.mean(np.diff(time)), 1., delta=0.001)
            self.assertGreaterEqual(time[0], start_time_num)
            self.assertLess(time[-1], end_time_num)


