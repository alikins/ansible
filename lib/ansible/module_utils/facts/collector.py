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

from collections import defaultdict

import sys

from ansible.module_utils.facts import timeout


# TODO: BaseFactCollectors (plural) -> walks over list of collectors
#       BaseFactCollector (singular) -> returns a dict (collectors 'leaf' node)
#       and/or BaseFactCollectorNode etc
# TODO/MAYBE: static/cls method of fact_id/tag matching? Someway for the gather spec
#             matcher to handle semi dynamic names (like networks 'ansible_INTERFACENAME' facts)
#             so gather could match them
class BaseFactCollector:
    _fact_ids = set([])
    name = None

    def __init__(self, collectors=None, namespace=None):
        '''Base class for things that collect facts.

        'collectors' is an optional list of other FactCollectors for composing.'''
        self.collectors = collectors or []

        # self.namespace is a object with a 'transform' method that transforms
        # the name to indicate the namespace (ie, adds a prefix or suffix).
        self.namespace = namespace

        self.fact_ids = set([self.name])
        self.fact_ids.update(self._fact_ids)

    def _transform_name(self, key_name):
        if self.namespace:
            return self.namespace.transform(key_name)
        return key_name

    def _transform_dict_keys(self, fact_dict):
        '''update a dicts keys to use new names as transformed by self._transform_name'''

        # TODO: instead of changing fact_dict, just create a new dict and copy items into
        #       it with transformed key name.
        # TODO: rename... apply? apply_namespace?
        # TODO: this could also move items into a sub dict from the top level space
        #       (ie, from {'my_fact: ['sdf'], 'fact2': 1} -> {'ansible_facts': {'my_fact': ['sdf'], 'facts2': 1}}
        for old_key in list(fact_dict.keys()):
            new_key = self._transform_name(old_key)
            # pop the item by old_key and replace it using new_key
            fact_dict[new_key] = fact_dict.pop(old_key)
        return fact_dict

    # TODO/MAYBE: rename to 'collect' and add 'collect_without_namespace'
    # TODO: this could also add a top level direct with namespace (for ex, 'ansible_facts'
    #       for normal case, or 'whatever_some_other_facts' for others based on self.namespace
    def collect_with_namespace(self, module=None, collected_facts=None):
        # collect, then transform the key names if needed
        facts_dict = self.collect(module=module, collected_facts=collected_facts)
        if self.namespace:
            facts_dict = self._transform_dict_keys(facts_dict)
        return facts_dict

    def collect(self, module=None, collected_facts=None):
        '''do the fact collection

        'collected_facts' is a object (a dict, likely) that holds all previously
          facts. This is intended to be used if a FactCollector needs to reference
          another fact (for ex, the system arch) and should not be modified (usually).

          Returns a dict of facts.

          '''
        # abc or NotImplemented
        facts_dict = {}
        return facts_dict

    def collect_ids(self, collected_ids=None):
        '''Return a list of the fact ids this collector can collector.

        Used to allow gather_subset to address a single fact, potentially.

        atm, the ids are based on the final fact name sans 'ansible_' prefix.
        ie, 'env' for the 'ansible_env' fact.

        'collected_ids' is passed so a collector could alter the ids it returns
        based on what ids already are known. It should be considered read only.
        '''

        id_set = set([])
        for collector in self.collectors:
            info_set = set([])
            try:
                info_set = collector.collect_ids(collected_ids=collected_ids)
            except Exception as e:
                # FIXME: do fact collection exception warning/logging
                sys.stderr.write(repr(e))
                sys.stderr.write('\n')

                raise

            # NOTE: If we want complicated fact id merging (custom set ops?) this is where
            id_set.update(info_set)

        id_set.update(self.fact_ids)

        return id_set


