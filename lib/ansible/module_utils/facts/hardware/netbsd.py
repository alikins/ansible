from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os
import re

from ansible.module_utils.facts.hardware.base import Hardware
from ansible.module_utils.facts.timeout import TimeoutError, timeout

from ansible.module_utils.facts.utils import get_file_content, get_file_lines, get_mount_size
from ansible.module_utils.facts.sysctl import get_sysctl


class NetBSDHardware(Hardware):
    """
    NetBSD-specific subclass of Hardware.  Defines memory and CPU facts:
    - memfree_mb
    - memtotal_mb
    - swapfree_mb
    - swaptotal_mb
    - processor (a list)
    - processor_cores
    - processor_count
    - devices
    """
    platform = 'NetBSD'
    MEMORY_FACTS = ['MemTotal', 'SwapTotal', 'MemFree', 'SwapFree']

    def populate(self):
        self.sysctl = get_sysctl(self.module, ['machdep'])
        self.get_cpu_facts()
        self.get_memory_facts()
        try:
            self.get_mount_facts()
        except TimeoutError:
            pass
        self.get_dmi_facts()
        return self.facts

    def get_cpu_facts(self):

        i = 0
        physid = 0
        sockets = {}
        if not os.access("/proc/cpuinfo", os.R_OK):
            return
        self.facts['processor'] = []
        for line in get_file_lines("/proc/cpuinfo"):
            data = line.split(":", 1)
            key = data[0].strip()
            # model name is for Intel arch, Processor (mind the uppercase P)
            # works for some ARM devices, like the Sheevaplug.
            if key == 'model name' or key == 'Processor':
                if 'processor' not in self.facts:
                    self.facts['processor'] = []
                self.facts['processor'].append(data[1].strip())
                i += 1
            elif key == 'physical id':
                physid = data[1].strip()
                if physid not in sockets:
                    sockets[physid] = 1
            elif key == 'cpu cores':
                sockets[physid] = int(data[1].strip())
        if len(sockets) > 0:
            self.facts['processor_count'] = len(sockets)
            self.facts['processor_cores'] = reduce(lambda x, y: x + y, sockets.values())
        else:
            self.facts['processor_count'] = i
            self.facts['processor_cores'] = 'NA'

    def get_memory_facts(self):
        if not os.access("/proc/meminfo", os.R_OK):
            return
        for line in get_file_lines("/proc/meminfo"):
            data = line.split(":", 1)
            key = data[0]
            if key in NetBSDHardware.MEMORY_FACTS:
                val = data[1].strip().split(' ')[0]
                self.facts["%s_mb" % key.lower()] = int(val) // 1024

    @timeout()
    def get_mount_facts(self):
        self.facts['mounts'] = []
        fstab = get_file_content('/etc/fstab')
        if fstab:
            for line in fstab.splitlines():
                if line.startswith('#') or line.strip() == '':
                    continue
                fields = re.sub(r'\s+', ' ', line).split()
                size_total, size_available = get_mount_size(fields[1])
                self.facts['mounts'].append({
                    'mount': fields[1],
                    'device': fields[0],
                    'fstype': fields[2],
                    'options': fields[3],
                    'size_total': size_total,
                    'size_available': size_available
                })

    def get_dmi_facts(self):
        # We don't use dmidecode(1) here because:
        # - it would add dependency on an external package
        # - dmidecode(1) can only be ran as root
        # So instead we rely on sysctl(8) to provide us the information on a
        # best-effort basis. As a bonus we also get facts on non-amd64/i386
        # platforms this way.
        sysctl_to_dmi = {
            'machdep.dmi.system-product': 'product_name',
            'machdep.dmi.system-version': 'product_version',
            'machdep.dmi.system-uuid': 'product_uuid',
            'machdep.dmi.system-serial': 'product_serial',
            'machdep.dmi.system-vendor': 'system_vendor',
        }

        for mib in sysctl_to_dmi:
            if mib in self.sysctl:
                self.facts[sysctl_to_dmi[mib]] = self.sysctl[mib]
