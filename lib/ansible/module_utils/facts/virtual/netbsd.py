import os

from ansible.module_utils.facts.virtual.base import Virtual
from ansible.module_utils.facts.virtual.sysctl import VirtualSysctlDetectionMixin


class NetBSDVirtual(Virtual, VirtualSysctlDetectionMixin):
    platform = 'NetBSD'

    def get_virtual_facts(self):
        # Set empty values as default
        self.facts['virtualization_type'] = ''
        self.facts['virtualization_role'] = ''

        self.detect_virt_product('machdep.dmi.system-product')
        if self.facts['virtualization_type'] == '':
            self.detect_virt_vendor('machdep.dmi.system-vendor')

        if os.path.exists('/dev/xencons'):
            self.facts['virtualization_type'] = 'xen'
            self.facts['virtualization_role'] = 'guest'
