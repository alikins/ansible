import logging
import logging.handlers

from ansible.logger.filters import unsafe
from ansible.logger.filers import elevate_exceptions


# NOTE: python 2.6 and earlier versions of the logging module
#       defined the log handlers as old style classes. In order
#       to use super(), we also inherit from 'object'
class AnsibleWatchedFileHandler(logging.handlers.WatchedFileHandler, object):
    def __init__(self, *args, **kwargs):
        super(AnsibleWatchedFileHandler, self).__init__(*args, **kwargs)

        self.addFilter(unsafe.UnsafeFilter(name=""))
        self.addFilter(elevate_exceptions.ElevateExceptionToCriticalLoggingFilter(name=""))
