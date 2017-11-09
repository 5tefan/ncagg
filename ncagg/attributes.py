import re
import os
from datetime import datetime
import netCDF4 as nc
import logging, traceback

logger = logging.getLogger(__name__)


def datetime_format(dt):
    """
    Consistent format for timestamps throughout global attirbutes.
    :type dt: datetime
    :param dt: a datetime object
    :return: dt to string
    """
    return dt.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + "Z"


class Strat(object):
    """
    The template for a strategy implementation. Strategies should be implemented
    with the same signatures as here.

    Each attribute will be associated with an instance of the strategy it is
    aggregated along. For each attribute seen, inst.process(attribute) will be
    called. After aggregation, inst.finalize(nc_out) will be called and it is
    expected that a nonempty string is returned if the attribute should be set
    to the value returned.
    """
    def __init__(self, *args, **kwargs):
        super(Strat, self).__init__()
        self.attr = ""

    @classmethod
    def setup_handler(cls, *args, **kwargs):
        instance = cls(*args, **kwargs)
        return instance.process, instance.finalize

    def process(self, attr):
        """
        Collect an attribute from a file according to the strategy cls implemnets.

        :type attr: str
        :param attr: an incoming attribute
        :return: None
        """
        self.attr = attr

    def finalize(self, nc_out):
        """
        Return the value the attribute should be set to. This method should not
        actually set the attribute on nc_out, but the argument is expected in case
        the finalize method needs to access data in order to find the value to return.

        :type nc_out: nc.Dataset
        :param nc_out: The resulting aggregation file.
        :return: value of the attribute
        """
        return self.attr


class StratFirst(Strat):
    """
    Strategy processes to the first attribute value processed.
    """
    def process(self, attr):
        if self.attr == "":
            self.attr = attr


class StratLast(Strat):
    """
    Strategy finalizes to the value of the last attribute value
    processed.

    Note, this is included to semantics as the base Strat class
    implements StratLast.
    """
    pass


class StratUniqueList(Strat):
    """
    Finalize to a comma separated list of unique values detected
    during processing.
    """
    def __init__(self, *args, **kwargs):
        super(StratUniqueList, self).__init__()
        self.attr = []

    def process(self, attr):
        for each in re.split(", *", attr):
            if each not in self.attr:
                self.attr.append(each)

    def finalize(self, nc_out):
        return ", ".join(self.attr)


class StratIntSum(Strat):
    """
    Process attributes as integer values and finalize to their sum.
    """
    def __init__(self, *args, **kwargs):
        super(StratIntSum, self).__init__()
        self.attr = 0

    def process(self, attr):
        self.attr += int(attr)


class StratFloatSum(Strat):
    """
    Process attributes as float values and finalize to their sum.
    """
    def __init__(self, *args, **kwargs):
        super(StratFloatSum, self).__init__()
        self.attr = 0.0

    def process(self, attr):
        self.attr += float(attr)


class StratAssertConst(Strat):
    """
    Strategy raises an exception if any subsequent attributes processed
    do not match the first one seen.
    """
    def process(self, attr):
        if self.attr == "":
            self.attr = attr
        elif self.attr != attr:
            raise AssertionError("Non constant attribute %s --> %s" % (self.attr, attr))


class StratDateCreated(Strat):
    """
    Strategy returns a timestamp indicating when finalize was called.
    """
    # noinspection PyMissingConstructor
    def __init__(self, *args, **kwargs):
        pass

    def process(self, attr):
        pass

    def finalize(self, nc_out):
        return datetime_format(datetime.now())


class StratRemove(Strat):
    """
    Strategy always finalizes to an empty string, meaning the attribute
    this strategy is assigned to will not be included in the aggregated
    output.
    """
    # noinspection PyMissingConstructor
    def __init__(self, *args, **kwargs):
        pass

    def process(self, attr):
        pass

    def finalize(self, nc_out):
        return ""


class StratWithConfig(Strat):
    """
    The previous strategies were blind to world politics.
    """
    def __init__(self, config, *args, **kwargs):
        super(StratWithConfig, self).__init__()
        self.config = config

    def process(self, attr):
        pass


class StratStatic(StratWithConfig):
    def __init__(self, *args, **kwargs):
        super(StratStatic, self).__init__(*args, **kwargs)

    def process(self, attr):
        return self.config.attrs.get(attr, {}).get("value", "")


