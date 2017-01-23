__author__ = 'meg tilton'


"""create_file_file.py: Creates file with fill values for all time stamps and all variables except time.

Args:

    filename: netCDF sample file of type fill file is to be based on. Should be same DSN, resolution, and satellite as fill file.
    start_time: start time of file to be created
    end_time: end time of file to be created
    output_dir: directory of output file to be created

"""

# ToDo: Figure out why file is populated w/blanks instead of fills (and if this is even a problem)
# ToDo: test if works on hidden attributes (e.g., chunking and chunksizes).
# ToDo: check if works on files with resolution higher than 1 Hz, e.g. MAG
# during createVariable.
# ToDo: See if InsertFills is needed


from netCDF4 import Dataset, date2num
import argparse
import datetime
import os
import traceback
import numpy as np
import numpy.ma as ma
from nco import Nco
import sys




def extant_file(x):
    try:
        if os.path.isfile(x):
            return x
        else:
            raise argparse.ArgumentTypeError("{0} does not exist.".format(x))
    except:
        raise argparse.ArgumentTypeError("{0} does not exist.".format(x))


def valid_datetime(s):
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ")               # test that date is valid
    except:
        raise argparse.ArgumentTypeError("Not a valid date: '{0}'.".format(s))


def writable_dir(prospective_dir):
    if not os.path.isdir(prospective_dir):
        raise Exception("writable_dir:{0} is not a valid path".format(prospective_dir))
    if os.access(prospective_dir, os.W_OK):
        return prospective_dir
    else:
        raise Exception("writable_dir:{0} is not a writable dir".format(prospective_dir))

def valid_env(env_prefix):
    if env_prefix in ['OR', 'OT', 'IR', 'IT', 'IP', 'IS']:
        return env_prefix
    else:
        raise Exception("{0} is not a valid system environment prefix.".format(env_prefix))


parser = argparse.ArgumentParser(description="netCDF4 Fill File Creation")
parser.add_argument("filename", help="netCDF4 sample file that the fill file should be based on", metavar="FILE",
                    type=extant_file)
parser.add_argument("-s", "--startDate", help="Start of file to be created", type=valid_datetime)
parser.add_argument("-e", "--endDate", help="End of file to be created", type=valid_datetime)
parser.add_argument("-o", "--outputDir", help="Output directory for fill file", type=writable_dir)
args = parser.parse_args()


def create_header(infile, outfile): 
    try:
        nc_in = Dataset(infile, 'r')
        nc_fill = Dataset(outfile,'w')
        resolution = round(nc_in.variables['time'][1] - nc_in.variables['time'][0])
        # Create dimensions
        newdim = nc_fill.createDimension('report_number', None)
        for dim in nc_in.dimensions:
            if dim != 'report_number':
                newdim=nc_fill.createDimension(dim, len(nc_in.dimensions[dim]))
        # Create variables
        key_array = nc_in.variables.keys()
        value_array = nc_in.variables.values()
        for n in range(0, len(key_array)):
            if '-' in key_array[n]:
                # logfile.write(key_array[n]+' has hyphen in its name, so script will not work. Exiting.')
                # logfile.write('\n****************************************************************************')
                print key_array[n]+' has hyphen in its name, so script will not work. Exiting.'
                sys.exit(1)
            else:
                # set variable attributes that need to be set at variable creation
                if set(['_FillValue', '_ChunkSizes']).issubset(value_array[n].ncattrs()):
                    fv = getattr(value_array[n], '_FillValue')
                    cs = getattr(value_array[n], '_ChunkSizes')
                    newvar = nc_fill.createVariable(key_array[n], value_array[n].datatype, value_array[n].dimensions, fill_value=fv, chunksizes=cs)
                elif '_FillValue' in value_array[n].ncattrs():
                    fv = getattr(value_array[n], '_FillValue')
                    newvar = nc_fill.createVariable(key_array[n], value_array[n].datatype, value_array[n].dimensions, fill_value=fv)
                elif '_ChunkSizes' in value_array[n].ncattrs():
                    cs = getattr(value_array[n], '_ChunkSizes')
                    newvar = nc_fill.createVariable(key_array[n], value_array[n].datatype, value_array[n].dimensions, chunksizes=cs)
                else:
                    newvar = nc_fill.createVariable(key_array[n], value_array[n].datatype, value_array[n].dimensions)
                # set all other variable attributes
                for val in value_array[n].ncattrs():
                    if val != '_FillValue':
                        setattr(nc_fill.variables.values()[n], val, getattr(value_array[n], val))
        # Create globals
        for attr in nc_in.ncattrs():
            setattr(nc_fill, attr, nc_in.getncattr(attr))
        setattr(nc_fill, 'time_coverage_start', datetime.datetime.strftime(args.startDate, "%Y-%m-%dT%H:%M:%S.%fZ"))
        setattr(nc_fill, 'time_coverage_end', datetime.datetime.strftime(args.endDate, "%Y-%m-%dT%H:%M:%S.%fZ"))
        print datetime.datetime.strftime(args.startDate, "%Y-%m-%dT%H:%M:%S.%fZ")
        print datetime.datetime.strftime(args.endDate, "%Y-%m-%dT%H:%M:%S.%fZ")
        nc_in.close()
        # nc_fill.close()
        # nco = Nco()
        # ncdump_string = nco.ncdump(input=outfile)
        # print ncdump_string
    except:
        print '\n Exception caught in create_header function.'
        traceback.print_exc()
    return nc_fill, resolution




