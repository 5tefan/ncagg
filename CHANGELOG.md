


# v0.3.2

- Fix: Make sure Nans are replaced by a variable's `_FillValue`.
- Feature: Allow specification of new dimensions through Config.
    New dimensions specified in the config are implicitly a dimension
    representing dependence on file and so use size 1 for each input 
    file. (Behavior of added dimensions under non default UDC configs
    has not been tested and may not work.)
- Repo: Started keeping CHANGELOG document.
