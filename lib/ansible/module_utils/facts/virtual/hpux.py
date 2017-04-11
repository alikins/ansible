from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os
import re

from ansible.module_utils.facts.virtual.base import Virtual


class HPUXVirtual(Virtual):
    """
    This is a HP-UX specific subclass of Virtual. It defines
    - virtualization_type
    - virtualization_role
    """
    platform = 'HP-UX'

    def get_virtual_facts(self):
        virtual_facts = {}
        if os.path.exists('/usr/sbin/vecheck'):
            rc, out, err = self.module.run_command("/usr/sbin/vecheck")
            if rc == 0:
                virtual_facts['virtualization_type'] = 'guest'
                virtual_facts['virtualization_role'] = 'HP vPar'
        if os.path.exists('/opt/hpvm/bin/hpvminfo'):
            rc, out, err = self.module.run_command("/opt/hpvm/bin/hpvminfo")
            if rc == 0 and re.match('.*Running.*HPVM vPar.*', out):
                virtual_facts['virtualization_type'] = 'guest'
                virtual_facts['virtualization_role'] = 'HPVM vPar'
            elif rc == 0 and re.match('.*Running.*HPVM guest.*', out):
                virtual_facts['virtualization_type'] = 'guest'
                virtual_facts['virtualization_role'] = 'HPVM IVM'
            elif rc == 0 and re.match('.*Running.*HPVM host.*', out):
                virtual_facts['virtualization_type'] = 'host'
                virtual_facts['virtualization_role'] = 'HPVM'
        if os.path.exists('/usr/sbin/parstatus'):
            rc, out, err = self.module.run_command("/usr/sbin/parstatus")
            if rc == 0:
                virtual_facts['virtualization_type'] = 'guest'
                virtual_facts['virtualization_role'] = 'HP nPar'

        return virtual_facts
