# Collect facts related to system service manager and init.
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

import os
import platform
import re

from ansible.module_utils._text import to_native

from ansible.module_utils.facts.utils import get_file_content
from ansible.module_utils.facts.collector import BaseFactCollector

# FIXME: compat module, if still needed
# The distutils module is not shipped with SUNWPython on Solaris.
# It's in the SUNWPython-devel package which also contains development files
# that don't belong on production boxes.  Since our Solaris code doesn't
# depend on LooseVersion, do not import it on Solaris.
if platform.system() != 'SunOS':
    from distutils.version import LooseVersion


# the fact ends up being 'service_mgr' so stick with that naming
class ServiceMgrFactCollector(BaseFactCollector):
    _fact_ids = set(['service_mgr'])

    def collect(self, collected_facts=None):
        # FIXME: no self
        self.facts = {}

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

        return self.facts
