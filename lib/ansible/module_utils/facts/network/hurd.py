import os

from ansible.module_utils.facts import Network


class HurdPfinetNetwork(Network):
    """
    This is a GNU Hurd specific subclass of Network. It use fsysopts to
    get the ip address and support only pfinet.
    """
    platform = 'GNU'
    _socket_dir = '/servers/socket/'

    def populate(self):
        fsysopts_path = self.module.get_bin_path('fsysopts')
        if fsysopts_path is None:
            return self.facts
        socket_path = None
        for l in ('inet', 'inet6'):
            link = os.path.join(self._socket_dir, l)
            if os.path.exists(link):
                socket_path = link
                break

        if socket_path:
            rc, out, err = self.module.run_command([fsysopts_path, '-L', socket_path])
            self.facts['interfaces'] = []
            for i in out.split():
                if '=' in i and i.startswith('--'):
                    k, v = i.split('=', 1)
                    # remove '--'
                    k = k[2:]
                    if k == 'interface':
                        # remove /dev/ from /dev/eth0
                        v = v[5:]
                        self.facts['interfaces'].append(v)
                        self.facts[v] = {
                            'active': True,
                            'device': v,
                            'ipv4': {},
                            'ipv6': [],
                        }
                        current_if = v
                    elif k == 'address':
                        self.facts[current_if]['ipv4']['address'] = v
                    elif k == 'netmask':
                        self.facts[current_if]['ipv4']['netmask'] = v
                    elif k == 'address6':
                        address, prefix = v.split('/')
                        self.facts[current_if]['ipv6'].append({
                            'address': address,
                            'prefix': prefix,
                        })

        return self.facts
