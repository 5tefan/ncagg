import sys
import json
import logging
from datetime import datetime, timedelta

import click
import pkg_resources

from .aggregator import generate_aggregation_list, evaluate_aggregation_list
from .config import Config

try:
    version = pkg_resources.require("ncagg")[0].version
except pkg_resources.DistributionNotFound:
    # if version unknwon - you're probably running cli from a clone of the repo, not setup through setuputils/pip
    # if version is wrong - same as above, but you probably have an older version installed through setuputils
    version = "unknown"

logger = logging.getLogger(__name__)


def parse_time(dt_str):
    """
    Parse a YYYYMMDD[HH[MM]] type string. HH and MM are optional.

    :param dt_str: datetime string to parse
    :return: interpreted datetime
    """
    year = int(dt_str[:4])
    month = int(dt_str[4:6] or 1)
    day = int(dt_str[6:8] or 1)
    hour = int(dt_str[8:10] or 0)
    minute = int(dt_str[10:12] or 0)
    return datetime(year, month, day, hour, minute)


def parse_bound_arg(b):
    # type: (str) -> (datetime, datetime)
    """
    Parse a "-b" argument specifying bounds of aggregation. Bounds are min:max or Tstart[:[T]stop].
    start and stop are of the form YYYY[MM[DD[HH[MM]]]]. If only Tstart is provided, the end (Tstop)
    is assumed to be an increment of the least significant portion specified.

    :param b: String bound specifier to parse into start and end time.
    :return: tuple of parsed (start datetime, end datetime)
    """
    b_split = b.split(":")
    if b_split[0].startswith("T"):
        # parse as a time indication, cut out the T before sending to parse
        if len(b_split) == 2:
            b_split[0] = parse_time(b_split[0][1:])
            # friendly cli: for the second bound, ignore whether it starts with a T or not.
            b_split[1] = parse_time(b_split[1][1:] if b_split[1].startswith("T") else b_split[1])
        elif len(b_split) == 1:
            # if there's only one, infer dayfile, monthfile, or yearfile based on the length
            if len(b_split[0][1:]) == 4:  # infer -bTYYYY:TYYYY+1
                b_split[0] = parse_time(b_split[0][1:])
                b_split.append(datetime(b_split[0].year + 1, 1, 1) - timedelta(microseconds=1))
            elif len(b_split[0][1:]) == 6:  # infer -bTYYYYMM:TYYYYMM+1
                b_split[0] = parse_time(b_split[0][1:])
                # datetime month must be in 1..12, so if month+1 == 13, increment year
                next_month = b_split[0].month + 1
                if next_month > 12:
                    assert next_month == 13
                    next_year = b_split[0].year + 1
                    next_month = 1
                else:
                    next_year = b_split[0].year
                b_split.append(datetime(next_year, next_month, 1) - timedelta(microseconds=1))
            elif len(b_split[0][1:]) == 8:  # infer -bTYYYYMMDD:TYYYYMMDD+1
                b_split[0] = parse_time(b_split[0][1:])
                b_split.append(b_split[0] + timedelta(days=1) - timedelta(microseconds=1))
            elif len(b_split[0][1:]) == 10:  # infer -bTYYYYMMDDHH:TYYYYMMDDHH+1
                b_split[0] = parse_time(b_split[0][1:])
                b_split.append(b_split[0] + timedelta(hours=1) - timedelta(microseconds=1))
            elif len(b_split[0][1:]) == 12:  # infer -bTYYYYMMDDHHMM:TYYYYMMDDHHMM+1
                b_split[0] = parse_time(b_split[0][1:])
                b_split.append(b_split[0] + timedelta(minutes=1) - timedelta(microseconds=1))
        else:
            raise click.BadParameter("")
    else:
        if not len(b_split) == 2:
            raise click.BadParameter("Expected min:max format.", param="-b")
        # otherwise convert to numerical
        b_split = map(float, b_split)

    assert len(b_split) == 2
    return b_split


def print_config(ctx, param, sample_netcdf):
    # type: (click.Context, str, str) -> None
    """
    Click callback to print a json config generated from the sample_netcdf and exit.

    :param ctx: click.Context
    :param param: name of the parameter, irrelevant here.
    :param sample_netcdf: string path to sample_netcdf
    :return: None
    """
    if not sample_netcdf or ctx.resilient_parsing:
        return
    the_config = Config.from_nc(click.format_filename(sample_netcdf)).to_dict()
    click.echo(json.dumps(the_config, sort_keys=True, indent=4))
    ctx.exit()


