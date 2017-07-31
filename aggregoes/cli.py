from aggregoes.aggregator import Aggregator
import click
from datetime import datetime, timedelta
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
    month = int(dt_str[4:6] or 1)
    day = int(dt_str[6:8] or 1)
    hour = int(dt_str[8:10] or 0)
    minute = int(dt_str[10:12] or 0)
    return datetime(year, month, day, hour, minute)

def parse_bound_arg(b):
    """
    Parse a -b argument specifying bounds of aggregation. Bounds are min:max or Tstart[:[T]stop].
    start and stop are of the form YYYY[MM[DD[HH[MM]]]]
    :param b:
    :return:
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
                b_split.append(datetime(b_split[0].year+1, 1, 1) - timedelta(microseconds=1))
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
        if not len(b_split) == 2: raise click.BadParameter("Expected min:max format.", param="-b")
        # otherwise convert to numerical
        b_split = map(float, b_split)

    assert len(b_split) == 2
    return b_split


@click.command()
@click.argument("dst", type=click.Path(exists=False))
@click.argument("src", nargs=-1, type=click.Path(exists=True))
@click.option("-u", help="Give an Unlimited Dimension Configuration as udim:ivar[:hz[:hz]]")
@click.option("-b", help="If -u given, specify bounds for ivar as min:max or Tstart[:[T]stop]. "
                         "min and max are numerical, otherwise T indicates start and stop are times."
                         "start and stop are of the form YYYY[MM[DD[HH[MM]]]] and of stop is omitted,"
                         "it will be inferred to be the least significantly specified date + 1.")
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
            start, stop = parse_bound_arg(b)
            runtime_config[u_split[0]]["min"] = start
            runtime_config[u_split[0]]["max"] = stop

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
