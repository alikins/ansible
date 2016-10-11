
import logging


# This uses the default behavor of LoggerAdapter, adding the
# dict like 'extra' object passed to it's init to the log records __dict__
# so the keys in 'extra' can be used in custom log formats. Where we
# use this class, we include 'remote_addr' in the dict
class HostLoggerAdapter(logging.LoggerAdapter):
    pass
