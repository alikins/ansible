import logging
import sys

from ansible.logger.formatters import display_compat as display_compat_formatter
from ansible.logger.formatters import debug as debug_formatter
from ansible.logger.filters import display_compat as display_compat_filter

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


# a console logger that impersonates existing 'display' based one
class DisplayCompatHandler(logging.StreamHandler, object):
    def __init__(self, *args, **kwargs):
        # the display.display logs to stdout, so use that for our stream as well
        super(DisplayCompatHandler, self).__init__(*args, **kwargs)
        # Default will use a DebugFormatter
        #if self.isatty:
        #    self.setFormatter(display_compat_formatter.DisplayCompatFormatter())
        #else:
        #    self.setFormatter(debug_formatter.DebugFormatter())
        self.stream = sys.stdout

        # so QueueListener's DisplayCompatHandler only shows messages for the display
        self.addFilter(display_compat_filter.DisplayCompatLoggingFilter(name=''))

    @property
    def isatty(self):
        if hasattr(self.stream, 'isatty'):
            return self.stream.isatty()
        return False

    def __repr__(self):
        # Mostly just so logging_tree shows the stream info and if it is a tty or not.
        return '%s(stream=%s, <isatty=%s>)' % (self.__class__.__name__,
                                               self.stream, self.isatty)


class DisplayCompatDebugHandler(DisplayCompatHandler):
    def __init__(self, *args, **kwargs):
        # the display.display logs to stdout, so use that for our stream as well
        super(DisplayCompatDebugHandler, self).__init__(*args, **kwargs)
        self.addFilter(display_compat_filter.DisplayCompatDebugLoggingFilter(name=""))
