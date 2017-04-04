
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os
import platform
import re
import shlex
import socket

from ansible.module_utils._text import to_native

from ansible.module_utils.facts.distribution import Distribution
from ansible.module_utils.facts.utils import get_file_content

# FIXME: compat module, if still needed
# The distutils module is not shipped with SUNWPython on Solaris.
# It's in the SUNWPython-devel package which also contains development files
# that don't belong on production boxes.  Since our Solaris code doesn't
# depend on LooseVersion, do not import it on Solaris.
if platform.system() != 'SunOS':
    from distutils.version import LooseVersion


# NOTE: This Facts class is mostly facts gathering implementation.
#       A FactsModel data structure class would be useful, especially
#       if we ever plan on documenting what various facts mean. This would
#       also be a good place to map fact label to fact class -akl
# NOTE: And a class similar to this one that composites a set or tree of
#       other fact gathering classes. Potentially driven by run time passing
#       of a list of the fact gather classes to include (finer grained gather_facts)
#       Or, possibly even a list or dict of fact labels 'ansible_lvm' for ex, that
#       the driver class would use to determine which fact gathering classes to load
class Facts:
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

    # A list of dicts.  If there is a platform with more than one
    # package manager, put the preferred one last.  If there is an
    # ansible module, use that as the value for the 'name' key.
    # NOTE: This is really constants. This dict is also used in a weird way by
    #       ansible.executor.action_write_locks that introduces a weird dep that could
    #       be avoided if this dict was elsewhere. -akl
    PKG_MGRS = [{'path': '/usr/bin/yum', 'name': 'yum'},
                {'path': '/usr/bin/dnf', 'name': 'dnf'},
                {'path': '/usr/bin/apt-get', 'name': 'apt'},
                {'path': '/usr/bin/zypper', 'name': 'zypper'},
                {'path': '/usr/sbin/urpmi', 'name': 'urpmi'},
                {'path': '/usr/bin/pacman', 'name': 'pacman'},
                {'path': '/bin/opkg', 'name': 'opkg'},
                {'path': '/usr/pkg/bin/pkgin', 'name': 'pkgin'},
                {'path': '/opt/local/bin/pkgin', 'name': 'pkgin'},
                {'path': '/opt/tools/bin/pkgin', 'name': 'pkgin'},
                {'path': '/opt/local/bin/port', 'name': 'macports'},
                {'path': '/usr/local/bin/brew', 'name': 'homebrew'},
                {'path': '/sbin/apk', 'name': 'apk'},
                {'path': '/usr/sbin/pkg', 'name': 'pkgng'},
                {'path': '/usr/sbin/swlist', 'name': 'SD-UX'},
                {'path': '/usr/bin/emerge', 'name': 'portage'},
                {'path': '/usr/sbin/pkgadd', 'name': 'svr4pkg'},
                {'path': '/usr/bin/pkg', 'name': 'pkg5'},
                {'path': '/usr/bin/xbps-install', 'name': 'xbps'},
                {'path': '/usr/local/sbin/pkg', 'name': 'pkgng'},
                {'path': '/usr/bin/swupd', 'name': 'swupd'},
                {'path': '/usr/sbin/sorcery', 'name': 'sorcery'},
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
        # FIXME: This is where Facts() should end, with the rest being left to some
        #        composed fact gathering classes.


        # TODO: Eventually, these should all get moved to populate().  But
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

        # TODO: de-dup fact_gatherers
        # for gatherer in fact_gatherers:
        #    data = gatherer.gather()
        #    self.facts.update(data)

        if load_on_init:
            self.get_platform_facts()
            # Example of returning new facts and updating self.facts with it -akl
            self.facts.update(Distribution(module).populate())
            self.get_cmdline()
            self.get_public_ssh_host_keys()
            # NOTE: lots of linux specific facts here.  A finer grained gather_subset could drive this. -akl
            self.get_pkg_mgr_facts()
            self.get_service_mgr_facts()

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

        # FIXME: as much as possible, avoid arch/platform bits here
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
                if os.path.exists(pkg['path']):
                    self.facts['pkg_mgr'] = pkg['name']

    # NOTE: This is definately complicated enough to warrant its own module or class (and tests) -akl
    def get_service_mgr_facts(self):
        # TODO: detect more custom init setups like bootscripts, dmd, s6, Epoch, etc
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
            # FIXME: find way to query executable, version matching is not ideal
            if LooseVersion(platform.mac_ver()[0]) >= LooseVersion('10.4'):
                self.facts['service_mgr'] = 'launchd'
            else:
                self.facts['service_mgr'] = 'systemstarter'
        elif 'BSD' in self.facts['system'] or self.facts['system'] in ['Bitrig', 'DragonFly']:
            # FIXME: we might want to break out to individual BSDs or 'rc'
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

    def is_systemd_managed(self):
        # tools must be installed
        if self.module.get_bin_path('systemctl'):

            # this should show if systemd is the boot init system, if checking init faild to mark as systemd
            # these mirror systemd's own sd_boot test http://www.freedesktop.org/software/systemd/man/sd_booted.html
            for canary in ["/run/systemd/system/", "/dev/.run/systemd/", "/dev/.systemd/"]:
                if os.path.exists(canary):
                    return True
        return False

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

