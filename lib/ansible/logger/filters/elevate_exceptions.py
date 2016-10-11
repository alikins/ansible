import logging


# I don't think this is a good idea. People really don't like it when
# you log to CRITICAL
class ElevateExceptionToCriticalLoggingFilter(object):
    """Elevate the log level of log.exception from ERROR to CRITICAL."""
    def __init__(self, name):
        self.name = name

    def filter(self, record):
        if record.exc_info:
            record.levelname = 'CRITICAL'
            record.levelno = logging.CRITICAL
        return True
