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
  --datadir TEXT   Explicitly set your own directory to pull data from.
  --output TEXT    Override the output filename.
  --debug          Enable verbose/debug printing.
  --help           Show this message and exit.
```

Notes:

 - The PRODUCT argument should be a L1b or l2+ data short name.
 - --env will restrict to taking files only from the specified env, like OR, dn, etc. (case sensitive)
 - --output to your own path instead of /nfs/goesr-private
 - Taking tens of minutes is normal, a progress bar will indicate time remaining.

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

