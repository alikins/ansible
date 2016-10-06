
import getpass
import logging
import sys

from ansible.constants import C
from ansible.logger import debug

user = getpass.getuser()
hostname = 'FIXME'

# rough approx of existing display format
# based on:
#logger = logging.getLogger("p=%s u=%s | " % (mypid, user))
# logging.basicConfig(filename=path, level=logging.DEBUG, format='%(asctime)s %(name)s %(message)s')
# self.display("<%s> %s" % (host, msg), color=C.COLOR_VERBOSE, screen_only=True)
# user and hostname attributes would be up to a logging.Filter to add
# DISPLAY_LOG_FORMAT = "%(asctime)s p=%(process)d u=%(user)s <%(hostname)s> %(message)s"
DISPLAY_LOG_FORMAT = " %(process)d %(created)f: p=%(process)d u=" + user + " <" + hostname + "> " + "%(message)s"
DISPLAY_DEBUG_LOG_FORMAT = " hostname=|%(hostname)s| %(process)6d %(created)0.5f: %(message)s"
DISPLAY_VERBOSE_LOG_FORMAT = "<%(hostname)s> %(message)s"
# TODO: remove, these are just for testing that we can emulate existing behavior


class DisplayConsoleDebugLoggingFilter(object):
    """Filter all log records unless env ANSIBLE_DEBUG env or DEFAULT_DEBUG cfg exists

    Used to turn on stdout logging for cli debugging."""

    def __init__(self, name):
        self.name = name
        self.on = C.DEFAULT_DEBUG

    def filter(self, record):
        # display.debug equiv only display messages sent to DEBUG
        # and not any higher levels (INFO for ex)
        if record.levelno != logging.DEBUG:
            return False
        return self.on


# emulate the format of 'display.debug'
class DisplayConsoleDebugFormatter(debug.ConsoleDebugFormatter):
    debug_format = DISPLAY_DEBUG_LOG_FORMAT


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
