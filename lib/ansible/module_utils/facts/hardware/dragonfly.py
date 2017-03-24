
from ansible.module_utils.facts.hardware.freebsd import FreeBSDHardware


class DragonFlyHardware(FreeBSDHardware):
    platform = 'DragonFly'
