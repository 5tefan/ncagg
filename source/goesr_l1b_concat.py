__author__ = 'meg tilton'


"""goesr_l1b_concat.py: Concatenates granular netCDF files to a daily netCDF file.
   Input files must meet the following criteria to be included:
      - They must appear in the correct directory (progam will search on [root_dir/
      - They must be of the satellite and product type (pattern-matching performed)

Args:

    config (String): The path name to a json config file, which should contain values for the follow parameters:

        products: A list of the L1b granular products to be aggregated
        root_dir: The root directory for input files
        output_file: The location of the aggregated output file.
        log_file: The location of the log file.

    date (String): Optional input that specifies date for which aggregations should be run in YYYY-MM-DD format. Defaults to yesterday's date.

Routine should only be used to aggregate granular files into a day's worth of files. Various parameters (the output file name,
the algorithm_dynamic_input_data_container, etc.) assume that the file duration is for a complete day.

"""

# ToDO: Output file lists string algorithm_dynamic_input_data_container:input_EUVS_L0_data = "OR_EXIS-L0_G16_s2016270*.nc".
# ToDO: The "string" shouldn't be there, and isn't when I run the routine locally. Same prefix with time_coverage_end.

# ToDO: Verify with William that day files are separated by start time being in same day. Then modify glob.glob so it pulls according to day.

import sys
import argparse
import goesr_nc_concat
import json
import datetime
import traceback
import glob


def extant_file(x):
    try:
        return open(x, 'r')
    except:
        raise argparse.ArgumentTypeError("{0} does not exist.".format(x))

def valid_date(s):
    try:
        d = datetime.datetime.strptime(s, "%Y-%m-%d").date()                # test that date is valid
        return s
    except:
        raise argparse.ArgumentTypeError("Not a valid date: '{0}'.".format(s))


parser = argparse.ArgumentParser(description="GOES-R L1b file aggregation")
parser.add_argument("filename", help="json config file", metavar="FILE",
                    type=extant_file)
parser.add_argument('-d', "--date2agg", help="Date of files to be aggregated ", required=False, type=valid_date)
args = parser.parse_args()

try:

    # Get config file parameters
    config_data = json.load(args.filename)
    products = config_data["products"]
    satellites = config_data["satellites"]
    root_dir = config_data["root_dir"]
    output_dir = config_data["output_dir"]
    log_file = config_data["log_file"]
    version = config_data["version"]


    # Get date to aggregate
    if args.date2agg:
        date2agg = args.date2agg
    else:
        date2agg = datetime.date.fromordinal(datetime.date.today().toordinal()-1).strftime("%Y-%m-%d")
    year2agg = date2agg[0:4]
    month2agg = date2agg[5:7]
    day2agg = date2agg[8:10]


    log = open(log_file, 'w')
    log.write('goesr_1lb_concat.py started at {0}.'.format(datetime.datetime.now()))
    log.write('\nconfig parameters: {0}, {1}, {2}, {3}'.format(products, root_dir, output_dir, log_file))
    log.write('\n\ndate2agg: {0}'.format(date2agg))


    for s in satellites:
        for p in products:
            # prod_dir = "{0}/GOES-{1}/{2}/{3}/{4}/{5}/".format(root_dir, s, p, year2agg, month2agg, day2agg)
            prod_dir = root_dir       # remove when done testing, use line above instead
            fn_list = sorted(
                    glob.glob( '{0}/??_{1}_G{2}_s{3}??????????_e??????????????_c??????????????.nc'.format(prod_dir,p,s,year2agg)) )
            log.write( '\n\nFound {0} files\n'.format(len( fn_list ) ))
            if not len( fn_list ):
                continue
            output_file = 'OR_{0}_g{1}_d{2}{3}{4}_v{5}.nc'.format(p,s,year2agg,month2agg,day2agg,version)
            # Create output file name
            fn_concat = '{0}/{1}'.format(output_dir, output_file)
            log.write('output file: {0}'.format(fn_concat))
            print fn_list[-6:]
            global_attrs = []
            # Get concatenated data set:
            nc_all = goesr_nc_concat.goesr_nc_concat( fn_list[-6:], fn_concat=fn_concat, read_only=False, global_attrs=global_attrs, debug=True )
            if not nc_all:
                log.write( '\nConcatenation failed.' )
                sys.exit( 1 )
            lastFileGlobals = global_attrs[-1]      # lastFileGlobals = dictonary of global values for last file
            setattr(nc_all, 'time_coverage_end', lastFileGlobals['time_coverage_end'])
            cur_time = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-5] + 'Z'
            # Not exact since the tenths of a second get truncated rather than rounded -- no one should care
            setattr(nc_all, 'date_created', cur_time)
            setattr(nc_all, 'dataset_name', output_file)
            setattr(nc_all, 'license', 'Unclassified data.')
            setattr(nc_all, 'id', 'N/A')
            setattr(nc_all, 'iso_series_metadata_id', 'N/A')

            # update algorithm_dynamic_input_data_container's input attribute
            key_array = nc_all.variables.keys()
            value_array = nc_all.variables.values()
            for n in range(0, len(key_array)):
                if key_array[n] == 'algorithm_dynamic_input_data_container':
                    count = n               # Nasty way of doing this; improve when time permits
                    break
            for val in value_array[count].ncattrs():
                if val == 'input_EUVS_L0_data':
                    original_l0 = (getattr(value_array[count], val))
                    end_str = original_l0.find('_s20') + 9
                    new_l0 = original_l0[:end_str] + '*.nc'
                    setattr(value_array[count], val, new_l0)
            nc_all.close()
    log.close()

except IOError as e:
    print "I/O error({0}): {1}".format(e.errno, e.strerror)
    traceback.print_exc()
except:
    print '\n Exception caught.'
    traceback.print_exc()



