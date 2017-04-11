from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import platform

from ansible.module_utils.basic import get_all_subclasses
from ansible.module_utils.six import PY3

from ansible.module_utils.facts.facts import Facts

from ansible.module_utils.facts.collector import BaseFactCollector


class Hardware(Facts):
    """
    This is a generic Hardware subclass of Facts.  This should be further
    subclassed to implement per platform.  If you subclass this, it
    should define:
    - memfree_mb
    - memtotal_mb
    - swapfree_mb
    - swaptotal_mb
    - processor (a list)
    - processor_cores
    - processor_count

    All subclasses MUST define platform.
    """
    platform = 'Generic'

    def __new__(cls, *arguments, **keyword):
        # When Hardware is created, it chooses a subclass to create instead.
        # This check prevents the subclass from then trying to find a subclass
        # and create that.
        if cls is not Hardware:
            return super(Hardware, cls).__new__(cls)

        subclass = cls
        for sc in get_all_subclasses(Hardware):
            if sc.platform == platform.system():
                subclass = sc
        if PY3:
            return super(cls, subclass).__new__(subclass)
        else:
            return super(cls, subclass).__new__(subclass, *arguments, **keyword)

    def populate(self):
        return self.facts


class HardwareCollector(BaseFactCollector):
    _fact_ids = set(['hardware',
                     'processor',
                     'processor_cores',
                     'processor_count',
                     # TODO: mounts isnt exactly hardware
                     'mounts',
                     'devices',
                     'virtualization_type', 'virtualization_role'])

    def collect(self, collected_facts=None):
        collected_facts = collected_facts or {}

        # Virtual isnt update to not munge self.facts yet, so just pass in the facts it
        # needs

        # facts from other modules that we need to pass to Hardware
        # FIXME: this can be removed once Hardware stops return self.facts
        collected_keys = ('ansible_processor',
                          'ansible_architecture',
                          'ansible_machine',
                          'ansible_distribution_version')
        filtered_collected_facts = {}
        for key in collected_keys:
            if key in collected_facts:
                filtered_collected_facts[key] = collected_facts[key]

        hardware_facts = Hardware(self.module, cached_facts=filtered_collected_facts)

        facts_dict = hardware_facts.populate()

        return facts_dict
