# (c) 2012, Michael DeHaan <michael.dehaan@gmail.com>
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

# GOALS:
# - finer grained fact gathering
# - better tested facts code
# - more module facts code
# - pluggable fact gatherers (fact plugins)
# - test cases
# - split up this py module into smaller modules
# - improve the multiplatform support and simplify how Facts implementations are chosen
# - document model and structure of found facts
# - try to make classes/methods have less side effects

# TODO: try to increase unit test coverage
# TODO: module_utils/facts.py -> module_utils/facts/__init__.py
# TODO: mv platform specific stuff into facts/* modules?
# TODO: general pep8/style clean ups
# TODO: tiny bit of abstractions for run_command() and get_file_content() use
#       ie, code like self.module.run_command('some_netinfo_tool --someoption')[1].splitlines[][0].split()[1] ->
#          netinfo_output = self._netinfo_provider()
#          netinfo_data = self._netinfo_parse(netinfo_output)
#       why?
#          - much much easier to test
import os
import fnmatch
import glob
import platform
import re
import signal
import socket
import struct

from ansible.module_utils.basic import get_all_subclasses
from ansible.module_utils.six import PY3

# FIXME: not a fan of importing symbols into a different namespace (vs import a module)
from ansible.module_utils.facts.utils import get_file_content, get_file_lines

from ansible.module_utils.facts.facts import Facts
from ansible.module_utils.facts.ohai import Ohai
from ansible.module_utils.facts.facter import Facter


try:
    import json
    # Detect python-json which is incompatible and fallback to simplejson in
    # that case
    try:
        json.loads
        json.dumps
    except AttributeError:
        raise ImportError
except ImportError:
    import simplejson as json


# --------------------------------------------------------------
# timeout function to make sure some fact gathering
# steps do not exceed a time limit

GATHER_TIMEOUT = None


class TimeoutError(Exception):
    pass


def timeout(seconds=None, error_message="Timer expired"):

    if seconds is None:
        seconds = globals().get('GATHER_TIMEOUT') or 10

    def decorator(func):
        def _handle_timeout(signum, frame):
            raise TimeoutError(error_message)

        def wrapper(*args, **kwargs):
            signal.signal(signal.SIGALRM, _handle_timeout)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
            return result

        return wrapper

    # If we were called as @timeout, then the first parameter will be the
    # function we are to wrap instead of the number of seconds.  Detect this
    # and correct it by setting seconds to our default value and return the
    # inner decorator function manually wrapped around the function
    if callable(seconds):
        func = seconds
        seconds = 10
        return decorator(func)

    # If we were called as @timeout([...]) then python itself will take
    # care of wrapping the inner decorator around the function

    return decorator

# --------------------------------------------------------------


class Hardware(Facts):
    """
    This is a generic Hardware subclass of Facts.  This should be further
    subclassed to implement per platform.  If you subclass this, it
    should define:
    - memfree_mb
    - memtotal_mb
    - swapfree_mb
    - swaptotal_mb
    - processor (a list)
    - processor_cores
    - processor_count

    All subclasses MUST define platform.
    """
    platform = 'Generic'

    def __new__(cls, *arguments, **keyword):
        # When Hardware is created, it chooses a subclass to create instead.
        # This check prevents the subclass from then trying to find a subclass
        # and create that.
        if cls is not Hardware:
            return super(Hardware, cls).__new__(cls)

        subclass = cls
        for sc in get_all_subclasses(Hardware):
            if sc.platform == platform.system():
                subclass = sc
        if PY3:
            return super(cls, subclass).__new__(subclass)
        else:
            return super(cls, subclass).__new__(subclass, *arguments, **keyword)

    def populate(self):
        return self.facts

    def get_sysctl(self, prefixes):
        sysctl_cmd = self.module.get_bin_path('sysctl')
        cmd = [sysctl_cmd]
        cmd.extend(prefixes)
        rc, out, err = self.module.run_command(cmd)
        if rc != 0:
            return dict()
        sysctl = dict()
        for line in out.splitlines():
            if not line:
                continue
            (key, value) = re.split('\s?=\s?|: ', line, maxsplit=1)
            sysctl[key] = value.strip()
        return sysctl


class Network(Facts):
    """
    This is a generic Network subclass of Facts.  This should be further
    subclassed to implement per platform.  If you subclass this,
    you must define:
    - interfaces (a list of interface names)
    - interface_<name> dictionary of ipv4, ipv6, and mac address information.

    All subclasses MUST define platform.
    """
    platform = 'Generic'

    IPV6_SCOPE = { '0' : 'global',
                   '10' : 'host',
                   '20' : 'link',
                   '40' : 'admin',
                   '50' : 'site',
                   '80' : 'organization' }

    def __new__(cls, *arguments, **keyword):
        # When Network is created, it chooses a subclass to create instead.
        # This check prevents the subclass from then trying to find a subclass
        # and create that.
        if cls is not Network:
            return super(Network, cls).__new__(cls)

        subclass = cls
        for sc in get_all_subclasses(Network):
            if sc.platform == platform.system():
                subclass = sc
        if PY3:
            return super(cls, subclass).__new__(subclass)
        else:
            return super(cls, subclass).__new__(subclass, *arguments, **keyword)

    def populate(self):
        return self.facts


