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

from ansible.module_utils.facts.collector import BaseFactCollector
from ansible.module_utils.facts.namespace import FactNamespace

from ansible.module_utils.facts.system.user import UserFactCollector
from ansible.module_utils.facts.system.python import PythonFactCollector
from ansible.module_utils.facts.system.dns import DnsFactCollector


class SystemFactCollector(BaseFactCollector):
    def __init__(self, collectors=None, namespace=None):
        _collectors = []

        user_namespace = FactNamespace(namespace_name='user')
        user_collector = UserFactCollector(namespace=user_namespace)

        python_namespace = FactNamespace(namespace_name='python')
        python_collector = PythonFactCollector(namespace=python_namespace)

        dns_collector = DnsFactCollector()

        _collectors = [user_collector,
                       python_collector,
                       dns_collector]

        system_namespace = FactNamespace(namespace_name='system')

        super(SystemFactCollector, self).__init__(collectors=_collectors,
                                                  namespace=system_namespace)

