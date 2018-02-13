# NetCDF Aggregation (ncagg)

So... you want to aggregate time series NetCDF files?


## TL;DR

Install the utility with with pip:
```
pip install ncagg
```

On the command line, use `ncagg`:

```
Usage: ncagg [OPTIONS] DST [SRC]...

Options:
  -v, --version                   Show the version and exit.
  --generate_template PATH        Print the default template generated for
                                  PATH and exit.
  -u TEXT                         Give an Unlimited Dimension Configuration as
                                  udim:ivar[:hz[:hz]]
  -b TEXT                         If -u given, specify bounds for ivar as
                                  min:max or Tstart[:[T]stop]. min and max are
                                  numerical, otherwise T indicates start and
                                  stop are times.start and stop are of the
                                  form YYYY[MM[DD[HH[MM]]]] and of stop is
                                  omitted,it will be inferred to be the least
                                  significantly specified date + 1.
  -l [DEBUG|INFO|WARNING|ERROR|CRITICAL]
                                  log level
  -t FILENAME                     Specify a configuration template
  --help                          Show this message and exit.
```

Notes:

 - DST is the filename for the NetCDF output and should not already exist, or will be overwritten.
 - SRC is a list of input NetCDF files to aggregate, can be passed on the command line or piped to ncagg.
 - -u should specify an Unlimited Dimension Configuration. See below for details.
 - Taking tens of minutes for a day is normal, a progress bar will indicate time remaining.
 - For fine grained control over the output, specify a configuration template (-t). See below for details.

Examples:

```
#     explicitly list files to aggregate
ncagg output_filename.nc file_0.nc file_02.nc #...

#     aggregate by globbing all files in some directory
ncagg output_filename.nc path_to_files/*.nc

#     sort the unlimited dimension record_number, according to the variable time
ncagg -u record_number:time output_filename.nc path_to_files/*.nc

#     sort the unlimited dimension record_number, according to the variable time, and insert
#     or remove fill values to ensure time occurrs at 10hz.
ncagg -u record_number:time:10 output_filename.nc path_to_files/*.nc

#     only include time values between 2017-06-01 to 2017-06-02 (bounds), including
#     sorting and filling, as above
ncagg -u record_number:time:10 -b T20170601:T20170602 output_filename.nc path_to_files/*.nc
#     or equivalently, if only one bound is specified, the end is inferred to be most significant + 1
ncagg -u record_number:time:10 -b T20170601 output_filename.nc path_to_files/*.nc

#     aggregate more files than fit on the command line... (in case of: Argument list too long)
find /path/to/files -type f -name "*.nc" | ncagg output.nc
```

For more information, see the Unlimited Dimension Configuration below. The `ncagg` Command Line Interface (CLI)
builds a Config based on the arguments specified.

## High level overview

Aggregation works in two stages:

1. Create a Aggregation List describing steps and order of aggregation.
2. Evaluate the Aggregation List.

The Aggregation List object is just a list that describes the order in which to combine components of an aggregation.
The objects within the list represent source files, or segments of fill values. Source files are associated
with sorting and filling instructions within the file. Fill values indicate where, and how many fill values to create.

During stage 1, the Aggregation List is generated. The level of configuration given determines how much is done here.
At most, each file is inspected according to it's unlimited dimension and the variable that indexes it to determine
sorting and filling. No data except for index_by variables are read and none written to disk during this stage. If
an expected cadence is not provided, filling is not done. If bounds are provided, the unlimited dimension is clipped
to ensure data is included only within the bounds. For the minimum configuration given, files are simply assembed in
order of sorted filename.

During stage 2, the Aggregation List is evaluated. Evaluating the Aggregation List means simply iterating over the
components contained and copying data from these into the output aggregation file, while keeping track of global attributes.

Reasons for using this approach:

 - Possible to aggregate more data than fits in memory.
 - Sort once per unlimited dimension.
 - Modular code, easier to maintain, extend, and debug.


## Configuration

The sophistication of the aggregation is determine by how much configuration information is given on
generation of the Aggregation List.

 - No Config -> agg files along unlimited dims, sorted by filename.
 - Config with index_by -> agg such that index_by is in ascending order.
 - Config with index_by and bounds -> agg such that index_by is in ascending order within bounds.
 - Config with index_by and expected_cadences -> agg and regularize, removing duplicates/inserting fills if needed.

The Config contains information that a NetCDF CDL specification would, but in json format, extended
with aggregation configuration information. If not provided, a default version will be created using the first
file in the list to aggregate.

