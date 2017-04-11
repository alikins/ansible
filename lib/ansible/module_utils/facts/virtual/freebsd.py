from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os

from ansible.module_utils.facts.virtual.base import Virtual


class FreeBSDVirtual(Virtual):
    """
    This is a FreeBSD-specific subclass of Virtual.  It defines
    - virtualization_type
    - virtualization_role
    """
    platform = 'FreeBSD'

    def get_virtual_facts(self):
        virtual_facts = {}
        # Set empty values as default
        virtual_facts['virtualization_type'] = ''
        virtual_facts['virtualization_role'] = ''

        if os.path.exists('/dev/xen/xenstore'):
            virtual_facts['virtualization_type'] = 'xen'
            virtual_facts['virtualization_role'] = 'guest'

        return virtual_facts
