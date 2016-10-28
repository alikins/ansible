
import logging
import multiprocessing
import os
import sys

from ansible.logger import formats
from ansible.logger.loggers import default
from ansible.logger.handlers import default_handler
from ansible.logger.handlers import queue_handler
from ansible.logger import dict_setup
from ansible.logger.formatters import color_debug
from ansible.logger.filters import display_compat as display_compat_filter

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


def queue_listener(handlers):
    # This seems like a bad idea...
    global log_queue
    log_queue = multiprocessing.Queue()
    queue_listener = queue_handler.QueueListener(log_queue, *handlers)

    queue_listener.start()
    return queue_listener


def log_queue_listener_stop(queue):
    queue.put(None)


def log_setup_code(name=None, level=None, fmt=None, log_stdout=None):
    name = name or 'ansible'

    null_handler = logging.NullHandler()

    root_log_level = os.getenv('ROOT_LOG_LEVEL', None) or logging.DEBUG
    root_logger = logging.getLogger()
    root_logger.setLevel(root_log_level)
    root_logger.addHandler(null_handler)

    log_level = level or os.getenv('%s_log_level' % name, None) or logging.DEBUG
    log = logging.getLogger(name)
    log.setLevel(log_level)

    filename_env = os.environ.get('ANSIBLE_LOG_FILE', None)
    file_handler = None
    if filename_env:
        filename = os.path.expanduser(filename_env)

        print('filename=%s' % filename)
        try:
            file_handler = default_handler.AnsibleWatchedFileHandler(filename=filename)
        # fallback to NullHandler if we can't open our log file
        except Exception as e:
            sys.stderr.write('%s\n' % e)
            log.error(e)
            log.exception(e)
            raise
            file_handler = logging.NullHandler()

        file_handler.setLevel(logging.DEBUG)
        file_fmt_string = fmt or formats.THREAD_DEBUG_LOG_FORMAT
        file_formatter = logging.Formatter(fmt=file_fmt_string)
        file_handler.setFormatter(file_formatter)

    stream_handler = None
    stream_handler_env = log_stdout or os.getenv('ANSIBLE_LOG_STDOUT', None)
    if stream_handler_env:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(log_level)

        # fmt=None uses ColorFormatters built in format
        fmt_string = fmt or os.getenv('%s_fmt_string' % name, None)
        formatter = color_debug.ColorFormatter(fmt=fmt_string, use_color=True, default_color_by_attr='process')
        formatter.use_thread_color = True
        stream_handler.setFormatter(formatter)

        df = display_compat_filter.DisplayCompatOtherLoggingFilter(name='')
        stream_handler.addFilter(df)

    listener_handlers = [x for x in [stream_handler, file_handler] if x]
    print(listener_handlers)
    ql = queue_listener(listener_handlers)
    qh = queue_handler.QueueHandler(log_queue)
    qh.setLevel(log_level)

    root_logger.addHandler(qh)

    mp_log_level = os.getenv('MP_LOG_LEVEL', None)
    if mp_log_level:
        mplog = multiprocessing.get_logger()
        mplog.setLevel(mp_log_level)
        mplog.propagate = True
        mplog.addHandler(null_handler)
        mplog.addHandler(qh)

    # turn down some loggers. One of many reasons logging is useful
    logging.getLogger('ansible.plugins.action').setLevel(logging.INFO)
    logging.getLogger('ansible.plugins').setLevel(logging.INFO)
    logging.getLogger('ansible.executor.play_iterator').setLevel(logging.INFO)
    #logging.getLogger('ansible.plugins.strategy').setLevel(logging.DEBUG)
    logging.getLogger('ansible.playbook').setLevel(logging.INFO)
    #logging.getLogger('ansible.executor').setLevel(logging.DEBUG)
    logging.getLogger('ansible.plugins.connection').setLevel(multiprocessing.SUBDEBUG)
    logging.getLogger('ansible.plugins.PluginLoader').setLevel(logging.INFO)
    #logging.getLogger('ansible.executor.task_executor').setLevel(logging.INFO)
    #logging.getLogger('ansible.executor.play_iterator').setLevel(logging.INFO)

    return qh, ql
