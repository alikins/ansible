
import logging
import logging.handlers
import os

from ansible import constants as C
from ansible.utils import color
from ansible.logger import levels

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
        self.addFilter(DebugLoggingFilter(name=""))
        self.setFormatter(DebugFormatter())

    def __repr__(self):
        # Mostly just so logging_tree shows the stream info and if it is a tty or not.
        return '%s(stream=%s, <isatty=%s>)' % (self.__class__.__name__,
                                               self.stream, self.isatty)


# TODO: add 'VVV' levels
level_to_ansible_color = {logging.NOTSET: None,
                          logging.DEBUG: C.COLOR_DEBUG,
                          logging.INFO: None,
                          logging.WARN: C.COLOR_WARN,
                          logging.ERROR: C.COLOR_ERROR,
                          logging.CRITICAL: C.COLOR_UNREACHABLE,
                          # the old 'vvv' levels
                          levels.V: C.COLOR_VERBOSE,
                          levels.VV: C.COLOR_VERBOSE,
                          levels.VVV: C.COLOR_VERBOSE,
                          levels.VVVV: C.COLOR_VERBOSE,
                          levels.VVVVV: C.COLOR_VERBOSE,
                          }


class ConsoleDebugFormatter(DebugFormatter):
    def format(self, record):
        message = super(ConsoleDebugFormatter, self).format(record)
        return self._color(message, record.levelno)

    def _color(self, message, level):
        color_code = level_to_ansible_color.get(level, None)
        if not color_code:
            return message
        return self._colorize(message, color_code)

    # more or less ansible.utils.color.stringc, except without the check if stdout is a tty, since
    # we are going to log to stderr by default and we let the handler decide if stream is a tty
    def _colorize(self, message, color_code):
        return u"\033[%sm%s\033[0m" % (color.codeCodes[color_code], message)


class ConsoleDebugHandler(DebugHandler):
    """Logging handler for output to a console, with optional colors."""
    def __init__(self, *args, **kwargs):
        print('init')
        super(ConsoleDebugHandler, self).__init__(*args, **kwargs)
        # Default will use a DebugFormatter
        if self.isatty:
            self.setFormatter(ConsoleDebugFormatter())

    @property
    def isatty(self):
        if hasattr(self.stream, 'isatty'):
            return self.stream.isatty()
        return False
