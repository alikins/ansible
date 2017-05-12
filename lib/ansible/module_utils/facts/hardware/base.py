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

from ansible.module_utils.facts.facts import Facts

from ansible.module_utils.facts.collector import BaseFactCollector


class Hardware(Facts):
    """
    This is a base Hardware subclass of Facts.  This should be further
    subclassed to implement per platform.

    All subclasses MUST define self.platform as a class variable.
    """
    platform = 'Generic'
    impl = True

    def populate(self, collected_facts=None):
        return {}


class HardwareCollector(BaseFactCollector):
    name = 'hardware'
    _fact_ids = set(['processor',
                     'processor_cores',
                     'processor_count',
                     # TODO: mounts isnt exactly hardware
                     'mounts',
                     'devices',
                     'virtualization_type', 'virtualization_role'])

    def collect(self, module=None, collected_facts=None):
        collected_facts = collected_facts or {}

        if not module:
            return {}

        hardware_facts = Hardware(module)

        facts_dict = hardware_facts.populate(collected_facts=collected_facts)

        return facts_dict
