# ncei-l1b-cli

This cli is for `/nfs/goesr_private/internal/aggregation/workspace` data. 

ncei-l1b-cli is a command line interface implemented for aggregation at NCEI. It wraps the basic functionality
of the core aggregation routines with routines to interface with data and configuration specific to our systems. 
It will gather the inputs, lookup the output product configuration, and specify an output file according to the
file naming convention and expected output location.

This specific cli is intended to run on a cron, producing L1b day files. It takes data from the aggregation 
workspace and outputs day files into the l1b/data directory. 

On the command line, use `ncei-l1b-cli`:

```
Usage: ncei-l1b-cli agg_day [OPTIONS] YYYYMMDD PRODUCT

Options:
  --sat [goes16|goes17|goes18]  Which satellite.
  --env TEXT                    Which environment.
  --help                        Show this message and exit.
```

## NOTE

It's unlikely that anyone will be manually running this cron, especially since it's intended that aggregation 
workspace data (the granules) will be delete sometime not too long after being aggregated. Justifying, granules
will be stored forever in CLASS and we want to store only one copy of the data (in day file format) on disk to
serve to users.

For manual aggregation operations, other clis may be more appropriate:

 - The general cli for aggregating arbitrary files - [README.md](../README.md)
 - For SPADES specific aggregation (from /nfs/spades_[inst]_prod), see [ncei-spades-cli](ncei-spades-cli.md)

