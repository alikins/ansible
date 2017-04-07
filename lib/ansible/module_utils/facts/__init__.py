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
# TODO: general pep8/style clean ups
# TODO: tiny bit of abstractions for run_command() and get_file_content() use
#       ie, code like self.module.run_command('some_netinfo_tool
#                                             --someoption')[1].splitlines[][0].split()[1] ->
#          netinfo_output = self._netinfo_provider()
#          netinfo_data = self._netinfo_parse(netinfo_output)
#       why?
#          - much much easier to test
# TODO: replace Facts and subclasses with FactCollector subclasses
# TODO: empty out this __init__
# TODO: hook up fact filtering again
# IDEA: once Collector api is used, it wouldn't be that hard to add a collect_iter()
#       that would return a generator that would yield facts
#       ... top level Collector could 'emit' facts as found (or changed) which would
#           make it possibly to watch a fact (or attach a callback to be called when changed)
#            (more useful for controller side _info than client/remote _facts though given the
#             controler->remote interface is not really async or non-blocking at all)
# IDEA: parallel/threaded/multiprocess fact collection
#       ... the collect_iter() approach above would make that easier, but even for blocking
#           fact collection, a given Collector could choose to run its sub collectors concurrently.
#           Might improve latency/total time to collect facts, since fact collection is currently very
#           serial with lots of things that block and can be slow (more or less every run_command() for
#           ex). In theory fact collection should be entirely 'read-only' (and with Collector api, with
#           very few side effects) so might be a reasonable place for some concurency.
# TODO: possibly rename FooCollector to just FooFacts, esp once the existing Facts() class is barebones/unneeded
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import sys

from ansible.module_utils.facts.collector import BaseFactCollector
from ansible.module_utils.facts.facts import Facts
from ansible.module_utils.facts.ohai import Ohai

from ansible.module_utils.facts.namespace import PrefixFactNamespace
from ansible.module_utils.facts import timeout

from ansible.module_utils.facts import hardware
from ansible.module_utils.facts import network

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
    facts_class = hardware.base.Hardware


class NetworkCollector(WrapperCollector):
    facts_class = network.base.Network


class OhaiCollector(WrapperCollector):
    facts_class = Ohai


class TempFactCollector(WrapperCollector):
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


# FIXME: split 'build list of fact subset names' from 'inst those classes' and 'run those classes'
# FIXME: decouple from 'module'
# FIXME: make sure get_collector_names returns a useful ordering
# TODO: method of AnsibleFactCollector ?
# TODO: may need some form of AnsibleFactNameResolver
# NOTE: This maps the gather_subset module param to a list of classes that provide them -akl
# def get_all_facts(module):
def get_collector_names(module, valid_subsets=None,
                        minimal_gather_subset=None,
                        gather_subset=None):
    # Retrieve module parameters
    gather_subset = gather_subset or ['all']

    valid_subsets = valid_subsets or frozenset([])

    # if provided, minimal_gather_subset is always added, even after all negations
    minimal_gather_subset = minimal_gather_subset or frozenset([])

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
            raise TypeError("Bad subset '%s' given to Ansible. gather_subset options allowed: all, %s" % (subset, ", ".join(valid_subsets)))

        if exclude:
            exclude_subsets.add(subset)
        else:
            additional_subsets.add(subset)

    if not additional_subsets:
        additional_subsets.update(valid_subsets)
    additional_subsets.difference_update(exclude_subsets)

    additional_subsets.update(minimal_gather_subset)

    return additional_subsets


# Allowed fact subset for gather_subset options and what classes they use
# Note: have to define this at the bottom as it references classes defined earlier in this file -akl

# This map could be thought of as a fact name resolver, where we map
# some fact identifier (currently just the couple of gather_subset types) to the classes
# that provide it. -akl

# TODO: build this up semi dynamically

# This is the main entry point for facts.py. This is the only method from this module
# called directly from setup.py module.
# FIXME: This is coupled to AnsibleModule (it assumes module.params has keys 'gather_subset',
#        'gather_timeout', 'filter' instead of passing those are args or oblique ds
#        module is passed in and self.module.misc_AnsibleModule_methods
#        are used, so hard to decouple.

