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
