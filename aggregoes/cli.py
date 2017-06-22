from aggregoes.aggregator import Aggregator
import click
from datetime import datetime
import logging


class ProgressAggregator(Aggregator):
    def evaluate_aggregation_list(self, aggregation_list, to_fullpath, callback=None):
        with click.progressbar(label="Aggregating...", length=len(aggregation_list)) as bar:
            super(ProgressAggregator, self).evaluate_aggregation_list(
                aggregation_list,
                to_fullpath,
                lambda: next(bar)
            )


def parse_time(dt_str):
    """
    Parse a YYYYMMDD[HH[MM]] type string. HH and MM are optional.
    :param dt_str: datetime string to parse
    :return: interpreted datetime
    """
    year = int(dt_str[:4])
    month = int(dt_str[4:6])
    day = int(dt_str[6:8] or 1)
    hour = int(dt_str[8:10] or 0)
    minute = int(dt_str[10:12] or 0)
    return datetime(year, month, day, hour, minute)


@click.command()
@click.argument("dst", type=click.Path(exists=False))
@click.argument("src", nargs=-1, type=click.Path(exists=True))
@click.option("-u", help="Give an Unlimited Dimension Configuration as udim:ivar[:hz[:hz]]")
@click.option("-b", help="If -u given, specify bounds for ivar as min:max. min and max should be numbers, or "
                         "start with T to indicate a time and then should be TYYYYMMDD[HH[MM]] format.")
def cli(dst, src, u=None, b=None):
    runtime_config = {}
    if u is not None:
        # we have an Unlimited Dim Configuration, fill out runtime_config
        u_split = u.split(":")
        runtime_config[u_split[0]] = {
            "index_by": u_split[1]
        }
        if len(u_split) > 2:
            # TODO: handle multidim indexby, might have to look in one of the src files.
            runtime_config[u_split[0]]["expected_cadence"] = {u_split[0]: float(u_split[2])}

        if b is not None:
            b_split = b.split(":")
            if not len(b_split) == 2: raise click.BadParameter("Expected min:max format.", param="-b")
            if b_split[0].startswith("T"):
                # parse as a time indication, cut out the T before sending to parse
                b_split[0] = parse_time(b_split[0][1:])
                b_split[1] = parse_time(b_split[1][1:])
            else:
                # otherwise convert to numerical
                b_split = map(float, b_split)

            runtime_config[u_split[0]]["min"] = b_split[0]
            runtime_config[u_split[0]]["max"] = b_split[1]

    # Step 2: generate the aggregation list
    a = ProgressAggregator()
    aggregation_list = a.generate_aggregation_list(src, runtime_config)

    # Step 3: evaluate the aggregation list
    click.echo("Evaluating aggregation list...")
    a.evaluate_aggregation_list(aggregation_list, dst)
    click.echo("Finished: %s" % dst)


if __name__ == "__main__":

    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(console)

    cli()
