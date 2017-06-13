import logging
import smtplib
from logging import handlers

logger = logging.getLogger(__name__)

SMTP_HOST = "localhost"
SMTP_PORT = 587

class BufferedEmailHandler(handlers.SMTPHandler):
    """
    Notes:
        - In gerenal, swallowing all error here, possibly logging them, understanding that this should
        be called atexit, so we don't want the program to crash at the very end just because it couldn't
        send the emails.
    """
    def __init__(self, fromaddr, toaddrs, subject,
                 credentials=None, secure=None):
        super(BufferedEmailHandler, self).__init__(SMTP_HOST, fromaddr, toaddrs, subject,
                                                   credentials, secure)
        self.setLevel(logging.ERROR)
        # hold the queued messages in self.buffer
        self.buffer = []  # type: list[str]

    def emit(self, record):
        # called when something like logger.error("AHH!") comes through
        self.buffer.append(record.getMessage())

    def finalize(self):
        # send out an email if there is anything in the buffer.
        if len(self.buffer) > 0:
            # check if we can connect to the server
            if not self.test_connection():
                logger.error("No SMTP server found, could not send ERROR mail summary.")
            else:
                try:
                    # if we have smtp, call handlers.SMTPHandler.emit which will send an email with
                    # return of self.format() as the body.
                    super(BufferedEmailHandler, self).emit(None)
                except (KeyboardInterrupt, SystemExit):
                    raise
                except:
                    logger.error("Sending email failed! Content was: \n %s" % self.format())
            self.buffer = []

    def format(self, _=None):
        # ignore record _, handlers.SMTPHandler emit() calls self.format() to get the contents
        # of the email. In this case, the content of the message should be list of Error messages.
        return "Unexpected errors occurred during aggregation:\n " + "\n".join(self.buffer)

    def handleError(self, record=None):
        pass

    @staticmethod
    def test_connection():
        """
        Test the smtp connection, from https://stackoverflow.com/a/14678273

        Will be useful above in finalize, and also in testing, ie. don't run
        test if can't connect to smtp_host.
        :return: True or False, if can connect to SMTP_HOST on SMTP_PORT
        """
        try:
            conn = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
            status = conn.noop()[0]
        except:
            status = -1
        return True if status == 250 else False
