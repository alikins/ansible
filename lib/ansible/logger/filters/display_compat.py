import logging
import os


from ansible import constants as C


class DisplayCompatDebugLoggingFilter(object):
    """Filter all log records unless env ANSIBLE_DEBUG env or DEFAULT_DEBUG cfg exists

    Used to turn on stdout logging for cli debugging."""

    def __init__(self, name):
        self.name = name
        self.on = C.DEFAULT_DEBUG

        # FIXME: remove, this lets us test by turning on ANSIBLE_DEBUG and ANSIBLE_LOG_DEBUG seperately
        self.on = os.environ.get('ANSIBLE_LOG_DEBUG', None) or False

    def filter(self, record):
        # display.debug equiv only display messages sent to DEBUG
        # and not any higher levels (INFO for ex)
        if record.levelno != logging.DEBUG:
            return False
        return self.on
