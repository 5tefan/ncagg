# Generating the config

The config is generated with `ncagg --generate_template OR_EXIS-L1b-SFXR_G16_s20231431621001_e20231431621296_c20231431621299.nc > copy_from_alt_config.json`
and then modified by adding the `input_file` dimension, and finally adding the `input_file`
dimension to the `SPP_roll_angle` variable.

This must be done, otherwise ncagg pulls the scalar value and doesn't actually aggregate. No
dependence on an unlimited dimension means no aggregation.

