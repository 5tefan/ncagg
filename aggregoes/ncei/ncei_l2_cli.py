from aggregoes.cli import ProgressAggregator as Aggregator
from aggregoes.ncei.BufferedEmailHandler import BufferedEmailHandler
from aggregoes.ncei.ncei_l2_mapper import get_files_for, get_product_config, get_runtime_config, get_output_filename
from aggregoes.ncei.ncei_l2_mapper import mapping
from aggregoes.aggregator import FillNode, InputFileNode
from datetime import datetime, timedelta
import tempfile
import click
import logging
import re
import os
import sys
import shutil
import atexit

logger = logging.getLogger(__name__)


def reduce_version(versions):
    """
    Given a list of version, determine what the output version should be. Examples:
    1_0_0, 1_0_0, ...   => 1_0_0
    1_0_0, 1_0_1        => 1_0_0-1
    1_0_0, 2_0_0        => 1-2_0_0
    1_0_0, 1_0_1, 2_0_0 => 1-2_0_x
    
    :rtype: list[str]
    :param versions: A list of versions a_b_c where a, b, c are decimal major, minor and patch
    :return: version for concatenated file
    """
    def cmp(a_str, b_str):
        a = map(lambda s: s.split("-"), a_str.split("_"))  # eg 1-2_0_0 => [[1,2], [0], [0]]
        b = map(lambda s: s.split("-"), b_str.split("_"))
        assert len(a) == len(b) == 3, "Expected 3 element versions, found %s and %s" % (a_str, b_str)
        change_detected = reduce(   # list of booleans, moving left to right, indicating if
                                    # a change in version has been detected yet
            lambda acc, n: acc + [True] if acc[-1] else acc + [n[0] != n[1]],
            zip(a, b),  # so n above is a tuple containing 2 arrays
            [False]    # initialize acc (accumulator) with no change detected.
        )[:-1]  # shift over by 1 so that change is True _after_ detection. Works because initialization with False.

        def cmp_comp(x, y, c):
            if c and x != y:
                return "x"
            else:
                return "-".join(sorted(set(x+y)))
        return "_".join(map(cmp_comp, a, b, change_detected))

    return reduce(cmp, set(versions))


cli = click.group()(lambda: None)


@cli.command()
@click.argument("yyyymmdd")
@click.argument("product", type=click.Choice(mapping.keys()))
@click.option("--sat", default="goes16", type=click.Choice(["goes16", "goes17", "goes18"]), help="Which satellite.")
@click.option("--env", default="dr", help="Which environment.")
@click.option("--email", "-e", multiple=True)
def agg_day(yyyymmdd, product, sat="goes16", env="dr", email=list()):

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

    product_config = get_product_config(product)
    a = Aggregator(config=product_config)

    runtime_config = get_runtime_config(product)
    runtime_config.values()[0].update({
        "min": start_time,
        "max": end_time
    })

    # Generate the aggregation list.
    aggregation_list = a.generate_aggregation_list(files, runtime_config)
    logger.debug("Aggregation list contains %s items" % len(aggregation_list))

    # derive version from the file names - first get list of filename from nodes that are InputFileNodes
    file_names = map(lambda x: x.filename, filter(lambda n: isinstance(n, InputFileNode), aggregation_list))
    version_match = re.compile("_v(?P<ver>[0-9][-0-9]*_[0-9x][-0-9]*_[0-9x][-0-9]*)")
    def get_version(from_filename):
        """Return version string or None if not found in from_filename."""
        match = version_match.search(from_filename)
        if match is not None:
            return match.group("ver")
    version = reduce_version(filter(lambda x: x is not None, map(lambda n: get_version(n), file_names)))

    # Initialize the aggregator.

    if len(aggregation_list) == 1 and isinstance(aggregation_list[0], FillNode):
        logger.info("Aggregation contains only FillValues! Exiting.")
        return

    # Evaluate it to a temporary working file.
    logger.info("Evaluating aggregation list...")
    _, tmp_filename = tempfile.mkstemp(prefix="agg_%s_%s" % (product, yyyymmdd))
    a.evaluate_aggregation_list(aggregation_list, tmp_filename)

    # Rename (atomicish move) it to the final filename.
    final_filename = get_output_filename(sat, product, yyyymmdd, env, version)
    shutil.move(tmp_filename, final_filename)
    os.chmod(final_filename, 0o664)
    logger.info("Finished: %s" % final_filename)
    click.echo(final_filename)


if __name__ == "__main__":

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(console)

    cli()

