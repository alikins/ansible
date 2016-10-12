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

# Make coding more python3-ish
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import logging
import logging.handlers
import re

# from ansible.utils.unicode import to_bytes
from ansible.plugins.callback import CallbackBase

# import logging_tree


# NOTE: in Ansible 1.2 or later general logging is available without
# this plugin, just set ANSIBLE_LOG_PATH as an environment variable
# or log_path in the DEFAULTS section of your ansible configuration
# file.  This callback is an example of per hosts logging for those
# that want it.

DEBUG_LOG_FORMAT = "%(asctime)s [%(name)s %(levelname)s %(playbook)s] (%(process)d):%(funcName)s:%(lineno)d - %(message)s"
CONTEXT_DEBUG_LOG_FORMAT = "%(asctime)s [%(name)s %(levelname)s] [playbook=%(playbook)s:%(playbook_uuid)s play=%(play)s:%(play_uuid)s task=%(task)s:%(task_uuid)s] (%(process)d):%(funcName)s:%(lineno)d - %(message)s"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(process)d @%(filename)s:%(lineno)d - %(message)s"
MIN_LOG_FORMAT = "%(asctime)s %(funcName)s:%(lineno)d - %(message)s"


def sluggify(value):
    return '%s' % (re.sub(r'[^\w-]', '_', value).lower().lstrip('_'))


class CallbackModule(CallbackBase):
    """
    Logging callbacks using python stdlin logging
    """
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'notification'
    # CALLBACK_TYPE = "aggregate"
    CALLBACK_NAME = 'generic_stdlog'
    CALLBACK_NEEDS_WHITELIST = True

    log_level = logging.DEBUG
    #log_name = 'ansible_generic_stdlog'
    #log_format = CONTEXT_DEBUG_LOG_FORMAT
    log_format = LOG_FORMAT

    def __init__(self):
        super(CallbackModule, self).__init__()

        # TODO: replace with a stack
        self.host = None

        #self.formatter = logging.Formatter(fmt=self.log_format)

        #stream_handler = logging.StreamHandler()
        #log = logging.getLogger(__name__)
        #self.stream_handler = logging.StreamHandler()
        #stream_handler.setFormatter(self.formatter)

        #self.file_handler = logging.FileHandler('/home/adrian/ansible_stdlog.log')
        #self.file_handler.setFormatter(self.formatter)

        # attempts to be clever about this failed
        self.logger = logging.getLogger('ansible.plugins.callbacks.generic_stdlog')
        #log.addHandler(stream_handler)
        # self.logger.addHandler(self.file_handler)

        self.logger.setLevel(self.log_level)
        import logging_tree
        logging_tree.printout()

    # Note: it would be useful to have a 'always called'
    # callback, and a 'only called if not handled' callback
    def _v2_on_any(self, *args, **kwargs):
        for arg in args:
            self.logger.debug(arg)

        for k, v in kwargs.items():
            self.logger.debug('kw_k=%s', k)
            self.logger.debug('kw_v=%s', v)

    v2_on_any = _v2_on_any
    v2_on_all = _v2_on_any
    #v2_on_missing = _v2_on_any