class GenericBsdIfconfigNetwork(Network):
    """
    This is a generic BSD subclass of Network using the ifconfig command.
    It defines
    - interfaces (a list of interface names)
    - interface_<name> dictionary of ipv4, ipv6, and mac address information.
    - all_ipv4_addresses and all_ipv6_addresses: lists of all configured addresses.
    """
    platform = 'Generic_BSD_Ifconfig'

    def populate(self):

        ifconfig_path = self.module.get_bin_path('ifconfig')

        if ifconfig_path is None:
            return self.facts
        route_path = self.module.get_bin_path('route')

        if route_path is None:
            return self.facts

        default_ipv4, default_ipv6 = self.get_default_interfaces(route_path)
        interfaces, ips = self.get_interfaces_info(ifconfig_path)
        self.detect_type_media(interfaces)
        self.merge_default_interface(default_ipv4, interfaces, 'ipv4')
        self.merge_default_interface(default_ipv6, interfaces, 'ipv6')
        self.facts['interfaces'] = interfaces.keys()

        for iface in interfaces:
            self.facts[iface] = interfaces[iface]

        self.facts['default_ipv4'] = default_ipv4
        self.facts['default_ipv6'] = default_ipv6
        self.facts['all_ipv4_addresses'] = ips['all_ipv4_addresses']
        self.facts['all_ipv6_addresses'] = ips['all_ipv6_addresses']

        return self.facts

    def detect_type_media(self, interfaces):
        for iface in interfaces:
            if 'media' in interfaces[iface]:
                if 'ether' in interfaces[iface]['media'].lower():
                    interfaces[iface]['type'] = 'ether'

    def get_default_interfaces(self, route_path):

        # Use the commands:
        #     route -n get 8.8.8.8                            -> Google public DNS
        #     route -n get -inet6 2404:6800:400a:800::1012    -> ipv6.google.com
        # to find out the default outgoing interface, address, and gateway

        command = dict(
            v4 = [route_path, '-n', 'get', '8.8.8.8'],
            v6 = [route_path, '-n', 'get', '-inet6', '2404:6800:400a:800::1012']
        )

        interface = dict(v4 = {}, v6 = {})

        for v in 'v4', 'v6':

            if v == 'v6' and not socket.has_ipv6:
                continue
            rc, out, err = self.module.run_command(command[v])
            if not out:
                # v6 routing may result in
                #   RTNETLINK answers: Invalid argument
                continue
            for line in out.splitlines():
                words = line.split()
                # Collect output from route command
                if len(words) > 1:
                    if words[0] == 'interface:':
                        interface[v]['interface'] = words[1]
                    if words[0] == 'gateway:':
                        interface[v]['gateway'] = words[1]

        return interface['v4'], interface['v6']

    def get_interfaces_info(self, ifconfig_path, ifconfig_options='-a'):
        interfaces = {}
        current_if = {}
        ips = dict(
            all_ipv4_addresses = [],
            all_ipv6_addresses = [],
        )
        # FreeBSD, DragonflyBSD, NetBSD, OpenBSD and OS X all implicitly add '-a'
        # when running the command 'ifconfig'.
        # Solaris must explicitly run the command 'ifconfig -a'.
        rc, out, err = self.module.run_command([ifconfig_path, ifconfig_options])

        for line in out.splitlines():

            if line:
                words = line.split()

                if words[0] == 'pass':
                    continue
                elif re.match('^\S', line) and len(words) > 3:
                    current_if = self.parse_interface_line(words)
                    interfaces[ current_if['device'] ] = current_if
                elif words[0].startswith('options='):
                    self.parse_options_line(words, current_if, ips)
                elif words[0] == 'nd6':
                    self.parse_nd6_line(words, current_if, ips)
                elif words[0] == 'ether':
                    self.parse_ether_line(words, current_if, ips)
                elif words[0] == 'media:':
                    self.parse_media_line(words, current_if, ips)
                elif words[0] == 'status:':
                    self.parse_status_line(words, current_if, ips)
                elif words[0] == 'lladdr':
                    self.parse_lladdr_line(words, current_if, ips)
                elif words[0] == 'inet':
                    self.parse_inet_line(words, current_if, ips)
                elif words[0] == 'inet6':
                    self.parse_inet6_line(words, current_if, ips)
                elif words[0] == 'tunnel':
                    self.parse_tunnel_line(words, current_if, ips)
                else:
                    self.parse_unknown_line(words, current_if, ips)

        return interfaces, ips

    def parse_interface_line(self, words):
        device = words[0][0:-1]
        current_if = {'device': device, 'ipv4': [], 'ipv6': [], 'type': 'unknown'}
        current_if['flags']  = self.get_options(words[1])
        if 'LOOPBACK' in current_if['flags']:
            current_if['type'] = 'loopback'
        current_if['macaddress'] = 'unknown'    # will be overwritten later

        if len(words) >= 5 :  # Newer FreeBSD versions
            current_if['metric'] = words[3]
            current_if['mtu'] = words[5]
        else:
            current_if['mtu'] = words[3]

        return current_if

    def parse_options_line(self, words, current_if, ips):
        # Mac has options like this...
        current_if['options'] = self.get_options(words[0])

    def parse_nd6_line(self, words, current_if, ips):
        # FreeBSD has options like this...
        current_if['options'] = self.get_options(words[1])

    def parse_ether_line(self, words, current_if, ips):
        current_if['macaddress'] = words[1]
        current_if['type'] = 'ether'

    def parse_media_line(self, words, current_if, ips):
        # not sure if this is useful - we also drop information
        current_if['media'] = words[1]
        if len(words) > 2:
            current_if['media_select'] = words[2]
        if len(words) > 3:
            current_if['media_type'] = words[3][1:]
        if len(words) > 4:
            current_if['media_options'] = self.get_options(words[4])

    def parse_status_line(self, words, current_if, ips):
        current_if['status'] = words[1]

    def parse_lladdr_line(self, words, current_if, ips):
        current_if['lladdr'] = words[1]

    def parse_inet_line(self, words, current_if, ips):
        # netbsd show aliases like this
        #  lo0: flags=8049<UP,LOOPBACK,RUNNING,MULTICAST> mtu 33184
        #         inet 127.0.0.1 netmask 0xff000000
        #         inet alias 127.1.1.1 netmask 0xff000000
        if words[1] == 'alias':
            del words[1]
        address = {'address': words[1]}
        # deal with hex netmask
        if re.match('([0-9a-f]){8}', words[3]) and len(words[3]) == 8:
            words[3] = '0x' + words[3]
        if words[3].startswith('0x'):
            address['netmask'] = socket.inet_ntoa(struct.pack('!L', int(words[3], base=16)))
        else:
            # otherwise assume this is a dotted quad
            address['netmask'] = words[3]
        # calculate the network
        address_bin = struct.unpack('!L', socket.inet_aton(address['address']))[0]
        netmask_bin = struct.unpack('!L', socket.inet_aton(address['netmask']))[0]
        address['network'] = socket.inet_ntoa(struct.pack('!L', address_bin & netmask_bin))
        # broadcast may be given or we need to calculate
        if len(words) > 5:
            address['broadcast'] = words[5]
        else:
            address['broadcast'] = socket.inet_ntoa(struct.pack('!L', address_bin | (~netmask_bin & 0xffffffff)))
        # add to our list of addresses
        if not words[1].startswith('127.'):
            ips['all_ipv4_addresses'].append(address['address'])
        current_if['ipv4'].append(address)

    def parse_inet6_line(self, words, current_if, ips):
        address = {'address': words[1]}
        if (len(words) >= 4) and (words[2] == 'prefixlen'):
            address['prefix'] = words[3]
        if (len(words) >= 6) and (words[4] == 'scopeid'):
            address['scope'] = words[5]
        localhost6 = ['::1', '::1/128', 'fe80::1%lo0']
        if address['address'] not in localhost6:
            ips['all_ipv6_addresses'].append(address['address'])
        current_if['ipv6'].append(address)

    def parse_tunnel_line(self, words, current_if, ips):
        current_if['type'] = 'tunnel'

    def parse_unknown_line(self, words, current_if, ips):
        # we are going to ignore unknown lines here - this may be
        # a bad idea - but you can override it in your subclass
        pass

    def get_options(self, option_string):
        start = option_string.find('<') + 1
        end = option_string.rfind('>')
        if (start > 0) and (end > 0) and (end > start + 1):
            option_csv = option_string[start:end]
            return option_csv.split(',')
        else:
            return []

    def merge_default_interface(self, defaults, interfaces, ip_type):
        if 'interface' not in defaults:
            return
        if not defaults['interface'] in interfaces:
            return
        ifinfo = interfaces[defaults['interface']]
        # copy all the interface values across except addresses
        for item in ifinfo:
            if item != 'ipv4' and item != 'ipv6':
                defaults[item] = ifinfo[item]
        if len(ifinfo[ip_type]) > 0:
            for item in ifinfo[ip_type][0]:
                defaults[item] = ifinfo[ip_type][0][item]


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
                    interfaces[device] = { 'device': device }
                    address = words[i+3]
                    interfaces[device]['ipv4'] = { 'address': address }
                    network = words[i+2]
                    interfaces[device]['ipv4'] = { 'network': network,
                                                   'interface': device,
                                                   'address': address }
        return interfaces


