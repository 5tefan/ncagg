import re
import os
from datetime import datetime
import netCDF4 as nc
import logging, traceback

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def datetime_format(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + "Z"


class Strat(object):
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
    def process(self, attr):
        if self.attr == "":
            self.attr = attr


class StratLast(Strat):
    def process(self, attr):
        self.attr = attr


class StratUniqueList(Strat):
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
    def __init__(self, *args, **kwargs):
        super(StratIntSum, self).__init__()
        self.attr = 0

    def process(self, attr):
        self.attr += int(attr)


class StratFloatSum(Strat):
    def __init__(self, *args, **kwargs):
        super(StratFloatSum, self).__init__()
        self.attr = 0.0

    def process(self, attr):
        self.attr += float(attr)


class StratAssertConst(Strat):
    def process(self, attr):
        if self.attr == "":
            self.attr = attr
        else:
            assert self.attr == attr


class StratDateCreated(Strat):
    # noinspection PyMissingConstructor
    def __init__(self, *args, **kwargs):
        pass

    def process(self, attr):
        pass

    def finalize(self, nc_out):
        return datetime_format(datetime.now())


class StratWithConfig(Strat):
    def __init__(self, attr_config, runtime_config, *args, **kwargs):
        super(StratWithConfig, self).__init__()
        self.attr_config = attr_config or {}
        self.runtime_config = runtime_config or {}

    def process(self, attr):
        pass


class StratStatic(StratWithConfig):
    def __init__(self, *args, **kwargs):
        super(StratStatic, self).__init__(*args, **kwargs)
        self.attr = self.attr_config.get("value", "")


class StratTimeCoverageBegin(StratWithConfig):
    def __init__(self, *args, **kwargs):
        super(StratTimeCoverageBegin, self).__init__(*args, **kwargs)

    def finalize(self, nc_out):
        # do raise exceptions
        udim = next((udim for udim in self.runtime_config.keys()
                     if self.runtime_config[udim].get("min", None) is not None), None)
        if udim is None:
            # bail early if udim is None, ie. no unlimited dim configured
            return ""

        min = self.runtime_config[udim]["min"]
        if isinstance(min, datetime):
            return datetime_format(min)
        else:
            udim_indexed_by = self.runtime_config[udim]["index_by"]
            dt = nc.num2date([min], nc_out.variables[udim_indexed_by].units)[0]
            return datetime_format(dt)


class StratTimeCoverageEnd(StratWithConfig):
    def __init__(self, *args, **kwargs):
        super(StratTimeCoverageEnd, self).__init__(*args, **kwargs)

    def finalize(self, nc_out):
        # TODO: when primary is implemented, make sure to use primary min and max
        # actually, do raise exceptions here, handle higher up
        udim = next((udim for udim in self.runtime_config.keys()
                     if self.runtime_config[udim].get("max", None) is not None), None)
        if udim is None:
            # bail early if udim is None, ie. no unlimited dim configured
            return ""

        max = self.runtime_config[udim]["max"]
        if isinstance(max, datetime):
            return datetime_format(max)
        else:
            udim_indexed_by = self.runtime_config[udim]["index_by"]
            dt = nc.num2date([max], nc_out.variables[udim_indexed_by].units)[0]
            return datetime_format(dt)


class StratOutputFilename(Strat):
    # noinspection PyMissingConstructor
    def __init__(self, *args, **kwargs):
        pass

    def process(self, attr):
        pass

    def finalize(self, nc_out):
        return os.path.basename(nc_out.filepath())


class AttributeHandler(object):
    # dict to look up handlers for specific strategies
    strategy_handlers = {
        "first": StratFirst,
        "last": StratLast,
        "unique_list": StratUniqueList,
        "int_sum": StratIntSum,
        "float_sum": StratFloatSum,
        "constant": StratAssertConst,
        "date_created": StratDateCreated,
        "time_coverage_begin": StratTimeCoverageBegin,
        "time_coverage_end": StratTimeCoverageEnd,
        "filename": StratOutputFilename
    }

    def __init__(self, global_attr_config=None, runtime_config=None):
        super(AttributeHandler, self).__init__()
        self.config = global_attr_config or []

        self.attr_handlers = {
            attr["name"]: self.strategy_handlers.get(attr.get("strategy", "first"), StratFirst).setup_handler(
                attr_config=attr, runtime_config=runtime_config
            )
            for attr in self.config
            }

    def process_file(self, nc_in):
        """
        Take the attributes from nc_in and process them.

        :type nc_in: nc.Dataset
        :param nc_in: the netcdf object to process attributes from
        :return: None
        """
        for attr in self.config:
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
                    pass

    def finalize_file(self, nc_out):
        """
        Write the processed attributes to nc_out.

        :type nc_out: nc.Dataset
        :param nc_out: The aggregated output file on which to set the processed attributes.
        :return: None
        """
        for attr in self.config:
            # handler will be a tuple of functions the first being the process one.
            handler = self.attr_handlers.get(attr["name"], None)
            if handler is not None and handler[1] is not None:
                try:
                    attr_val = handler[1](nc_out)
                    if attr_val != "":
                        nc_out.setncattr(attr["name"], attr_val)
                except Exception as e:
                    logger.error(traceback.format_exc())
                    logger.error("Error setting global attribute %s: %s" % (attr["name"], repr(e)))

