import os

from ansible.module_utils.facts import Virtual


class SunOSVirtual(Virtual):
    """
    This is a SunOS-specific subclass of Virtual.  It defines
    - virtualization_type
    - virtualization_role
    - container
    """
    platform = 'SunOS'

    def get_virtual_facts(self):

        # Check if it's a zone

        zonename = self.module.get_bin_path('zonename')
        if zonename:
            rc, out, err = self.module.run_command(zonename)
            if rc == 0 and out.rstrip() != "global":
                self.facts['container'] = 'zone'
        # Check if it's a branded zone (i.e. Solaris 8/9 zone)
        if os.path.isdir('/.SUNWnative'):
            self.facts['container'] = 'zone'
        # If it's a zone check if we can detect if our global zone is itself virtualized.
        # Relies on the "guest tools" (e.g. vmware tools) to be installed
        if 'container' in self.facts and self.facts['container'] == 'zone':
            modinfo = self.module.get_bin_path('modinfo')
            if modinfo:
                rc, out, err = self.module.run_command(modinfo)
                if rc == 0:
                    for line in out.splitlines():
                        if 'VMware' in line:
                            self.facts['virtualization_type'] = 'vmware'
                            self.facts['virtualization_role'] = 'guest'
                        if 'VirtualBox' in line:
                            self.facts['virtualization_type'] = 'virtualbox'
                            self.facts['virtualization_role'] = 'guest'

        if os.path.exists('/proc/vz'):
            self.facts['virtualization_type'] = 'virtuozzo'
            self.facts['virtualization_role'] = 'guest'

        # Detect domaining on Sparc hardware
        virtinfo = self.module.get_bin_path('virtinfo')
        if virtinfo:
            # The output of virtinfo is different whether we are on a machine with logical
            # domains ('LDoms') on a T-series or domains ('Domains') on a M-series. Try LDoms first.
            rc, out, err = self.module.run_command("/usr/sbin/virtinfo -p")
            # The output contains multiple lines with different keys like this:
            #   DOMAINROLE|impl=LDoms|control=false|io=false|service=false|root=false
            # The output may also be not formatted and the returncode is set to 0 regardless of the error condition:
            #   virtinfo can only be run from the global zone
            if rc == 0:
                try:
                    for line in out.splitlines():
                        fields = line.split('|')
                        if( fields[0] == 'DOMAINROLE' and fields[1] == 'impl=LDoms' ):
                            self.facts['virtualization_type'] = 'ldom'
                            self.facts['virtualization_role'] = 'guest'
                            hostfeatures = []
                            for field in fields[2:]:
                                arg = field.split('=')
                                if( arg[1] == 'true' ):
                                    hostfeatures.append(arg[0])
                            if( len(hostfeatures) > 0 ):
                                self.facts['virtualization_role'] = 'host (' + ','.join(hostfeatures) + ')'
                except ValueError:
                    pass

        else:
            smbios = self.module.get_bin_path('smbios')
            if not smbios:
                return
            rc, out, err = self.module.run_command(smbios)
            if rc == 0:
                for line in out.splitlines():
                    if 'VMware' in line:
                        self.facts['virtualization_type'] = 'vmware'
                        self.facts['virtualization_role'] = 'guest'
                    elif 'Parallels' in line:
                        self.facts['virtualization_type'] = 'parallels'
                        self.facts['virtualization_role'] = 'guest'
                    elif 'VirtualBox' in line:
                        self.facts['virtualization_type'] = 'virtualbox'
                        self.facts['virtualization_role'] = 'guest'
                    elif 'HVM domU' in line:
                        self.facts['virtualization_type'] = 'xen'
                        self.facts['virtualization_role'] = 'guest'
                    elif 'KVM' in line:
                        self.facts['virtualization_type'] = 'kvm'
                        self.facts['virtualization_role'] = 'guest'
