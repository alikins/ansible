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
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.module_utils.facts.collector import BaseFactCollector
from ansible.module_utils.facts.namespace import PrefixFactNamespace, FactNamespace
from ansible.module_utils.facts.facts import Facts
from ansible.module_utils.facts.ohai import Ohai
from ansible.module_utils.facts.facter import Facter

from ansible.module_utils.facts import virtual
from ansible.module_utils.facts import hardware
from ansible.module_utils.facts import network

# FIXME: sort out when we fix facts api exporting / empty this __init__
from ansible.module_utils.facts import timeout


# FIXME: share and/or remove
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

# TODO: remove these once we replace them
class WrapperCollector(BaseFactCollector):
    facts_class = None

    def __init__(self, module, collectors=None, namespace=None):
        super(WrapperCollector, self).__init__(collectors=collectors,
                                               namespace=namespace)
        self.module = module

    def collect(self, collected_facts=None):
        collected_facts = collected_facts or {}

        #print('self.facts_class: %s %s' % (self.facts_class, self.__class__.__name__))
        # WARNING: virtual.populate mutates cached_facts and returns a ref
        #          so for now, pass in a copy()
        facts_obj = self.facts_class(self.module, cached_facts=collected_facts.copy())

        #print('facts_obj: %s' % facts_obj)
        #print('self.facts_class.__subclasses__: %s' % self.facts_class.__subclasses__())
        facts_dict = facts_obj.populate()

        if self.namespace:
            facts_dict = self._transform_dict_keys(facts_dict)

        return facts_dict


class HardwareCollector(WrapperCollector):
    facts_class = hardware.base.Hardware


class NetworkCollector(WrapperCollector):
    facts_class = network.base.Network


class OhaiCollector(WrapperCollector):
    facts_class = Ohai


class FacterCollector(WrapperCollector):
    facts_class = Facter

    # TODO: wont need once we implement FacterCollector directly
    def __init__(self, module, collectors=None, namespace=None):
        namespace = PrefixFactNamespace(namespace_name='facter',
                                        prefix='facter_')
        super(FacterCollector, self).__init__(module,
                                              collectors=collectors,
                                              namespace=namespace)


class VirtualCollector(WrapperCollector):
    facts_class = virtual.base.Virtual


class TempFactCollector(WrapperCollector):
    facts_class = Facts

    # kluge to compensate for 'Facts' adding 'ansible_' prefix itself
    def __init__(self, module, collectors=None, namespace=None):
        namespace = FactNamespace(namespace_name='temp_fact')
        super(TempFactCollector, self).__init__(module,
                                                collectors=collectors,
                                                namespace=namespace)

    def collect(self, collected_facts=None):
        collected_facts = collected_facts or {}

        # WARNING: virtual.populate mutates cached_facts and returns a ref
        #          so for now, pass in a copy()
        facts_obj = self.facts_class(self.module, cached_facts=collected_facts.copy())

        facts_dict = facts_obj.populate()

        if self.namespace:
            facts_dict = self._transform_dict_keys(facts_dict)

        return facts_dict


# utility subclass of FactCollector
# TODO: mv to collector.py?
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



# FIXME: split 'build list of fact subset names' from 'inst those classes' and 'run those classes'
# FIXME: decouple from 'module'
# FIXME: make sure get_collector_names returns a useful ordering
# TODO: method of AnsibleFactCollector ?
# TODO: may need some form of AnsibleFactNameResolver
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

# This is the main entry point for facts.py. This is the only method from this module
# called directly from setup.py module.
# FIXME: This is coupled to AnsibleModule (it assumes module.params has keys 'gather_subset',
#        'gather_timeout', 'filter' instead of passing those are args or oblique ds
#        module is passed in and self.module.misc_AnsibleModule_methods
#        are used, so hard to decouple.

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
                # FIXME: remove whens table
                raise Exception('collector_name: %s not found' % collector_name)
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
