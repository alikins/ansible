from ansible.module_utils.facts.network.generic_bsd import GenericBsdIfconfigNetwork


class DragonFlyNetwork(GenericBsdIfconfigNetwork):
    """
    This is the DragonFly Network Class.
    It uses the GenericBsdIfconfigNetwork unchanged.
    """
    platform = 'DragonFly'
