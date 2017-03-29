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

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.module_utils.facts.network import aix
from ansible.module_utils.facts.network import darwin
from ansible.module_utils.facts.network import dragonfly
from ansible.module_utils.facts.network import freebsd
from ansible.module_utils.facts.network import hpux
from ansible.module_utils.facts.network import hurd
from ansible.module_utils.facts.network import linux
from ansible.module_utils.facts.network import netbsd
from ansible.module_utils.facts.network import openbsd
from ansible.module_utils.facts.network import sunos

__all__ = [aix, darwin, dragonfly, freebsd, hpux, hurd, linux, netbsd, openbsd, sunos]
