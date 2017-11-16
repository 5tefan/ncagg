
# V0.4.0

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
