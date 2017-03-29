from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.module_utils.facts.hardware.freebsd import FreeBSDHardware


class DragonFlyHardware(FreeBSDHardware):
    platform = 'DragonFly'