# Replace masked values with fill values. Used in load_prods function
# Put result in data_array, a two-dimensional array of size col_numbers x row_numbers.
# May be better way to do this? Turn maskedandscale off on file?
def insert_fills(col_set, nc_fill):
    for col_name in col_set:
        try:
            is_masked_array = isinstance(nc_fill.variables[col_name][:], ma.core.MaskedArray)
            if is_masked_array:
                # print nc_fill.variables[col_name][:].data
                nc_fill.variables[col_name] = nc_fill.variables[col_name][:].data
            else:
                nc_fill.variables[col_name] = nc_fill.variables[col_name][:]
        except:
            print("\nProblem with insert_fills procedure (masked arrays) for column " + col_name + ". Exiting.")
            os._exit(1)


def clean_date(date_formatted):
    date_cleaned = date_formatted.replace("-", "")
    date_cleaned = date_cleaned.replace(":", "")
    date_cleaned = date_cleaned.replace("T", "")
    date_cleaned = date_cleaned.replace("Z", "")
    date_cleaned = date_cleaned.replace(".", "")
    return date_cleaned


if __name__ == "__main__":
    # nco = Nco()
    # ncdump_string = nco.ncdump(input = "/data/backup/GOES_R/data/samples/OR_EXIS-L1b-SFXR_G16_s20162700009320_e20162700010019_c20162700010021.nc", options="-h")
    # nco.ncgen(input=ncdump_string, output="/home/mtilton/Documents/test.nc", options="--netcdf4")
    try:
        cur_time = datetime.datetime.utcnow().strftime("%Y%j%H%M%S%f")[:-5]
        fname = args.filename.split("/")[-1]
        env_prefix = fname.split("_")[0]
        DSN = fname.split("_")[1]
        sat = fname.split("_")[2]
        start_date_string = datetime.datetime.strftime(args.startDate, "%Y%j%H%M%S%f")[:-5]
        end_date_string = datetime.datetime.strftime(args.endDate, "%Y%j%H%M%S%f")[:-5]
        outfile = "{0}/{1}_{2}_{3}_s{4}_e{5}_c{6}.nc".format(args.outputDir, env_prefix, DSN, sat, start_date_string, end_date_string, cur_time)
        print outfile
        nc_out, res = create_header(args.filename, outfile)
        print res
    except:
        print '\n Exception caught.'
        traceback.print_exc()

t_var = nc_out.variables['time']
start_seconds = date2num(args.startDate, 'seconds since 2000-01-01 12:00:00', calendar='standard')
end_seconds = date2num(args.endDate, 'seconds since 2000-01-01 12:00:00', calendar='standard')
t_var[:] = np.arange(start_seconds, end_seconds, res)
insert_fills(['irradiance_xrsa1', 'irradiance_xrsa2'], nc_out)    # not sure if this is needed
nc_out.close()
