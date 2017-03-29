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

        # Set empty values as default
        self.facts['virtualization_type'] = ''
        self.facts['virtualization_role'] = ''

        if os.path.exists('/dev/xen/xenstore'):
            self.facts['virtualization_type'] = 'xen'
            self.facts['virtualization_role'] = 'guest'
