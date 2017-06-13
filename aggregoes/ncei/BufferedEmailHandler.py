import logging
from logging import handlers


class BufferedEmailHandler(handlers.SMTPHandler):
    def __init__(self, mailhost, fromaddr, toaddrs, subject,
                 credentials=None, secure=None):
        super(BufferedEmailHandler, self).__init__(mailhost, fromaddr, toaddrs, subject,
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
            super(BufferedEmailHandler, self).emit(None)

    def format(self, _):
        # ignore record _, handlers.SMTPHandler emit() calls self.format() to get the contents
        # of the email. In this case, the content of the message should be list of Error messages.
        return "Unexpected errors occurred during aggregation:\n " + "\n".join(self.buffer)

