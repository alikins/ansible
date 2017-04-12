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
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import re
import socket
import platform

from ansible.module_utils.facts.utils import get_file_content

from ansible.module_utils.facts.collector import BaseFactCollector

# i86pc is a Solaris and derivatives-ism
SOLARIS_I86_RE_PATTERN = r'i([3456]86|86pc)'
solaris_i86_re = re.compile(SOLARIS_I86_RE_PATTERN)


class PlatformFactCollector(BaseFactCollector):
    _fact_ids = set(['platform',
                     'system',
                     'kernel',
                     'machine',
                     'python_version',
                     'machine_id'])

    def collect(self, module=None, collected_facts=None):
        platform_facts = {}
        # Platform
        # platform.system() can be Linux, Darwin, Java, or Windows
        # NOTE: pretty much every method should create a new dict (or whatever the FactsModel ds is)
        #       and return it and let main Facts() class combine them. -akl
        # NOTE: a facts.Platform() class that wraps all of this would make mocking/testing easier -akl
        platform_facts['system'] = platform.system()
        platform_facts['kernel'] = platform.release()
        platform_facts['machine'] = platform.machine()

        # move to system/python.py?
        platform_facts['python_version'] = platform.python_version()

        # NOTE: not platform at all... -akl
        platform_facts['fqdn'] = socket.getfqdn()
        platform_facts['hostname'] = platform.node().split('.')[0]
        platform_facts['nodename'] = platform.node()

        # NOTE: not platform -akl
        platform_facts['domain'] = '.'.join(platform_facts['fqdn'].split('.')[1:])

        arch_bits = platform.architecture()[0]

        # NOTE: this could be split into arch and/or system specific classes/methods -akl
        platform_facts['userspace_bits'] = arch_bits.replace('bit', '')
        if platform_facts['machine'] == 'x86_64':
            platform_facts['architecture'] = platform_facts['machine']
            if platform_facts['userspace_bits'] == '64':
                platform_facts['userspace_architecture'] = 'x86_64'
            elif platform_facts['userspace_bits'] == '32':
                platform_facts['userspace_architecture'] = 'i386'
        elif solaris_i86_re.search(platform_facts['machine']):
            platform_facts['architecture'] = 'i386'
            if platform_facts['userspace_bits'] == '64':
                platform_facts['userspace_architecture'] = 'x86_64'
            elif platform_facts['userspace_bits'] == '32':
                platform_facts['userspace_architecture'] = 'i386'
        else:
            platform_facts['architecture'] = platform_facts['machine']

        # FIXME: as much as possible, avoid arch/platform bits here
        # NOTE: -> aix_platform = AixPlatform(); facts_dict.update(aix_platform) -akl
        if platform_facts['system'] == 'AIX':
            # Attempt to use getconf to figure out architecture
            # fall back to bootinfo if needed
            # NOTE: in general, the various 'get_bin_path(); data=run_command()' could be split to methods/classes for providing info
            #        one to get the raw data, another to parse it into useful chunks
            #        then both are easy to mock for testing -akl
            getconf_bin = module.get_bin_path('getconf')
            if getconf_bin:
                rc, out, err = module.run_command([getconf_bin, 'MACHINE_ARCHITECTURE'])
                data = out.splitlines()
                platform_facts['architecture'] = data[0]
            else:
                bootinfo_bin = module.get_bin_path('bootinfo')
                rc, out, err = module.run_command([bootinfo_bin, '-p'])
                data = out.splitlines()
                platform_facts['architecture'] = data[0]
        elif platform_facts['system'] == 'OpenBSD':
            platform_facts['architecture'] = platform.uname()[5]

        # NOTE: the same comment about get_bin_path() above also applies to fetching file content
        #       attempting to mock a file open and read is a PITA, but mocking read_dbus_machine_id() is easy to mock -akl
        machine_id = get_file_content("/var/lib/dbus/machine-id") or get_file_content("/etc/machine-id")
        if machine_id:
            machine_id = machine_id.splitlines()[0]
            platform_facts["machine_id"] = machine_id

        return platform_facts
