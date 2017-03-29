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
# TODO: replace Facts and subclasses with FactCollector subclasses
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import fnmatch
import platform

from ansible.module_utils.basic import get_all_subclasses
from ansible.module_utils.six import PY3

from ansible.module_utils.facts.collector import BaseFactCollector
from ansible.module_utils.facts.namespace import PrefixFactNamespace, FactNamespace
from ansible.module_utils.facts.facts import Facts
from ansible.module_utils.facts.ohai import Ohai
from ansible.module_utils.facts.facter import Facter

from ansible.module_utils.facts import virtual
from ansible.module_utils.facts import hardware
#from ansible.module_utils.facts import network

from ansible.module_utils.facts import timeout

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

# Allowed fact subset for gather_subset options and what classes they use
# Note: have to define this at the bottom as it references classes defined earlier in this file -akl

# This map could be thought of as a fact name resolver, where we map
# some fact identifier (currently just the couple of gather_subset types) to the classes
# that provide it. -akl


#    facts=TempFactCollector,
FACT_SUBSETS = dict(
    hardware=HardwareCollector,
    network=NetworkCollector,
    virtual=VirtualCollector,
    ohai=OhaiCollector,
    #    facter=FacterCollector,
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

        return facts_dict
