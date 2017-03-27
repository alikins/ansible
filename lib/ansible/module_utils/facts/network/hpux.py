from ansible.module_utils.facts import Network


class HPUXNetwork(Network):
    """
    HP-UX-specifig subclass of Network. Defines networking facts:
    - default_interface
    - interfaces (a list of interface names)
    - interface_<name> dictionary of ipv4 address information.
    """
    platform = 'HP-UX'

    def populate(self):
        netstat_path = self.module.get_bin_path('netstat')
        if netstat_path is None:
            return self.facts
        self.get_default_interfaces()
        interfaces = self.get_interfaces_info()
        self.facts['interfaces'] = interfaces.keys()
        for iface in interfaces:
            self.facts[iface] = interfaces[iface]
        return self.facts

    def get_default_interfaces(self):
        rc, out, err = self.module.run_command("/usr/bin/netstat -nr")
        lines = out.splitlines()
        for line in lines:
            words = line.split()
            if len(words) > 1:
                if words[0] == 'default':
                    self.facts['default_interface'] = words[4]
                    self.facts['default_gateway'] = words[1]

    def get_interfaces_info(self):
        interfaces = {}
        rc, out, err = self.module.run_command("/usr/bin/netstat -ni")
        lines = out.splitlines()
        for line in lines:
            words = line.split()
            for i in range(len(words) - 1):
                if words[i][:3] == 'lan':
                    device = words[i]
                    interfaces[device] = {'device': device}
                    address = words[i + 3]
                    interfaces[device]['ipv4'] = {'address': address}
                    network = words[i + 2]
                    interfaces[device]['ipv4'] = {'network': network,
                                                  'interface': device,
                                                  'address': address}
        return interfaces
