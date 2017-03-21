from aggregoes.aggregator import Aggregator
from aggregoes.utils.data_location_mapper import DataLocationMapper as DataLocationMapper
from datetime import datetime, timedelta
from glob import glob
import click
import os

"""
All data is expected to be in a YYYYMMDD structure under the path
returned by DataLocationMapper.
"""


class ProgressAggregator(Aggregator):
    def evaluate_aggregation_list(self, aggregation_list, to_fullpath, callback=None):
        with click.progressbar(label="Aggregating...", length=len(aggregation_list)) as bar:
            super(ProgressAggregator, self).evaluate_aggregation_list(
                aggregation_list,
                to_fullpath,
                lambda: next(bar)
            )


@click.group()
def cli():
    pass


@cli.command()
@click.argument("yyyymmdd")
@click.argument("product")
@click.option("--sat", default="GOES-16", type=click.Choice(["GOES-16"]), help="Which satellite to use.")
@click.option("--env", default="", help="Which environment to use.")
@click.option("--datadir", default=None, help="Explicitly set your own directory to pull data from.")
@click.option("--output", default=None, help="Override the output filename.")
@click.option("--simple", is_flag=True, help="No filling, no sorting, just aggregate.")
@click.option("--debug", is_flag=True, help="Enable verbose/debug printing.")
def do_day(yyyymmdd, product, sat="GOES-16", env="", datadir=None, output=None, simple=False, debug=False):
    start_time = datetime.strptime(yyyymmdd, "%Y%m%d")
    end_time = start_time + timedelta(days=1) - timedelta(microseconds=1)

    mapper = DataLocationMapper(sat)
    if datadir is None:
        time_dir_base = mapper.get_product(product)
        files = glob(os.path.join(time_dir_base, start_time.strftime("%Y/%m/%d"), "%s*.nc" % env))
        # add the day before and the day after as well, just in case (yes, really only need maybe
        # a couple of bounding files, but this is the lazy approach).
        if not simple:
            files += glob(os.path.join(time_dir_base, (start_time-timedelta(days=1)).strftime("%Y/%m/%d"), "%s*.nc" % env))
            files += glob(os.path.join(time_dir_base, (start_time+timedelta(days=1)).strftime("%Y/%m/%d"), "%s*.nc" % env))
    else:
        files = glob(os.path.join(datadir, "%s*.nc" % env))

    # TODO: when primary is implemented
    runtime_config = mapper.get_config(product)
    runtime_config.values()[0].update({
        "min": start_time,
        "max": end_time
    })

    a = ProgressAggregator()
    aggregation_list = a.generate_aggregation_list(files, runtime_config if not simple else None)

    if debug:
        print aggregation_list

    if output is None or not isinstance(output, str):
        output = os.path.join(mapper.get_output_base(product), mapper.get_filename(product, yyyymmdd, env))

    click.echo("Evaluating aggregation list...")
    a.evaluate_aggregation_list(aggregation_list, output)
    click.echo("Finished: %s" % output)


@cli.command()
@click.argument("yyyymm")
@click.argument("product")
@click.option("--sat", default="GOES-16", type=click.Choice(["GOES-16"]), help="Which satellite to use.")
@click.option("--env", default="", help="Which environment to use.")
@click.option("--datadir", default=None, help="Override the directory to pull data from.")
@click.option("--output", default=None, help="Override the output filename.")
@click.option("--simple", is_flag=True, help="No filling, no sorting, just aggregate.")
@click.option("--debug", is_flag=True, help="Enable verbose/debug printing.")
def do_month(yyyymm, product, sat="GOES-16", env="", datadir=None, output=None, simple=False, debug=False):
    start_time = datetime.strptime(yyyymm, "%Y%m")
    if start_time.day < 12:
        end_time = datetime(start_time.year, start_time.month + 1, start_time.day) - timedelta(microseconds=1)
    else:
        end_time = datetime(start_time.year + 1, 1, 1) - timedelta(microseconds=1)

    mapper = DataLocationMapper(sat)
    if datadir is None:
        time_dir_base = mapper.get_product(product)
        files = glob(os.path.join(time_dir_base, start_time.strftime("%Y/%m/**"), "%s*.nc" % env))
        # add the day before and the day after as well, just in case (yes, really only need maybe
        # a couple of bounding files, but this is the lazy approach).
        if not simple:
            files += glob(os.path.join(time_dir_base, (start_time-timedelta(days=1)).strftime("%Y/%m/%d"), "%s*.nc" % env))
            files += glob(os.path.join(time_dir_base, (end_time+timedelta(days=1)).strftime("%Y/%m/%d"), "%s*.nc" % env))
    else:
        files = glob(os.path.join(datadir, "%s*.nc" % env))

    # TODO: when primary is implemented
    runtime_config = mapper.get_config(product)
    runtime_config.values()[0].update({
        "min": start_time,
        "max": end_time
    })

    a = ProgressAggregator()
    aggregation_list = a.generate_aggregation_list(files, runtime_config if not simple else None)

    if debug:
        print aggregation_list

    if output is None or not isinstance(output, str):
        output = os.path.join(mapper.get_output_base(product), mapper.get_filename(product, yyyymm, env))

    click.echo("Evaluating aggregation list...")
    a.evaluate_aggregation_list(aggregation_list, output)
    click.echo("Finished: %s" % output)

@cli.command()
@click.argument("yyyy")
@click.argument("product")
@click.option("--sat", default="GOES-16", type=click.Choice(["GOES-16"]), help="Which satellite to use.")
@click.option("--env", default="", help="Which environment to use.")
@click.option("--datadir", default=None, help="Override the directory to pull data from.")
@click.option("--output", default=None, help="Override the output filename.")
@click.option("--simple", is_flag=True, help="No filling, no sorting, just aggregate.")
@click.option("--debug", is_flag=True, help="Enable verbose/debug printing.")
def do_year(yyyy, product, sat="GOES-16", env="", datadir=None, output=None, simple=False, debug=False):
    start_time = datetime.strptime(yyyy, "%Y")
    end_time = datetime(start_time.year + 1, 1, 1) - timedelta(microseconds=1)

    mapper = DataLocationMapper(sat)
    if datadir is None:
        time_dir_base = mapper.get_product(product)
        files = glob(os.path.join(time_dir_base, start_time.strftime("%Y/**/**"), "%s*.nc" % env))
        # add the day before and the day after as well, just in case (yes, really only need maybe
        # a couple of bounding files, but this is the lazy approach).
        if not simple:
            files += glob(os.path.join(time_dir_base, (start_time-timedelta(days=1)).strftime("%Y/%m/%d"), "%s*.nc" % env))
            files += glob(os.path.join(time_dir_base, (end_time+timedelta(days=1)).strftime("%Y/%m/%d"), "%s*.nc" % env))
    else:
        files = glob(os.path.join(datadir, "%s*.nc" % env))

    # TODO: when primary is implemented
    runtime_config = mapper.get_config(product)
    runtime_config.values()[0].update({
        "min": start_time,
        "max": end_time
    })

    a = ProgressAggregator()
    aggregation_list = a.generate_aggregation_list(files, runtime_config if not simple else None)

    if debug:
        print aggregation_list

    if output is None or not isinstance(output, str):
        output = os.path.join(mapper.get_output_base(product), mapper.get_filename(product, yyyy, env))

    click.echo("Evaluating aggregation list...")
    a.evaluate_aggregation_list(aggregation_list, output)
    click.echo("Finished: %s" % output)


if __name__ == "__main__":
    cli()
