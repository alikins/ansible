
from ansible.logger.formatters import console_debug

# rough approx of existing display format
# based on:
# logger = logging.getLogger("p=%s u=%s | " % (mypid, user))
# logging.basicConfig(filename=path, level=logging.DEBUG, format='%(asctime)s %(name)s %(message)s')
# self.display("<%s> %s" % (host, msg), color=C.COLOR_VERBOSE, screen_only=True)
# user and hostname attributes would be up to a logging.Filter to add
# DISPLAY_LOG_FORMAT = "%(asctime)s p=%(process)d u=%(user)s <%(hostname)s> %(message)s"
# DISPLAY_LOG_FORMAT = " %(process)d %(created)f: p=%(process)d u=" + user + " <" + hostname + "> " + "%(message)s"
# DISPLAY_VERBOSE_LOG_FORMAT = "<%(hostname)s> %(message)s"
DISPLAY_COMPAT_DEBUG_LOG_FORMAT = " hostname=|%(remote_addr)s| %(process)6d %(created)0.5f: %(message)s"
DISPLAY_COMPAT_LOG_FORMAT = "%(message)s"


# emulate the format of 'display.debug'
class DisplayCompatDebugFormatter(console_debug.ConsoleDebugFormatter):
    debug_format = DISPLAY_COMPAT_DEBUG_LOG_FORMAT


# emulate the format of 'display.v'
class DisplayCompatFormatter(console_debug.ConsoleDebugFormatter):
    debug_format = DISPLAY_COMPAT_LOG_FORMAT
