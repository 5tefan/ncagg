import os
import tempfile

"""
This is a wrapper around functionality for a single
"""

base = os.environ.get("goes_mount_base", "/nfs")


class DataLocationMapper(object):
    def __init__(self, sat="GOES-16"):
        self.sat = sat
        # rc is runtime config, note: it's missing the indexed by min and max,
        # that needs to be filled in before giving this to the generate_aggregation_list
        # function
        self.mapping = {

            ## MAG
            "MAG-L1b-GEOF": {
                "base": os.path.join(base, "spades_mag_prod/archive/", sat),
                "rc": {
                    "report_number": {
                        "index_by": "OB_time",
                        "other_dim_indicies": {"samples_per_record": 0},
                        "expected_cadence": {"report_number": 1, "number_samples_per_report": 10},
                    }
                }
            },
            "magn-l2-hires": {
                "base": os.path.join(base, "spades_mag_prod/archive/", sat),
                "rc": {
                    "time": {
                        "index_by": "time",
                        "expected_cadence": {"time": 10},
                    }
                }
            },
            "magn-l2-avg1m": {
                "base": os.path.join(base, "spades_mag_prod/archive/", sat),
                "rc": {
                    "time": {
                        "index_by": "time",
                        "expected_cadence": {"time": 1.0/60.},
                    }
                }
            },
            "magn-l2-quiet": {
                "base": os.path.join(base, "spades_mag_prod/archive/", sat),
                "rc": {
                    "time": {
                        "index_by": "time",
                        "expected_cadence": {"time": 10},
                    }
                }
            },

            ## EXIS
            "EXIS-L1b-SFXR": {
                "base": os.path.join(base, "spades_exis_prod/archive/", sat),
                "rc": {
                    "report_number": {
                        "index_by": "time",
                        "expected_cadence": {"report_number": 1},
                    }
                }
            },
            "xrsf-l2-flx1s": {
                "base": os.path.join(base, "spades_exis_prod/archive/", sat),
                "rc": {
                    "record_number": {
                        "index_by": "time",
                        "expected_cadence": {"record_number": 1},
                    }
                }
            },
            "xrsf-l2-avg1m": {
                "base": os.path.join(base, "spades_exis_prod/archive/", sat),
                "rc": {
                    "record_number": {
                        "index_by": "time",
                        "expected_cadence": {"record_number": 1.0/60.},
                    }
                }
            },

            ## SEIS
            "SEIS-L1b-MPSH": {
                "base": os.path.join(base, "spades_seis_prod/archive/", sat),
                "rc": {
                    "report_number": {
                        "index_by": "L1a_SciData_TimeStamp",
                        "expected_cadence": {"report_number": 1},
                    }
                }
            },
            "SEIS-L1b-MPSL": {
                "base": os.path.join(base, "spades_seis_prod/archive/", sat),
                "rc": {
                    "report_number": {
                        "index_by": "L1a_SciData_TimeStamp",
                        "expected_cadence": {"report_number": 1},
                    }
                }
            },
            "SEIS-L1b-SGPS": {
                "base": os.path.join(base, "spades_seis_prod/archive/", sat),
                "rc": {
                    "report_number": {
                        "index_by": "L1a_SciData_TimeStamp",
                        "expected_cadence": {"report_number": 1, "sensor_unit": 0},
                    }
                }
            },
            "mpsh-l2-avg5m": {
                "base": os.path.join(base, "spades_seis_prod/archive/", sat),
                "rc": {
                    "record_number": {
                        "index_by": "L2_SciData_TimeStamp",
                        "expected_cadence": {"record_number": 1.0 / (60.0 * 5.0)}
                    }
                }
            },
            "sgps-l2-avg5m": {
                "base": os.path.join(base, "spades_seis_prod/archive/", sat),
                "rc": {
                    "record_number": {
                        "index_by": "L2_SciData_TimeStamp",
                        "expected_cadence": {"record_number": 1.0 / (60.0 * 5.0)}
                    }
                }
            }
        }

    def get_product(self, product):
        return os.path.join(self.mapping[product]["base"], product)

    def get_config(self, product):
        return self.mapping[product]["rc"]

    def get_output_base(self, product):
        # TODO: implement real filename + archive structure
        return "/nfs/goesr_private/aggregation_testing"

    def get_filename(self, product, datestr, env):
        """
        Create the filename for the output product.

        :param product: The data short name for the aggregated product.
        :param datestr: A datestring of [[[yyyy]mm]dd]
        :param env: the data production environment
        :return: None
        """

        if not env:
            env = "xx"

        # TODO: get version in here
        sat = "G" + self.sat[-2:]

        aggregate_type = "x"
        if len(datestr) == 4:
            aggregate_type = "y"
        elif len(datestr) == 6:
            aggregate_type = "m"
        elif len(datestr) == 8:
            aggregate_type = "d"

        return "%s_%s_%s_%s%s.nc" % (env, product, sat, aggregate_type, datestr)

