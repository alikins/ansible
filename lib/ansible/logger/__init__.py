# logging support for ansible using stdlib logging
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

import logging
import logging.handlers
import multiprocessing

from ansible.logger import debug
from ansible.logger.levels import V, VV, VVV, VVVV, VVVVV    # noqa
#import logging_tree

THREAD_DEBUG_LOG_FORMAT = "%(asctime)s <%(remote_user)s@%(remote_addr)s> [%(name)s %(levelname)s] (%(process)d) tid=%(thread)d:%(threadName)s %(funcName)s:%(lineno)d - %(message)s"

# TODO/maybe: Logger subclass with v/vv/vvv etc methods?
# TODO: add logging filter that implements no_log
#       - ideally via '__unsafe__'
#       - AnsibleError could use it in it's str/repr
# TODO: add AnsibleContextLoggingFilter
#       extra records for current_cmd, sys.argv
# TODO: add AnsiblePlaybookLoggingFilter
#       extra records for playbook/play/task/block ?
# TODO: (yaml?) config based logging setup
# TODO: Any log Formatters or Handlers that are ansible specific
# TODO: base logging setup
# TODO: NullHandler for py2.4
# TODO: for unsafe, no_log, in some ways we want the Logger to censor unsafe item, before they
#       get sent to handlers or formatters. We can do that with a custom Logger and
#       logger.setLoggerClass(). The custom logger would define a makeRecord() that would example
#       any passed in records and scrub out sensitive ones. setLoggerClass() is gloabl for entire
#       process, so any used modules that use getLogger will get it as well, so it needs to be
#       robust.
# TODO: exception logging... if we end up using custom Logger, we can add methods for low priority
#       captured exceptions and send to DEBUG instead of ERROR or CRITICAL. Or use a seperate handler
#       and filter exceptions records from main handler.
# TODO: handler/logger filters for populating log records with defaults for any custom
#       format attributes we use  (so handlers dont get a record that is references in a format string)
# TODO: mv filters to a module?
# TODO: hook up logging for run_command argv/in/out/rc (env)?
# TODO: logging plugin? plugin would need to be able to run very early

# I don't think this is a good idea. People really don't like it when
# you log to CRITICAL


class ElevateExceptionToCriticalLoggingFilter(object):
    """Elevate the log level of log.exception from ERROR to CRITICAL."""
    def __init__(self, name):
        self.name = name

    def filter(self, record):
        if record.exc_info:
            record.levelname = 'CRITICAL'
            record.levelno = logging.CRITICAL
        return True


class UnsafeFilter(object):
    """Used to filter out msg args that are AnsibleUnsafe or have __UNSAFE__ attr."""
    def __init__(self, name):
        self.name = name

    def filter(self, record):
        # FIXME: filter stuff
        return True


# Another way to do this:
#  since we have a custom default Logger class, we can change it's makeRecord to
#  generate records with these fields populated
class DefaultAttributesFilter(object):
    """Used to make sure every LogRecord has all of our custom attributes.

    if the record doesn't populate an attribute, add it with a default value.

    This prevents log formats that reference custom log record attributes
    from causing a LogFormatter to fail when attempt to format the message."""

    def __init__(self, name):
        self.name = name
        self.defaults = {'remote_addr': '',
                         'remote_user': ''}

    def filter(self, record):
        # hostname
        for attr_name, default_value in self.defaults.items():
            if not hasattr(record, attr_name):
                # Suppose this could be 'localhost' or 'local' etc
                setattr(record, attr_name, default_value)
        return True


# NOTE: python 2.6 and earlier versions of the logging module
#       defined the log handlers as old style classes. In order
#       to use super(), we also inherit from 'object'
class AnsibleWatchedFileHandler(logging.handlers.WatchedFileHandler, object):
    def __init__(self, *args, **kwargs):
        try:
            super(AnsibleWatchedFileHandler, self).__init__(*args, **kwargs)
        # fallback to stdout if we can't open our logger
        except Exception:
            logging.NullHandler(self)

        self.addFilter(UnsafeFilter(name=""))
        self.addFilter(ElevateExceptionToCriticalLoggingFilter(name=""))


# yeah, the getLoggerClass() is weird, but the docs suggest it
# https://docs.python.org/2/library/logging.html#logging.getLoggerClass
# I'll see if it's troubleprone.
class AnsibleLogger(logging.getLoggerClass()):
    def __init__(self, name, level=logging.NOTSET, host=None):
        super(AnsibleLogger, self).__init__(name, level=level)

        self.addFilter(UnsafeFilter(name=""))
        self.addFilter(DefaultAttributesFilter(name=""))

# Make AnsibleLogger the default logger that logging.getLogger() returns instance of
logging.setLoggerClass(AnsibleLogger)


def log_setup():
    null_handler = logging.NullHandler()

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.CRITICAL)
    #root_logger.setLevel(logging.DEBUG)
    root_logger.propagate = True
    # root_logger.addHandler(null_handler)

    #log = logging.getLogger('ansible')
    log = logging.getLogger('ansible')
    log.setLevel(logging.DEBUG)
    # log.setLevel(logging.CRITICAL)
    #formatter = logging.Formatter(DEBUG_LOG_FORMAT)
    formatter = logging.Formatter(THREAD_DEBUG_LOG_FORMAT)
    # log.propagate = True

    # stream_handler = logging.StreamHandler()
    # stream_handler.setLevel(logging.DEBUG)
    # stream_handler.setFormatter(formatter)

    # file_handler = logging.FileHandler(filename='/home/adrian/ansible.log')
    file_handler = AnsibleWatchedFileHandler(filename='/home/adrian/ansible.log')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    #debug_handler = debug.DebugHandler()
    debug_handler = debug.ConsoleDebugHandler()
    debug_handler.setLevel(logging.DEBUG)

    #display_debug_handler = debug.DisplayConsoleDebugHandler()
    #display_debug_handler.setLevel(logging.DEBUG)
    #debug_handler.setFormatter(debug.DebugFormatter())

    mplog = multiprocessing.get_logger()
    mplog.setLevel(logging.INFO)
    #mplog.setLevel(multiprocessing.SUBDEBUG)
    mplog.propagate = True

    # log.addHandler(null_handler)
    # log.addHandler(stream_handler)
    # log.addHandler(file_handler)
    # NOTE: This defines a root '' logger, so any of the modules we use that using logging
    #       will log to our log file as well. This is mostly a dev setup, so disable before release
    # FIXME: disable in future
    root_logger.addHandler(null_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(debug_handler)
    #root_logger.addHandler(display_debug_handler)

    # turn down some loggers. One of many reasons logging is useful
    logging.getLogger('ansible.plugins.action').setLevel(logging.INFO)
    logging.getLogger('ansible.plugins.strategy.linear').setLevel(logging.INFO)
    logging.getLogger('ansible.plugins.PluginLoader').setLevel(logging.INFO)
    #logging.getLogger('ansible.executor.task_executor').setLevel(logging.INFO)
    #logging.getLogger('ansible.executor.play_iterator').setLevel(logging.INFO)

#    logging_tree.printout()
