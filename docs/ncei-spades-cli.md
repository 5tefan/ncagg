# ncei-spades-cli

This cli is for `/nfs/spades_[inst]_prod/archive` data. 

ncei-l1b-cli is a command line interface implemented for aggregation of SPADES data at NCEI. It wraps the basic functionality
of the core aggregation routines with routines to interface with data and configuration specific to our SPADES setup. 
It will gather the inputs, lookup the output product configuration, and specify an output file according to the
file naming convention and expected output location.

On the command line, use `ncei-spades-cli`:

```
Usage: ncei-spades-cli do_day [OPTIONS] YYYYMMDD PRODUCT
Usage: ncei-spades-cli do_month [OPTIONS] YYYYMMDD PRODUCT
Usage: ncei-spades-cli do_year [OPTIONS] YYYYMMDD PRODUCT

Options:
  --sat [GOES-16]  Which satellite to use.
  --env TEXT       Which environment to use.
  --datadir PATH   Explicitly set your own directory to pull data from.
  --output PATH    Override the output filename.
  --simple         No filling, no sorting, just aggregate.
  --debug          Enable verbose/debug printing.
  --help           Show this message and exit.
```

## NOTE


For other aggregation operations, other clis may be more appropriate:
 - The general cli for aggregating arbitrary files - [README.md](README.md)
 - For aggregation workspace specific aggregation, see [ncei-l1b-cli](docs/ncei-l1b-cli.md)

