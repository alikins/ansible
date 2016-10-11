
import os


class DebugLoggingFilter(object):
    """Filter all log records unless env ANSIBLE_DEBUG env or DEFAULT_DEBUG cfg exists

    Used to turn on stdout logging for cli debugging."""

    def __init__(self, name):
        self.name = name
        # self.on = C.DEFAULT_DEBUG

        # TODO/FIXME/REMOVE
        # so we can test this without also turning on regular ansible debug
        self.on = 'ANSIBLE_LOG_DEBUG' in os.environ

    def filter(self, record):
        return self.on
