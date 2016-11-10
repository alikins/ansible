
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


def log_setup(config_dict=None):
    # TODO: if we decide we need a way to configure our configuration style, figure it out here
    try:
        return dict_setup.log_setup_yaml_file(DEFAULT_YAML_LOGGING_CONF)
    except Exception as e:
        sys.stderr.write('error setting up logging: %s' % e)
        # TODO: raise a logging setup exception since we likely want to setup logging first, then the big try/except for cli
        raise


def env_log_level(var_name):

    env_var_value = os.environ.get(var_name, None)
    print('%s=%s' % (var_name, env_var_value))

    if not env_var_value:
        return None

    env_var_value = env_var_value.strip()

    log_level = getattr(logging, env_var_value, env_var_value)

    try:
        log_level = int(log_level)
    except ValueError:
        raise Exception('the log level %s is not known' % env_var_value)

    return log_level


def log_setup_code(name=None, level=None, fmt=None, log_stdout=None):
    name = name or 'ansible'

    null_handler = logging.NullHandler()

    #root_log_level = os.getenv('ROOT_LOG_LEVEL', None) or logging.DEBUG
    root_log_level = env_log_level('ROOT_LOG_LEVEL') or multiprocessing.SUBDEBUG

    root_logger = logging.getLogger()
    root_logger.setLevel(root_log_level)
    root_logger.addHandler(null_handler)

    log_level = level or env_log_level('%s_log_level' % name) or logging.DEBUG
    log = logging.getLogger(name)
    # log_level = logging.INFO
    #log_level = logging.CRITICAL
    log.setLevel(log_level)

    filename_env = os.environ.get('ANSIBLE_LOG_FILE', None)
    file_handler = None
    if filename_env:
        filename = os.path.expanduser(filename_env)

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
    stream_handler_env = log_stdout or os.environ.get('ANSIBLE_LOG_STDOUT', None)
    if stream_handler_env:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(log_level)

        # fmt=None uses ColorFormatters built in format
        fmt_string = fmt or os.environ.get('%s_fmt_string' % name, None)
        formatter = color_debug.ColorFormatter(fmt=fmt_string, use_color=True, default_color_by_attr='process')
        formatter.use_thread_color = True
        stream_handler.setFormatter(formatter)

#        df = display_compat_filter.DisplayCompatOtherLoggingFilter(name='')
#        stream_handler.addFilter(df)

    # Could add a NullHandler here
    listener_handlers = [x for x in [stream_handler, file_handler] if x]

    for lh in listener_handlers:
        logging.getLogger('ansible_handler').addHandler(lh)

    ql = queue_handler.QueueListener()
    qh = queue_handler.QueueHandler(ql.queue)
    qh.setLevel(log_level)

    root_logger.addHandler(qh)

    mp_log_level = env_log_level('MP_LOG_LEVEL') or logging.INFO
    #mp_log_level = logging.DEBUG
    #mp_log_level = multiprocessing.SUBDEBUG
    if mp_log_level:
        mplog = multiprocessing.get_logger()
        mplog.setLevel(mp_log_level)
        #mplog.propagate = True
        mplog.addHandler(null_handler)
        #mplog.addHandler(qh)
        #mp_stream_handler = logging.StreamHandler(sys.stderr)
        #mp_stream_handler.setLevel(log_level)
        #mplog.addHandler(stream_handler)

    logging.getLogger("paramiko").setLevel(logging.WARNING)
    # turn down some loggers. One of many reasons logging is useful
    ##logging.getLogger('ansible.plugins.action').setLevel(logging.INFO)
    ##logging.getLogger('ansible.plugins').setLevel(logging.INFO)
    ##logging.getLogger('ansible.executor.play_iterator').setLevel(logging.INFO)
    #logging.getLogger('ansible.plugins.strategy').setLevel(logging.DEBUG)
    ##logging.getLogger('ansible.playbook').setLevel(logging.INFO)
    #logging.getLogger('ansible.executor').setLevel(logging.DEBUG)
    ##logging.getLogger('ansible.plugins.connection').setLevel(multiprocessing.SUBDEBUG)
    ##logging.getLogger('ansible.plugins.PluginLoader').setLevel(logging.INFO)
    #logging.getLogger('ansible.executor.task_executor').setLevel(logging.INFO)
    #logging.getLogger('ansible.executor.play_iterator').setLevel(logging.INFO)

    #logging.getLogger('ansible_handler').setFormatter(logging.Formatter('%(asctime)s -%(name)s - %(process)d - %(message)s'))
    import logging_tree
    logging_tree.printout()

    #sys.exit()
    return qh, ql