class StratTimeCoverageStart(StratWithConfig):
    def __init__(self, *args, **kwargs):
        super(StratTimeCoverageStart, self).__init__(*args, **kwargs)

    def finalize(self, nc_out):
        # Yes, there are so many ways this can raise an exception. That's intentional.
        # find the first unlimited dimension minimum value
        udim = next((d for d in self.config.dims.values() if d["min"] is not None), None)
        if udim is None:
            # bail early if udim is None, ie. no unlimited dim configured
            return ""
        min = udim["min"]
        if isinstance(min, datetime):
            return datetime_format(min)
        else:
            udim_indexed_by = udim["index_by"]
            dt = nc.num2date(min, self.config.vars[udim_indexed_by]["attributes"]["units"])
            return datetime_format(dt)


class StratTimeCoverageEnd(StratWithConfig):
    def __init__(self, *args, **kwargs):
        super(StratTimeCoverageEnd, self).__init__(*args, **kwargs)

    def finalize(self, nc_out):
        # TODO: when primary is implemented, make sure to use primary min and max
        # actually, do raise exceptions here, handle higher up
        udim = next((d for d in self.config.dims.values() if d["max"] is not None), None)
        if udim is None:
            # bail early if udim is None, ie. no unlimited dim configured
            return ""
        max = udim["max"]
        if isinstance(max, datetime):
            return datetime_format(max)
        else:
            udim_indexed_by = udim["index_by"]
            dt = nc.num2date(max, self.config.vars[udim_indexed_by]["attributes"]["units"])
            return datetime_format(dt)


class StratOutputFilename(Strat):
    # noinspection PyMissingConstructor
    def __init__(self, *args, **kwargs):
        self.attr = kwargs.get("filename", "")

    def process(self, attr):
        pass

    def finalize(self, nc_out):
        # used to be os.path.basename(nc_out.filepath()), but the filenames are regularly too
        # long, see https://github.com/Unidata/netcdf4-python/blob/6087ae9b77b538b9c0ab3cdde3118b4ceb6f8946/netCDF4/_netCDF4.pyx#L1903
        # seems like we exceed pathlen and are getting nasty errors. Now instead passing it through the kwargs
        return os.path.basename(self.attr)


class AttributeHandler(object):
    # dict to look up handlers for specific strategies
    strategy_handlers = {
        "static": StratStatic,
        "first": StratFirst,
        "last": StratLast,
        "unique_list": StratUniqueList,
        "int_sum": StratIntSum,
        "float_sum": StratFloatSum,
        "constant": StratAssertConst,
        "date_created": StratDateCreated,
        "time_coverage_start": StratTimeCoverageStart,
        "time_coverage_end": StratTimeCoverageEnd,
        "filename": StratOutputFilename,
        "remove": StratRemove
    }

    def __init__(self, config, *args, **kwargs):
        super(AttributeHandler, self).__init__()
        self.config = config

        self.attr_handlers = {
            attr["name"]: self.strategy_handlers.get(attr.get("strategy", "first"), StratFirst).setup_handler(
                # expecting in kwargs at least runtime_config and filename
                config=config, *args, **kwargs
            )
            for attr in self.config.attrs.values()
        }

    def process_file(self, nc_in):
        """
        Take the attributes from nc_in and process them.

        :type nc_in: nc.Dataset
        :param nc_in: the netcdf object to process attributes from
        :return: None
        """
        for attr in self.config.attrs.values():
            # handler will be a tuple of functions the first being the process one.
            handler = self.attr_handlers.get(attr["name"], None)
            if handler is not None and handler[0] is not None:
                try:
                    attr_val = nc_in.getncattr(attr["name"])
                    if attr_val is not None and attr_val != "":
                        handler[0](attr_val)
                except Exception as e:
                    # ignore if there is no attribute, may happen in cases like date_created
                    # and time_coverage_begin if they don't exist in advance (which is ok)
                    logger.debug(traceback.format_exc())

    def finalize_file(self, nc_out):
        """
        Write the processed attributes to nc_out.

        :type nc_out: nc.Dataset
        :param nc_out: The aggregated output file on which to set the processed attributes.
        :return: None
        """
        for attr in self.config.attrs.values():
            # handler will be a tuple of functions the first being the process one.
            handler = self.attr_handlers.get(attr["name"], None)
            if handler is not None and handler[1] is not None:
                try:
                    attr_val = handler[1](nc_out)
                    if attr_val != "":
                        nc_out.setncattr(attr["name"], attr_val)
                except Exception as e:
                    logger.error("Error setting global attribute %s: %s" % (attr["name"], repr(e)))
                    logger.error(traceback.format_exc())