The Config contains three properties (keys):

 - dimensions
 - variables
 - attributes

 Each property is associated with a list of objects so to preserve ordering. The order in the
 objects corresponds to the order of appearence in the output. Objects of all sections
 have a "name" property.

 Dimensions specify the dimensions of the file and has at minimum a "name", and a "size"
 which can be null for an unlimited dimension. Unlimited dimensions may also have an
 Unlimited Dimension Configuration which will be described in a dedicated section below.

 Variable objects contain a "name", "dimensions", "datatype", "attributes", and
 "chunksizes". The dimensions property is a list of dimension names on which the variable depends, each
 must be configured in the dimensions section. datatype is something like int8, float32, string, etc.
 Finally, attributes is another property containing key and values corresponding to variable attributes
 commonly including "units", "valid_min", "_FillValue", etc.

 Attributes objects contain "name", "strategy", and optionally "value" for NetCDF Global Attributes. The
 strategies are described below.

### Unlimited Dimension Configuration

The Unlimited Dimension Configuration associates a particular unlimited dimension with a variable by which
it can be indexed. Commonly, a dimension named time is associated with a variable also named time which 
indicates some epoch value for all data associated with that index of the dimension.

For example, a file may have a dimension "record_number" which is indexed by a variable "time". Using
the Unlimited Dimension Configuration, we can specify to aggregate record_number such that the variable
"time" forms a monotonic sequence increasing at some expected frequency.

Here is what a typical GOES-R L1b product aggregation output looks like:

```json
{
    "name": "report_number",
    "size": null,
    "index_by": "time",
    "expected_cadence": {"report_number": 1},
}
```

In English, the configuration above says "Order the dimension report_number by the values in the variable time, where
time values are expected to increase along the dimension report_number incrementing at 1hz." This would be specified 
to the ncagg CLI using `ncagg -u report_number:time:1 output.nc in1.nc in2.nc`.

The configuration allows to even index by multidimensional time (ehem, mag with 10 samples per report). On the command
line specified as `-u report_number:OB_time:1:10`, or as json:

```json
{
    "name": "report_number",
    "size": null,
    "index_by": "OB_time",
    "other_dim_indicies": {"samples_per_record": 0},
    "expected_cadence": {"report_number": 1, "number_samples_per_report": 10},
}
```

One design constraint was to not reshape the data, so above, we order the data by looking at index 0 of 
samples_per_record for every value along the report_number dimension. We assume that the other timestamps along
samples_per_record are correct. Also, given the configuration above, we only insert fill records of OB_time
if a full report_number record is missing (all 10 values along the number_samples_per_report dimension missing).

------------------------

Indexing an unlimited dimension was described above. In addition to simply indexing by a variable, in the case that
the variable represents time, a common operation would be to restrict value to some range, to, for example, create
a day file. The Unlimited Dimension Configuration would look like:

```json
{
    "name": "report_number",
    "size": null,
    "index_by": "time",
    "min": 14000000,  # in units of the variable "time", expected
    "max": 14000060,  # something like "seconds since 2000-01-01 12:00:00"
    "expected_cadence": {"report_number": 1}
}
```
Which would be specified on the command line as `... -u report_number:time:1 -b1400000:14000060 ...` where the `-b`
option stands for "bounds".

As min and max almost exclusively indicate datetime values, for convenience, they
are accepted as types: numerical, string, or python datetime. In string representation, they must start with "T" and
can be of the form "TYYYY[MM[DD[HH[MM]]]]" where brackets indicate optional and if omitted, will be inferred to be
minimum valid value, ie: 01 for MM (month). A units attribute must available for the index_by variable in the
form of "<time units> since <reference time>". On the command line, string time can be given as
`... -u report_number:time:1 -bT20170101:T20170102 ...` or equivalently the end bound can be omitted and will be
inferred to be the rightmost specified of the beginning YYYY[MM[DD[HH[MM]]]] incremented by one: ie:
`... -u report_number:time:1 -bT20170101 ...`.



------------------------

Consider the suvi-l2-flloc (flare location) product which has two unlimited dimensions, time and feature_number.
At any time record, there can exist an arbitrary number of features. Consider a variable reporting the flux from
each feature at each time: `flux(time, feature_number)`. Although feature_number is unlimited, it is unique to
each time and thus needs to be "flattened":

```
flux([0], [0]) -> [[3.2e-6]]
flux([0], [0, 1]) -> [[3.3e-6, 5.4e-7]]

undesired_aggregated_flux(time, feature_number):
[[3.2e-6,      _,      _],
 [     _, 3.3e-6, 5.4e-7]]

desired_aggregated_flux(time, feature_number):
[[3.2e-6,      _],
 [3.3e-6, 5.4e-7]]
```

The `desired_aggregated_flux` is achieved by setting {"flatten": true} within an the unlimited dimension configuration for feature_number.
```json
[{
    "name": "time",
    "size": null,
    "index_by": "time",
}, {
    "name": "feature_number",
    "size": null,
    "flatten": true,
}]
```

#### Specify Global Attribute Aggregation Strategies

