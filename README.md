# GOES Aggregation (AggreGOES)

So... you want to aggregate? -- A utility to aggregate L1b and L2+ GOES Space Weather products.


## TL;DR

Install the utility with with pip:
```
pip install git+https://stash.ngdc.noaa.gov:8443/scm/stp/goes-aggregation.git
# or
pip install git+https://ctor.space/gitlab/work/goes-aggregation.git
```

On the command line, use `aggregoes`:

```
Usage: aggregoes [OPTIONS] DST [SRC]...

Options:
  -u TEXT  Give an Unlimited Dimension Configuration as udim:ivar[:hz[:hz]]
  -b TEXT  If -u given, specify bounds for ivar as min:max. min and max should
           be numbers, or start with T to indicate a time and then should be
           TYYYYMMDD[HH[MM]] format.
  --help   Show this message and exit.

```

Notes:

 - DST is the filename for the netcdf output and should not already exist, or will be overwritten.
 - SRC is a list of input netcdf files to aggregate.
 - -u should specify an Unlimited Dimension Configuration. See below for details.
 - Taking tens of minutes for a day is normal, a progress bar will indicate time remaining.

Examples:

```
# explicitly list files to aggregate
aggregoes output_filename.nc file_0.nc file_02.nc #...

# aggregate by globbing all files in some directory
aggregoes output_filename.nc path_to_files/*.nc

# sort the unlimited dimension record_number, according to the variable time
aggregoes -u record_number:time output_filename.nc path_to_files/*.nc

# sort the unlimited dimension record_number, according to the variable time, and insert
# or remove fill values to ensure time occurrs at 10hz.
aggregoes -u record_number:time:10 output_filename.nc path_to_files/*.nc

# only include time values between 2017-06-01 to 2017-06-02 (bounds), including
# sorting and filling, as above
aggregoes -u record_number:time:10 -b T20170601:T20170602 output_filename.nc path_to_files/*.nc

```

In addition, command line interfaces customized for NCEI systems are available:

 - Specific to the aggregation workspace - see [ncei-l1b-cli](docs/ncei-l1b-cli.md)
 - Specific to the spades mounts - see [ncei-spades-cli](docs/ncei-spades-cli.md)

## High level overview

Aggregation works in two stages:

1. Create an AggreList object.
2. Evaluate the AggreList.

The AggreList object is a data structure that describes how to combine a set of files. The structure of the
AggreList specifies the order of the files, what pieces of those files to include, fill values between files,
as well as fill values and sorting inside files.

During stage 1, the AggreList is generated. The level of configuration given determines how much is done here.
At most, each file is inspected according to it's unlimited dimension and the variable that indexes it to determine
sorting and filling. No data is not read or written to disk is done in this stage.

During stage 2, the AggreList is evaluated. Evaluating the AggreList means simply iterating over it and copying
data from the nodes into the output aggregation file, while keeping track of global attributes.

Reasons for using this approach:

 - Possible to aggregate more data than fits in memory.
 - Sort once per unlimited dimension.
 - Modular code, easier to maintain, extend, and debug.


## Configuration

The sophistication of the aggregation is determine by how much configuration information is given on
generation of the AggreList.

 - No config -> concat files along unlimited dims, sorted by filename
 - Unlimited dim config -> concat and fill within, between files as needed
 - Product config -> reshape, subset, and configure global attr strategies

### Unlimited Dimension Configuration

The Unlimited Dimension Configuration associates a particular unlimited dimension with a variable by which
it can be indexed. Commonly, a dimension named time is associated with a variable also named time which 
indicates some epoch value for all data associated with that index of the dimension.

For example, a file may have a dimension "record_number" which is indexed by a variable "time". Using
the Unlimited Dimension Configuration, we can specify to aggregate record_number such that the variable
"time" forms a monotonic sequence increasing at some expected frequency.

Here is what a typical GOES-R L1b product aggregation output looks like:

```
"report_number": {
    "index_by": "time",
    "expected_cadence": {"report_number": 1},
}
```

In English, the configuration above says "Order the dimension report_number by the values in the variable time, where
time values are expected to increase along the dimension report_number incrementing at 1hz." This would be specified 
on the aggregoes command line using `aggregoes -u report_number:time:1 output.nc in1.nc in2.nc`. 

The configuration allows to even index by multidimensional time (ehem, mag with 10 samples per report). On the command
line specified as `-u report_number:OB_time:1:10`, or as json:

