from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import re

from ansible.module_utils.facts.virtual.base import Virtual
from ansible.module_utils.facts.virtual.sysctl import VirtualSysctlDetectionMixin

from ansible.module_utils.facts.utils import get_file_content


class OpenBSDVirtual(Virtual, VirtualSysctlDetectionMixin):
    """
    This is a OpenBSD-specific subclass of Virtual.  It defines
    - virtualization_type
    - virtualization_role
    """
    platform = 'OpenBSD'
    DMESG_BOOT = '/var/run/dmesg.boot'

    def get_virtual_facts(self):

        # Set empty values as default
        self.facts['virtualization_type'] = ''
        self.facts['virtualization_role'] = ''

        self.detect_virt_product('hw.product')
        if self.facts['virtualization_type'] == '':
            self.detect_virt_vendor('hw.vendor')

        # Check the dmesg if vmm(4) attached, indicating the host is
        # capable of virtualization.
        dmesg_boot = get_file_content(OpenBSDVirtual.DMESG_BOOT)
        for line in dmesg_boot.splitlines():
            match = re.match('^vmm0 at mainbus0: (SVM/RVI|VMX/EPT)$', line)
            if match:
                self.facts['virtualization_type'] = 'vmm'
                self.facts['virtualization_role'] = 'host'
