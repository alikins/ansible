from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import re


class VirtualSysctlDetectionMixin(object):
    def detect_sysctl(self):
        self.sysctl_path = self.module.get_bin_path('sysctl')

    def detect_virt_product(self, key):
        self.detect_sysctl()
        if self.sysctl_path:
            rc, out, err = self.module.run_command("%s -n %s" % (self.sysctl_path, key))
            if rc == 0:
                if re.match('(KVM|Bochs|SmartDC).*', out):
                    self.facts['virtualization_type'] = 'kvm'
                    self.facts['virtualization_role'] = 'guest'
                elif re.match('.*VMware.*', out):
                    self.facts['virtualization_type'] = 'VMware'
                    self.facts['virtualization_role'] = 'guest'
                elif out.rstrip() == 'VirtualBox':
                    self.facts['virtualization_type'] = 'virtualbox'
                    self.facts['virtualization_role'] = 'guest'
                elif out.rstrip() == 'HVM domU':
                    self.facts['virtualization_type'] = 'xen'
                    self.facts['virtualization_role'] = 'guest'
                elif out.rstrip() == 'Parallels':
                    self.facts['virtualization_type'] = 'parallels'
                    self.facts['virtualization_role'] = 'guest'
                elif out.rstrip() == 'RHEV Hypervisor':
                    self.facts['virtualization_type'] = 'RHEV'
                    self.facts['virtualization_role'] = 'guest'

    def detect_virt_vendor(self, key):
        self.detect_sysctl()
        if self.sysctl_path:
            rc, out, err = self.module.run_command("%s -n %s" % (self.sysctl_path, key))
            if rc == 0:
                if out.rstrip() == 'QEMU':
                    self.facts['virtualization_type'] = 'kvm'
                    self.facts['virtualization_role'] = 'guest'
                if out.rstrip() == 'OpenBSD':
                    self.facts['virtualization_type'] = 'vmm'
                    self.facts['virtualization_role'] = 'guest'
