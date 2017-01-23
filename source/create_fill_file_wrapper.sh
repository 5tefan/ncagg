
#!/usr/bin/env bash

# wrapper script to execute create_fill_file.py.

python create_fill_file.py /data/backup/GOES_R/data/samples/EXIS-L1b-SFXR_header.nc -s 2016-11-01T00:00:00.0 -e 2016-11-02T00:00:00.0 -o /data/backup/GOES_R/goes-r/l1/aggregation/output -r 1.0
