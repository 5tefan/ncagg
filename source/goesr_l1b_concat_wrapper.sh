
#!/usr/bin/env bash

# wrapper script to execute python L1b file aggregation routine.

export PYTHONPATH=$PYTHONPATH:/data/backup/GOES_R/goes-r/l2/common/goesr/data

python goesr_l1b_concat.py l1b_concat.json -d 2016-09-26
