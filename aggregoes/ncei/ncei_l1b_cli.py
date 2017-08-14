from aggregoes.ncei.BufferedEmailHandler import BufferedEmailHandler
from aggregoes.aggregator import generate_aggregation_list, evaluate_aggregation_list
from aggregoes.ncei.ncei_l1b_mapper import get_files_for, get_product_config, get_runtime_config, get_output_filename
from aggregoes.ncei.ncei_l1b_mapper import mapping
from aggregoes.aggregator import FillNode
from aggregoes.validate_configs import Config
from datetime import datetime, timedelta
import tempfile
import click
import logging
import os
import sys
import shutil
import atexit

logger = logging.getLogger(__name__)


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
        # If any emails are specified with --email or -e options, set up an email handler
        # that will collect logging.error("msg") calls and email them to the recipient atexit.
        logger.debug("Configuring email error handler with recipients: %s" % email)
        hostname = os.environ.get("HOSTNAME", "")
        username = os.environ.get("USER", "aggregation")
        email_handler = BufferedEmailHandler("%s@%s" % (username, hostname), email,
                                             "Aggregation errors - %s %s %s %s" % (yyyymmdd, product, sat, env))
        logging.getLogger().addHandler(email_handler)
        atexit.register(email_handler.finalize)  # on exit, send the queued error messages

    start_time = datetime.strptime(yyyymmdd, "%Y%m%d")
    end_time = start_time + timedelta(days=1) - timedelta(microseconds=1)

    # get the files for the day, and add on first/last 60 files for the surrounding days, just in case
    # there is anything severely out of order.
    files = get_files_for(sat, product, start_time - timedelta(days=1), env)[-60:]
    files += get_files_for(sat, product, start_time, env)
    files += get_files_for(sat, product, start_time + timedelta(days=1), env)[:60]
    logger.debug("Found %s files total" % len(files))

    if len(files) == 0:
        logger.info("No files to aggregate! Exiting.")
        return

    config = get_product_config(product)  # type: Config

    # Runtime_config has dimension configurations. Keys are dims, v is indexing info
    # about that dim.
    runtime_config = get_runtime_config(product)
    for k, v in runtime_config.iteritems():
        v.update({
            "min": start_time,
            "max": end_time
        })
        config.dims[k].update(v)

    # Generate the aggregation list.
    agg_list = generate_aggregation_list(config, files)
    logger.debug("Aggregation list contains %s items" % len(agg_list))

    if len(agg_list) == 1 and isinstance(agg_list[0], FillNode):
        logger.info("Aggregation contains only FillValues! Exiting.")
        return

    # Evaluate it to a temporary working file.
    logger.info("Evaluating aggregation list...")
    _, tmp_filename = tempfile.mkstemp(prefix="agg_%s_%s" % (product, yyyymmdd))
    with click.progressbar(label="Aggregating...", length=len(agg_list)) as bar:
        evaluate_aggregation_list(config, agg_list, tmp_filename, lambda: next(bar))

    # Rename (atomicish move) it to the final filename.
    final_filename = get_output_filename(sat, product, yyyymmdd, env)
    shutil.move(tmp_filename, final_filename)
    os.chmod(final_filename, 0o664)
    logger.info("Finished: %s" % final_filename)
    click.echo(final_filename)


if __name__ == "__main__":

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(console)

    cli()
