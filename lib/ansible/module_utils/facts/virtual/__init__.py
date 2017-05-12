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

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.module_utils.facts.virtual import base
from ansible.module_utils.facts.virtual import sysctl

from ansible.module_utils.facts.virtual import dragonfly
from ansible.module_utils.facts.virtual import freebsd
from ansible.module_utils.facts.virtual import hpux
from ansible.module_utils.facts.virtual import linux
from ansible.module_utils.facts.virtual import netbsd
from ansible.module_utils.facts.virtual import openbsd
from ansible.module_utils.facts.virtual import sunos

__all__ = ['base', 'dragonfly', 'freebsd', 'hpux',
           'linux', 'netbsd', 'openbsd', 'sunos',
           'sysctl']