The aggregated netcdf file contains global attributes formed from the constituent granules. A number of
strategies exist to aggregate Global Attributes across the granules. Most are quite self explanatory:

 - "static": use the configured "value" in the template, ignoring any values that may be in the file.
 - "first": first value seen will be taken as the output value for this global attribute
 - "last": the last value seen will be taken as global attribute
 - "unique_list": compile values into a unique list "first, second, etc"
 - "int_sum": resulting in integer sum of the inputs
 - "float_sum": StratFloatSum
 - "constant": StratAssertConst, similar to first, but raises an error if value changes among input files.
 - "date_created": simply yeilds the current date when finalized, standard dt fmt
 - "time_coverage_start": start bound, if specified, standard dt fmt
 - "time_coverage_end": end bound, if specified, standard dt fmt
 - "filename": StratOutputFilename, set attribute to name of output file
 - "remove": remove/do not include this global attribute
 - "first_input": Filename of first file included in aggregate
 - "last_input": Filename of last file included in aggregate
 - "input_count": Number of files included in aggregate
 - "ncagg_version": Version number for the ncagg software running

 
 The configuration format expects a key "global attributes" associated with a list of objects each containing 
 a global attribute name, strategy, and possible value (for static). A list is used to preserve order, as the
 order in the configuration will be the resulting order in the output NetCDF.
 

```json
{
    "global attributes": [
        {
            "name": "production_site", 
            "strategy": "unique_list"
        }, {
            "name": "creator",
            "strategy": "static",
            "value": "Stefan Codrescu"
        }, {
            
        ...
        }
     ]
}
```

#### Specify Dimension Indecies to Extract and Flatten

NOT IMPLEMENTED. IN PROGRESS. SUBJECT TO CHANGE.

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


### Configuration Template

`ncagg` can be configured to output files into a format specified by a configuration template file. It is expected
that this is a json format file. A generic template can be created using the `ncagg --generate_template [SAMPLE_NC]` 
command. The output of the template command is the default template that is used internally if no template is specified.

#### Example usage

Use `ncagg --generate_template example_netcdf.nc > my_template.json` to save the default template for an example_netcdf.nc file
into my_template.nc. Edit my_template.json to your liking, then run aggregation using `ncagg -t my_template.json [...]`.

#### Template syntax

The template syntax is verbose, but hopefully straightforward and clear. The incoming template will be validated
upon initiating an aggregation, but some issues may only be found at runtime.

##### Attributes

The attributes section is a list of objects contianing global attributes:

- name: name of global attribute
- strategy: [aggregation strategy](#Specify-Global-Attribute-Aggregation-Strategies) to use for attribute.
- value: value used by strategy, if required. Eg. constant, where the value is "test".

##### Dimensions

The dimensions section is a list of objects containing the dimensions of the file. Most configuration options
are covered in [Unlimited Dimension Configuration](#Unlimited-Dimension-Configuration) section, but to clarify:

- size: integer if dimension has a fixed size. null if it's unlimited.

##### Variables

Similarly, variables section is a list of objects configuring output variables. Remove the object
corresponding to some variable to remove it from the output.

Important notes:

- The dimensions referenced must exist.
- chunksizes must be the same number of elements as dimensions.

Take care that everything is consistent when doing heavy modifications.

## Use from code

In addition to the CLI, `ncagg` exposes an API which makes it possible to call from Python code:

```
from ncagg import aggregate
aggregate(["file1.nc", "file2.nc"], "output.nc")
```

`aggregate` optionally accepts as a third argument a configuration template. If none is given,
the default template created from the first input file is used. Thus code above is equivalent to:

```
from ncagg import aggregate, Config
config = Config.from_nc("file1.nc")
aggregate(["file1.nc", "file2.nc"], "output.nc", config)
```

This allows for the possibility of programatically manipulating the configuration at runtime before
performing aggregation.

## Limitations

 - Does not support netCDF4 enum types.

## Technical and Implementation details

An Aggregation List is composed of two types of objects, InputFileNode and FillNode objects. These inherit in common
from an AbstractNode and must implement the `get_size_along(unlimited_dim)` and `data_for(var, dim)` 
methods. Evaluating an aggregation list is simply going though the Aggregation List and calling something like:

```
nc_out.variable[var][write_slice] = node.data_for(var)
```

The `data_for` must return data consistent with the shape promised from `node.get_size_along(dim)`.

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


## Testing

This software is written for aggregation of GOES-R series Space Weather data products (L1b and L2+). As
such, it contains extensive tests against real GOES-16 satellite data. Many "features" in this code are
intended to address "quirks" in the ground processing (implemented by a certain contractor...).

Tests are in the `test` subdirectory. Run all tests with

```bash
python -m unittest discover 
```

The code is compatible with Python2 (2.7) and Python3, so unittests should be run with both.


## Development

Setting up a virtualenv is recommended for development.

```
virtualenv venv
. venv/bin/activate
pip install --editable .
```

---------------------

Deploy to pip, after running unittest with both with python2 and python3. The `git stash` is important so that
the build is from a clean repo! We don't want any dev or debug changes that are sitting unstaged to be included.

```bash
git stash
rm -r dist/
python setup.py bdist_wheel --universal
twine upload dist/*
```

