
import logging
import logging.handlers
import os

from ansible import constants as C
from ansible.utils import color

#DEBUG_LOG_FORMAT = "%(asctime)s [%(name)s %(levelname)s %(playbook)s] (%(process)d):%(funcName)s:%(lineno)d - %(message)s"
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

        # TODO/FIXME/REMOVE
        # so we can test this without also turning on regular ansible debug
        self.on = 'ANSIBLE_LOG_DEBUG' in os.environ

    def filter(self, record):
        #return self.on
        return True


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


# TODO: add 'VVV' levels
level_to_ansible_color = {logging.NOTSET: None,
                          logging.DEBUG: C.COLOR_DEBUG,
                          logging.INFO: None,
                          logging.WARN: C.COLOR_WARN,
                          logging.ERROR: C.COLOR_ERROR,
                          logging.CRITICAL: C.COLOR_UNREACHABLE}


class ConsoleDebugFormatter(DebugFormatter):
    def format(self, record):
        message = super(ConsoleDebugFormatter, self).format(record)
        return self.color(message, record.levelno)

    def color(self, message, level):
        color_code = level_to_ansible_color.get(level, None)
        if not color_code:
            return message
        return color.stringc(message, color_code)


class ConsoleDebugHandler(DebugHandler):
    """Logging handler for output to a console, with optional colors."""
    def __init__(self, *args, **kwargs):
        print('init')
        super(ConsoleDebugHandler, self).__init__(*args, **kwargs)
        if self.isatty:
            self.formatter = ConsoleDebugFormatter()
        else:
            print('self.stream=%s dir=%s' % (self.stream, dir(self.stream)))
            self.formatter = DebugFormatter()

    @property
    def isatty(self):
        if hasattr(self.stream, 'isatty'):
            return self.stream.isatty()
        return False
