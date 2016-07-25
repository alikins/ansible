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
DEBUG_LOG_FORMAT = "%(asctime)s [%(name)s %(levelname)s %(playbook)s] (%(process)d):%(funcName)s:%(lineno)d - %(message)s"
logging.basicConfig(level=logging.DEBUG, filename='/home/adrian/ansible.log')
#logging.basicConfig(level=logging.DEBUG,)
