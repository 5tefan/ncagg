# Test remapping data

These data are from EXIS-L1b-SFEU, which has had some evolving issues. These tests
look at whether the ncagg can map all three of these file types into a consistent 
format. 

To do that, it will need to map data from regular to unlimited dimensions, 
and can make implicit dimension dependences explicit.


## type1

Initially files contained a dimension `report_number` that was supposed to be unlimited
but wasn't. For these data, test to see if we can map `report_number` to an unlimited dimension.


## type2 

Report number was fixed to be unlimited. This is a trivial case, if ncagg can
map type1 files into the output format, it can map type2 files as well.


# type3

EUVS files were modified to make `max_num_EUVS_C_obs_spectrum_interval` unlimited, but in
doing this, `report_number` was reverted again to NOT be unlimited, and the variable
euvscQualityFlags was originally `euvscQualityFlags(report_number, max_num_EUVS_C_obs_spectrum_interval)`
but got changed to `euvscQualityFlags(max_num_EUVS_C_obs_spectrum_interval)` (note removal of
`report_number`).

We will test to see if we can map type3 data into the consistent output format.
