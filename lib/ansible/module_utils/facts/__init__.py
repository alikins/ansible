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
#       ie, code like self.module.run_command('some_netinfo_tool
#                                             --someoption')[1].splitlines[][0].split()[1] ->
#          netinfo_output = self._netinfo_provider()
#          netinfo_data = self._netinfo_parse(netinfo_output)
#       why?
#          - much much easier to test
# TODO: mv timeout stuff to its own module
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import fnmatch
import platform
import signal

from ansible.module_utils.basic import get_all_subclasses
from ansible.module_utils.six import PY3

from ansible.module_utils.facts.collector import BaseFactCollector
from ansible.module_utils.facts.namespace import PrefixFactNamespace, FactNamespace
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

GATHER_TIMEOUT=None
DEFAULT_GATHER_TIMEOUT = 10


class TimeoutError(Exception):
    pass


def timeout(seconds=None, error_message="Timer expired"):

    def decorator(func):
        def _handle_timeout(signum, frame):
            raise TimeoutError(error_message)

        def wrapper(*args, **kwargs):
            local_seconds = seconds  # Make local var as we modify this every time it's invoked
            if local_seconds is None:
                local_seconds = globals().get('GATHER_TIMEOUT') or DEFAULT_GATHER_TIMEOUT

            signal.signal(signal.SIGALRM, _handle_timeout)
            signal.alarm(local_seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
            return result

        return wrapper

    # If we were called as @timeout, then the first parameter will be the
    # function we are to wrap instead of the number of seconds.  Detect this
    # and correct it by setting seconds to our sentinel value and return the
    # inner decorator function manually wrapped around the function
    if callable(seconds):
        func = seconds
        seconds = None
        return decorator(func)

    # If we were called as @timeout([...]) then python itself will take
    # care of wrapping the inner decorator around the function

    return decorator

# --------------------------------------------------------------

class WrapperCollector(BaseFactCollector):
    facts_class = None

    def __init__(self, module, collectors=None, namespace=None):
        super(WrapperCollector, self).__init__(collectors=collectors,
                                               namespace=namespace)
        self.module = module

    def collect(self, collected_facts=None):
        collected_facts = collected_facts or {}

        # WARNING: virtual.populate mutates cached_facts and returns a ref
        #          so for now, pass in a copy()
        facts_obj = self.facts_class(self.module, cached_facts=collected_facts.copy())

        facts_dict = facts_obj.populate()

        if self.namespace:
            facts_dict = self._transform_dict_keys(facts_dict)

        return facts_dict

# NOTE: This Facts class is mostly facts gathering implementation.
#       A FactsModel data structure class would be useful, especially
#       if we ever plan on documenting what various facts mean. This would
#       also be a good place to map fact label to fact class -akl
# NOTE: And a class similar to this one that composites a set or tree of
#       other fact gathering classes. Potentially driven by run time passing
#       of a list of the fact gather classes to include (finer grained gather_facts)
#       Or, possibly even a list or dict of fact labels 'ansible_lvm' for ex, that
#       the driver class would use to determine which fact gathering classes to load
class Facts(object):
    """
    This class should only attempt to populate those facts that
    are mostly generic to all systems.  This includes platform facts,
    service facts (e.g. ssh keys or selinux), and distribution facts.
    Anything that requires extensive code or may have more than one
    possible implementation to establish facts for a given topic should
    subclass Facts.
    """

    # i86pc is a Solaris and derivatives-ism
    _I386RE = re.compile(r'i([3456]86|86pc)')
    # For the most part, we assume that platform.dist() will tell the truth.
    # This is the fallback to handle unknowns or exceptions
    SELINUX_MODE_DICT = { 1: 'enforcing', 0: 'permissive', -1: 'disabled' }

    # A list of dicts.  If there is a platform with more than one
    # package manager, put the preferred one last.  If there is an
    # ansible module, use that as the value for the 'name' key.
    # NOTE: This is really constants. This dict is also used in a weird way by
    #       ansible.executor.action_write_locks that introduces a weird dep that could
    #       be avoided if this dict was elsewhere. -akl
    PKG_MGRS = [ { 'path' : '/usr/bin/yum',         'name' : 'yum' },
                 { 'path' : '/usr/bin/dnf',         'name' : 'dnf' },
                 { 'path' : '/usr/bin/apt-get',     'name' : 'apt' },
                 { 'path' : '/usr/bin/zypper',      'name' : 'zypper' },
                 { 'path' : '/usr/sbin/urpmi',      'name' : 'urpmi' },
                 { 'path' : '/usr/bin/pacman',      'name' : 'pacman' },
                 { 'path' : '/bin/opkg',            'name' : 'opkg' },
                 { 'path' : '/usr/pkg/bin/pkgin',   'name' : 'pkgin' },
                 { 'path' : '/opt/local/bin/pkgin', 'name' : 'pkgin' },
                 { 'path' : '/opt/tools/bin/pkgin', 'name' : 'pkgin' },
                 { 'path' : '/opt/local/bin/port',  'name' : 'macports' },
                 { 'path' : '/usr/local/bin/brew',  'name' : 'homebrew' },
                 { 'path' : '/sbin/apk',            'name' : 'apk' },
                 { 'path' : '/usr/sbin/pkg',        'name' : 'pkgng' },
                 { 'path' : '/usr/sbin/swlist',     'name' : 'SD-UX' },
                 { 'path' : '/usr/bin/emerge',      'name' : 'portage' },
                 { 'path' : '/usr/sbin/pkgadd',     'name' : 'svr4pkg' },
                 { 'path' : '/usr/bin/pkg',         'name' : 'pkg5' },
                 { 'path' : '/usr/bin/xbps-install','name' : 'xbps' },
                 { 'path' : '/usr/local/sbin/pkg',  'name' : 'pkgng' },
                 { 'path' : '/usr/bin/swupd',       'name' : 'swupd' },
                 { 'path' : '/usr/sbin/sorcery',    'name' : 'sorcery' },
                ]

    # NOTE: load_on_init is changed for ohai/facter classes. Ideally, all facts
    #       would be load_on_init=False and this could be removed. -akl
    # NOTE: cached_facts seems like a misnomer. Seems to be used more like an accumulator -akl
    def __init__(self, module, load_on_init=True, cached_facts=None):

        self.module = module
        if not cached_facts:
            self.facts = {}
        else:
            self.facts = cached_facts
        ### TODO: Eventually, these should all get moved to populate().  But
        # some of the values are currently being used by other subclasses (for
        # instance, os_family and distribution).  Have to sort out what to do
        # about those first.
        # NOTE: if the various gathering methods take a arg that is the 'accumulated' facts
        #       then this wouldn't need to happen on init. There would still be some ordering required
        #       though. If the gather methods return a dict of the new facts, then the accumulated facts
        #       can be read-only to avoid manipulating it by side effect. -akl

        # TODO: to avoid hard coding this, something like
        # list so we can imply some order suggestions
        # fact_providers is a map or lookup of fact label -> fact gather class/inst that provides it
        #  - likely will also involve a fact plugin lookup
        #    ( could fact providing modules include the list of fact labels in their metadata? so we could determine
        #      with plugin to load before we actually load and inst it?)
        # fact_gatherers = []
        # for requested_fact in requested_facts:
        #    fact_gatherer = self.fact_providers.get('requested_fact', None)
        #    if not fact_gatherer:
        #        continue
        #    fact_gatherers.append(fact_gatherer)

        ## TODO: de-dup fact_gatherers
        #for gatherer in fact_gatherers:
        #    data = gatherer.gather()
        #    self.facts.update(data)

        if load_on_init:
            self.get_platform_facts()
            # Example of returning new facts and updating self.facts with it -akl
            self.facts.update(Distribution(module).populate())
            self.get_cmdline()
            self.get_public_ssh_host_keys()
            # NOTE: lots of linux specific facts here.  A finer grained gather_subset could drive this. -akl
            self.get_selinux_facts()
            self.get_apparmor_facts()
            self.get_caps_facts()
            self.get_fips_facts()
            self.get_pkg_mgr_facts()
            self.get_service_mgr_facts()
            self.get_lsb_facts()
            self.get_date_time_facts()
            self.get_user_facts()
            self.get_local_facts()
            self.get_env_facts()
            self.get_dns_facts()
            self.get_python_facts()


    def populate(self):
        return self.facts

    # Platform
    # platform.system() can be Linux, Darwin, Java, or Windows
    def get_platform_facts(self):
        # NOTE: pretty much every method should create a new dict (or whatever the FactsModel ds is)
        #       and return it and let main Facts() class combine them. -akl
        # NOTE: a facts.Platform() class that wraps all of this would make mocking/testing easier -akl
        self.facts['system'] = platform.system()
        self.facts['kernel'] = platform.release()
        self.facts['machine'] = platform.machine()
        self.facts['python_version'] = platform.python_version()
        # NOTE: not platform at all... -akl
        self.facts['fqdn'] = socket.getfqdn()
        self.facts['hostname'] = platform.node().split('.')[0]
        self.facts['nodename'] = platform.node()

        # NOTE: not platform -akl
        self.facts['domain'] = '.'.join(self.facts['fqdn'].split('.')[1:])

        arch_bits = platform.architecture()[0]

        # NOTE: this could be split into arch and/or system specific classes/methods -akl
        self.facts['userspace_bits'] = arch_bits.replace('bit', '')
        if self.facts['machine'] == 'x86_64':
            self.facts['architecture'] = self.facts['machine']
            if self.facts['userspace_bits'] == '64':
                self.facts['userspace_architecture'] = 'x86_64'
            elif self.facts['userspace_bits'] == '32':
                self.facts['userspace_architecture'] = 'i386'
        elif Facts._I386RE.search(self.facts['machine']):
            self.facts['architecture'] = 'i386'
            if self.facts['userspace_bits'] == '64':
                self.facts['userspace_architecture'] = 'x86_64'
            elif self.facts['userspace_bits'] == '32':
                self.facts['userspace_architecture'] = 'i386'
        else:
            self.facts['architecture'] = self.facts['machine']

        # NOTE: -> aix_platform = AixPlatform(); facts_dict.update(aix_platform) -akl
        if self.facts['system'] == 'AIX':
            # Attempt to use getconf to figure out architecture
            # fall back to bootinfo if needed
            # NOTE: in general, the various 'get_bin_path(); data=run_command()' could be split to methods/classes for providing info
            #        one to get the raw data, another to parse it into useful chunks
            #        then both are easy to mock for testing -akl
            getconf_bin = self.module.get_bin_path('getconf')
            if getconf_bin:
                rc, out, err = self.module.run_command([getconf_bin, 'MACHINE_ARCHITECTURE'])
                data = out.splitlines()
                self.facts['architecture'] = data[0]
            else:
                bootinfo_bin = self.module.get_bin_path('bootinfo')
                rc, out, err = self.module.run_command([bootinfo_bin, '-p'])
                data = out.splitlines()
                self.facts['architecture'] = data[0]
        elif self.facts['system'] == 'OpenBSD':
            self.facts['architecture'] = platform.uname()[5]

        # NOTE: the same comment about get_bin_path() above also applies to fetching file content
        #       attempting to mock a file open and read is a PITA, but mocking read_dbus_machine_id() is easy to mock -akl
        machine_id = get_file_content("/var/lib/dbus/machine-id") or get_file_content("/etc/machine-id")
        if machine_id:
            machine_id = machine_id.splitlines()[0]
            self.facts["machine_id"] = machine_id

    def get_local_facts(self):

        # NOTE: -> _has_local_facts()
        #      or better, a local_facts iterator that is empty if there is no fact_path/etc -kl
        fact_path = self.module.params.get('fact_path', None)
        # NOTE: pretty much any unwrapped os.path.* is a PITA to unittest -akl
        if not fact_path or not os.path.exists(fact_path):
            return

        local = {}
        for fn in sorted(glob.glob(fact_path + '/*.fact')):
            # where it will sit under local facts
            fact_base = os.path.basename(fn).replace('.fact','')
            if stat.S_IXUSR & os.stat(fn)[stat.ST_MODE]:
                # run it
                # try to read it as json first
                # if that fails read it with ConfigParser
                # if that fails, skip it
                try:
                    rc, out, err = self.module.run_command(fn)
                except UnicodeError:
                    fact = 'error loading fact - output of running %s was not utf-8' % fn
                    local[fact_base] = fact
                    self.facts['local'] = local
                    return
            else:
                out = get_file_content(fn, default='')

            # load raw json
            fact = 'loading %s' % fact_base
            try:
                fact = json.loads(out)
            except ValueError:
                # load raw ini
                cp = configparser.ConfigParser()
                try:
                    cp.readfp(StringIO(out))
                except configparser.Error:
                    fact = "error loading fact - please check content"
                else:
                    fact = {}
                    for sect in cp.sections():
                        if sect not in fact:
                            fact[sect] = {}
                        for opt in cp.options(sect):
                            val = cp.get(sect, opt)
                            fact[sect][opt]=val

            local[fact_base] = fact
        # NOTE: just return the new facts dict, empty or not -akl
        if not local:
            return
        self.facts['local'] = local

    def get_cmdline(self):
        data = get_file_content('/proc/cmdline')
        if data:
            self.facts['cmdline'] = {}
            try:
                for piece in shlex.split(data):
                    item = piece.split('=', 1)
                    if len(item) == 1:
                        self.facts['cmdline'][item[0]] = True
                    else:
                        self.facts['cmdline'][item[0]] = item[1]
            except ValueError:
                pass

    def get_public_ssh_host_keys(self):
        keytypes = ('dsa', 'rsa', 'ecdsa', 'ed25519')

        # list of directories to check for ssh keys
        # used in the order listed here, the first one with keys is used
        keydirs = ['/etc/ssh', '/etc/openssh', '/etc']

        for keydir in keydirs:
            for type_ in keytypes:
                factname = 'ssh_host_key_%s_public' % type_
                if factname in self.facts:
                    # a previous keydir was already successful, stop looking
                    # for keys
                    return
                key_filename = '%s/ssh_host_%s_key.pub' % (keydir, type_)
                keydata = get_file_content(key_filename)
                if keydata is not None:
                    self.facts[factname] = keydata.split()[1]

    def get_pkg_mgr_facts(self):
        if self.facts['system'] == 'OpenBSD':
            self.facts['pkg_mgr'] = 'openbsd_pkg'
        else:
            self.facts['pkg_mgr'] = 'unknown'
            for pkg in Facts.PKG_MGRS:
                if os.path.isfile(pkg['path']):
                    self.facts['pkg_mgr'] = pkg['name']

    # NOTE: This is definately complicated enough to warrant its own module or class (and tests) -akl
    def get_service_mgr_facts(self):
        #TODO: detect more custom init setups like bootscripts, dmd, s6, Epoch, etc
        # also other OSs other than linux might need to check across several possible candidates

        # Mapping of proc_1 values to more useful names
        proc_1_map = {
            'procd': 'openwrt_init',
            'runit-init': 'runit',
            'svscan': 'svc',
            'openrc-init': 'openrc',
        }

        # try various forms of querying pid 1
        proc_1 = get_file_content('/proc/1/comm')
        if proc_1 is None:
            rc, proc_1, err = self.module.run_command("ps -p 1 -o comm|tail -n 1", use_unsafe_shell=True)
            # If the output of the command starts with what looks like a PID, then the 'ps' command
            # probably didn't work the way we wanted, probably because it's busybox
            if re.match(r' *[0-9]+ ', proc_1):
                proc_1 = None

        # The ps command above may return "COMMAND" if the user cannot read /proc, e.g. with grsecurity
        if proc_1 == "COMMAND\n":
            proc_1 = None

        if proc_1 is not None:
            proc_1 = os.path.basename(proc_1)
            proc_1 = to_native(proc_1)
            proc_1 = proc_1.strip()

        if proc_1 is not None and (proc_1 == 'init' or proc_1.endswith('sh')):
            # many systems return init, so this cannot be trusted, if it ends in 'sh' it probalby is a shell in a container
            proc_1 = None

        # if not init/None it should be an identifiable or custom init, so we are done!
        if proc_1 is not None:
            # Lookup proc_1 value in map and use proc_1 value itself if no match
            self.facts['service_mgr'] = proc_1_map.get(proc_1, proc_1)

        # start with the easy ones
        elif self.facts['distribution'] == 'MacOSX':
            #FIXME: find way to query executable, version matching is not ideal
            if LooseVersion(platform.mac_ver()[0]) >= LooseVersion('10.4'):
                self.facts['service_mgr'] = 'launchd'
            else:
                self.facts['service_mgr'] = 'systemstarter'
        elif 'BSD' in self.facts['system'] or self.facts['system'] in ['Bitrig', 'DragonFly']:
            #FIXME: we might want to break out to individual BSDs or 'rc'
            self.facts['service_mgr'] = 'bsdinit'
        elif self.facts['system'] == 'AIX':
            self.facts['service_mgr'] = 'src'
        elif self.facts['system'] == 'SunOS':
            self.facts['service_mgr'] = 'smf'
        elif self.facts['distribution'] == 'OpenWrt':
            self.facts['service_mgr'] = 'openwrt_init'
        elif self.facts['system'] == 'Linux':
            if self.is_systemd_managed():
                self.facts['service_mgr'] = 'systemd'
            elif self.module.get_bin_path('initctl') and os.path.exists("/etc/init/"):
                self.facts['service_mgr'] = 'upstart'
            elif os.path.exists('/sbin/openrc'):
                self.facts['service_mgr'] = 'openrc'
            elif os.path.exists('/etc/init.d/'):
                self.facts['service_mgr'] = 'sysvinit'

        if not self.facts.get('service_mgr', False):
            # if we cannot detect, fallback to generic 'service'
            self.facts['service_mgr'] = 'service'

    def get_lsb_facts(self):
        # NOTE: looks like two seperate methods to me - akl
        lsb_path = self.module.get_bin_path('lsb_release')
        if lsb_path:
            rc, out, err = self.module.run_command([lsb_path, "-a"], errors='surrogate_then_replace')
            if rc == 0:
                self.facts['lsb'] = {}
                for line in out.splitlines():
                    if len(line) < 1 or ':' not in line:
                        continue
                    value = line.split(':', 1)[1].strip()
                    if 'LSB Version:' in line:
                        self.facts['lsb']['release'] = value
                    elif 'Distributor ID:' in line:
                        self.facts['lsb']['id'] = value
                    elif 'Description:' in line:
                        self.facts['lsb']['description'] = value
                    elif 'Release:' in line:
                        self.facts['lsb']['release'] = value
                    elif 'Codename:' in line:
                        self.facts['lsb']['codename'] = value
        elif lsb_path is None and os.path.exists('/etc/lsb-release'):
            self.facts['lsb'] = {}
            for line in get_file_lines('/etc/lsb-release'):
                value = line.split('=',1)[1].strip()
                if 'DISTRIB_ID' in line:
                    self.facts['lsb']['id'] = value
                elif 'DISTRIB_RELEASE' in line:
                    self.facts['lsb']['release'] = value
                elif 'DISTRIB_DESCRIPTION' in line:
                    self.facts['lsb']['description'] = value
                elif 'DISTRIB_CODENAME' in line:
                    self.facts['lsb']['codename'] = value

        if 'lsb' in self.facts and 'release' in self.facts['lsb']:
            self.facts['lsb']['major_release'] = self.facts['lsb']['release'].split('.')[0]

    # NOTE: the weird module deps required for this is confusing. Likely no good approach though... - akl
    # NOTE: also likely a good candidate for it's own module or class, it barely uses self
    def get_selinux_facts(self):
        if not HAVE_SELINUX:
            self.facts['selinux'] = False
            return
        self.facts['selinux'] = {}
        if not selinux.is_selinux_enabled():
            self.facts['selinux']['status'] = 'disabled'
        # NOTE: this could just return in the above clause and the rest of this is up an indent -akl
        else:
            self.facts['selinux']['status'] = 'enabled'
            try:
                self.facts['selinux']['policyvers'] = selinux.security_policyvers()
            except (AttributeError,OSError):
                self.facts['selinux']['policyvers'] = 'unknown'
            try:
                (rc, configmode) = selinux.selinux_getenforcemode()
                if rc == 0:
                    # NOTE: not sure I understand why the class attributes are referenced via Facts class here when it's self
                    #       though that makes the case for all of that constants info to be in a constants class (ie, class SelinuxMode) -akl
                    self.facts['selinux']['config_mode'] = Facts.SELINUX_MODE_DICT.get(configmode, 'unknown')
                else:
                    self.facts['selinux']['config_mode'] = 'unknown'
            except (AttributeError,OSError):
                self.facts['selinux']['config_mode'] = 'unknown'
            try:
                mode = selinux.security_getenforce()
                self.facts['selinux']['mode'] = Facts.SELINUX_MODE_DICT.get(mode, 'unknown')
            except (AttributeError,OSError):
                self.facts['selinux']['mode'] = 'unknown'
            try:
                (rc, policytype) = selinux.selinux_getpolicytype()
                if rc == 0:
                    self.facts['selinux']['type'] = policytype
                else:
                    self.facts['selinux']['type'] = 'unknown'
            except (AttributeError,OSError):
                self.facts['selinux']['type'] = 'unknown'

    def get_apparmor_facts(self):
        self.facts['apparmor'] = {}
        if os.path.exists('/sys/kernel/security/apparmor'):
            self.facts['apparmor']['status'] = 'enabled'
        else:
            self.facts['apparmor']['status'] = 'disabled'

    def get_caps_facts(self):
        capsh_path = self.module.get_bin_path('capsh')
        # NOTE: early exit 'if not crash_path' and unindent rest of method -akl
        if capsh_path:
            # NOTE: -> get_caps_data()/parse_caps_data() for easier mocking -akl
            rc, out, err = self.module.run_command([capsh_path, "--print"], errors='surrogate_then_replace')
            enforced_caps = []
            enforced = 'NA'
            for line in out.splitlines():
                if len(line) < 1:
                    continue
                if line.startswith('Current:'):
                    if line.split(':')[1].strip() == '=ep':
                        enforced = 'False'
                    else:
                        enforced = 'True'
                        enforced_caps = [i.strip() for i in line.split('=')[1].split(',')]

            self.facts['system_capabilities_enforced'] = enforced
            self.facts['system_capabilities'] = enforced_caps


    def get_fips_facts(self):
        # NOTE: this is populated even if it is not set
        self.facts['fips'] = False
        data = get_file_content('/proc/sys/crypto/fips_enabled')
        if data and data == '1':
            self.facts['fips'] = True


    def get_date_time_facts(self):
        self.facts['date_time'] = {}

        now = datetime.datetime.now()
        self.facts['date_time']['year'] = now.strftime('%Y')
        self.facts['date_time']['month'] = now.strftime('%m')
        self.facts['date_time']['weekday'] = now.strftime('%A')
        self.facts['date_time']['weekday_number'] = now.strftime('%w')
        self.facts['date_time']['weeknumber'] = now.strftime('%W')
        self.facts['date_time']['day'] = now.strftime('%d')
        self.facts['date_time']['hour'] = now.strftime('%H')
        self.facts['date_time']['minute'] = now.strftime('%M')
        self.facts['date_time']['second'] = now.strftime('%S')
        self.facts['date_time']['epoch'] = now.strftime('%s')
        if self.facts['date_time']['epoch'] == '' or self.facts['date_time']['epoch'][0] == '%':
            # NOTE: in this case, the epoch wont match the rest of the date_time facts? ie, it's a few milliseconds later..? -akl
            self.facts['date_time']['epoch'] = str(int(time.time()))
        self.facts['date_time']['date'] = now.strftime('%Y-%m-%d')
        self.facts['date_time']['time'] = now.strftime('%H:%M:%S')
        self.facts['date_time']['iso8601_micro'] = now.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        self.facts['date_time']['iso8601'] = now.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        self.facts['date_time']['iso8601_basic'] = now.strftime("%Y%m%dT%H%M%S%f")
        self.facts['date_time']['iso8601_basic_short'] = now.strftime("%Y%m%dT%H%M%S")
        self.facts['date_time']['tz'] = time.strftime("%Z")
        self.facts['date_time']['tz_offset'] = time.strftime("%z")

    def is_systemd_managed(self):
        # tools must be installed
        if self.module.get_bin_path('systemctl'):

            # this should show if systemd is the boot init system, if checking init faild to mark as systemd
            # these mirror systemd's own sd_boot test http://www.freedesktop.org/software/systemd/man/sd_booted.html
            for canary in ["/run/systemd/system/", "/dev/.run/systemd/", "/dev/.systemd/"]:
                if os.path.exists(canary):
                    return True
        return False

    # User
    def get_user_facts(self):
        self.facts['user_id'] = getpass.getuser()
        pwent = pwd.getpwnam(getpass.getuser())
        self.facts['user_uid'] = pwent.pw_uid
        self.facts['user_gid'] = pwent.pw_gid
        self.facts['user_gecos'] = pwent.pw_gecos
        self.facts['user_dir'] = pwent.pw_dir
        self.facts['user_shell'] = pwent.pw_shell
        self.facts['real_user_id'] = os.getuid()
        self.facts['effective_user_id'] = os.geteuid()
        self.facts['real_group_id'] = os.getgid()
        self.facts['effective_group_id'] = os.getgid()

    def get_env_facts(self):
        self.facts['env'] = {}
        for k,v in iteritems(os.environ):
            self.facts['env'][k] = v

    def get_dns_facts(self):
        self.facts['dns'] = {}
        for line in get_file_content('/etc/resolv.conf', '').splitlines():
            if line.startswith('#') or line.startswith(';') or line.strip() == '':
                continue
            tokens = line.split()
            if len(tokens) == 0:
                continue
            if tokens[0] == 'nameserver':
                if not 'nameservers' in self.facts['dns']:
                    self.facts['dns']['nameservers'] = []
                for nameserver in tokens[1:]:
                    self.facts['dns']['nameservers'].append(nameserver)
            elif tokens[0] == 'domain':
                if len(tokens) > 1:
                    self.facts['dns']['domain'] = tokens[1]
            elif tokens[0] == 'search':
                self.facts['dns']['search'] = []
                for suffix in tokens[1:]:
                    self.facts['dns']['search'].append(suffix)
            elif tokens[0] == 'sortlist':
                self.facts['dns']['sortlist'] = []
                for address in tokens[1:]:
                    self.facts['dns']['sortlist'].append(address)
            elif tokens[0] == 'options':
                self.facts['dns']['options'] = {}
                if len(tokens) > 1:
                    for option in tokens[1:]:
                        option_tokens = option.split(':', 1)
                        if len(option_tokens) == 0:
                            continue
                        val = len(option_tokens) == 2 and option_tokens[1] or True
                        self.facts['dns']['options'][option_tokens[0]] = val

    def _get_mount_size_facts(self, mountpoint):
        size_total = None
        size_available = None
        try:
            statvfs_result = os.statvfs(mountpoint)
            size_total = statvfs_result.f_frsize * statvfs_result.f_blocks
            size_available = statvfs_result.f_frsize * (statvfs_result.f_bavail)
        except OSError:
            pass
        return size_total, size_available

    def get_python_facts(self):
        self.facts['python'] = {
            'version': {
                'major': sys.version_info[0],
                'minor': sys.version_info[1],
                'micro': sys.version_info[2],
                'releaselevel': sys.version_info[3],
                'serial': sys.version_info[4]
            },
            'version_info': list(sys.version_info),
            'executable': sys.executable,
            'has_sslcontext': HAS_SSLCONTEXT
        }
        try:
            self.facts['python']['type'] = sys.subversion[0]
        except AttributeError:
            try:
                self.facts['python']['type'] = sys.implementation.name
            except AttributeError:
                self.facts['python']['type'] = None


class Distribution(object):
    """
    This subclass of Facts fills the distribution, distribution_version and distribution_release variables

    To do so it checks the existence and content of typical files in /etc containing distribution information

    This is unit tested. Please extend the tests to cover all distributions if you have them available.
    """

    # every distribution name mentioned here, must have one of
    #  - allowempty == True
    #  - be listed in SEARCH_STRING
    #  - have a function get_distribution_DISTNAME implemented
    OSDIST_LIST = (
        {'path': '/etc/oracle-release', 'name': 'OracleLinux'},
        {'path': '/etc/slackware-version', 'name': 'Slackware'},
        {'path': '/etc/redhat-release', 'name': 'RedHat'},
        {'path': '/etc/vmware-release', 'name': 'VMwareESX', 'allowempty': True},
        {'path': '/etc/openwrt_release', 'name': 'OpenWrt'},
        {'path': '/etc/system-release', 'name': 'Amazon'},
        {'path': '/etc/alpine-release', 'name': 'Alpine'},
        {'path': '/etc/arch-release', 'name': 'Archlinux', 'allowempty': True},
        {'path': '/etc/os-release', 'name': 'SuSE'},
        {'path': '/etc/SuSE-release', 'name': 'SuSE'},
        {'path': '/etc/gentoo-release', 'name': 'Gentoo'},
        {'path': '/etc/os-release', 'name': 'Debian'},
        {'path': '/etc/lsb-release', 'name': 'Mandriva'},
        {'path': '/etc/altlinux-release', 'name': 'Altlinux'},
        {'path': '/etc/sourcemage-release', 'name': 'SMGL'},
        {'path': '/etc/os-release', 'name': 'NA'},
        {'path': '/etc/coreos/update.conf', 'name': 'Coreos'},
        {'path': '/usr/lib/os-release', 'name': 'ClearLinux'},
    )

    SEARCH_STRING = {
        'OracleLinux': 'Oracle Linux',
        'RedHat': 'Red Hat',
        'Altlinux': 'ALT Linux',
        'ClearLinux': 'Clear Linux',
        'SMGL': 'Source Mage GNU/Linux',
    }

    # A list with OS Family members
    OS_FAMILY = dict(
        RedHat = 'RedHat', Fedora = 'RedHat', CentOS = 'RedHat', Scientific = 'RedHat',
        SLC = 'RedHat', Ascendos = 'RedHat', CloudLinux = 'RedHat', PSBM = 'RedHat',
        OracleLinux = 'RedHat', OVS = 'RedHat', OEL = 'RedHat', Amazon = 'RedHat', Virtuozzo = 'RedHat',
        XenServer = 'RedHat', Ubuntu = 'Debian', Debian = 'Debian', Raspbian = 'Debian', Slackware = 'Slackware', SLES = 'Suse',
        SLED = 'Suse', openSUSE = 'Suse', openSUSE_Tumbleweed = 'Suse', SuSE = 'Suse', SLES_SAP = 'Suse', SUSE_LINUX = 'Suse', Gentoo = 'Gentoo',
        Funtoo = 'Gentoo', Archlinux = 'Archlinux', Manjaro = 'Archlinux', Mandriva = 'Mandrake', Mandrake = 'Mandrake', Altlinux = 'Altlinux', SMGL = 'SMGL',
        Solaris = 'Solaris', Nexenta = 'Solaris', OmniOS = 'Solaris', OpenIndiana = 'Solaris',
        SmartOS = 'Solaris', AIX = 'AIX', Alpine = 'Alpine', MacOSX = 'Darwin',
        FreeBSD = 'FreeBSD', HPUX = 'HP-UX', openSUSE_Leap = 'Suse', Neon = 'Debian'
    )

    def __init__(self, module):
        self.system = platform.system()
        self.facts = {}
        self.module = module

    def populate(self):
        self.get_distribution_facts()
        return self.facts

    def get_distribution_facts(self):
        # The platform module provides information about the running
        # system/distribution. Use this as a baseline and fix buggy systems
        # afterwards
        self.facts['distribution'] = self.system
        self.facts['distribution_release'] = platform.release()
        self.facts['distribution_version'] = platform.version()
        systems_implemented = ('AIX', 'HP-UX', 'Darwin', 'FreeBSD', 'OpenBSD', 'SunOS', 'DragonFly', 'NetBSD')

        self.facts['distribution'] = self.system

        if self.system in systems_implemented:
            cleanedname = self.system.replace('-','')
            distfunc = getattr(self, 'get_distribution_'+cleanedname)
            distfunc()
        elif self.system == 'Linux':
            # try to find out which linux distribution this is
            dist = platform.dist()
            self.facts['distribution'] = dist[0].capitalize() or 'NA'
            self.facts['distribution_version'] = dist[1] or 'NA'
            self.facts['distribution_major_version'] = dist[1].split('.')[0] or 'NA'
            self.facts['distribution_release'] = dist[2] or 'NA'
            # Try to handle the exceptions now ...
            # self.facts['distribution_debug'] = []
            for ddict in self.OSDIST_LIST:
                name = ddict['name']
                path = ddict['path']

                if not os.path.exists(path):
                    continue
                # if allowempty is set, we only check for file existance but not content
                if 'allowempty' in ddict and ddict['allowempty']:
                    self.facts['distribution'] = name
                    break
                if os.path.getsize(path) == 0:
                    continue

                data = get_file_content(path)
                if name in self.SEARCH_STRING:
                    # look for the distribution string in the data and replace according to RELEASE_NAME_MAP
                    # only the distribution name is set, the version is assumed to be correct from platform.dist()
                    if self.SEARCH_STRING[name] in data:
                        # this sets distribution=RedHat if 'Red Hat' shows up in data
                        self.facts['distribution'] = name
                    else:
                        # this sets distribution to what's in the data, e.g. CentOS, Scientific, ...
                        self.facts['distribution'] = data.split()[0]
                    break
                else:
                    # call a dedicated function for parsing the file content
                    try:
                        distfunc = getattr(self, 'get_distribution_' + name)
                        parsed = distfunc(name, data, path)
                        if parsed is None or parsed:
                            # distfunc return False if parsing failed
                            # break only if parsing was succesful
                            # otherwise continue with other distributions
                            break
                    except AttributeError:
                        # this should never happen, but if it does fail quitely and not with a traceback
                        pass



                    # to debug multiple matching release files, one can use:
                    # self.facts['distribution_debug'].append({path + ' ' + name:
                    #         (parsed,
                    #          self.facts['distribution'],
                    #          self.facts['distribution_version'],
                    #          self.facts['distribution_release'],
                    #          )})

        self.facts['os_family'] = self.facts['distribution']
        distro = self.facts['distribution'].replace(' ', '_')
        if distro in self.OS_FAMILY:
            self.facts['os_family'] = self.OS_FAMILY[distro]

    def get_distribution_AIX(self):
        rc, out, err = self.module.run_command("/usr/bin/oslevel")
        data = out.split('.')
        self.facts['distribution_version'] = data[0]
        self.facts['distribution_release'] = data[1]

    def get_distribution_HPUX(self):
        rc, out, err = self.module.run_command("/usr/sbin/swlist |egrep 'HPUX.*OE.*[AB].[0-9]+\.[0-9]+'", use_unsafe_shell=True)
        data = re.search('HPUX.*OE.*([AB].[0-9]+\.[0-9]+)\.([0-9]+).*', out)
        if data:
            self.facts['distribution_version'] = data.groups()[0]
            self.facts['distribution_release'] = data.groups()[1]

    def get_distribution_Darwin(self):
        self.facts['distribution'] = 'MacOSX'
        rc, out, err = self.module.run_command("/usr/bin/sw_vers -productVersion")
        data = out.split()[-1]
        self.facts['distribution_version'] = data

    def get_distribution_FreeBSD(self):
        self.facts['distribution_release'] = platform.release()
        data = re.search('(\d+)\.(\d+)-RELEASE.*', self.facts['distribution_release'])
        if data:
            self.facts['distribution_major_version'] = data.group(1)
            self.facts['distribution_version'] = '%s.%s' % (data.group(1), data.group(2))

    def get_distribution_OpenBSD(self):
        self.facts['distribution_version'] = platform.release()
        rc, out, err = self.module.run_command("/sbin/sysctl -n kern.version")
        match = re.match('OpenBSD\s[0-9]+.[0-9]+-(\S+)\s.*', out)
        if match:
            self.facts['distribution_release'] = match.groups()[0]
        else:
            self.facts['distribution_release'] = 'release'

    def get_distribution_DragonFly(self):
        pass

    def get_distribution_NetBSD(self):
        self.facts['distribution_major_version'] = self.facts['distribution_release'].split('.')[0]

    def get_distribution_Slackware(self, name, data, path):
        if 'Slackware' not in data:
            return False  # TODO: remove
        self.facts['distribution'] = name
        version = re.findall('\w+[.]\w+', data)
        if version:
            self.facts['distribution_version'] = version[0]

    def get_distribution_Amazon(self, name, data, path):
        if 'Amazon' not in data:
            return False  # TODO: remove
        self.facts['distribution'] = 'Amazon'
        self.facts['distribution_version'] = data.split()[-1]

    def get_distribution_OpenWrt(self, name, data, path):
        if 'OpenWrt' not in data:
            return False  # TODO: remove
        self.facts['distribution'] = name
        version = re.search('DISTRIB_RELEASE="(.*)"', data)
        if version:
            self.facts['distribution_version'] = version.groups()[0]
        release = re.search('DISTRIB_CODENAME="(.*)"', data)
        if release:
            self.facts['distribution_release'] = release.groups()[0]

    def get_distribution_Alpine(self, name, data, path):
        self.facts['distribution'] = 'Alpine'
        self.facts['distribution_version'] = data

    def get_distribution_SMGL(self):
        self.facts['distribution'] = 'Source Mage GNU/Linux'

    def get_distribution_SunOS(self):
        data = get_file_content('/etc/release').splitlines()[0]
        if 'Solaris' in data:
            ora_prefix = ''
            if 'Oracle Solaris' in data:
                data = data.replace('Oracle ','')
                ora_prefix = 'Oracle '
            self.facts['distribution'] = data.split()[0]
            self.facts['distribution_version'] = data.split()[1]
            self.facts['distribution_release'] = ora_prefix + data
            return

        uname_v = get_uname_version(self.module)
        distribution_version = None
        if 'SmartOS' in data:
            self.facts['distribution'] = 'SmartOS'
            if os.path.exists('/etc/product'):
                product_data = dict([l.split(': ', 1) for l in get_file_content('/etc/product').splitlines() if ': ' in l])
                if 'Image' in product_data:
                    distribution_version = product_data.get('Image').split()[-1]
        elif 'OpenIndiana' in data:
            self.facts['distribution'] = 'OpenIndiana'
        elif 'OmniOS' in data:
            self.facts['distribution'] = 'OmniOS'
            distribution_version = data.split()[-1]
        elif uname_v is not None and 'NexentaOS_' in uname_v:
            self.facts['distribution'] = 'Nexenta'
            distribution_version = data.split()[-1].lstrip('v')

        if self.facts['distribution'] in ('SmartOS', 'OpenIndiana', 'OmniOS', 'Nexenta'):
            self.facts['distribution_release'] = data.strip()
            if distribution_version is not None:
                self.facts['distribution_version'] = distribution_version
            elif uname_v is not None:
                self.facts['distribution_version'] = uname_v.splitlines()[0].strip()
            return

        return False  # TODO: remove if tested without this

    def get_distribution_SuSE(self, name, data, path):
        if 'suse' not in data.lower():
            return False  # TODO: remove if tested without this
        if path == '/etc/os-release':
            for line in data.splitlines():
                distribution = re.search("^NAME=(.*)", line)
                if distribution:
                    self.facts['distribution'] = distribution.group(1).strip('"')
                # example pattern are 13.04 13.0 13
                distribution_version = re.search('^VERSION_ID="?([0-9]+\.?[0-9]*)"?', line)
                if distribution_version:
                    self.facts['distribution_version'] = distribution_version.group(1)
                if 'open' in data.lower():
                    release = re.search('^VERSION_ID="?[0-9]+\.?([0-9]*)"?', line)
                    if release:
                        self.facts['distribution_release'] = release.groups()[0]
                elif 'enterprise' in data.lower() and 'VERSION_ID' in line:
                    # SLES doesn't got funny release names
                    release = re.search('^VERSION_ID="?[0-9]+\.?([0-9]*)"?', line)
                    if release.group(1):
                        release = release.group(1)
                    else:
                        release = "0"  # no minor number, so it is the first release
                    self.facts['distribution_release'] = release
        elif path == '/etc/SuSE-release':
            if 'open' in data.lower():
                data = data.splitlines()
                distdata = get_file_content(path).splitlines()[0]
                self.facts['distribution'] = distdata.split()[0]
                for line in data:
                    release = re.search('CODENAME *= *([^\n]+)', line)
                    if release:
                        self.facts['distribution_release'] = release.groups()[0].strip()
            elif 'enterprise' in data.lower():
                lines = data.splitlines()
                distribution = lines[0].split()[0]
                if "Server" in data:
                    self.facts['distribution'] = "SLES"
                elif "Desktop" in data:
                    self.facts['distribution'] = "SLED"
                for line in lines:
                    release = re.search('PATCHLEVEL = ([0-9]+)', line) # SLES doesn't got funny release names
                    if release:
                        self.facts['distribution_release'] = release.group(1)
                        self.facts['distribution_version'] = self.facts['distribution_version'] + '.' + release.group(1)

    def get_distribution_Debian(self, name, data, path):
        if 'Debian' in data or 'Raspbian' in data:
            self.facts['distribution'] = 'Debian'
            release = re.search("PRETTY_NAME=[^(]+ \(?([^)]+?)\)", data)
            if release:
                self.facts['distribution_release'] = release.groups()[0]

            # Last resort: try to find release from tzdata as either lsb is missing or this is very old debian
            if self.facts['distribution_release'] == 'NA' and 'Debian' in data:
                dpkg_cmd = self.module.get_bin_path('dpkg')
                if dpkg_cmd:
                    cmd = "%s --status tzdata|grep Provides|cut -f2 -d'-'" % dpkg_cmd
                    rc, out, err = self.module.run_command(cmd)
                    if rc == 0:
                        self.facts['distribution_release'] = out.strip()
        elif 'Ubuntu' in data:
            self.facts['distribution'] = 'Ubuntu'
            # nothing else to do, Ubuntu gets correct info from python functions
        else:
            return False

    def get_distribution_Mandriva(self, name, data, path):
        if 'Mandriva' in data:
            self.facts['distribution'] = 'Mandriva'
            version = re.search('DISTRIB_RELEASE="(.*)"', data)
            if version:
                self.facts['distribution_version'] = version.groups()[0]
            release = re.search('DISTRIB_CODENAME="(.*)"', data)
            if release:
                self.facts['distribution_release'] = release.groups()[0]
            self.facts['distribution'] = name
        else:
            return False

    def get_distribution_NA(self, name, data, path):
        for line in data.splitlines():
            distribution = re.search("^NAME=(.*)", line)
            if distribution and self.facts['distribution'] == 'NA':
                self.facts['distribution'] = distribution.group(1).strip('"')
            version = re.search("^VERSION=(.*)", line)
            if version and self.facts['distribution_version'] == 'NA':
                self.facts['distribution_version'] = version.group(1).strip('"')

    def get_distribution_Coreos(self, name, data, path):
        if self.facts['distribution'].lower() == 'coreos':
            if not data:
                # include fix from #15230, #15228
                return
            release = re.search("^GROUP=(.*)", data)
            if release:
                self.facts['distribution_release'] = release.group(1).strip('"')
        else:
            return False  # TODO: remove if tested without this


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


class HardwareCollector(WrapperCollector):
    facts_class = Hardware


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

    IPV6_SCOPE = {'0': 'global',
                  '10': 'host',
                  '20': 'link',
                  '40': 'admin',
                  '50': 'site',
                  '80': 'organization'}

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



class NetworkCollector(WrapperCollector):
    facts_class = Network


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


class VirtualCollector(WrapperCollector):
    facts_class = Virtual



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
#        module is passed in and self.module.misc_AnsibleModule_methods
#        are used, so hard to decouple.
# FIXME: split 'build list of fact subset names' from 'inst those classes' and 'run those classes'

# FIXME: make sure get_collector_names returns a useful ordering
#
# NOTE: This maps the gather_subset module param to a list of classes that provide them -akl
# def get_all_facts(module):
def get_collector_names(module, valid_subsets=None, gather_subset=None, gather_timeout=None):
    # Retrieve module parameters
    gather_subset = gather_subset or ['all']

    valid_subsets = valid_subsets or frozenset([])

    global GATHER_TIMEOUT
    GATHER_TIMEOUT = gather_timeout

    # Retrieve all facts elements
    additional_subsets = set()
    exclude_subsets = set()
    for subset in gather_subset:
        if subset == 'all':
            additional_subsets.update(valid_subsets)
            continue
        if subset.startswith('!'):
            subset = subset[1:]
            if subset == 'all':
                exclude_subsets.update(valid_subsets)
                continue
            exclude = True
        else:
            exclude = False

        if subset not in valid_subsets:
            raise TypeError("Bad subset '%s' given to Ansible. gather_subset options allowed: all, %s" % (subset, ", ".join(FACT_SUBSETS.keys())))

        if exclude:
            exclude_subsets.add(subset)
        else:
            additional_subsets.add(subset)

    if not additional_subsets:
        additional_subsets.update(valid_subsets)

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

    # FIXME/TODO: let Ohai/Facter class setup its own namespace
    # TODO: support letting class set a namespace and somehow letting user/playbook set it
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
    collector_names = get_collector_names(module)

    # FIXME: avoid having to pass in module until we populate
    all_facts = _get_all_facts(collector_names, module)

    return all_facts


class OhaiCollector(WrapperCollector):
    facts_class = Ohai


class FacterCollector(WrapperCollector):
    facts_class = Facter


class TempFactCollector(WrapperCollector):
    facts_class = Facts

    # kluge to compensate for 'Facts' adding 'ansible_' prefix itself
    def __init__(self, module, collectors=None, namespace=None):
        namespace = FactNamespace(namespace_name='temp_fact')
        super(TempFactCollector, self).__init__(module,
                                                collectors=collectors,
                                                namespace=namespace)


# Allowed fact subset for gather_subset options and what classes they use
# Note: have to define this at the bottom as it references classes defined earlier in this file -akl

# This map could be thought of as a fact name resolver, where we map
# some fact identifier (currently just the couple of gather_subset types) to the classes
# that provide it. -akl

FACT_SUBSETS = dict(
    facts=TempFactCollector,
    hardware=HardwareCollector,
    network=NetworkCollector,
    virtual=VirtualCollector,
    ohai=OhaiCollector,
    facter=FacterCollector,
)
VALID_SUBSETS = frozenset(FACT_SUBSETS.keys())


class NestedFactCollector(BaseFactCollector):
    '''collect returns a dict with the rest of the collection results under top_level_name'''
    def __init__(self, top_level_name, collectors=None, namespace=None):
        super(NestedFactCollector, self).__init__(collectors=collectors,
                                                  namespace=namespace)
        self.top_level_name = top_level_name

    def collect(self, collected_facts=None):
        collected = super(NestedFactCollector, self).collect(collected_facts=collected_facts)
        facts_dict = {self.top_level_name: collected}
        return facts_dict


class AnsibleFactCollector(NestedFactCollector):
    '''A FactCollector that returns results under 'ansible_facts' top level key.

       Has a 'from_gather_subset() constructor that populates collectors based on a
       gather_subset specifier.'''

    def __init__(self, collectors=None, namespace=None,
                 gather_subset=None):
        namespace = PrefixFactNamespace(namespace_name='ansible',
                                        prefix='ansible_')
        super(AnsibleFactCollector, self).__init__('ansible_facts',
                                                   collectors=collectors,
                                                   namespace=namespace)
        self.gather_subset = gather_subset

    @classmethod
    def from_gather_subset(cls, module, gather_subset=None, gather_timeout=None):
        # use gather_name etc to get the list of collectors
        collector_names = get_collector_names(module, valid_subsets=VALID_SUBSETS)

        collectors = []
        for collector_name in collector_names:
            collector_class = FACT_SUBSETS.get(collector_name, None)
            if not collector_class:
                continue
            # FIXME: hmm, kind of annoying... it would be useful to have a namespace instance
            #        here...
            collector = collector_class(module)
            collectors.append(collector)

        instance = cls(collectors=collectors,
                       gather_subset=gather_subset)
        return instance

    # FIXME: best place to set gather_subset?
    def collect(self, collected_facts=None):
        facts_dict = super(AnsibleFactCollector, self).collect(collected_facts=collected_facts)

        # FIXME: kluge
        facts_dict['ansible_facts']['ansible_gather_subset'] = self.gather_subset

        # FIXME: double kluge, seems like 'setup.py' should do this?
        #        also, this fact name doesnt follow namespace
        facts_dict['ansible_facts']['module_setup'] = True

        return facts_dict