class FreeBSDNetwork(GenericBsdIfconfigNetwork):
    """
    This is the FreeBSD Network Class.
    It uses the GenericBsdIfconfigNetwork unchanged.
    """
    platform = 'FreeBSD'


class DragonFlyNetwork(GenericBsdIfconfigNetwork):
    """
    This is the DragonFly Network Class.
    It uses the GenericBsdIfconfigNetwork unchanged.
    """
    platform = 'DragonFly'


class AIXNetwork(GenericBsdIfconfigNetwork):
    """
    This is the AIX Network Class.
    It uses the GenericBsdIfconfigNetwork unchanged.
    """
    platform = 'AIX'

    def get_default_interfaces(self, route_path):
        netstat_path = self.module.get_bin_path('netstat')

        rc, out, err = self.module.run_command([netstat_path, '-nr'])

        interface = dict(v4 = {}, v6 = {})

        lines = out.splitlines()
        for line in lines:
            words = line.split()
            if len(words) > 1 and words[0] == 'default':
                if '.' in words[1]:
                    interface['v4']['gateway'] = words[1]
                    interface['v4']['interface'] = words[5]
                elif ':' in words[1]:
                    interface['v6']['gateway'] = words[1]
                    interface['v6']['interface'] = words[5]

        return interface['v4'], interface['v6']

    # AIX 'ifconfig -a' does not have three words in the interface line
    def get_interfaces_info(self, ifconfig_path, ifconfig_options='-a'):
        interfaces = {}
        current_if = {}
        ips = dict(
            all_ipv4_addresses = [],
            all_ipv6_addresses = [],
        )

        uname_rc = None
        uname_out = None
        uname_err = None
        uname_path = self.module.get_bin_path('uname')
        if uname_path:
            uname_rc, uname_out, uname_err = self.module.run_command([uname_path, '-W'])

        rc, out, err = self.module.run_command([ifconfig_path, ifconfig_options])

        for line in out.splitlines():

            if line:
                words = line.split()

                # only this condition differs from GenericBsdIfconfigNetwork
                if re.match('^\w*\d*:', line):
                    current_if = self.parse_interface_line(words)
                    interfaces[ current_if['device'] ] = current_if
                elif words[0].startswith('options='):
                    self.parse_options_line(words, current_if, ips)
                elif words[0] == 'nd6':
                    self.parse_nd6_line(words, current_if, ips)
                elif words[0] == 'ether':
                    self.parse_ether_line(words, current_if, ips)
                elif words[0] == 'media:':
                    self.parse_media_line(words, current_if, ips)
                elif words[0] == 'status:':
                    self.parse_status_line(words, current_if, ips)
                elif words[0] == 'lladdr':
                    self.parse_lladdr_line(words, current_if, ips)
                elif words[0] == 'inet':
                    self.parse_inet_line(words, current_if, ips)
                elif words[0] == 'inet6':
                    self.parse_inet6_line(words, current_if, ips)
                else:
                    self.parse_unknown_line(words, current_if, ips)

            # don't bother with wpars it does not work
            # zero means not in wpar
            if not uname_rc and uname_out.split()[0] == '0':

                if current_if['macaddress'] == 'unknown' and re.match('^en', current_if['device']):
                    entstat_path = self.module.get_bin_path('entstat')
                    if entstat_path:
                        rc, out, err = self.module.run_command([entstat_path, current_if['device'] ])
                        if rc != 0:
                            break
                        for line in out.splitlines():
                            if not line:
                                pass
                            buff = re.match('^Hardware Address: (.*)', line)
                            if buff:
                                current_if['macaddress'] = buff.group(1)

                            buff = re.match('^Device Type:', line)
                            if buff and re.match('.*Ethernet', line):
                                current_if['type'] = 'ether'

                # device must have mtu attribute in ODM
                if 'mtu' not in current_if:
                    lsattr_path = self.module.get_bin_path('lsattr')
                    if lsattr_path:
                        rc, out, err = self.module.run_command([lsattr_path,'-El', current_if['device'] ])
                        if rc != 0:
                            break
                        for line in out.splitlines():
                            if line:
                                words = line.split()
                                if words[0] == 'mtu':
                                    current_if['mtu'] = words[1]
        return interfaces, ips

    # AIX 'ifconfig -a' does not inform about MTU, so remove current_if['mtu'] here
    def parse_interface_line(self, words):
        device = words[0][0:-1]
        current_if = {'device': device, 'ipv4': [], 'ipv6': [], 'type': 'unknown'}
        current_if['flags'] = self.get_options(words[1])
        current_if['macaddress'] = 'unknown'    # will be overwritten later
        return current_if