```
"report_number": {
    "index_by": "OB_time",
    "other_dim_indicies": {"samples_per_record": 0},
    "expected_cadence": {"report_number": 1, "number_samples_per_report": 10},
}
```

One design constraint was to not reshape the data, so above, we order the data by looking at index 0 of 
samples_per_record for every value along the report_number dimension. We assume that the other timestamps along
samples_per_record are correct. Also, given the configuration above, we only insert fill records of OB_time
if a full report_number row type is missing.


### Product Configuration

The product config contains a lot of the same information as a NetCDF CDL would, but in json format, extended
with fields custom to aggregation. If not provided, a default version will be created using the routines in 
`init_config_template.py` using the first file in the list to aggregate.

The Product Configuration is used for a number of things:

#### Specify Global Attribute Aggregation Strategies

The aggregated result file contains global attributes formed from the constituent granules. A number of
strategies exist to aggregate Global Attributes across the granules. Most are quite self explanatory:

 -         "first": StratFirst  # first value seen will be taken as the output value for this global attribute
 -         "last": StratLast    # the last value seen will be taken as global attribute
 -         "unique_list": StratUniqueList  # compile values into a unique list "first, second, etc"
 -         "int_sum": StratIntSum          # resulting in integer sum of the inputs
 -         "float_sum": StratFloatSum
 -         "constant": StratAssertConst
 -         "date_created": StratDateCreated   # simply yeilds the current date when finalized, standard dt fmt
 -         "time_coverage_start": StratTimeCoverageStart  # start bound, if specified, standard dt fmt
 -         "time_coverage_end": StratTimeCoverageEnd      # end bound, if specified, standard dt fmt
 -         "filename": StratOutputFilename                
 -         "remove": StratRemove                          # remove/do not include this global attribute
 
 The configuration format expects a key "global attributes" associated with a list of objects each containing 
 a global attribute name and strategy. A list is used to preserve order, as the order in the configuration will
 be the resulting order in the output NetCDF.
 

```json
{
    "global attributes": [
        {
            "name": "production_site", 
            "strategy": "unique_list"
        }, {
        ...
        }
     ]
}
```

#### Specify Dimension Indecies to Extract and Flatten

Consider SEIS SGPS files which contain the data from two sensor units, +X and -X. Most variables are of the form
var[record_number, sensor_unit, channel, ...]. It is possible to create an aggregate file for the +X and -X sensor 
units individually using the take_dim_indicies configuration key.

```json
{
    "take_dim_indicies": {
        "sensor_unit": 0
    }
}
```

With the above configuration, sensor_unit must be removed from the dimensions configuration. Please also ensure that
variables do not list sensor_unit as a dimension, and also update chunk sizes accordingly. Chunk sizes must be a list
of values of the same length as dimensions.



## Technical and Implementation details

An AggreList is composed of two types of objects, InputFileNode and FillNode objects. These inherit in common
from an AbstractNode and must implement the `get_size_along(unlimited_dim)` and `data_for(var, dim)` 
methods. Evaluating an aggregation list is simply going though the AggreList and calling something like:

```
write_slice = slice(written_up_to, written_up_to + node.get_size_along(dim))
nc_out.variable[var][write_slice] = node.data_for(var, dim)
```

The `data_for` must return data consistent with the shape promised from `get_size_along`.

The complixity of aggregation comes in handling the dimensions and building the aggregation list. In addition to
the interface exposed by an AbstractNode, each InputFileNode and FillNode implement their own specific functionality.

A FillNode is simpler, and needs to be told how many fills to insert along a certain unlimited dimension and 
optionally, can be configured to return values from `data_for` that are increasing along multiple dimensions
according to configured `expected_cadence` values from a certain start value.


An InputFileNode is more complicated and exposes methods to find the time bounds of the file, and additionally, 
is internally capable of sorting itself and inserting fill values into itself. Of course, it doesn't modify the
actual input file, this is all done on the fly as data is being read out through `data_for`. Implementation wise,
an InputFileNode may contain within itself a mini aggregation list containing two types of objects: slice and 
FillNode objects. Similarly to the large scale process of aggregating, an InputFileNode returns data that has 
been assembled according to it's internal aggregation list and internal sorting.


## Development

Setting up a virtualenv is recommended for development.

```
virtualenv venv
. venv/bin/activate
pip install --editable .
```
