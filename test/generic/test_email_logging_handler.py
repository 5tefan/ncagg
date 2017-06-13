import unittest
import logging
import os
from aggregoes.ncei.BufferedEmailHandler import BufferedEmailHandler
import atexit


class TestBufferedEmailHandler(unittest.TestCase):

    def test_it(self):
        email = "Stefan.Codrescu@noaa.gov"
        hostname = os.environ.get("HOSTNAME", "")
        email_handler = BufferedEmailHandler("localhost", "%s@%s" % (os.environ.get("USER", "aggregation"), hostname),
                                             email, "Aggregation errors - test!")
        email_handler.setLevel(logging.ERROR)
        logging.getLogger().addHandler(email_handler)
        atexit.register(email_handler.finalize)

        logging.getLogger().error("Test ERRORRRR!")
        logging.getLogger().error("Oh no!, Another test ERRORRRR!")



