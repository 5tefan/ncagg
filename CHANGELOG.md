# v0.6.2 - 2018-02-27

Fixes:
 - Improvents to boundary calculations...
    - prevent chop initial record if too close to start bound.
    - prevent chop of final record if too close to end bound.
    - Fill backwards @ `expected_cadence` from next available
        time value when a previous one isn't available, eg. at
        beginning of day.

# v0.6.0 - 2018-01-24

Bug fixes and new attribute strategy:

 - Adds ncagg_version global attribute strategy
 - Revise creation of the Aggregation List, primarily addressing overlapping
    single record granules.

# v0.5.0

Support piped list of files to aggregate in case [Argument list too long] encountered
when attempting to pass argument in commandline.

eg: `find /path/to/files -type f -name "*.nc" | ncagg output.nc`

# v0.4.5

Minor changes, 5 patch increments because of some mistakes on my part creating releases:

- `aggregate` function and `Config` class available in root (ncagg) namespace.
- correctly handle changed `valid_min` and `valid_max` in template.
- Fix StratStatic "static" attribute stragey implementation, adds test for it.

# v0.4.0

Minor version bump because `template-ncagg` command is gone, everything
is in `ncagg` now. (delaying v1.0.0 for a seriously mature version).

- Feature: `ncagg -v` prints version info.
- Change: Former `template-ncagg` command removed, use `ncagg --generate_template [example.nc]` now.
- Adds: New strategies: StratFirstInputFilename, StratLastInputFilename, StratCountInputFiles


# v0.3.3

- Adds: StratStatic global attribute handler, for predefined static values.
- Fix: output format of template generator
- Minor documentation improvements.


# v0.3.2

- Fix: Make sure Nans are replaced by a variable's `_FillValue`.
- Feature: Allow specification of new dimensions through Config.
    New dimensions specified in the config are implicitly a dimension
    representing dependence on file and so use size 1 for each input 
    file. (Behavior of added dimensions under non default UDC configs
    has not been tested and may not work.)
- Repo: Started keeping CHANGELOG document.
