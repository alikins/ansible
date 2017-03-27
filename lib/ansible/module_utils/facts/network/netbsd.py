from ansible.module_utils.facts.network.generic_bsd import GenericBsdIfconfigNetwork


class NetBSDNetwork(GenericBsdIfconfigNetwork):
    """
    This is the NetBSD Network Class.
    It uses the GenericBsdIfconfigNetwork
    """
    platform = 'NetBSD'

    def parse_media_line(self, words, current_if, ips):
        # example of line:
        # $ ifconfig
        # ne0: flags=8863<UP,BROADCAST,NOTRAILERS,RUNNING,SIMPLEX,MULTICAST> mtu 1500
        #    ec_capabilities=1<VLAN_MTU>
        #    ec_enabled=0
        #    address: 00:20:91:45:00:78
        #    media: Ethernet 10baseT full-duplex
        #    inet 192.168.156.29 netmask 0xffffff00 broadcast 192.168.156.255
        current_if['media'] = words[1]
        if len(words) > 2:
            current_if['media_type'] = words[2]
        if len(words) > 3:
            current_if['media_options'] = words[3].split(',')
