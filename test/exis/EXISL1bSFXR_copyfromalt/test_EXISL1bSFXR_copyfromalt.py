import unittest
import tempfile
import netCDF4 as nc
from ncagg.config import Config
from ncagg.aggregator import generate_aggregation_list, evaluate_aggregation_list
from datetime import datetime
import glob
import os
import numpy as np
import json


import logging

logger = logging.getLogger(__name__)


class TestExisCopyFromAlt(unittest.TestCase):
    def setUp(self):
        # tmp file to aggregate to
        _, self.nc_out_filename = tempfile.mkstemp()

        pwd = os.path.dirname(__file__)
        self.files = sorted(glob.glob(os.path.join(pwd, "data", "*.nc")))
        with open(os.path.join(pwd, "copy_from_alt_config.json")) as config_in:
            self.config = Config.from_dict(json.load(config_in))

    def tearDown(self):
        os.remove(self.nc_out_filename)

    def test_exis_with_config(self):
        """
        Test an EXIS-L1b-SFXR aggregation with copy_from_alt configured.

        On May 23, 2023, EXIS-L1b-SFXR granules changed from having SPP_to_Sun_roll_angle
        to having SPP_roll_angle. The variable was renamed, but we'd like to make a consistent
        record.
        """
        self.config.inter_validate()
        aggregation_list = generate_aggregation_list(self.config, self.files)
        evaluate_aggregation_list(self.config, aggregation_list, self.nc_out_filename)
        with nc.Dataset(self.nc_out_filename) as nc_out:  # type: nc.Dataset
            time = nc_out.variables["time"][:]
            self.assertAlmostEqual(np.min(np.diff(time)), 1.0, delta=0.001)
            self.assertAlmostEqual(np.max(np.diff(time)), 1.0, delta=0.001)
            self.assertAlmostEqual(np.mean(np.diff(time)), 1.0, delta=0.001)

            data = np.ma.filled(nc_out.variables["SPP_roll_angle"][:], np.nan)
            self.assertFalse(np.any(np.isnan(data)))
            self.assertEqual(len(data), 2)  # one record in each file

