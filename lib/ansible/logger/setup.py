
import logging
import multiprocessing
import sys

from ansible.logger import formats
from ansible.logger.loggers import default
from ansible.logger.handlers import default_handler
from ansible.logger.handlers import queue_handler
from ansible.logger import dict_setup
from ansible.logger.formatters import color_debug

# Make AnsibleLogger the default logger that logging.getLogger() returns instance of
logging.setLoggerClass(default.AnsibleLogger)

# TODO: suppose we need to make the config file location configurable
DEFAULT_YAML_LOGGING_CONF = "/home/adrian/ansible_logging.yaml"


def log_setup():
    # TODO: if we decide we need a way to configure our configuration style, figure it out here
    try:
        return dict_setup.log_setup_yaml_file(DEFAULT_YAML_LOGGING_CONF)
    except Exception as e:
        sys.stderr.write('error setting up logging: %s' % e)
        # TODO: raise a logging setup exception since we likely want to setup logging first, then the big try/except for cli
        raise

log_queue = None


def queue_listener(handler):
    # This seems like a bad idea...
    global log_queue
    log_queue = multiprocessing.Queue()
    queue_listener = queue_handler.QueueListener(log_queue, handler)

    queue_listener.start()
    return queue_listener


def log_queue_listener_stop(queue):
    queue.put(None)


def setup_listener():

    ql = queue_listener(stream_handler)
    print(ql)


def log_setup_code():
    #null_handler = logging.NullHandler()

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.CRITICAL)
    #root_logger.setLevel(logging.DEBUG)
    #root_logger.propagate = True
    # root_logger.addHandler(null_handler)

    #log = logging.getLogger('ansible')
    log = logging.getLogger('ansible')
    #log.setLevel(logging.INFO)
    log.setLevel(logging.DEBUG)
    # log.setLevel(logging.CRITICAL)
    #formatter = logging.Formatter(DEBUG_LOG_FORMAT)
    #formatter = logging.Formatter(THREAD_DEBUG_LOG_FORMAT)
    formatter = color_debug.ColorFormatter(use_color=True, default_color_by_attr='process')
    formatter.use_thread_color = True
    # formatter = logging.Formatter(formats.REMOTE_DEBUG_LOG_FORMAT)

    #import logmatic
    #j_f = logmatic.JsonFormatter()
    #formatter = j_f
    #formatter = logging.Formatter(LOG_INDEXER_FRIENDLY_FORMAT)
    # log.propagate = True

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(multiprocessing.SUBDEBUG)
    stream_handler.setFormatter(formatter)
    # stream_handler.setLevel(logging.DEBUG)
    # stream_handler.setFormatter(formatter)

    # file_handler = logging.FileHandler(filename='/home/adrian/ansible.log')
    try:
        file_handler = default_handler.AnsibleWatchedFileHandler(filename='/home/adrian/ansible.log')
    # fallback to NullHandler if we can't open our log file
    except Exception as e:
        sys.stderr.write('%s\n' % e)
        log.error(e)
        log.exception()
        raise
        log.exception('error setting up default_handler.AnsibleWatchedFileHandler')
        file_handler = logging.NullHandler()

    #file_handler.setLevel(logging.DEBUG)
    file_handler.setLevel(multiprocessing.SUBDEBUG)
    #file_handler.setLevel(logging.ERROR)
    file_handler.setFormatter(formatter)

    #debug_handler = debug.DebugHandler()

    #debug_handler = debug.ConsoleDebugHandler()
    #debug_handler.setLevel(logging.DEBUG)

    # emulate display.debug output
    #display_debug_handler = debug.DisplayConsoleDebugHandler()
    #display_debug_handler.setLevel(logging.DEBUG)
    #debug_handler.setFormatter(debug.DebugFormatter())

#    mplog.setLevel(logging.INFO)
    #mplog.setLevel(multiprocessing.SUBDEBUG)
    #mplog.propagate = True

    # log.addHandler(null_handler)
    # log.addHandler(stream_handler)
    # log.addHandler(file_handler)
    # NOTE: This defines a root '' logger, so any of the modules we use that using logging
    #       will log to our log file as well. This is mostly a dev setup, so disable before release
    # FIXME: disable in future
    #root_logger.addHandler(null_handler)


    #root_logger.addHandler(file_handler)


    #root_logger.addHandler(debug_handler)

    #root_logger.addHandler(display_debug_handler)

    # setup listener
    ql = queue_listener(stream_handler)
    print(ql)

    qh = queue_handler.QueueHandler(log_queue)
    root_logger.addHandler(qh)

#    mplog.addHandler(qh)

    mplog = multiprocessing.get_logger()
    mplog.setLevel(logging.DEBUG)
    mplog.debug('MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM')
    #mplog.propagate = True
    # turn down some loggers. One of many reasons logging is useful
    logging.getLogger('ansible.plugins.action').setLevel(logging.INFO)
    logging.getLogger('ansible.plugins.strategy').setLevel(logging.DEBUG)

    logging.getLogger('ansible.executor').setLevel(logging.DEBUG)
    logging.getLogger('ansible.plugins.connection').setLevel(logging.INFO)
    logging.getLogger('ansible.plugins.PluginLoader').setLevel(logging.INFO)
    #logging.getLogger('ansible.executor.task_executor').setLevel(logging.INFO)
    #logging.getLogger('ansible.executor.play_iterator').setLevel(logging.INFO)

    import logging_tree
    logging_tree.printout()
#    sys.exit()
    return qh, ql
