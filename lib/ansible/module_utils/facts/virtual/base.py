# base classes for virtualization facts
# -*- coding: utf-8 -*-
#
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
#

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import platform

from ansible.module_utils.basic import get_all_subclasses
from ansible.module_utils.six import PY3

from ansible.module_utils.facts.facts import Facts

from ansible.module_utils.facts.collector import BaseFactCollector


class Virtual(Facts):
    """
    This is a generic Virtual subclass of Facts.  This should be further
    subclassed to implement per platform.  If you subclass this,
    you should define:
    - virtualization_type
    - virtualization_role
    - container (e.g. solaris zones, freebsd jails, linux containers)

    All subclasses MUST define platform.
    """

    def __new__(cls, *arguments, **keyword):
        # When Virtual is created, it chooses a subclass to create instead.
        # This check prevents the subclass from then trying to find a subclass
        # and create that.
        if cls is not Virtual:
            return super(Virtual, cls).__new__(cls)

        subclass = cls
        for sc in get_all_subclasses(Virtual):
            if sc.platform == platform.system():
                subclass = sc

        if PY3:
            return super(cls, subclass).__new__(subclass)
        else:
            return super(cls, subclass).__new__(subclass, *arguments, **keyword)

    # FIXME: just here for existing tests cases till they are updated
    def populate(self):
        virtual_facts = self.get_virtual_facts()

        return virtual_facts

    def get_virtual_facts(self):
        virtual_facts = {'virtualization_type': '',
                         'virtualization_role': ''}
        return virtual_facts


class VirtualCollector(BaseFactCollector):
    _fact_ids = set(['virtual',
                     'virtualization_type', 'virtualization_role'])

    def collect(self, module=None, collected_facts=None):
        collected_facts = collected_facts or {}

        # Virtual isnt update to not munge self.facts yet, so just pass in the facts it
        # needs
        virtual_facts = Virtual(module, cached_facts=collected_facts.copy())

        facts_dict = virtual_facts.get_virtual_facts()

        return facts_dict
