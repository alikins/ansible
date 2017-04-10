#!/usr/bin/python
# -*- coding: utf-8 -*-

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

ANSIBLE_METADATA = {'metadata_version': '1.0',
                    'status': ['stableinterface'],
                    'supported_by': 'core'}


DOCUMENTATION = '''
---
module: setup
version_added: historical
short_description: Gathers facts about remote hosts
options:
    gather_subset:
        version_added: "2.1"
        description:
            - "if supplied, restrict the additional facts collected to the given subset.
              Possible values: all, hardware, network, virtual, ohai, and
              facter Can specify a list of values to specify a larger subset.
              Values can also be used with an initial C(!) to specify that
              that specific subset should not be collected.  For instance:
              !hardware, !network, !virtual, !ohai, !facter.  Note that a few
              facts are always collected.  Use the filter parameter if you do
              not want to display those."
        required: false
        default: 'all'
    gather_timeout:
        version_added: "2.2"
        description:
            - "Set the default timeout in seconds for individual fact gathering"
        required: false
        default: 10
    filter:
        version_added: "1.1"
        description:
            - if supplied, only return facts that match this shell-style (fnmatch) wildcard.
        required: false
        default: '*'
    fact_path:
        version_added: "1.3"
        description:
            - path used for local ansible facts (*.fact) - files in this dir
              will be run (if executable) and their results be added to ansible_local facts
              if a file is not executable it is read. Check notes for Windows options. (from 2.1 on)
              File/results format can be json or ini-format
        required: false
        default: '/etc/ansible/facts.d'
description:
     - This module is automatically called by playbooks to gather useful
       variables about remote hosts that can be used in playbooks. It can also be
       executed directly by C(/usr/bin/ansible) to check what variables are
       available to a host. Ansible provides many I(facts) about the system,
       automatically.
notes:
    - More ansible facts will be added with successive releases. If I(facter) or
      I(ohai) are installed, variables from these programs will also be snapshotted
      into the JSON file for usage in templating. These variables are prefixed
      with C(facter_) and C(ohai_) so it's easy to tell their source. All variables are
      bubbled up to the caller. Using the ansible facts and choosing to not
      install I(facter) and I(ohai) means you can avoid Ruby-dependencies on your
      remote systems. (See also M(facter) and M(ohai).)
    - The filter option filters only the first level subkey below ansible_facts.
    - If the target host is Windows, you will not currently have the ability to use
      C(filter) as this is provided by a simpler implementation of the module.
    - If the target host is Windows you can now use C(fact_path). Make sure that this path
      exists on the target host. Files in this path MUST be PowerShell scripts (``*.ps1``) and
      their output must be formattable in JSON (Ansible will take care of this). Test the
      output of your scripts.
      This option was added in Ansible 2.1.
author:
    - "Ansible Core Team"
    - "Michael DeHaan"
    - "David O'Brien @david_obrien davidobrien1985"
'''

EXAMPLES = """
# Display facts from all hosts and store them indexed by I(hostname) at C(/tmp/facts).
# ansible all -m setup --tree /tmp/facts

# Display only facts regarding memory found by ansible on all hosts and output them.
# ansible all -m setup -a 'filter=ansible_*_mb'

# Display only facts returned by facter.
# ansible all -m setup -a 'filter=facter_*'

# Display only facts about certain interfaces.
# ansible all -m setup -a 'filter=ansible_eth[0-2]'

# Restrict additional gathered facts to network and virtual.
# ansible all -m setup -a 'gather_subset=network,virtual'

# Do not call puppet facter or ohai even if present.
# ansible all -m setup -a 'gather_subset=!facter,!ohai'

# Only collect the minimum amount of facts:
# ansible all -m setup -a 'gather_subset=!all'

# Display facts from Windows hosts with custom facts stored in C(C:\\custom_facts).
# ansible windows -m setup -a "fact_path='c:\\custom_facts'"
"""

# import module snippets
from ansible.module_utils.basic import AnsibleModule

from ansible.module_utils.facts import AnsibleFactCollector

from ansible.module_utils.facts.facts import Facts

from ansible.module_utils.facts import hardware
from ansible.module_utils.facts import network

from ansible.module_utils.facts.ohai import Ohai

from ansible.module_utils.facts.collector import BaseFactCollector

from ansible.module_utils.facts.other.facter import FacterFactCollector

from ansible.module_utils.facts.system.apparmor import ApparmorFactCollector
from ansible.module_utils.facts.system.caps import SystemCapabilitiesFactCollector
from ansible.module_utils.facts.system.date_time import DateTimeFactCollector
from ansible.module_utils.facts.system.env import EnvFactCollector
from ansible.module_utils.facts.system.dns import DnsFactCollector
from ansible.module_utils.facts.system.fips import FipsFactCollector
from ansible.module_utils.facts.system.local import LocalFactCollector
from ansible.module_utils.facts.system.lsb import LSBFactCollector
from ansible.module_utils.facts.system.pkg_mgr import PkgMgrFactCollector
from ansible.module_utils.facts.system.python import PythonFactCollector
from ansible.module_utils.facts.system.selinux import SelinuxFactCollector
from ansible.module_utils.facts.system.service_mgr import ServiceMgrFactCollector
from ansible.module_utils.facts.system.user import UserFactCollector

