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


from ansible.module_utils.facts.other.facter import FacterFactCollector
from ansible.module_utils.facts.other.ohai import OhaiFactCollector

from ansible.module_utils.facts.system.apparmor import ApparmorFactCollector
from ansible.module_utils.facts.system.caps import SystemCapabilitiesFactCollector
from ansible.module_utils.facts.system.cmdline import CmdLineFactCollector
from ansible.module_utils.facts.system.distribution import DistributionFactCollector
from ansible.module_utils.facts.system.date_time import DateTimeFactCollector
from ansible.module_utils.facts.system.env import EnvFactCollector
from ansible.module_utils.facts.system.dns import DnsFactCollector
from ansible.module_utils.facts.system.fips import FipsFactCollector
from ansible.module_utils.facts.system.local import LocalFactCollector
from ansible.module_utils.facts.system.lsb import LSBFactCollector
from ansible.module_utils.facts.system.pkg_mgr import PkgMgrFactCollector
from ansible.module_utils.facts.system.platform import PlatformFactCollector
from ansible.module_utils.facts.system.python import PythonFactCollector
from ansible.module_utils.facts.system.selinux import SelinuxFactCollector
from ansible.module_utils.facts.system.service_mgr import ServiceMgrFactCollector
from ansible.module_utils.facts.system.ssh_pub_keys import SshPubKeyFactCollector
from ansible.module_utils.facts.system.user import UserFactCollector

from ansible.module_utils.facts.hardware.base import HardwareCollector
from ansible.module_utils.facts.hardware.linux import LinuxHardwareCollector

from ansible.module_utils.facts.network.base import NetworkCollector

from ansible.module_utils.facts.virtual.base import VirtualCollector

# TODO: make config driven
collectors = [ApparmorFactCollector,
              CmdLineFactCollector,
              DateTimeFactCollector,
              DistributionFactCollector,
              DnsFactCollector,
              EnvFactCollector,
              FipsFactCollector,
              HardwareCollector,
              LinuxHardwareCollector,
              LocalFactCollector,
              LSBFactCollector,
              NetworkCollector,
              PkgMgrFactCollector,
              PlatformFactCollector,
              PythonFactCollector,
              SelinuxFactCollector,
              ServiceMgrFactCollector,
              SshPubKeyFactCollector,
              SystemCapabilitiesFactCollector,
              UserFactCollector,
              VirtualCollector]

external_collectors = [FacterFactCollector,
                       OhaiFactCollector]
