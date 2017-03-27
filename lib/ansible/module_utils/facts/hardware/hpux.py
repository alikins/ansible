import os
import re

from ansible.module_utils.facts import Hardware


class HPUXHardware(Hardware):
    """
    HP-UX-specific subclass of Hardware. Defines memory and CPU facts:
    - memfree_mb
    - memtotal_mb
    - swapfree_mb
    - swaptotal_mb
    - processor
    - processor_cores
    - processor_count
    - model
    - firmware
    """

    platform = 'HP-UX'

    def populate(self):
        self.get_cpu_facts()
        self.get_memory_facts()
        self.get_hw_facts()
        return self.facts

    def get_cpu_facts(self):
        if self.facts['architecture'] == '9000/800':
            rc, out, err = self.module.run_command("ioscan -FkCprocessor | wc -l", use_unsafe_shell=True)
            self.facts['processor_count'] = int(out.strip())
        # Working with machinfo mess
        elif self.facts['architecture'] == 'ia64':
            if self.facts['distribution_version'] == "B.11.23":
                rc, out, err = self.module.run_command("/usr/contrib/bin/machinfo | grep 'Number of CPUs'", use_unsafe_shell=True)
                self.facts['processor_count'] = int(out.strip().split('=')[1])
                rc, out, err = self.module.run_command("/usr/contrib/bin/machinfo | grep 'processor family'", use_unsafe_shell=True)
                self.facts['processor'] = re.search('.*(Intel.*)', out).groups()[0].strip()
                rc, out, err = self.module.run_command("ioscan -FkCprocessor | wc -l", use_unsafe_shell=True)
                self.facts['processor_cores'] = int(out.strip())
            if self.facts['distribution_version'] == "B.11.31":
                # if machinfo return cores strings release B.11.31 > 1204
                rc, out, err = self.module.run_command("/usr/contrib/bin/machinfo | grep core | wc -l", use_unsafe_shell=True)
                if out.strip() == '0':
                    rc, out, err = self.module.run_command("/usr/contrib/bin/machinfo | grep Intel", use_unsafe_shell=True)
                    self.facts['processor_count'] = int(out.strip().split(" ")[0])
                    # If hyperthreading is active divide cores by 2
                    rc, out, err = self.module.run_command("/usr/sbin/psrset | grep LCPU", use_unsafe_shell=True)
                    data = re.sub(' +', ' ', out).strip().split(' ')
                    if len(data) == 1:
                        hyperthreading = 'OFF'
                    else:
                        hyperthreading = data[1]
                    rc, out, err = self.module.run_command("/usr/contrib/bin/machinfo | grep logical", use_unsafe_shell=True)
                    data = out.strip().split(" ")
                    if hyperthreading == 'ON':
                        self.facts['processor_cores'] = int(data[0]) / 2
                    else:
                        if len(data) == 1:
                            self.facts['processor_cores'] = self.facts['processor_count']
                        else:
                            self.facts['processor_cores'] = int(data[0])
                    rc, out, err = self.module.run_command("/usr/contrib/bin/machinfo | grep Intel |cut -d' ' -f4-", use_unsafe_shell=True)
                    self.facts['processor'] = out.strip()
                else:
                    rc, out, err = self.module.run_command("/usr/contrib/bin/machinfo | egrep 'socket[s]?$' | tail -1", use_unsafe_shell=True)
                    self.facts['processor_count'] = int(out.strip().split(" ")[0])
                    rc, out, err = self.module.run_command("/usr/contrib/bin/machinfo | grep -e '[0-9] core' | tail -1", use_unsafe_shell=True)
                    self.facts['processor_cores'] = int(out.strip().split(" ")[0])
                    rc, out, err = self.module.run_command("/usr/contrib/bin/machinfo | grep Intel", use_unsafe_shell=True)
                    self.facts['processor'] = out.strip()

    def get_memory_facts(self):
        pagesize = 4096
        rc, out, err = self.module.run_command("/usr/bin/vmstat | tail -1", use_unsafe_shell=True)
        data = int(re.sub(' +', ' ', out).split(' ')[5].strip())
        self.facts['memfree_mb'] = pagesize * data // 1024 // 1024
        if self.facts['architecture'] == '9000/800':
            try:
                rc, out, err = self.module.run_command("grep Physical /var/adm/syslog/syslog.log")
                data = re.search('.*Physical: ([0-9]*) Kbytes.*', out).groups()[0].strip()
                self.facts['memtotal_mb'] = int(data) // 1024
            except AttributeError:
                # For systems where memory details aren't sent to syslog or the log has rotated, use parsed
                # adb output. Unfortunately /dev/kmem doesn't have world-read, so this only works as root.
                if os.access("/dev/kmem", os.R_OK):
                    rc, out, err = self.module.run_command("echo 'phys_mem_pages/D' | adb -k /stand/vmunix /dev/kmem | tail -1 | awk '{print $2}'",
                                                           use_unsafe_shell=True)
                    if not err:
                        data = out
                        self.facts['memtotal_mb'] = int(data) / 256
        else:
            rc, out, err = self.module.run_command("/usr/contrib/bin/machinfo | grep Memory", use_unsafe_shell=True)
            data = re.search('Memory[\ :=]*([0-9]*).*MB.*', out).groups()[0].strip()
            self.facts['memtotal_mb'] = int(data)
        rc, out, err = self.module.run_command("/usr/sbin/swapinfo -m -d -f -q")
        self.facts['swaptotal_mb'] = int(out.strip())
        rc, out, err = self.module.run_command("/usr/sbin/swapinfo -m -d -f | egrep '^dev|^fs'", use_unsafe_shell=True)
        swap = 0
        for line in out.strip().splitlines():
            swap += int(re.sub(' +', ' ', line).split(' ')[3].strip())
        self.facts['swapfree_mb'] = swap

    def get_hw_facts(self):
        rc, out, err = self.module.run_command("model")
        self.facts['model'] = out.strip()
        if self.facts['architecture'] == 'ia64':
            separator = ':'
            if self.facts['distribution_version'] == "B.11.23":
                separator = '='
            rc, out, err = self.module.run_command("/usr/contrib/bin/machinfo |grep -i 'Firmware revision' | grep -v BMC", use_unsafe_shell=True)
            self.facts['firmware_version'] = out.split(separator)[1].strip()
            rc, out, err = self.module.run_command("/usr/contrib/bin/machinfo |grep -i 'Machine serial number' ", use_unsafe_shell=True)
            if rc == 0 and out:
                self.facts['product_serial'] = out.split(separator)[1].strip()