src_path_type = click.Path(exists=True, dir_okay=False)


def get_src_from_stdin(ctx, param, value):
    # type: (click.Context, str, object) -> list[str]
    """
    Click callback to parse standard input (stdin) as a whitespace separated list of files.

    :param ctx: click.Context
    :param param: name of the parameter to parse
    :param value: the command line argument value of the parameter
    :return: a list of files parsed from stdin
    """
    stdin = click.get_text_stream("stdin")
    if not value and not stdin.isatty():
        f = lambda should_be_file: src_path_type.convert(should_be_file, param, ctx)
        value = list(map(f, stdin.read().strip().split()))
        if not value:
            # otherwise, nothing found
            raise click.BadParameter(
                "No files provided as argument or via stdin.",
                ctx=ctx,
                param=param,
            )
    elif not value:
        # otherwise, nothing found
        raise click.BadParameter("No files provided as argument or via stdin.", ctx=ctx, param=param)
    return value


@click.command()
@click.version_option(version, "-v", "--version")
@click.option(
    "--generate_template",
    callback=print_config,
    expose_value=False,
    is_eager=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Print the default template generated for PATH and exit.",
)
@click.argument("dst", type=click.Path(exists=False, dir_okay=False))
@click.argument("src", nargs=-1, callback=get_src_from_stdin, type=src_path_type)
@click.option(
    "-u",
    help="Give an Unlimited Dimension Configuration as udim:ivar[:hz[:hz]]",
)
@click.option(
    "-c",
    help="Give an Chunksize Configuration as udim:chunksize to chunk the ulimited dimension udim by chunksize",
)
@click.option(
    "-b",
    help="If -u given, specify bounds for ivar as min:max or Tstart[:[T]stop]. "
    "min and max are numerical, otherwise T indicates start and stop are times."
    "start and stop are of the form YYYY[MM[DD[HH[MM]]]] and of stop is omitted,"
    "it will be inferred to be the least significantly specified date + 1.",
)
@click.option(
    "-l",
    help="log level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="WARNING",
)
@click.option("-t", help="Specify a configuration template", type=click.File("r"))
def cli(dst, src, u=None, c=None, b=None, l="WARNING", t=None):
    """ Aggregate NetCDF files. """
    logging.getLogger().setLevel(l)
    if t is not None:  # if given a template...
        config = Config.from_dict(json.load(t))
    else:  # otherwise, use the first src file to create a default
        config = Config.from_nc(src[0])  # config from first input.

    if u is not None:
        # we have an Unlimited Dim Configuration, fill out.
        u_split = u.split(":")
        dim_indexed, index_by = u_split[:2]
        config.dims[dim_indexed].update({"index_by": index_by})
        for i, cadence in enumerate(u_split[2:]):
            dim = config.vars[index_by]["dimensions"][i]
            config.dims[dim_indexed]["expected_cadence"].update({dim: float(cadence)})

        if b is not None:
            start, stop = parse_bound_arg(b)
            config.dims[dim_indexed].update({"min": start, "max": stop})

    if c is not None:
        # chunksize specified... apply to config
        c_split = c.split(":")
        udim = c_split[0]
        chunksize = int(c_split[1])
        if udim not in config.dims.keys():
            logger.warning(f"Chunksize specified for non-existent dimension {udim}")
        else:
            for var in config.vars.values():
                if udim in var["dimensions"]:
                    udim_index = var["dimensions"].index(udim)
                    var["chunksizes"][udim_index] = chunksize

    # Step 2: generate the aggregation list
    aggregation_list = generate_aggregation_list(config, src)

    # Step 3: evaluate the aggregation list
    click.echo("Evaluating aggregation list...")
    with click.progressbar(label="Aggregating...", length=len(aggregation_list)) as bar:
        evaluate_aggregation_list(config, aggregation_list, dst, lambda: bar.update(1))
    click.echo("Finished: %s" % dst)


# set logging handler to lowest level: DEBUG to catch everything,
# on the fly set of log level in CLI happens on root logger, everything should
# flow through the root logger anyway. Also, code use of ncagg shouldn't import
# anything from CLI, so I don't expect this to be a problem setting up a handler
# in this scope.
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.DEBUG)
logging.getLogger().addHandler(console)

if __name__ == "__main__":
    cli()
