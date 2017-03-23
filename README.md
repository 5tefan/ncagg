# GOES Aggregation (AggreGOES)

So... you want to aggregate? -- A utility to aggregate L1b and L2+ GOES Space Weather products.


## TL;DR

Install the utility with with pip:
```
pip install git+https://scodrescu@stash.ngdc.noaa.gov:8443/scm/stp/goes-aggregation.git
```

On the command line, use `aggregoes`, in the following three flavours:

```
Usage: aggregoes do_day [OPTIONS] YYYYMMDD PRODUCT
Usage: aggregoes do_month [OPTIONS] YYYYMMDD PRODUCT
Usage: aggregoes do_year [OPTIONS] YYYYMMDD PRODUCT

Options:
  --sat [GOES-16]  Which satellite to use.
  --env TEXT       Which environment to use.
  --datadir PATH   Explicitly set your own directory to pull data from.
  --output PATH    Override the output filename.
  --simple         No filling, no sorting, just aggregate.
  --debug          Enable verbose/debug printing.
  --help           Show this message and exit.
```

Notes:

 - The PRODUCT argument should be a L1b or l2+ data short name.
 - --env will restrict to taking files only from the specified env, like OR, dn, etc. (case sensitive)
 - --output path to filename to write to instead of default behavior.
 - Using both --simple and --datadir will try to aggregate all data in your datadir, regardless of bounds
 - Taking tens of minutes is normal, a progress bar will indicate time remaining.

 ### goes_mount_base

 To use on a system where spades_[inst]_prod directories are not mounted under /nfs, use the environment
 variable `goes_mount_base` to locate them to aggregoes.

 The following is a recommended setup:

```
 mkdir -p ~/mounts/spades_[inst]_prod
 sshfs -o ro user@spadesdev:/nfs/spades_[inst]_prod ~/mounts/spades_[inst]_prod
 # with the nfs volume mounted locally, you can run aggregoes against that
 goes_mount_base=~/mounts/ aggregoes do_day [OPTIONS] YYYYMMDD PRODUCT
```

## High level overview

Aggregation works in two stages:

1. Create an AggreList object.
2. Evaluate the AggreList.

The AggreList object is a data structure that describes how to combine a set of files. The structure of the
AggreList specifies the order of the files, what pieces of those files to include, fill values between files,
as well as fill values and sorting inside files.

During stage 1, the AggreList is generated. The level of configuration given determines how much is done here.
At most, each file is inspected according to it's unlimited dimension and the variable that indexes it to determine
sorting and filling. No copying or writing to disk is done in this stage.

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

### Unlimited Dimension Config

The unlimited dimension config associates a particular unlimited dimension with a variable by which
it can be indexed.

For example, a file may have a dimension "record_number" which is indexed by a variable "time". Using
the Unlimited Dimension Configuration, we can specify to aggregate record_number such that the variable
"time" forms a monotonic sequence increasing at some expected frequency.

Here is what a typical L1b product aggregation output looks like:

```
"report_number": {
    "index_by": "time",
    "expected_cadence": {"report_number": 1},
}
```

The configuration allows to even index by multidimensional time: (ehem, mag)

```
"report_number": {
    "index_by": "OB_time",
    "other_dim_indicies": {"samples_per_record": 0},
    "expected_cadence": {"report_number": 1, "number_samples_per_report": 10},
}
```


### Product Config

The product config contains a lot of the same information as a NetCDF CDL would, but in json format, extended
with fields custom to aggregation.


## More than you wanted to know

An AggreList is composed of two types of objects, InputFileNode and FillNode objects. These inherit in common from an AbstractNode and must
implement the `get_size_along(unlimited_dim)` and `data_for(var, dim, att_processor)` methods. Evaluating an aggregation list is simply going
though the AggreList and calling something like:

 ```
write_slice = slice(written_up_to, written_up_to + node.get_size_along(dim))
nc_out.variable[var][write_slice] = node.data_for(var, dim, att_processor)
```

The `data_for` must return data consistent with the shape promised from `get_size_along`.

The complixity of aggregation comes in handling the dimensions and building the aggregation list. In addition to the interface exposed by an 
AbstractNode, each InputFileNode and FillNode implement Node specific functionality.

A FillNode is simpler, and needs to be told how many fills to insert along a certain unlimited dimension and optionally, can be configured to
return values from `data_for` that are increasing along multiple dimensions according to configured `expected_cadence` values from a certain start
value.


An InputFileNode is more complicated and exposes methods to find the time bounds of the file, and additionally, is internally capable 
of sorting itself and inserting fill values into itself. Of course, it doesn't modify the actual input file, this is all done on the fly as data is
being read out through `data_for`. Implementation wise, an InputFileNode may contain within itself a mini aggregation list containing two types of 
objects: slice and FillNode objects. Similarly to the large scale process of aggregating, an InputFileNode returns data that has been assembled 
according to it's internal aggregation list and internal sorting.


