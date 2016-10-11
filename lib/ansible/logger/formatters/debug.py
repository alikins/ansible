import logging

DEFAULT_DEBUG_LOG_FORMAT = "%(asctime)s [%(name)s %(levelname)s] (%(process)d):%(funcName)s:%(lineno)d - %(message)s"


class DebugFormatter(logging.Formatter):
    debug_format = DEFAULT_DEBUG_LOG_FORMAT

    def __init__(self, fmt=None, datefmt=None):
        fmt = fmt or self.debug_format
        super(DebugFormatter, self).__init__(fmt=fmt, datefmt=datefmt)

    # TODO: add fancy tty color
    # TODO: add formatException() ?
