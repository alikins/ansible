
import getpass
import logging
import sys

from ansible.constants import C
from ansible.logger import debug

user = getpass.getuser()
hostname = 'FIXME'

DISPLAY_LOG_FORMAT = " %(process)d %(created)f: p=%(process)d u=" + user + " <" + hostname + "> " + "%(message)s"
OLD_DISPLAY_LOG_FORMAT = " %(process)6d %(created)0.5f: %(message)s"

# TODO: remove, these are just for testing that we can emulate existing behavior


class DisplayConsoleDebugLoggingFilter(object):
    """Filter all log records unless env ANSIBLE_DEBUG env or DEFAULT_DEBUG cfg exists

    Used to turn on stdout logging for cli debugging."""

    def __init__(self, name):
        self.name = name
        self.on = C.DEFAULT_DEBUG

    def filter(self, record):
        return self.on


# emulate the format of 'display.debug'
class DisplayConsoleDebugFormatter(debug.ConsoleDebugFormatter):
    debug_format = OLD_DISPLAY_LOG_FORMAT


# Intentional bad name since this is temp.
# a console logger that impersonates existing 'display' based one
class DisplayConsoleDebugHandler(logging.StreamHandler, object):
    def __init__(self, *args, **kwargs):
        # the display.display logs to stdout, so use that for our stream as well
        super(DisplayConsoleDebugHandler, self).__init__(sys.stdout, *args, **kwargs)
        #self.addFilter(DisplayConsoleDebugLoggingFilter(name=""))
        # Default will use a DebugFormatter
        if self.isatty:
            self.setFormatter(DisplayConsoleDebugFormatter())
        else:
            self.setFormatter(debug.DebugFormatter())

    @property
    def isatty(self):
        if hasattr(self.stream, 'isatty'):
            return self.stream.isatty()
        return False

    def __repr__(self):
        # Mostly just so logging_tree shows the stream info and if it is a tty or not.
        return '%s(stream=%s, <isatty=%s>)' % (self.__class__.__name__,
                                               self.stream, self.isatty)
