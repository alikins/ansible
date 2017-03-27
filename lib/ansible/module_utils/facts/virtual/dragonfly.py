from ansible.module_utils.facts.virtual.freebsd import FreeBSDVirtual


class DragonFlyVirtual(FreeBSDVirtual):
    platform = 'DragonFly'
