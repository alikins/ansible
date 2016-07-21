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

import getpass
import logging

# TODO: config based logging setup
# TODO: Any log Formatters or Handlers that are ansible specific
# TODO: base logging setup
# TODO: NullHandler for py2.4

# logging.INFO = 20
V = 17
VV = 16
VVV = 15
# logging.DEBUG = 10
VVVV = 9
VVVVV = 10
#DEBUG_LOG_FORMAT = "%(asctime)s [%(name)s %(levelname)s %(playbook)s] (%(process)d):%(funcName)s:%(lineno)d - %(message)s"
DEBUG_LOG_FORMAT = "%(asctime)s [%(name)s %(levelname)s] (%(process)d):%(funcName)s:%(lineno)d - %(message)s"

# rough approx of existing display format
# based on:
#logger = logging.getLogger("p=%s u=%s | " % (mypid, user))
# logging.basicConfig(filename=path, level=logging.DEBUG, format='%(asctime)s %(name)s %(message)s')
# self.display("<%s> %s" % (host, msg), color=C.COLOR_VERBOSE, screen_only=True)
# user and hostname attributes would be up to a logging.Filter to add
# DISPLAY_LOG_FORMAT = "%(asctime)s p=%(process)d u=%(user)s <%(hostname)s> %(message)s"

user = getpass.getuser()
hostname = 'FIXME'
OLD_LOG_FORMAT = "%(asctime)s p=%(process)d u=" + user + " <" + hostname + "> " + "%(message)s"

import logging_tree

def log_setup():
    null_handler = logging.NullHandler()

    root_logger = logging.getLogger()
    # root_logger.setLevel(logging.CRITICAL)
    root_logger.setLevel(logging.DEBUG)
    root_logger.propagate = True
    # root_logger.addHandler(null_handler)

    log = logging.getLogger('ansible')
    log.setLevel(logging.DEBUG)
    # log.setLevel(logging.CRITICAL)
    formatter = logging.Formatter(DEBUG_LOG_FORMAT)
    # log.propagate = True

    # stream_handler = logging.StreamHandler()
    # stream_handler.setLevel(logging.DEBUG)
    # stream_handler.setFormatter(formatter)

    # file_handler = logging.FileHandler(filename='/home/adrian/ansible.log')
    file_handler = logging.handlers.WatchedFileHandler(filename='/home/adrian/ansible.log')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # log.addHandler(null_handler)
    # log.addHandler(stream_handler)
    # log.addHandler(file_handler)
    root_logger.addHandler(file_handler)
    # logging.basicConfig(level=logging.DEBUG,
    #                    filename='/home/adrian/ansible.log',
    #                    format=DEBUG_LOG_FORMAT)
    #                   format=DISPLAY_LOG_FORMAT)

logging_tree.printout()
log_setup()
logging_tree.printout()