class AnsibleFactCollector(BaseFactCollector):
    '''A FactCollector that returns results under 'ansible_facts' top level key.

       Has a 'from_gather_subset() constructor that populates collectors based on a
       gather_subset specifier.'''

    # All the gather subsets aliases/nicks/shortnames
    FACT_SUBSETS = dict(
        facts=TempFactCollector,
        # system=SystemFactCollector,
        apparmor=ApparmorFactCollector,
        caps=SystemCapabilitiesFactCollector,
        date_time=DateTimeFactCollector,
        env=EnvFactCollector,
        dns=DnsFactCollector,
        fips=FipsFactCollector,
        local=LocalFactCollector,
        lsb=LSBFactCollector,
        pkg_mgr=PkgMgrFactCollector,
        python=PythonFactCollector,
        selinux=SelinuxFactCollector,
        service_mgr=ServiceMgrFactCollector,
        user=UserFactCollector,
        hardware=HardwareCollector,
        network=NetworkCollector,
        virtual=VirtualCollector,
        ohai=OhaiCollector,
        facter=FacterFactCollector,
    )
    VALID_SUBSETS = frozenset(FACT_SUBSETS.keys())

    def __init__(self, collectors=None, namespace=None,
                 gather_subset=None):
        # namespace = PrefixFactNamespace(namespace_name='ansible',
        #                                prefix='ansible_')
        self.VALID_SUBSETS = frozenset(self.FACT_SUBSETS.keys())

        super(AnsibleFactCollector, self).__init__('ansible_facts',
                                                   collectors=collectors,
                                                   namespace=namespace)
        self.gather_subset = gather_subset

    @classmethod
    def from_gather_subset(cls, module,
                           valid_subsets=None,
                           minimal_gather_subset=None,
                           gather_subset=None,
                           gather_timeout=None):
        # use gather_name etc to get the list of collectors

        minimal_gather_subset = minimal_gather_subset or frozenset([])

        # FIXME: decorator weirdness rel to timeout module scope
        gather_timeout = gather_timeout or timeout.DEFAULT_GATHER_TIMEOUT

        # tweak the modules GATHER_TIMEOUT
        timeout.GATHER_TIMEOUT = gather_timeout

        valid_subsets = valid_subsets or cls.VALID_SUBSETS

        # build up the set of names we can use to identify facts collection subsets (a fact name, or a gather_subset name)
        id_collector_map = {}
        all_collector_classes = cls.FACT_SUBSETS.values()

        for all_collector_class in all_collector_classes:
            for fact_id in all_collector_class._fact_ids:
                id_collector_map[fact_id] = all_collector_class

        all_fact_subsets = {}
        all_fact_subsets.update(cls.FACT_SUBSETS)
        # TODO: name collisions here? are there facts with the same name as a gather_subset (all, network, hardware, virtual, ohai, facter)
        all_fact_subsets.update(id_collector_map)

        all_valid_subsets = frozenset(all_fact_subsets.keys())

        # expand any fact_id/collectorname/gather_subset term ('all', 'env', etc) to the list of names that represents
        collector_names = get_collector_names(module,
                                              valid_subsets=all_valid_subsets,
                                              minimal_gather_subset=minimal_gather_subset,
                                              gather_subset=gather_subset)

#        print('collector_names: %s' % collector_names)
        collectors = []
        seen_collector_classes = []
        for collector_name in collector_names:
            collector_class = all_fact_subsets.get(collector_name, None)
            if not collector_class:
                # FIXME: remove whens table
                raise Exception('collector_name: %s not found' % collector_name)
                continue

            if collector_class not in seen_collector_classes:
                collector = collector_class(module)
                collectors.append(collector)
                seen_collector_classes.append(collector_class)

        # import pprint
        # print('collectors: %s' % pprint.pformat(collectors))
        instance = cls(collectors=collectors,
                       gather_subset=gather_subset)
        return instance

    # FIXME: best place to set gather_subset?
    def collect(self, collected_facts=None):
        facts_dict = {}
        facts_dict['ansible_facts'] = {}

        for collector in self.collectors:
            info_dict = {}
            try:
                # Note: this collects with namespaces
                info_dict = collector.collect_with_namespace(collected_facts=collected_facts)
            except Exception as e:
                # FIXME: do fact collection exception warning/logging
                sys.stderr.write(repr(e))
                sys.stderr.write('\n')

                raise

            # NOTE: If we want complicated fact dict merging, this is where it would hook in
            facts_dict['ansible_facts'].update(info_dict)

        # FIXME: kluge, not really sure where the best place to do this would be.
        facts_dict['ansible_facts']['ansible_gather_subset'] = self.gather_subset

        # FIXME: double kluge, seems like 'setup.py' should do this?
        #        (so we can distinquish facts collected by running setup.py and facts potentially
        #         collected by invoking a FactsCollector() directly ?)
        #        also, this fact name doesnt follow namespace
        facts_dict['ansible_facts']['module_setup'] = True

        # TODO: this may be best place to apply fact 'filters' as well. They
        #       are currently ignored -akl
        return facts_dict
