import unittest
from ncagg.cli import parse_bound_arg
from datetime import datetime, timedelta
from itertools import permutations

years = {str(y): datetime(y, 01, 01) for y in xrange(2010, 2020)}

months = {d.strftime("%Y%m"): d for d in [datetime(2015, m, 01) for m in xrange(1, 12)]}

days = {d.strftime("%Y%m%d"): d for d in [datetime(2016, 01, x) for x in xrange(1,30)]}

adjust = timedelta(microseconds=1)

class TestBoundArgParsing(unittest.TestCase):

    def test_one(self):
        start, stop = parse_bound_arg("T2017:2019")
        self.assertEqual(start, datetime(2017, 01, 01))
        self.assertEqual(stop, datetime(2019, 01, 01))

    def test_year_edge(self):
        start, stop = parse_bound_arg("T201312")
        self.assertEqual(start, datetime(2013, 12, 01))
        self.assertEqual(stop, datetime(2014, 01, 01) - adjust)

    def test_many_times_with_start_and_stop(self):
        for a, b in permutations(years.items() + months.items() + days.items(), 2):
            start, stop = parse_bound_arg("T%s:T%s" % (a[0], b[0]))
            self.assertEqual(start, a[1])
            self.assertEqual(stop, b[1],"T%s" % b[0] + ", %s != %s" % (stop, b[1]))

    def test_many_start_days(self):
        for a, b in days.items():
            start, stop = parse_bound_arg("T%s" % a)
            self.assertEqual(start, b)
            self.assertEqual(stop, b + timedelta(days=1) - adjust)


