import unittest
import tempfile
import netCDF4 as nc
from ncagg.config import Config
from ncagg.aggregator import (
    generate_aggregation_list,
    evaluate_aggregation_list,
    FillNode,
)
from datetime import datetime, timedelta
import glob
import os
import numpy as np


import logging

logger = logging.getLogger(__name__)


class TestMpsh(unittest.TestCase):
    def setUp(self):
        # tmp file to aggregate to
        _, self.nc_out_filename = tempfile.mkstemp()

        pwd = os.path.dirname(__file__)
        self.files = sorted(glob.glob(os.path.join(pwd, "data", "*.nc")))
        self.config = Config.from_nc(self.files[0])

    def tearDown(self):
        os.remove(self.nc_out_filename)

    def test_mpsh_with_config(self):
        start_time = datetime(2017, 7, 20, 0, 0)
        end_time = datetime(2017, 7, 20, 0, 1) - timedelta(microseconds=1)

        self.config.dims["report_number"].update(
            {
                "index_by": "L1a_SciData_TimeStamp",
                "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
                "max": end_time,
                "expected_cadence": {"report_number": 1},
            }
        )

        self.config.inter_validate()
        aggregation_list = generate_aggregation_list(self.config, self.files)
        evaluate_aggregation_list(self.config, aggregation_list, self.nc_out_filename)
        with nc.Dataset(self.nc_out_filename) as nc_out:  # type: nc.Dataset
            start_time_num, end_time_num = nc.date2num(
                [start_time, end_time], nc_out["L1a_SciData_TimeStamp"].units
            )
            time = nc_out.variables["L1a_SciData_TimeStamp"][:]
            # test spacing
            self.assertAlmostEqual(np.min(np.diff(time)), 1.0, delta=0.001)
            self.assertAlmostEqual(np.max(np.diff(time)), 1.0, delta=0.001)
            self.assertAlmostEqual(np.mean(np.diff(time)), 1.0, delta=0.001)

            # test bounds are inside
            self.assertGreaterEqual(time[0], start_time_num)
            self.assertLess(time[-1], end_time_num)

            # test bounds are within one cadence of start
            self.assertLess((start_time_num - time[0]), 1)
            self.assertLessEqual((end_time_num - time[-1]), 1)

    def test_mpsh_with_start_fill(self):
        start_time = datetime(2017, 7, 20, 0, 0)
        end_time = datetime(2017, 7, 20, 0, 1) - timedelta(microseconds=1)

        self.config.dims["report_number"].update(
            {
                "index_by": "L1a_SciData_TimeStamp",
                "min": start_time,  # for convenience, will convert according to index_by units if this is datetime
                "max": end_time,
                "expected_cadence": {"report_number": 1},
            }
        )

        self.config.inter_validate()

        # note, exclude the first file!
        aggregation_list = generate_aggregation_list(self.config, self.files[1:])
        self.assertIsInstance(aggregation_list[0], FillNode)
        evaluate_aggregation_list(self.config, aggregation_list, self.nc_out_filename)
        with nc.Dataset(self.nc_out_filename) as nc_out:  # type: nc.Dataset
            start_time_num, end_time_num = nc.date2num(
                [start_time, end_time], nc_out["L1a_SciData_TimeStamp"].units
            )
            time = nc_out.variables["L1a_SciData_TimeStamp"][:]
            # test spacing
            self.assertAlmostEqual(np.min(np.diff(time)), 1.0, delta=0.001)
            self.assertAlmostEqual(np.max(np.diff(time)), 1.0, delta=0.001)
            self.assertAlmostEqual(np.mean(np.diff(time)), 1.0, delta=0.001)

            # test bounds are inside
            self.assertGreaterEqual(time[0], start_time_num)
            self.assertLess(time[-1], end_time_num)

            # test bounds are within one cadence of start
            self.assertLess((start_time_num - time[0]), 1)
            self.assertLessEqual((end_time_num - time[-1]), 1)
