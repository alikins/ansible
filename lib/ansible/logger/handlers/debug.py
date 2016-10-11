import logging

from ansible.logger.filters import debug as debug_filter
from ansible.logger.formatters import debug as debug_formatter


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
        self.addFilter(debug_filter.DebugLoggingFilter(name=""))
        self.setFormatter(debug_formatter.DebugFormatter())

    def __repr__(self):
        # Mostly just so logging_tree shows the stream info and if it is a tty or not.
        return '%s(stream=%s, <isatty=%s>)' % (self.__class__.__name__,
                                               self.stream, self.isatty)
