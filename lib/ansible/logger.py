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
DISPLAY_LOG_FORMAT = "%(asctime)s p=%(process)d u=" + user + " <" + hostname + "> " + "%(message)s"

logging.basicConfig(level=logging.DEBUG,
                    filename='/home/adrian/ansible.log',
                    #format=DEBUG_LOG_FORMAT)
                    format=DISPLAY_LOG_FORMAT)
#logging.basicConfig(level=logging.DEBUG,)
