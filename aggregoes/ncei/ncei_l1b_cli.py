from aggregoes.cli import ProgressAggregator as Aggregator
from aggregoes.ncei.ncei_l1b_mapper import get_files_for, get_product_config, get_runtime_config, get_output_filename
from aggregoes.ncei.ncei_l1b_mapper import mapping
from datetime import datetime, timedelta
import click
import logging
import os
from aggregoes.ncei.BufferedEmailHandler import BufferedEmailHandler
import atexit

@click.group()
def cli():
    pass


@cli.command()
@click.argument("yyyymmdd")
@click.argument("product", type=click.Choice(mapping.keys()))
@click.option("--sat", default="goes16", type=click.Choice(["goes16", "goes17", "goes18"]), help="Which satellite.")
@click.option("--env", default="OR", help="Which environment.")
@click.option("--email", "-e", multiple=True)
def agg_day(yyyymmdd, product, sat="goes16", env="OR", email=list()):

    if len(email) > 0:
        hostname = os.environ.get("HOSTNAME", "")
        username = os.environ.get("USER", "aggregation")
        email_handler = BufferedEmailHandler("%s@%s" % (username, hostname), email,
                                             "Aggregation errors - %s %s %s %s" % (yyyymmdd, product, sat, env))
        logging.getLogger().addHandler(email_handler)
        atexit.register(email_handler.finalize)

    start_time = datetime.strptime(yyyymmdd, "%Y%m%d")
    end_time = start_time + timedelta(days=1) - timedelta(microseconds=1)

    # get the files for the day, and add on first/last 60 files for the surrounding days, just in case
    # there is anything severely out of order.
    files = get_files_for(sat, product, start_time - timedelta(days=1), env)[-60:]
    files += get_files_for(sat, product, start_time, env)
    files += get_files_for(sat, product, start_time + timedelta(days=1), env)[:60]

    # Step 1: initialize the aggregator.
    product_config = get_product_config(product)
    a = Aggregator(config=product_config)

    runtime_config = get_runtime_config(product)
    runtime_config.values()[0].update({
        "min": start_time,
        "max": end_time
    })

    # Step 2: generate the aggregation list
    aggregation_list = a.generate_aggregation_list(files, runtime_config)
    output_filename = get_output_filename(sat, product, yyyymmdd, env)

    # Step 3: evaluate the aggregation list
    click.echo("Evaluating aggregation list...")
    a.evaluate_aggregation_list(aggregation_list, output_filename)

    click.echo("Finished: %s" % output_filename)


if __name__ == "__main__":

    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(console)

    cli()