class OpenBSDNetwork(GenericBsdIfconfigNetwork):
    """
    This is the OpenBSD Network Class.
    It uses the GenericBsdIfconfigNetwork.
    """
    platform = 'OpenBSD'

    # OpenBSD 'ifconfig -a' does not have information about aliases
    def get_interfaces_info(self, ifconfig_path, ifconfig_options='-aA'):
        return super(OpenBSDNetwork, self).get_interfaces_info(ifconfig_path, ifconfig_options)

    # Return macaddress instead of lladdr
    def parse_lladdr_line(self, words, current_if, ips):
        current_if['macaddress'] = words[1]
        current_if['type'] = 'ether'


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


class SunOSNetwork(GenericBsdIfconfigNetwork):
    """
    This is the SunOS Network Class.
    It uses the GenericBsdIfconfigNetwork.

    Solaris can have different FLAGS and MTU for IPv4 and IPv6 on the same interface
    so these facts have been moved inside the 'ipv4' and 'ipv6' lists.
    """
    platform = 'SunOS'

    # Solaris 'ifconfig -a' will print interfaces twice, once for IPv4 and again for IPv6.
    # MTU and FLAGS also may differ between IPv4 and IPv6 on the same interface.
    # 'parse_interface_line()' checks for previously seen interfaces before defining
    # 'current_if' so that IPv6 facts don't clobber IPv4 facts (or vice versa).
    def get_interfaces_info(self, ifconfig_path):
        interfaces = {}
        current_if = {}
        ips = dict(
            all_ipv4_addresses = [],
            all_ipv6_addresses = [],
        )
        rc, out, err = self.module.run_command([ifconfig_path, '-a'])

        for line in out.splitlines():

            if line:
                words = line.split()

                if re.match('^\S', line) and len(words) > 3:
                    current_if = self.parse_interface_line(words, current_if, interfaces)
                    interfaces[ current_if['device'] ] = current_if
                elif words[0].startswith('options='):
                    self.parse_options_line(words, current_if, ips)
                elif words[0] == 'nd6':
                    self.parse_nd6_line(words, current_if, ips)
                elif words[0] == 'ether':
                    self.parse_ether_line(words, current_if, ips)
                elif words[0] == 'media:':
                    self.parse_media_line(words, current_if, ips)
                elif words[0] == 'status:':
                    self.parse_status_line(words, current_if, ips)
                elif words[0] == 'lladdr':
                    self.parse_lladdr_line(words, current_if, ips)
                elif words[0] == 'inet':
                    self.parse_inet_line(words, current_if, ips)
                elif words[0] == 'inet6':
                    self.parse_inet6_line(words, current_if, ips)
                else:
                    self.parse_unknown_line(words, current_if, ips)

        # 'parse_interface_line' and 'parse_inet*_line' leave two dicts in the
        # ipv4/ipv6 lists which is ugly and hard to read.
        # This quick hack merges the dictionaries. Purely cosmetic.
        for iface in interfaces:
            for v in 'ipv4', 'ipv6':
                combined_facts = {}
                for facts in interfaces[iface][v]:
                    combined_facts.update(facts)
                if len(combined_facts.keys()) > 0:
                    interfaces[iface][v] = [combined_facts]

        return interfaces, ips

    def parse_interface_line(self, words, current_if, interfaces):
        device = words[0][0:-1]
        if device not in interfaces:
            current_if = {'device': device, 'ipv4': [], 'ipv6': [], 'type': 'unknown'}
        else:
            current_if = interfaces[device]
        flags = self.get_options(words[1])
        v = 'ipv4'
        if 'IPv6' in flags:
            v = 'ipv6'
        if 'LOOPBACK' in flags:
            current_if['type'] = 'loopback'
        current_if[v].append({'flags': flags, 'mtu': words[3]})
        current_if['macaddress'] = 'unknown'    # will be overwritten later
        return current_if

    # Solaris displays single digit octets in MAC addresses e.g. 0:1:2:d:e:f
    # Add leading zero to each octet where needed.
    def parse_ether_line(self, words, current_if, ips):
        macaddress = ''
        for octet in words[1].split(':'):
            octet = ('0' + octet)[-2:None]
            macaddress += (octet + ':')
        current_if['macaddress'] = macaddress[0:-1]


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
                    k,v = i.split('=',1)
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
                        address,prefix = v.split('/')
                        self.facts[current_if]['ipv6'].append({
                            'address': address,
                            'prefix': prefix,
                        })

        return self.facts


