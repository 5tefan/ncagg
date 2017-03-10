import os
import tempfile

"""
This is a wrapper around functionality for a single
"""

base = os.environ.get("goes_mount_base", "/nfs")


class DataLocationMapper(object):
    def __init__(self, sat="GOES-16"):
        # rc is runtime config, note: it's missing the indexed by min and max,
        # that needs to be filled in before giving this to the generate_aggregation_list
        # function
        self.mapping = {
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
                "base": os.path.join(base, "spades_mag_prod/archive/", sat)
            },
            "magn-l2-avg1m": {
                "base": os.path.join(base, "spades_mag_prod/archive/", sat)
            },
            "magn-l2-quiet": {
                "base": os.path.join(base, "spades_mag_prod/archive/", sat)
            },

            "EXIS-L1b-SFXR": {
                "base": os.path.join(base, "spades_exis_prod/archive/", sat)
            },
            "EXIS-L1b-SFEU": {
                "base": os.path.join(base, "spades_exis_prod/archive/", sat)
            },
            "xrsf-l2-flx1s": {
                "base": os.path.join(base, "spades_exis_prod/archive/", sat)
            },
            "xrsf-l2-avg1m": {
                "base": os.path.join(base, "spades_exis_prod/archive/", sat)
            },

        }

    def get_product(self, product):
        return os.path.join(self.mapping[product]["base"], product)

    def get_config(self, product):
        return self.mapping[product]["rc"]

    def get_output(self, product):
        # TODO: implement real filename + archive structure
        _, tmpfile = tempfile.mkstemp()
        return tmpfile
