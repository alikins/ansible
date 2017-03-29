from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.module_utils.facts.virtual.freebsd import FreeBSDVirtual


class DragonFlyVirtual(FreeBSDVirtual):
    platform = 'DragonFly'
