
from ansible.module_utils.facts import Hardware

from ansible.module_utils.facts.sysctl import get_sysctl


class DarwinHardware(Hardware):
    """
    Darwin-specific subclass of Hardware.  Defines memory and CPU facts:
    - processor
    - processor_cores
    - memtotal_mb
    - memfree_mb
    - model
    - osversion
    - osrevision
    """
    platform = 'Darwin'

    def populate(self):
        self.sysctl = get_sysctl(self.module, ['hw', 'machdep', 'kern'])
        self.get_mac_facts()
        self.get_cpu_facts()
        self.get_memory_facts()
        return self.facts

    def get_system_profile(self):
        rc, out, err = self.module.run_command(["/usr/sbin/system_profiler", "SPHardwareDataType"])
        if rc != 0:
            return dict()
        system_profile = dict()
        for line in out.splitlines():
            if ': ' in line:
                (key, value) = line.split(': ', 1)
                system_profile[key.strip()] = ' '.join(value.strip().split())
        return system_profile

    def get_mac_facts(self):
        rc, out, err = self.module.run_command("sysctl hw.model")
        if rc == 0:
            self.facts['model'] = out.splitlines()[-1].split()[1]
        self.facts['osversion'] = self.sysctl['kern.osversion']
        self.facts['osrevision'] = self.sysctl['kern.osrevision']

    def get_cpu_facts(self):
        if 'machdep.cpu.brand_string' in self.sysctl:  # Intel
            self.facts['processor'] = self.sysctl['machdep.cpu.brand_string']
            self.facts['processor_cores'] = self.sysctl['machdep.cpu.core_count']
        else:  # PowerPC
            system_profile = self.get_system_profile()
            self.facts['processor'] = '%s @ %s' % (system_profile['Processor Name'], system_profile['Processor Speed'])
            self.facts['processor_cores'] = self.sysctl['hw.physicalcpu']

    def get_memory_facts(self):
        self.facts['memtotal_mb'] = int(self.sysctl['hw.memsize']) // 1024 // 1024

        rc, out, err = self.module.run_command("sysctl hw.usermem")
        if rc == 0:
            self.facts['memfree_mb'] = int(out.splitlines()[-1].split()[1]) // 1024 // 1024