# FIXME: make sure get_collector_names returns a useful ordering
# TODO: may need some form of AnsibleFactNameResolver
# NOTE: This maps the gather_subset module param to a list of classes that provide them -akl
def get_collector_names(valid_subsets=None,
                        minimal_gather_subset=None,
                        gather_subset=None,
                        aliases_map=None):
    '''return a set of FactCollector names based on gather_subset spec.

    gather_subset is a spec describing which facts to gather.
    valid_subsets is a frozenset of potential matches for gather_subset ('all', 'network') etc
    minimal_gather_subsets is a frozenset of matches to always use, even for gather_subset='!all'
    '''

    # Retrieve module parameters
    gather_subset = gather_subset or ['all']

    valid_subsets = valid_subsets or frozenset([])

    # if provided, minimal_gather_subset is always added, even after all negations
    minimal_gather_subset = minimal_gather_subset or frozenset([])

    aliases_map = aliases_map or defaultdict(set)

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

        if exclude:
            # include 'devices', 'dmi' etc for '!hardware'
            exclude_subsets.update(aliases_map.get(subset, set([])))
            exclude_subsets.add(subset)
        else:
            # NOTE: this only considers adding an unknown gather subsetup an error. Asking to
            #       exclude an unknown gather subset is ignored.
            if subset not in valid_subsets:
                raise TypeError("Bad subset '%s' given to Ansible. gather_subset options allowed: all, %s" %
                                (subset, ", ".join(sorted(valid_subsets))))

            additional_subsets.add(subset)

    if not additional_subsets:
        additional_subsets.update(valid_subsets)
    additional_subsets.difference_update(exclude_subsets)

    additional_subsets.update(minimal_gather_subset)

    return additional_subsets


def collector_classes_from_gather_subset(all_collector_classes=None,
                                         valid_subsets=None,
                                         minimal_gather_subset=None,
                                         gather_subset=None,
                                         gather_timeout=None):
    '''return a list of collector classes that match the args'''

    # use gather_name etc to get the list of collectors

    all_collector_classes = all_collector_classes or []

    minimal_gather_subset = minimal_gather_subset or frozenset([])

    # FIXME: decorator weirdness rel to timeout module scope
    gather_timeout = gather_timeout or timeout.DEFAULT_GATHER_TIMEOUT

    # tweak the modules GATHER_TIMEOUT
    timeout.GATHER_TIMEOUT = gather_timeout

    # valid_subsets = valid_subsets or cls.VALID_SUBSETS
    valid_subsets = valid_subsets or frozenset([])
    # import pprint
    # print('valid_subsets: %s' % pprint.pformat(valid_subsets))

    # build up the set of names we can use to identify facts collection subsets (a fact name, or a gather_subset name)
    id_collector_map = {}
    # all_collector_classes = cls.FACT_SUBSETS.values()

    # maps alias names like 'hardware' to the list of names that are part of hardware
    # like 'devices' and 'dmi'
    aliases_map = defaultdict(set)
    for all_collector_class in all_collector_classes:
        primary_name = all_collector_class.name
        id_collector_map[primary_name] = all_collector_class

        for fact_id in all_collector_class._fact_ids:
            id_collector_map[fact_id] = all_collector_class
            aliases_map[primary_name].add(fact_id)

    all_fact_subsets = {}
    # all_fact_subsets.update(cls.FACT_SUBSETS)
    # TODO: name collisions here? are there facts with the same name as a gather_subset (all, network, hardware, virtual, ohai, facter)
    all_fact_subsets.update(id_collector_map)

    # print('all_fact_subsets: %s' % pprint.pformat(all_fact_subsets))

    # TODO: if we want to be picky about ordering, will need to avoid squashing into dicts
    all_valid_subsets = frozenset(all_fact_subsets.keys())

    # print('all_valid_subsets: %s' % pprint.pformat(all_valid_subsets))

    # expand any fact_id/collectorname/gather_subset term ('all', 'env', etc) to the list of names that represents
    collector_names = get_collector_names(valid_subsets=all_valid_subsets,
                                          minimal_gather_subset=minimal_gather_subset,
                                          gather_subset=gather_subset,
                                          aliases_map=aliases_map)

    # print('collector_names: %s' % collector_names)
    seen_collector_classes = []
    selected_collector_classes = []
    for collector_name in collector_names:
        # TODO: fact_id -> [list, of, classes] instead of fact_id -> class 1:1 map?
        collector_class = all_fact_subsets.get(collector_name, None)
        if not collector_class:
            # FIXME: remove whens table
            raise Exception('collector_name: %s not found' % collector_name)
            continue

        if collector_class not in seen_collector_classes:
            selected_collector_classes.append(collector_class)
            seen_collector_classes.append(collector_class)

    return selected_collector_classes