class Virtual(Facts):
    """
    This is a generic Virtual subclass of Facts.  This should be further
    subclassed to implement per platform.  If you subclass this,
    you should define:
    - virtualization_type
    - virtualization_role
    - container (e.g. solaris zones, freebsd jails, linux containers)

    All subclasses MUST define platform.
    """

    def __new__(cls, *arguments, **keyword):
        # When Virtual is created, it chooses a subclass to create instead.
        # This check prevents the subclass from then trying to find a subclass
        # and create that.
        if cls is not Virtual:
            return super(Virtual, cls).__new__(cls)

        subclass = cls
        for sc in get_all_subclasses(Virtual):
            if sc.platform == platform.system():
                subclass = sc

        if PY3:
            return super(cls, subclass).__new__(subclass)
        else:
            return super(cls, subclass).__new__(subclass, *arguments, **keyword)

    def populate(self):
        self.get_virtual_facts()
        return self.facts

    def get_virtual_facts(self):
        self.facts['virtualization_type'] = ''
        self.facts['virtualization_role'] = ''


class LinuxVirtual(Virtual):
    """
    This is a Linux-specific subclass of Virtual.  It defines
    - virtualization_type
    - virtualization_role
    """
    platform = 'Linux'

    # For more information, check: http://people.redhat.com/~rjones/virt-what/
    def get_virtual_facts(self):
        # lxc/docker
        if os.path.exists('/proc/1/cgroup'):
            for line in get_file_lines('/proc/1/cgroup'):
                if re.search(r'/docker(/|-[0-9a-f]+\.scope)', line):
                    self.facts['virtualization_type'] = 'docker'
                    self.facts['virtualization_role'] = 'guest'
                    return
                if re.search('/lxc/', line) or re.search('/machine.slice/machine-lxc', line):
                    self.facts['virtualization_type'] = 'lxc'
                    self.facts['virtualization_role'] = 'guest'
                    return

        # lxc does not always appear in cgroups anymore but sets 'container=lxc' environment var, requires root privs
        if os.path.exists('/proc/1/environ'):
            for line in get_file_lines('/proc/1/environ'):
                if re.search('container=lxc', line):
                    self.facts['virtualization_type'] = 'lxc'
                    self.facts['virtualization_role'] = 'guest'
                    return

        if os.path.exists('/proc/vz'):
            self.facts['virtualization_type'] = 'openvz'
            if os.path.exists('/proc/bc'):
                self.facts['virtualization_role'] = 'host'
            else:
                self.facts['virtualization_role'] = 'guest'
            return

        systemd_container = get_file_content('/run/systemd/container')
        if systemd_container:
            self.facts['virtualization_type'] = systemd_container
            self.facts['virtualization_role'] = 'guest'
            return

        if os.path.exists("/proc/xen"):
            self.facts['virtualization_type'] = 'xen'
            self.facts['virtualization_role'] = 'guest'
            try:
                for line in get_file_lines('/proc/xen/capabilities'):
                    if "control_d" in line:
                        self.facts['virtualization_role'] = 'host'
            except IOError:
                pass
            return

        product_name = get_file_content('/sys/devices/virtual/dmi/id/product_name')

        if product_name in ['KVM', 'Bochs']:
            self.facts['virtualization_type'] = 'kvm'
            self.facts['virtualization_role'] = 'guest'
            return

        if product_name == 'RHEV Hypervisor':
            self.facts['virtualization_type'] = 'RHEV'
            self.facts['virtualization_role'] = 'guest'
            return

        if product_name == 'VMware Virtual Platform':
            self.facts['virtualization_type'] = 'VMware'
            self.facts['virtualization_role'] = 'guest'
            return

        if product_name == 'OpenStack Nova':
            self.facts['virtualization_type'] = 'openstack'
            self.facts['virtualization_role'] = 'guest'
            return

        bios_vendor = get_file_content('/sys/devices/virtual/dmi/id/bios_vendor')

        if bios_vendor == 'Xen':
            self.facts['virtualization_type'] = 'xen'
            self.facts['virtualization_role'] = 'guest'
            return

        if bios_vendor == 'innotek GmbH':
            self.facts['virtualization_type'] = 'virtualbox'
            self.facts['virtualization_role'] = 'guest'
            return

        sys_vendor = get_file_content('/sys/devices/virtual/dmi/id/sys_vendor')

        # FIXME: This does also match hyperv
        if sys_vendor == 'Microsoft Corporation':
            self.facts['virtualization_type'] = 'VirtualPC'
            self.facts['virtualization_role'] = 'guest'
            return

        if sys_vendor == 'Parallels Software International Inc.':
            self.facts['virtualization_type'] = 'parallels'
            self.facts['virtualization_role'] = 'guest'
            return

        if sys_vendor == 'QEMU':
            self.facts['virtualization_type'] = 'kvm'
            self.facts['virtualization_role'] = 'guest'
            return

        if sys_vendor == 'oVirt':
            self.facts['virtualization_type'] = 'kvm'
            self.facts['virtualization_role'] = 'guest'
            return

        if sys_vendor == 'OpenStack Foundation':
            self.facts['virtualization_type'] = 'openstack'
            self.facts['virtualization_role'] = 'guest'
            return

        if os.path.exists('/proc/self/status'):
            for line in get_file_lines('/proc/self/status'):
                if re.match('^VxID: \d+', line):
                    self.facts['virtualization_type'] = 'linux_vserver'
                    if re.match('^VxID: 0', line):
                        self.facts['virtualization_role'] = 'host'
                    else:
                        self.facts['virtualization_role'] = 'guest'
                    return

        if os.path.exists('/proc/cpuinfo'):
            for line in get_file_lines('/proc/cpuinfo'):
                if re.match('^model name.*QEMU Virtual CPU', line):
                    self.facts['virtualization_type'] = 'kvm'
                elif re.match('^vendor_id.*User Mode Linux', line):
                    self.facts['virtualization_type'] = 'uml'
                elif re.match('^model name.*UML', line):
                    self.facts['virtualization_type'] = 'uml'
                elif re.match('^vendor_id.*PowerVM Lx86', line):
                    self.facts['virtualization_type'] = 'powervm_lx86'
                elif re.match('^vendor_id.*IBM/S390', line):
                    self.facts['virtualization_type'] = 'PR/SM'
                    lscpu = self.module.get_bin_path('lscpu')
                    if lscpu:
                        rc, out, err = self.module.run_command(["lscpu"])
                        if rc == 0:
                            for line in out.splitlines():
                                data = line.split(":", 1)
                                key = data[0].strip()
                                if key == 'Hypervisor':
                                    self.facts['virtualization_type'] = data[1].strip()
                    else:
                        self.facts['virtualization_type'] = 'ibm_systemz'
                else:
                    continue
                if self.facts['virtualization_type'] == 'PR/SM':
                    self.facts['virtualization_role'] = 'LPAR'
                else:
                    self.facts['virtualization_role'] = 'guest'
                return

        # Beware that we can have both kvm and virtualbox running on a single system
        if os.path.exists("/proc/modules") and os.access('/proc/modules', os.R_OK):
            modules = []
            for line in get_file_lines("/proc/modules"):
                data = line.split(" ", 1)
                modules.append(data[0])

            if 'kvm' in modules:

                if os.path.isdir('/rhev/'):

                    # Check whether this is a RHEV hypervisor (is vdsm running ?)
                    for f in glob.glob('/proc/[0-9]*/comm'):
                        try:
                            if open(f).read().rstrip() == 'vdsm':
                                self.facts['virtualization_type'] = 'RHEV'
                                break
                        except:
                            pass
                    else:
                        self.facts['virtualization_type'] = 'kvm'

                else:
                    self.facts['virtualization_type'] = 'kvm'
                self.facts['virtualization_role'] = 'host'
                return

            if 'vboxdrv' in modules:
                self.facts['virtualization_type'] = 'virtualbox'
                self.facts['virtualization_role'] = 'host'
                return

        # If none of the above matches, return 'NA' for virtualization_type
        # and virtualization_role. This allows for proper grouping.
        self.facts['virtualization_type'] = 'NA'
        self.facts['virtualization_role'] = 'NA'
        return


