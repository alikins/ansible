
import logging
import logging.handlers

from ansible import constants as C

DEBUG_LOG_FORMAT = "%(asctime)s [%(name)s %(levelname)s] (%(process)d):%(funcName)s:%(lineno)d - %(message)s"


class DebugFormatter(logging.Formatter):
    debug_format = DEBUG_LOG_FORMAT

    def __init__(self, fmt=None, datefmt=None):
        fmt = fmt or self.debug_format
        super(DebugFormatter, self).__init__(fmt=fmt, datefmt=datefmt)

    # TODO: add fancy tty color
    # TODO: add formatException() ?


class DebugLoggingFilter(object):
    """Filter all log records unless env ANSIBLE_DEBUG env or DEFAULT_DEBUG cfg exists

    Used to turn on stdout logging for cli debugging."""

    def __init__(self, name):
        self.name = name
        self.on = C.DEFAULT_DEBUG

    def filter(self, record):
        return self.on


class DebugHandler(logging.StreamHandler, object):
    """Logging Handler for cli debugging.

    This handler only emits records if ANSIBLE_DEBUG exists in os.environ."""

    # This handler is always added, but the filter doesn't let anything propagate
    # unless C.DEFAULT_DEBUG is True.
    #
    # This should let debug output be turned on and off withing one invocation
    # TODO: verify

    def __init__(self, *args, **kwargs):
        super(DebugHandler, self).__init__(*args, **kwargs)
        # self.addFilter(ContextLoggingFilter(name=""))
        self.addFilter(DebugLoggingFilter(name=""))
