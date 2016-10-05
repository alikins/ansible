
import logging


class HostLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return '<%s> %s' % (self.extra['remote_addr'], msg), kwargs