class VirtualSysctlDetectionMixin(object):
    def detect_sysctl(self):
        self.sysctl_path = self.module.get_bin_path('sysctl')

    def detect_virt_product(self, key):
        self.detect_sysctl()
        if self.sysctl_path:
            rc, out, err = self.module.run_command("%s -n %s" % (self.sysctl_path, key))
            if rc == 0:
                if re.match('(KVM|Bochs|SmartDC).*', out):
                    self.facts['virtualization_type'] = 'kvm'
                    self.facts['virtualization_role'] = 'guest'
                elif re.match('.*VMware.*', out):
                    self.facts['virtualization_type'] = 'VMware'
                    self.facts['virtualization_role'] = 'guest'
                elif out.rstrip() == 'VirtualBox':
                    self.facts['virtualization_type'] = 'virtualbox'
                    self.facts['virtualization_role'] = 'guest'
                elif out.rstrip() == 'HVM domU':
                    self.facts['virtualization_type'] = 'xen'
                    self.facts['virtualization_role'] = 'guest'
                elif out.rstrip() == 'Parallels':
                    self.facts['virtualization_type'] = 'parallels'
                    self.facts['virtualization_role'] = 'guest'
                elif out.rstrip() == 'RHEV Hypervisor':
                    self.facts['virtualization_type'] = 'RHEV'
                    self.facts['virtualization_role'] = 'guest'

    def detect_virt_vendor(self, key):
        self.detect_sysctl()
        if self.sysctl_path:
            rc, out, err = self.module.run_command("%s -n %s" % (self.sysctl_path, key))
            if rc == 0:
                if out.rstrip() == 'QEMU':
                    self.facts['virtualization_type'] = 'kvm'
                    self.facts['virtualization_role'] = 'guest'
                if out.rstrip() == 'OpenBSD':
                    self.facts['virtualization_type'] = 'vmm'
                    self.facts['virtualization_role'] = 'guest'


