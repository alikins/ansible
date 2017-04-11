from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os

from ansible.module_utils.facts.virtual.base import Virtual
from ansible.module_utils.facts.virtual.sysctl import VirtualSysctlDetectionMixin


class NetBSDVirtual(Virtual, VirtualSysctlDetectionMixin):
    platform = 'NetBSD'

    def get_virtual_facts(self):
        virtual_facts = {}
        # Set empty values as default
        virtual_facts['virtualization_type'] = ''
        virtual_facts['virtualization_role'] = ''

        virtual_product_facts = self.detect_virt_product('machdep.dmi.system-product')
        virtual_facts.update(virtual_product_facts)

        if virtual_facts['virtualization_type'] == '':
            virtual_vendor_facts = self.detect_virt_vendor('machdep.dmi.system-vendor')
            virtual_facts.update(virtual_vendor_facts)

        if os.path.exists('/dev/xencons'):
            virtual_facts['virtualization_type'] = 'xen'
            virtual_facts['virtualization_role'] = 'guest'

        return virtual_facts
