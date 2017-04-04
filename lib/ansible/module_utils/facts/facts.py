
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os
import platform
import re
import shlex
import socket

from ansible.module_utils.facts.distribution import Distribution
from ansible.module_utils.facts.utils import get_file_content


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

