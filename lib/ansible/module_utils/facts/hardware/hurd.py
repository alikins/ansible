from ansible.module_utils.facts import TimeoutError
from ansible.module_utils.facts.hardware.linux import LinuxHardware


class HurdHardware(LinuxHardware):
    """
    GNU Hurd specific subclass of Hardware. Define memory and mount facts
    based on procfs compatibility translator mimicking the interface of
    the Linux kernel.
    """

    platform = 'GNU'

    def populate(self):
        self.get_uptime_facts()
        self.get_memory_facts()
        try:
            self.get_mount_facts()
        except TimeoutError:
            pass
        return self.facts
