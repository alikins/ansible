import re

from ansible.module_utils.facts.utils import get_file_content

from ansible.module_utils.facts import Hardware
from ansible.module_utils.facts import TimeoutError, timeout


class SunOSHardware(Hardware):
    """
    In addition to the generic memory and cpu facts, this also sets
    swap_reserved_mb and swap_allocated_mb that is available from *swap -s*.
    """
    platform = 'SunOS'

    def populate(self):
        self.get_cpu_facts()
        self.get_memory_facts()
        self.get_dmi_facts()
        self.get_device_facts()
        self.get_uptime_facts()
        try:
            self.get_mount_facts()
        except TimeoutError:
            pass
        return self.facts

    def get_cpu_facts(self):
        physid = 0
        sockets = {}
        rc, out, err = self.module.run_command("/usr/bin/kstat cpu_info")
        self.facts['processor'] = []
        for line in out.splitlines():
            if len(line) < 1:
                continue
            data = line.split(None, 1)
            key = data[0].strip()
            # "brand" works on Solaris 10 & 11. "implementation" for Solaris 9.
            if key == 'module:':
                brand = ''
            elif key == 'brand':
                brand = data[1].strip()
            elif key == 'clock_MHz':
                clock_mhz = data[1].strip()
            elif key == 'implementation':
                processor = brand or data[1].strip()
                # Add clock speed to description for SPARC CPU
                if self.facts['machine'] != 'i86pc':
                    processor += " @ " + clock_mhz + "MHz"
                if 'processor' not in self.facts:
                    self.facts['processor'] = []
                self.facts['processor'].append(processor)
            elif key == 'chip_id':
                physid = data[1].strip()
                if physid not in sockets:
                    sockets[physid] = 1
                else:
                    sockets[physid] += 1
        # Counting cores on Solaris can be complicated.
        # https://blogs.oracle.com/mandalika/entry/solaris_show_me_the_cpu
        # Treat 'processor_count' as physical sockets and 'processor_cores' as
        # virtual CPUs visisble to Solaris. Not a true count of cores for modern SPARC as
        # these processors have: sockets -> cores -> threads/virtual CPU.
        if len(sockets) > 0:
            self.facts['processor_count'] = len(sockets)
            self.facts['processor_cores'] = reduce(lambda x, y: x + y, sockets.values())
        else:
            self.facts['processor_cores'] = 'NA'
            self.facts['processor_count'] = len(self.facts['processor'])

    def get_memory_facts(self):
        rc, out, err = self.module.run_command(["/usr/sbin/prtconf"])
        for line in out.splitlines():
            if 'Memory size' in line:
                self.facts['memtotal_mb'] = int(line.split()[2])
        rc, out, err = self.module.run_command("/usr/sbin/swap -s")
        allocated = int(out.split()[1][:-1])
        reserved = int(out.split()[5][:-1])
        used = int(out.split()[8][:-1])
        free = int(out.split()[10][:-1])
        self.facts['swapfree_mb'] = free // 1024
        self.facts['swaptotal_mb'] = (free + used) // 1024
        self.facts['swap_allocated_mb'] = allocated // 1024
        self.facts['swap_reserved_mb'] = reserved // 1024

    @timeout()
    def get_mount_facts(self):
        self.facts['mounts'] = []
        # For a detailed format description see mnttab(4)
        #   special mount_point fstype options time
        fstab = get_file_content('/etc/mnttab')
        if fstab:
            for line in fstab.splitlines():
                fields = line.split('\t')
                size_total, size_available = self._get_mount_size_facts(fields[1])
                self.facts['mounts'].append({
                    'mount': fields[1],
                    'device': fields[0],
                    'fstype' : fields[2],
                    'options': fields[3],
                    'time': fields[4],
                    'size_total': size_total,
                    'size_available': size_available
                })

    def get_dmi_facts(self):
        uname_path = self.module.get_bin_path("prtdiag")
        rc, out, err = self.module.run_command(uname_path)
        """
        rc returns 1
        """
        if out:
            system_conf = out.split('\n')[0]
            found = re.search(r'(\w+\sEnterprise\s\w+)',system_conf)
            if found:
                self.facts['product_name'] = found.group(1)

    def get_device_facts(self):
        # Device facts are derived for sdderr kstats. This code does not use the
        # full output, but rather queries for specific stats.
        # Example output:
        # sderr:0:sd0,err:Hard Errors     0
        # sderr:0:sd0,err:Illegal Request 6
        # sderr:0:sd0,err:Media Error     0
        # sderr:0:sd0,err:Predictive Failure Analysis     0
        # sderr:0:sd0,err:Product VBOX HARDDISK   9
        # sderr:0:sd0,err:Revision        1.0
        # sderr:0:sd0,err:Serial No       VB0ad2ec4d-074a
        # sderr:0:sd0,err:Size    53687091200
        # sderr:0:sd0,err:Soft Errors     0
        # sderr:0:sd0,err:Transport Errors        0
        # sderr:0:sd0,err:Vendor  ATA

        self.facts['devices'] = {}

        disk_stats = {
            'Product': 'product',
            'Revision': 'revision',
            'Serial No': 'serial',
            'Size': 'size',
            'Vendor': 'vendor',
            'Hard Errors': 'hard_errors',
            'Soft Errors': 'soft_errors',
            'Transport Errors': 'transport_errors',
            'Media Error': 'media_errors',
            'Predictive Failure Analysis': 'predictive_failure_analysis',
            'Illegal Request': 'illegal_request',
        }

        cmd = ['/usr/bin/kstat', '-p']

        for ds in disk_stats:
            cmd.append('sderr:::%s' % ds)

        d = {}
        rc, out, err = self.module.run_command(cmd)
        if rc != 0:
            return dict()

        sd_instances = frozenset(line.split(':')[1] for line in out.split('\n') if line.startswith('sderr'))
        for instance in sd_instances:
            lines = (line for line in out.split('\n') if ':' in line and line.split(':')[1] == instance)
            for line in lines:
                text, value = line.split('\t')
                stat = text.split(':')[3]

                if stat == 'Size':
                    d[disk_stats.get(stat)] = self.module.pretty_bytes(float(value))
                else:
                    d[disk_stats.get(stat)] = value.rstrip()

            diskname = 'sd' + instance
            self.facts['devices'][diskname] = d
            d = {}

    def get_uptime_facts(self):
        # On Solaris, unix:0:system_misc:snaptime is created shortly after machine boots up
        # and displays tiem in seconds. This is much easier than using uptime as we would
        # need to have a parsing procedure for translating from human-readable to machine-readable
        # format.
        # Example output:
        # unix:0:system_misc:snaptime     1175.410463590
        rc, out, err = self.module.run_command('/usr/bin/kstat -p unix:0:system_misc:snaptime')

        if rc != 0:
            return

        self.facts['uptime_seconds'] = int(float(out.split('\t')[1]))