from ansible.module_utils.facts.virtual.base import VirtualCollector

from ansible.module_utils.facts.namespace import PrefixFactNamespace


# TODO: remove these once we replace them
class WrapperCollector(BaseFactCollector):
    facts_class = None

    def __init__(self, module, collectors=None, namespace=None):
        super(WrapperCollector, self).__init__(collectors=collectors,
                                               namespace=namespace)
        self.module = module

    def collect(self, collected_facts=None):
        collected_facts = collected_facts or {}

        # print('self.facts_class: %s %s' % (self.facts_class, self.__class__.__name__))
        # WARNING: virtual.populate mutates cached_facts and returns a ref
        #          so for now, pass in a copy()
        facts_obj = self.facts_class(self.module, cached_facts=collected_facts.copy())

        # print('facts_obj: %s' % facts_obj)
        # print('self.facts_class.__subclasses__: %s' % self.facts_class.__subclasses__())
        facts_dict = facts_obj.populate()

        return facts_dict


class HardwareCollector(WrapperCollector):
    _fact_ids = set(['hardware'])
    facts_class = hardware.base.Hardware


class NetworkCollector(WrapperCollector):
    _fact_ids = set(['network'])
    facts_class = network.base.Network


class OhaiCollector(WrapperCollector):
    _fact_ids = set(['ohai'])
    facts_class = Ohai


class TempFactCollector(WrapperCollector):
    _fact_ids = set(['facts'])

    facts_class = Facts

    # kluge to compensate for 'Facts' adding 'ansible_' prefix itself
    def __init__(self, module, collectors=None, namespace=None):
        namespace = PrefixFactNamespace(namespace_name='temp_fact',
                                        prefix='ansible_')
        super(TempFactCollector, self).__init__(module,
                                                collectors=collectors,
                                                namespace=namespace)

    def collect(self, collected_facts=None):
        collected_facts = collected_facts or {}

        # WARNING: virtual.populate mutates cached_facts and returns a ref
        #          so for now, pass in a copy()
        facts_obj = self.facts_class(self.module, cached_facts=collected_facts.copy())

        facts_dict = facts_obj.populate()

        return facts_dict


def main():
    module = AnsibleModule(
        argument_spec=dict(
            gather_subset=dict(default=["all"], required=False, type='list'),
            gather_timeout=dict(default=10, required=False, type='int'),
            filter=dict(default="*", required=False),
            fact_path=dict(default='/etc/ansible/facts.d', required=False, type='path'),
        ),
        supports_check_mode=True,
    )

    gather_subset = module.params['gather_subset']
    gather_timeout = module.params['gather_timeout']

    # TODO: this mimics existing behavior where gather_subset=["!all"] actually means
    #       to collect nothing except for the below list
    # TODO: decide what '!all' means, I lean towards making it mean none, but likely needs
    #       some tweaking on how gather_subset operations are performed
    minimal_gather_subset = frozenset(['apparmor', 'caps', 'date_time', 'dns',
                                       'env', 'facts', 'fips', 'local', 'lsb',
                                       'pkg_mgr', 'python', 'selinux', 'service_mgr',
                                       'user'])

    # TODO: the ordering here is more or less arbitrary, except that it mimics the
    #       order facts.py used to collect these in.
    all_collector_classes = [TempFactCollector,
                             SelinuxFactCollector,
                             ApparmorFactCollector,
                             SystemCapabilitiesFactCollector,
                             FipsFactCollector,
                             PkgMgrFactCollector,
                             ServiceMgrFactCollector,
                             LSBFactCollector,
                             DateTimeFactCollector,
                             UserFactCollector,
                             LocalFactCollector,
                             EnvFactCollector,
                             DnsFactCollector,
                             PythonFactCollector,
                             HardwareCollector,
                             NetworkCollector,
                             VirtualCollector,
                             OhaiCollector,
                             FacterFactCollector]

    fact_collector = AnsibleFactCollector.from_gather_subset(module,
                                                             all_collector_classes=all_collector_classes,
                                                             minimal_gather_subset=minimal_gather_subset,
                                                             gather_subset=gather_subset,
                                                             gather_timeout=gather_timeout)

    facts_dict = {'gather_subset': gather_subset}

    data = fact_collector.collect()

    facts_dict.update(data)

    module.exit_json(**facts_dict)


if __name__ == '__main__':
    main()
