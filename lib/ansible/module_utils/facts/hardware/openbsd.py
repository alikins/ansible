import re

from ansible.module_utils._text import to_text

from ansible.module_utils.facts import Hardware
from ansible.module_utils.facts import TimeoutError, timeout

from ansible.module_utils.facts.utils import get_file_content


class OpenBSDHardware(Hardware):
    """
    OpenBSD-specific subclass of Hardware. Defines memory, CPU and device facts:
    - memfree_mb
    - memtotal_mb
    - swapfree_mb
    - swaptotal_mb
    - processor (a list)
    - processor_cores
    - processor_count
    - processor_speed

    In addition, it also defines number of DMI facts and device facts.
    """
    platform = 'OpenBSD'

    def populate(self):
        self.sysctl = self.get_sysctl(['hw'])
        self.get_memory_facts()
        self.get_processor_facts()
        self.get_device_facts()
        try:
            self.get_mount_facts()
        except TimeoutError:
            pass
        self.get_dmi_facts()
        return self.facts

    @timeout()
    def get_mount_facts(self):
        self.facts['mounts'] = []
        fstab = get_file_content('/etc/fstab')
        if fstab:
            for line in fstab.splitlines():
                if line.startswith('#') or line.strip() == '':
                    continue
                fields = re.sub(r'\s+',' ', line).split()
                if fields[1] == 'none' or fields[3] == 'xx':
                    continue
                size_total, size_available = self._get_mount_size_facts(fields[1])
                self.facts['mounts'].append({
                    'mount': fields[1],
                    'device': fields[0],
                    'fstype' : fields[2],
                    'options': fields[3],
                    'size_total': size_total,
                    'size_available': size_available
                })

    def get_memory_facts(self):
        # Get free memory. vmstat output looks like:
        #  procs    memory       page                    disks    traps          cpu
        #  r b w    avm     fre  flt  re  pi  po  fr  sr wd0 fd0  int   sys   cs us sy id
        #  0 0 0  47512   28160   51   0   0   0   0   0   1   0  116    89   17  0  1 99
        rc, out, err = self.module.run_command("/usr/bin/vmstat")
        if rc == 0:
            self.facts['memfree_mb'] = int(out.splitlines()[-1].split()[4]) // 1024
            self.facts['memtotal_mb'] = int(self.sysctl['hw.usermem']) // 1024 // 1024

        # Get swapctl info. swapctl output looks like:
        # total: 69268 1K-blocks allocated, 0 used, 69268 available
        # And for older OpenBSD:
        # total: 69268k bytes allocated = 0k used, 69268k available
        rc, out, err = self.module.run_command("/sbin/swapctl -sk")
        if rc == 0:
            swaptrans = { ord(u'k'): None, ord(u'm'): None, ord(u'g'): None}
            data = to_text(out, errors='surrogate_or_strict').split()
            self.facts['swapfree_mb'] = int(data[-2].translate(swaptrans)) // 1024
            self.facts['swaptotal_mb'] = int(data[1].translate(swaptrans)) // 1024

    def get_processor_facts(self):
        processor = []
        for i in range(int(self.sysctl['hw.ncpu'])):
            processor.append(self.sysctl['hw.model'])

        self.facts['processor'] = processor
        # The following is partly a lie because there is no reliable way to
        # determine the number of physical CPUs in the system. We can only
        # query the number of logical CPUs, which hides the number of cores.
        # On amd64/i386 we could try to inspect the smt/core/package lines in
        # dmesg, however even those have proven to be unreliable.
        # So take a shortcut and report the logical number of processors in
        # 'processor_count' and 'processor_cores' and leave it at that.
        self.facts['processor_count'] = self.sysctl['hw.ncpu']
        self.facts['processor_cores'] = self.sysctl['hw.ncpu']

    def get_device_facts(self):
        devices = []
        devices.extend(self.sysctl['hw.disknames'].split(','))
        self.facts['devices'] = devices

    def get_dmi_facts(self):
        # We don't use dmidecode(1) here because:
        # - it would add dependency on an external package
        # - dmidecode(1) can only be ran as root
        # So instead we rely on sysctl(8) to provide us the information on a
        # best-effort basis. As a bonus we also get facts on non-amd64/i386
        # platforms this way.
        sysctl_to_dmi = {
            'hw.product':  'product_name',
            'hw.version':  'product_version',
            'hw.uuid':     'product_uuid',
            'hw.serialno': 'product_serial',
            'hw.vendor':   'system_vendor',
        }

        for mib in sysctl_to_dmi:
            if mib in self.sysctl:
                self.facts[sysctl_to_dmi[mib]] = self.sysctl[mib]