class FreeBSDVirtual(Virtual):
    """
    This is a FreeBSD-specific subclass of Virtual.  It defines
    - virtualization_type
    - virtualization_role
    """
    platform = 'FreeBSD'

    def get_virtual_facts(self):

        # Set empty values as default
        self.facts['virtualization_type'] = ''
        self.facts['virtualization_role'] = ''

        if os.path.exists('/dev/xen/xenstore'):
            self.facts['virtualization_type'] = 'xen'
            self.facts['virtualization_role'] = 'guest'


class DragonFlyVirtual(FreeBSDVirtual):
    platform = 'DragonFly'


class OpenBSDVirtual(Virtual, VirtualSysctlDetectionMixin):
    """
    This is a OpenBSD-specific subclass of Virtual.  It defines
    - virtualization_type
    - virtualization_role
    """
    platform = 'OpenBSD'
    DMESG_BOOT = '/var/run/dmesg.boot'

    def get_virtual_facts(self):

        # Set empty values as default
        self.facts['virtualization_type'] = ''
        self.facts['virtualization_role'] = ''

        self.detect_virt_product('hw.product')
        if self.facts['virtualization_type'] == '':
            self.detect_virt_vendor('hw.vendor')

        # Check the dmesg if vmm(4) attached, indicating the host is
        # capable of virtualization.
        dmesg_boot = get_file_content(OpenBSDVirtual.DMESG_BOOT)
        for line in dmesg_boot.splitlines():
            match = re.match('^vmm0 at mainbus0: (SVM/RVI|VMX/EPT)$', line)
            if match:
                self.facts['virtualization_type'] = 'vmm'
                self.facts['virtualization_role'] = 'host'


class NetBSDVirtual(Virtual, VirtualSysctlDetectionMixin):
    platform = 'NetBSD'

    def get_virtual_facts(self):
        # Set empty values as default
        self.facts['virtualization_type'] = ''
        self.facts['virtualization_role'] = ''

        self.detect_virt_product('machdep.dmi.system-product')
        if self.facts['virtualization_type'] == '':
            self.detect_virt_vendor('machdep.dmi.system-vendor')

        if os.path.exists('/dev/xencons'):
            self.facts['virtualization_type'] = 'xen'
            self.facts['virtualization_role'] = 'guest'


class HPUXVirtual(Virtual):
    """
    This is a HP-UX specific subclass of Virtual. It defines
    - virtualization_type
    - virtualization_role
    """
    platform = 'HP-UX'

    def get_virtual_facts(self):
        if os.path.exists('/usr/sbin/vecheck'):
            rc, out, err = self.module.run_command("/usr/sbin/vecheck")
            if rc == 0:
                self.facts['virtualization_type'] = 'guest'
                self.facts['virtualization_role'] = 'HP vPar'
        if os.path.exists('/opt/hpvm/bin/hpvminfo'):
            rc, out, err = self.module.run_command("/opt/hpvm/bin/hpvminfo")
            if rc == 0 and re.match('.*Running.*HPVM vPar.*', out):
                self.facts['virtualization_type'] = 'guest'
                self.facts['virtualization_role'] = 'HPVM vPar'
            elif rc == 0 and re.match('.*Running.*HPVM guest.*', out):
                self.facts['virtualization_type'] = 'guest'
                self.facts['virtualization_role'] = 'HPVM IVM'
            elif rc == 0 and re.match('.*Running.*HPVM host.*', out):
                self.facts['virtualization_type'] = 'host'
                self.facts['virtualization_role'] = 'HPVM'
        if os.path.exists('/usr/sbin/parstatus'):
            rc, out, err = self.module.run_command("/usr/sbin/parstatus")
            if rc == 0:
                self.facts['virtualization_type'] = 'guest'
                self.facts['virtualization_role'] = 'HP nPar'


class SunOSVirtual(Virtual):
    """
    This is a SunOS-specific subclass of Virtual.  It defines
    - virtualization_type
    - virtualization_role
    - container
    """
    platform = 'SunOS'

    def get_virtual_facts(self):

        # Check if it's a zone

        zonename = self.module.get_bin_path('zonename')
        if zonename:
            rc, out, err = self.module.run_command(zonename)
            if rc == 0 and out.rstrip() != "global":
                self.facts['container'] = 'zone'
        # Check if it's a branded zone (i.e. Solaris 8/9 zone)
        if os.path.isdir('/.SUNWnative'):
            self.facts['container'] = 'zone'
        # If it's a zone check if we can detect if our global zone is itself virtualized.
        # Relies on the "guest tools" (e.g. vmware tools) to be installed
        if 'container' in self.facts and self.facts['container'] == 'zone':
            modinfo = self.module.get_bin_path('modinfo')
            if modinfo:
                rc, out, err = self.module.run_command(modinfo)
                if rc == 0:
                    for line in out.splitlines():
                        if 'VMware' in line:
                            self.facts['virtualization_type'] = 'vmware'
                            self.facts['virtualization_role'] = 'guest'
                        if 'VirtualBox' in line:
                            self.facts['virtualization_type'] = 'virtualbox'
                            self.facts['virtualization_role'] = 'guest'

        if os.path.exists('/proc/vz'):
            self.facts['virtualization_type'] = 'virtuozzo'
            self.facts['virtualization_role'] = 'guest'

        # Detect domaining on Sparc hardware
        virtinfo = self.module.get_bin_path('virtinfo')
        if virtinfo:
            # The output of virtinfo is different whether we are on a machine with logical
            # domains ('LDoms') on a T-series or domains ('Domains') on a M-series. Try LDoms first.
            rc, out, err = self.module.run_command("/usr/sbin/virtinfo -p")
            # The output contains multiple lines with different keys like this:
            #   DOMAINROLE|impl=LDoms|control=false|io=false|service=false|root=false
            # The output may also be not formatted and the returncode is set to 0 regardless of the error condition:
            #   virtinfo can only be run from the global zone
            if rc == 0:
                try:
                    for line in out.splitlines():
                        fields = line.split('|')
                        if( fields[0] == 'DOMAINROLE' and fields[1] == 'impl=LDoms' ):
                            self.facts['virtualization_type'] = 'ldom'
                            self.facts['virtualization_role'] = 'guest'
                            hostfeatures = []
                            for field in fields[2:]:
                                arg = field.split('=')
                                if( arg[1] == 'true' ):
                                    hostfeatures.append(arg[0])
                            if( len(hostfeatures) > 0 ):
                                self.facts['virtualization_role'] = 'host (' + ','.join(hostfeatures) + ')'
                except ValueError:
                    pass

        else:
            smbios = self.module.get_bin_path('smbios')
            if not smbios:
                return
            rc, out, err = self.module.run_command(smbios)
            if rc == 0:
                for line in out.splitlines():
                    if 'VMware' in line:
                        self.facts['virtualization_type'] = 'vmware'
                        self.facts['virtualization_role'] = 'guest'
                    elif 'Parallels' in line:
                        self.facts['virtualization_type'] = 'parallels'
                        self.facts['virtualization_role'] = 'guest'
                    elif 'VirtualBox' in line:
                        self.facts['virtualization_type'] = 'virtualbox'
                        self.facts['virtualization_role'] = 'guest'
                    elif 'HVM domU' in line:
                        self.facts['virtualization_type'] = 'xen'
                        self.facts['virtualization_role'] = 'guest'
                    elif 'KVM' in line:
                        self.facts['virtualization_type'] = 'kvm'
                        self.facts['virtualization_role'] = 'guest'


