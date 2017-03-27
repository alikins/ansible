from ansible.module_utils.facts import GenericBsdIfconfigNetwork


class FreeBSDNetwork(GenericBsdIfconfigNetwork):
    """
    This is the FreeBSD Network Class.
    It uses the GenericBsdIfconfigNetwork unchanged.
    """
    platform = 'FreeBSD'
