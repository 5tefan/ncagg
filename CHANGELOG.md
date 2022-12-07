# 0.8.15 - 2022-11-30

- Fix bug: config fill value was ignored, reverting to netcdf default.

# 0.8.14 - 2022-10-03

- use long_description_content_type="text/markdown" in setup.py
- unpin click dep, tested with latest 8.1.3

# 0.8.13 - 2022-08-11

 - New feature: Support cli chunksize specification with `-c udim:chunksize`.
 - Fix: avoid TypeError crash if `index_by` given without an `expected_cadence` in UDC.

# 0.8.12 - 2020-04-05

 - Fix corrupt test data files (?!). 
 - Drop support for Python 2.7 and 3.6.
 - Update requirements.

# 0.8.11 - 2020-01-27

 - Removes test file that was causing issues with netCDF4-Python versions 1.5.{2,3}. Fixes #3.
 - Adjust calculation for number of fill values at beginning of interval.

# 0.8.10 - 2019-04-17

 - Fixes compatibility with Click version 7.0, now tested with Click version 6.7 and 7.

# 0.8.9 - 2019-02-21

 - Improve robustness of condition detecting gap at beginning
    of an aggregation.

# 0.8.8 - 2019-02-15

 - Perfects calculation of filling between files.
 - Perfects calculation of filling inside files. 

# 0.8.6 - 2019-02-12

 - Fixes issue with chopping at end boundary where negative size
    is fine while building preliminary aggregation list as long as
    it does not end up in the final.

# 0.8.5 - 2018-12-27

 - Fix handling of vlen (string) netcdf datatypes
 - Fix Python3 compatibility in cli and attribute handling
 - Resolves FutureWarning that was appearing with numpy 1.15.1

# 0.8.4 - 2018-07-18

- Further addressing numerical stability issues.

# 0.8.3 - 2018-07-09

- Setup Sphinx documentation
- Fix numerical issue in calculating start bound affecting
    aggregations where granule starts exactly on aggregation
    start bound.

# 0.8.2 - 2018-07-05

- Fixes an issue caused by aggregating over all fill value files.

# 0.8.1 - 2018-07-02

- Suppress Error logging for missing variable in input file.
    This scenario is supported and anticipated that files do 
    not have some variable contained within the template. Just
    move along. Considering adding more sophisticated handling
    of this with "strict" mode.
- Previous gap_between and num_overlap calculation was not tight
    enough, see new test case. Calculation on bound tightened.
    
# 0.8.0 - 2018-06-29

Fixes issue causing record immediately before unlim
dim start boundary would be included. 

# v0.7.1 - 2018-06-07

Fixes 2 issues:
 - Occasional non-fatal FutureWarning in attributes handling.
 - Error initializing config from netcdf file.

# v0.7.0 - 2018-05-25

When configured with an expected cadence, ncagg allows
some wiggle room (instruments may not have perfect time
steps). Previously, for the start of aggregation boundary
ncagg used (boundary - minimum expected timestep), this 
resulted in frequently excluding the first time step. Now
at beginning bound, subtract nominal time step.

A full minor increment because this will have significant
impact on our datasets. 

# v0.6.4 - 2018-05-10

Changes:
 - Some optimizations: users should see faster aggregations.
    I expect the improvement to scale relative to the number
    of variables per file being aggregated. 

# v0.6.3 - 2018-03-30

Changes:
 - Except and log errors from copying one time only variables
    (ones that don't depend on an unlimited dim)
 - attr strats, default self.attr value is None instead of
    empty string.

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
