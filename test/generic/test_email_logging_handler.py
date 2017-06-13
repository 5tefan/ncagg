import unittest
import logging
import os
from aggregoes.ncei.BufferedEmailHandler import BufferedEmailHandler

error_messages = ["TEST ERROR!", "Oh no!, Another test ERROR!"]
warning_messages = ["I'm just a harmless warning message.", "You should probably ignore warnings."]


class TestBufferedEmailHandler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.email = "Stefan.Codrescu@noaa.gov"
        cls.hostname = os.environ.get("HOSTNAME", "")
        cls.username = os.environ.get("USER", "aggregation")
        cls.email_handler = BufferedEmailHandler("%s@%s" % (cls.username, cls.hostname),
                                                 cls.email, "Aggregation errors - test!")
        logging.getLogger().addHandler(cls.email_handler)

        for message in error_messages:
            logging.getLogger().error(message)

        for message in warning_messages:
            logging.getLogger().warning(message)

    @unittest.skipIf(not BufferedEmailHandler.test_connection(), "No SMTP server on localhost, can't send email.")
    def test_sending(self):
        """
        At NCEI, we're expecting to have an SMTP server on localhost that we can access. If it's not there,
        tor we can't connect some other host, (see SMTP_HOST in BufferedEmailHandler.py), then of course
        this test will fail, but that won't tell us anything whether BufferedEmailHandler works.

        TODO: possibly a better test would be to simulate the finalize, with email as localhost and see
        if we can receive the email?
        """
        self.email_handler.finalize()

    def test_message(self):
        """
        Make sure the body of the email contains the error messages above.
        Make sure the body doesn't contain any of the warning messages.
        :return:
        """
        email_body = self.email_handler.format()
        for message in error_messages:
            self.assertIn(message, email_body)

        for message in warning_messages:
            self.assertNotIn(message, email_body)
