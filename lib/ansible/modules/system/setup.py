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
import sys

# import module snippets
from ansible.module_utils.basic import AnsibleModule

# TODO: mv to facts/base.py ?
from ansible.module_utils import facts

from ansible.module_utils.facts.collector import BaseFactCollector, CollectorMetaDataCollector

from ansible.module_utils.facts import default_collectors


# This is the main entry point for setup.py facts.py.
# FIXME: This is coupled to AnsibleModule (it assumes module.params has keys 'gather_subset',
#        'gather_timeout', 'filter' instead of passing those are args or oblique ds
#        module is passed in and self.module.misc_AnsibleModule_methods
#        are used, so hard to decouple.

class AnsibleFactCollector(BaseFactCollector):
    '''A FactCollector that returns results under 'ansible_facts' top level key.

       Has a 'from_gather_subset() constructor that populates collectors based on a
       gather_subset specifier.'''

    def __init__(self, collectors=None, namespace=None):
        # namespace = PrefixFactNamespace(namespace_name='ansible',
        #                                prefix='ansible_')

        super(AnsibleFactCollector, self).__init__(collectors=collectors,
                                                   namespace=namespace)

    def collect(self, module=None, collected_facts=None):
        collected_facts = collected_facts or {}

        facts_dict = {}
        facts_dict['ansible_facts'] = {}

        for collector in self.collectors:
            info_dict = {}

            # shallow copy of the accumulated collected facts to pass to each collector
            # for reference.
            collected_facts.update(facts_dict['ansible_facts'].copy())

            try:

                # print('\n about to collect %s for module %s' % (collector.__class__.__name__, module))
                # Note: this collects with namespaces, so collected_facts also includes namespaces
                info_dict = collector.collect_with_namespace(module=module,
                                                             collected_facts=collected_facts)
                # print('\nINFO_DICT(%s): %s' % (collector.__class__.__name__, pprint.pformat(info_dict)))
            except Exception as e:
                # FIXME: do fact collection exception warning/logging
                sys.stderr.write(repr(e))
                sys.stderr.write('\n')

                raise

            # NOTE: If we want complicated fact dict merging, this is where it would hook in
            facts_dict['ansible_facts'].update(info_dict)

        # FIXME: double kluge, seems like 'setup.py' should do this?
        #        (so we can distinquish facts collected by running setup.py and facts potentially
        #         collected by invoking a FactsCollector() directly ?)
        #        also, this fact name doesnt follow namespace
        # FIXME/TODO: add collector?
        facts_dict['ansible_facts']['module_setup'] = True

        # TODO: this may be best place to apply fact 'filters' as well. They
        #       are currently ignored -akl
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
    minimal_gather_subset = frozenset(['apparmor', 'caps', 'cmdline', 'date_time',
                                       'distribution', 'dns', 'env', 'fips', 'local', 'lsb',
                                       'pkg_mgr', 'platform', 'python', 'selinux',
                                       'service_mgr', 'ssh_pub_keys', 'user'])

    all_collector_classes = default_collectors.collectors

    collector_classes = \
        facts.collector_classes_from_gather_subset(
            all_collector_classes=all_collector_classes,
            minimal_gather_subset=minimal_gather_subset,
            gather_subset=gather_subset,
            gather_timeout=gather_timeout)

    # print('collector_classes: %s' % pprint.pformat(collector_classes))

    collectors = []
    for collector_class in collector_classes:
        collector_obj = collector_class()
        collectors.append(collector_obj)

    # Add a collector that knows what gather_subset we used so it it can provide a fact
    collector_meta_data_collector = \
        CollectorMetaDataCollector(gather_subset=gather_subset)
    collectors.append(collector_meta_data_collector)

    # print('collectors: %s' % pprint.pformat(collectors))

    fact_collector = \
        AnsibleFactCollector(collectors=collectors)

    facts_dict = fact_collector.collect(module=module)

    module.exit_json(**facts_dict)


if __name__ == '__main__':
    main()
