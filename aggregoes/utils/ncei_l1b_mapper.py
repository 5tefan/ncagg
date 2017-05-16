import os
import glob
from datetime import datetime
import json
import pkg_resources

"""
Implements get_files_for, get_runtime_config, and get_output_filename for L1b products at NCEI using
our specified structure and flow inside /nfs/goesr_private/.
"""

# in_base is expected to point to a directory containing directories named equivalently to the keys in mapping
in_base = os.environ.get("l1b_aggregation_in_base", "/nfs/goesr_private/internal/aggregation/workspace/l1b/data/")
# out_base is expected to point to a directory where directories and sat/product/year/month/ directories will
# be created below it as necessary
out_base = os.environ.get("l1b_aggregation_out_base", "/nfs/goesr_private/l1b/data/")

mapping = {
    ## MAG
    "mag-l1b-geof": {
        "report_number": {
            "index_by": "OB_time",
            "other_dim_indicies": {"samples_per_record": 0},
            "expected_cadence": {"report_number": 1, "number_samples_per_report": 10},
        }
    },

    ## EXIS
    "exis-l1b-sfxr": {
        "report_number": {
            "index_by": "time",
            "expected_cadence": {"report_number": 1},
        }
    },

    ## SEIS
    "seis-l1b-mpsh": {
        "report_number": {
            "index_by": "L1a_SciData_TimeStamp",
            "expected_cadence": {"report_number": 1},
        }
    },
    "seis-l1b-mpsl": {
        "report_number": {
            "index_by": "L1a_SciData_TimeStamp",
            "expected_cadence": {"report_number": 1},
        }
    },
    "seis-l1b-sgps": {
        "report_number": {
            "index_by": "L1a_SciData_TimeStamp",
            "expected_cadence": {"report_number": 1, "sensor_unit": 0},
        }
    }
}


def get_files_for(sat, product, dt, env="OR"):
    """
    
    :param sat: which goes sat, eg goes16
    :param product: L1b product type
    :type dt: datetime
    :param dt: datetime specification of day to get files for
    :param env: env to look for products in, defualt OR for L1b
    :return: list of files matching query
    """
    # check inputs
    check_product(product)
    check_sat(sat)

    path = os.path.join(in_base, sat, product, dt.strftime("%Y/%m/%d"), "%s-%s-*.nc" % (env, product))
    return sorted(glob.glob(path))


def get_runtime_config(product):
    # check inputs
    check_product(product)

    return mapping[product]


def get_product_config(product):
    config = pkg_resources.resource_filename("aggregoes", "aggregoes/util/config/%s.json" % product)
    with open(config) as config_file:
        return json.load(config_file)


def get_output_filename(sat, product, datestr, env="xx"):
    # check inputs
    assert int(datestr), "datestr should be numerical %Y, %Y%m, or %Y%m%d"
    check_product(product)
    check_sat(sat)

    if len(datestr) == 4:  # is a year file
        agg_length_prefix = "y"
        # put all year files in the product directory
        path_from_base = os.path.join(sat, product)
    elif len(datestr) == 6:  # is a month file
        agg_length_prefix = "m"
        # put all month files in the year directory
        path_from_base = os.path.join(sat, product, datestr[:4])
    elif len(datestr) == 8:  # is a day file
        agg_length_prefix = "d"
        # put all date files in a month directory
        path_from_base = os.path.join(sat, product, datestr[:4], datestr[4:6])
    else:
        raise ValueError("Unknown datestr: %s, expected %Y, %Y%m, or %Y%m%d")

    # create base of path if it doesn't exist already
    path = os.path.join(out_base, path_from_base)
    if not os.path.exists(path):
        os.mkdir(path)

    filename_sat = "g%s" % int(sat[-2:])
    filename = "%s_%s_%s_%s%s.nc" % (env, product, filename_sat, agg_length_prefix, datestr)

    return os.path.join(path, filename)


def check_sat(sat):
    """
    Validate sat string.
    
    :type sat: str
    :param sat: a satellite
    :return: None
    """
    assert sat.startswith("goes"), "Unknown satellite: %s" % sat


def check_product(product):
    """
    Validate product string.
    :param product: 
    :return: 
    """
    assert product in mapping.keys(), "Unknown L1b product: %s" % product