def ansible_facts(module, gather_subset):
    facts = {}
    facts['gather_subset'] = list(gather_subset)
    facts.update(Facts(module).populate())
    for subset in gather_subset:
        facts.update(FACT_SUBSETS[subset](module,
                                         load_on_init=False,
                                         cached_facts=facts).populate())
    return facts


# This is the main entry point for facts.py. This is the only method from this module
# called directly from setup.py module.
# FIXME: This is coupled to AnsibleModule (it assumes module.params has keys 'gather_subset',
#        'gather_timeout', 'filter' instead of passing those are args or oblique ds
#        module is passed in and self.module.misc_AnsibleModule_methods are used, so hard to decouple.
# FIXME: split 'build list of fact subset names' from 'inst those classes' and 'run those classes'
#def get_all_facts(module):
def get_gatherer_names(module):
    # Retrieve module parameters
    gather_subset = module.params['gather_subset']

    global GATHER_TIMEOUT
    GATHER_TIMEOUT = module.params['gather_timeout']

    # Retrieve all facts elements
    additional_subsets = set()
    exclude_subsets = set()
    for subset in gather_subset:
        if subset == 'all':
            additional_subsets.update(VALID_SUBSETS)
            continue
        if subset.startswith('!'):
            subset = subset[1:]
            if subset == 'all':
                exclude_subsets.update(VALID_SUBSETS)
                continue
            exclude = True
        else:
            exclude = False

        if subset not in VALID_SUBSETS:
            raise TypeError("Bad subset '%s' given to Ansible. gather_subset options allowed: all, %s" % (subset, ", ".join(FACT_SUBSETS.keys())))

        if exclude:
            exclude_subsets.add(subset)
        else:
            additional_subsets.add(subset)

    if not additional_subsets:
        additional_subsets.update(VALID_SUBSETS)

    additional_subsets.difference_update(exclude_subsets)
    return additional_subsets


def _get_all_facts(gatherer_names, module):
    additional_subsets = gatherer_names

    setup_options = dict(module_setup=True)

    # FIXME: it looks like we run Facter/Ohai twice...

    # facter and ohai are given a different prefix than other subsets
    if 'facter' in additional_subsets:
        additional_subsets.difference_update(('facter',))
        # FIXME: .populate(prefix='facter')
        #   or a dict.update() that can prefix key names
        facter_ds = FACT_SUBSETS['facter'](module, load_on_init=False).populate()
        if facter_ds:
            for (k, v) in facter_ds.items():
                setup_options['facter_%s' % k.replace('-', '_')] = v

    if 'ohai' in additional_subsets:
        additional_subsets.difference_update(('ohai',))
        ohai_ds = FACT_SUBSETS['ohai'](module, load_on_init=False).populate()
        if ohai_ds:
            for (k, v) in ohai_ds.items():
                setup_options['ohai_%s' % k.replace('-', '_')] = v

    facts = ansible_facts(module, additional_subsets)

    for (k, v) in facts.items():
        setup_options["ansible_%s" % k.replace('-', '_')] = v

    setup_result = {'ansible_facts': {}}

    for (k, v) in setup_options.items():
        if module.params['filter'] == '*' or fnmatch.fnmatch(k, module.params['filter']):
            setup_result['ansible_facts'][k] = v

    return setup_result


def get_all_facts(module):
    gatherer_names = get_gatherer_names(module)

    # FIXME: avoid having to pass in module until we populate
    all_facts = _get_all_facts(gatherer_names, module)

    return all_facts


# Allowed fact subset for gather_subset options and what classes they use
# Note: have to define this at the bottom as it references classes defined earlier in this file
FACT_SUBSETS = dict(
    # FIXME: add facts=Facts,
    hardware=Hardware,
    network=Network,
    virtual=Virtual,
    ohai=Ohai,
    facter=Facter,
)
VALID_SUBSETS = frozenset(FACT_SUBSETS.keys())
