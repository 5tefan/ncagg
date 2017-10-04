# Test creating new dimension

These data are from a second version of EXIS-L1b-SFXR which now
includes SUVI_CROTA and SUVI_CROTA_time as variables with no dimension
associated with them.... So in every file, there is one value for each
of these.

In aggregation, the original variable would not be acceptable as it
does not depend on an unlimited and so only the first value would get
transferred.

To solve, a new unlimited dimension is specified in the template based
on the default. The new unlimited is called `crota_report_number` here
and SUVI_CROTA and SUVI_CROTA_time are specified to depend on this.

In this test, we ensure that this kind of remapping is handled
as expected.

