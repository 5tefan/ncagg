import unittest
import tempfile
import netCDF4 as nc
from ncagg.config import Config
from ncagg.aggregator import generate_aggregation_list, evaluate_aggregation_list
from datetime import datetime
import glob
import os
import numpy as np


class TestExis(unittest.TestCase):
    def setUp(self):
        # tmp file to aggregate to
        _, self.nc_out_filename = tempfile.mkstemp()

        pwd = os.path.dirname(__file__)
        self.files = sorted(glob.glob(os.path.join(pwd, "data", "*.nc")))
        self.config = Config.from_nc(self.files[0])

    def tearDown(self):
        os.remove(self.nc_out_filename)

    def test_exis_instantiation(self):
        """Create just the most basic aggregation list for EXIS."""
        aggregation_list = generate_aggregation_list(self.config, self.files[:2])
        self.assertEqual(len(aggregation_list), 2)
        evaluate_aggregation_list(self.config, aggregation_list, self.nc_out_filename)
        with nc.Dataset(self.nc_out_filename) as nc_out:  # type: nc.Dataset
            self.assertGreater(list(nc_out.variables.values())[0].size, 0)

    def test_tiny_exis_with_config(self):
        """Test an EXIS-L1b-SFXR aggregation with dimensions specified."""
        # March 5th 00:30 through 00:35
        start_time = datetime(2017, 3, 5, 0, 30)
        end_time = datetime(2017, 3, 5, 0, 31)

        self.config.dims["report_number"].update({
            "index_by": "time",
            "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
            "max": end_time,
            "expected_cadence": {"report_number": 1},
        })
        self.config.inter_validate()
        aggregation_list = generate_aggregation_list(self.config, self.files[:2])
        self.assertEqual(len(aggregation_list), 2)
        evaluate_aggregation_list(self.config, aggregation_list, self.nc_out_filename)
        with nc.Dataset(self.nc_out_filename) as nc_out:  # type: nc.Dataset
            time = nc_out.variables["time"][:]
            self.assertAlmostEqual(np.min(np.diff(time)), 1., delta=0.001)
            self.assertAlmostEqual(np.max(np.diff(time)), 1., delta=0.001)
            self.assertAlmostEqual(np.mean(np.diff(time)), 1., delta=0.001)
            # print nc_out.variables["irradiance_xrsb1"][:]

    def test_exis_with_config(self):
        """Test an EXIS-L1b-SFXR aggregation with dimensions specified."""
        # March 5th 00:30 through 00:35
        start_time = datetime(2017, 3, 5, 0, 30)
        end_time = datetime(2017, 3, 5, 0, 35)

        self.config.dims["report_number"].update({
            "index_by": "time",
            "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
            "max": end_time,
            "expected_cadence": {"report_number": 1},
        })
        self.config.inter_validate()
        aggregation_list = generate_aggregation_list(self.config, self.files)
        self.assertGreater(len(aggregation_list), 2)
        evaluate_aggregation_list(self.config, aggregation_list, self.nc_out_filename)
        with nc.Dataset(self.nc_out_filename) as nc_out:  # type: nc.Dataset
            time = nc_out.variables["time"][:]
            self.assertAlmostEqual(np.min(np.diff(time)), 1., delta=0.001)
            self.assertAlmostEqual(np.max(np.diff(time)), 1., delta=0.001)
            self.assertAlmostEqual(np.mean(np.diff(time)), 1., delta=0.001)
            #print nc_out.variables["irradiance_xrsb1"][:]
