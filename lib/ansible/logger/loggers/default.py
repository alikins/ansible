import logging

from ansible.logger.filters import unsafe
from ansible.logger.filters import default_attributes
from ansible.logger.filters import process_context


# yeah, the getLoggerClass() is weird, but the docs suggest it
# https://docs.python.org/2/library/logging.html#logging.getLoggerClass
# I'll see if it's troubleprone.
class AnsibleLogger(logging.getLoggerClass()):
    def __init__(self, name, level=logging.NOTSET, host=None):
        super(AnsibleLogger, self).__init__(name, level=level)

        self.addFilter(unsafe.UnsafeFilter(name=""))
        self.addFilter(default_attributes.DefaultAttributesFilter(name=""))
        self.addFilter(process_context.ProcessContextLoggingFilter(name=""))
