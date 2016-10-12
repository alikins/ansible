
import logging
import logging.config
import os
import sys

import yaml


# TODO: config option?
# TODO: env var setting?
#
def log_setup_yaml_file(yaml_config_file):
    config_file = os.environ.get('ANSIBLE_LOG_CONFIG', None) or yaml_config_file
    print('config %s' % config_file)
    try:
        with open(config_file, 'r') as log_f:
            logging_conf = yaml.load(log_f.read())
            return log_setup_dict(logging_conf)
    except Exception as e:
        sys.stderr.write('Error reading logging config file (%s) : %s' % (config_file, e))
        raise


def log_setup_dict(config_dict):
    return logging.config.dictConfig(config_dict)
