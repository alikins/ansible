import re

from ansible.module_utils.facts import Hardware


class AIXHardware(Hardware):
    """
    AIX-specific subclass of Hardware.  Defines memory and CPU facts:
    - memfree_mb
    - memtotal_mb
    - swapfree_mb
    - swaptotal_mb
    - processor (a list)
    - processor_cores
    - processor_count
    """
    platform = 'AIX'

    def populate(self):
        self.get_cpu_facts()
        self.get_memory_facts()
        self.get_dmi_facts()
        self.get_vgs_facts()
        self.get_mount_facts()
        return self.facts

    def get_cpu_facts(self):
        self.facts['processor'] = []

        rc, out, err = self.module.run_command("/usr/sbin/lsdev -Cc processor")
        if out:
            i = 0
            for line in out.splitlines():

                if 'Available' in line:
                    if i == 0:
                        data = line.split(' ')
                        cpudev = data[0]

                    i += 1
            self.facts['processor_count'] = int(i)

            rc, out, err = self.module.run_command("/usr/sbin/lsattr -El " + cpudev + " -a type")

            data = out.split(' ')
            self.facts['processor'] = data[1]

            rc, out, err = self.module.run_command("/usr/sbin/lsattr -El " + cpudev + " -a smt_threads")

            data = out.split(' ')
            self.facts['processor_cores'] = int(data[1])

    def get_memory_facts(self):
        pagesize = 4096
        rc, out, err = self.module.run_command("/usr/bin/vmstat -v")
        for line in out.splitlines():
            data = line.split()
            if 'memory pages' in line:
                pagecount = int(data[0])
            if 'free pages' in line:
                freecount = int(data[0])
        self.facts['memtotal_mb'] = pagesize * pagecount // 1024 // 1024
        self.facts['memfree_mb'] = pagesize * freecount // 1024 // 1024
        # Get swapinfo.  swapinfo output looks like:
        # Device          1M-blocks     Used    Avail Capacity
        # /dev/ada0p3        314368        0   314368     0%
        #
        rc, out, err = self.module.run_command("/usr/sbin/lsps -s")
        if out:
            lines = out.splitlines()
            data = lines[1].split()
            swaptotal_mb = int(data[0].rstrip('MB'))
            percused = int(data[1].rstrip('%'))
            self.facts['swaptotal_mb'] = swaptotal_mb
            self.facts['swapfree_mb'] = int(swaptotal_mb * (100 - percused) / 100)

    def get_dmi_facts(self):
        rc, out, err = self.module.run_command("/usr/sbin/lsattr -El sys0 -a fwversion")
        data = out.split()
        self.facts['firmware_version'] = data[1].strip('IBM,')
        lsconf_path = self.module.get_bin_path("lsconf")
        if lsconf_path:
            rc, out, err = self.module.run_command(lsconf_path)
            if rc == 0 and out:
                for line in out.splitlines():
                    data = line.split(':')
                    if 'Machine Serial Number' in line:
                        self.facts['product_serial'] = data[1].strip()
                    if 'LPAR Info' in line:
                        self.facts['lpar_info'] = data[1].strip()
                    if 'System Model' in line:
                        self.facts['product_name'] = data[1].strip()

    def get_vgs_facts(self):
        """
        Get vg and pv Facts
        rootvg:
        PV_NAME           PV STATE          TOTAL PPs   FREE PPs    FREE DISTRIBUTION
        hdisk0            active            546         0           00..00..00..00..00
        hdisk1            active            546         113         00..00..00..21..92
        realsyncvg:
        PV_NAME           PV STATE          TOTAL PPs   FREE PPs    FREE DISTRIBUTION
        hdisk74           active            1999        6           00..00..00..00..06
        testvg:
        PV_NAME           PV STATE          TOTAL PPs   FREE PPs    FREE DISTRIBUTION
        hdisk105          active            999         838         200..39..199..200..200
        hdisk106          active            999         599         200..00..00..199..200
        """

        lsvg_path = self.module.get_bin_path("lsvg")
        xargs_path = self.module.get_bin_path("xargs")
        cmd = "%s | %s %s -p" % (lsvg_path, xargs_path, lsvg_path)
        if lsvg_path and xargs_path:
            rc, out, err = self.module.run_command(cmd, use_unsafe_shell=True)
            if rc == 0 and out:
                self.facts['vgs'] = {}
                for m in re.finditer(r'(\S+):\n.*FREE DISTRIBUTION(\n(\S+)\s+(\w+)\s+(\d+)\s+(\d+).*)+', out):
                    self.facts['vgs'][m.group(1)] = []
                    pp_size = 0
                    cmd = "%s %s" % (lsvg_path, m.group(1))
                    rc, out, err = self.module.run_command(cmd)
                    if rc == 0 and out:
                        pp_size = re.search(r'PP SIZE:\s+(\d+\s+\S+)', out).group(1)
                        for n in re.finditer(r'(\S+)\s+(\w+)\s+(\d+)\s+(\d+).*', m.group(0)):
                            pv_info = {'pv_name': n.group(1),
                                       'pv_state': n.group(2),
                                       'total_pps': n.group(3),
                                       'free_pps': n.group(4),
                                       'pp_size': pp_size
                                       }
                            self.facts['vgs'][m.group(1)].append(pv_info)

    def get_mount_facts(self):
        self.facts['mounts'] = []
        # AIX does not have mtab but mount command is only source of info (or to use
        # api calls to get same info)
        mount_path = self.module.get_bin_path('mount')
        rc, mount_out, err = self.module.run_command(mount_path)
        if mount_out:
            for line in mount_out.split('\n'):
                fields = line.split()
                if len(fields) != 0 and fields[0] != 'node' and fields[0][0] != '-' and re.match('^/.*|^[a-zA-Z].*|^[0-9].*', fields[0]):
                    if re.match('^/', fields[0]):
                        # normal mount
                        self.facts['mounts'].append({'mount': fields[1],
                                                 'device': fields[0],
                                                 'fstype': fields[2],
                                                 'options': fields[6],
                                                 'time': '%s %s %s' % (fields[3], fields[4], fields[5])})
                    else:
                        # nfs or cifs based mount
                        # in case of nfs if no mount options are provided on command line
                        # add into fields empty string...
                        if len(fields) < 8:
                            fields.append("")
                        self.facts['mounts'].append({'mount': fields[2],
                                                 'device': '%s:%s' % (fields[0], fields[1]),
                                                 'fstype': fields[3],
                                                 'options': fields[7],
                                                 'time': '%s %s %s' % (fields[4], fields[5], fields[6])})
