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

import platform

from ansible.module_utils.basic import get_all_subclasses
from ansible.module_utils.six import PY3

from ansible.module_utils.facts.facts import Facts

from ansible.module_utils.facts.collector import BaseFactCollector


class Network(Facts):
    """
    This is a generic Network subclass of Facts.  This should be further
    subclassed to implement per platform.  If you subclass this,
    you must define:
    - interfaces (a list of interface names)
    - interface_<name> dictionary of ipv4, ipv6, and mac address information.

    All subclasses MUST define platform.
    """
    platform = 'Generic'

    IPV6_SCOPE = {'0': 'global',
                  '10': 'host',
                  '20': 'link',
                  '40': 'admin',
                  '50': 'site',
                  '80': 'organization'}

    def __new__(cls, *arguments, **keyword):
        # When Network is created, it chooses a subclass to create instead.
        # This check prevents the subclass from then trying to find a subclass
        # and create that.
        if cls is not Network:
            return super(Network, cls).__new__(cls)

        subclass = cls

        for sc in get_all_subclasses(Network):
            if sc.platform == platform.system():
                subclass = sc
        if PY3:
            return super(cls, subclass).__new__(subclass)
        else:
            return super(cls, subclass).__new__(subclass, *arguments, **keyword)

    # TODO: more or less abstract/NotImplemented
    def populate(self, collected_facts=None):
        return {}


class NetworkCollector(BaseFactCollector):
    # MAYBE: we could try to build this based on the arch specific implemementation of Network() or its kin
    name = 'network'
    _fact_ids = set(['interfaces',
                     'default_ipv4',
                     'default_ipv6',
                     'all_ipv4_addresses',
                     'all_ipv6_addresses'])

    def collect(self, module=None, collected_facts=None):
        collected_facts = collected_facts or {}
        if not module:
            return {}

        # Network munges cached_facts by side effect, so give it a copy
        network_facts = Network(module)

        facts_dict = network_facts.populate(collected_facts=collected_facts)

        return facts_dict
