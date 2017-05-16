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

import platform
import sys

from ansible.module_utils.facts import timeout


# TODO/MAYBE: static/cls method of fact_id/tag matching? Someway for the gather spec
#             matcher to handle semi dynamic names (like networks 'ansible_INTERFACENAME' facts)
#             so gather could match them
class BaseFactCollector:
    _fact_ids = set()
    _platform = 'Generic'
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

        for old_key in list(fact_dict.keys()):
            new_key = self._transform_name(old_key)
            # pop the item by old_key and replace it using new_key
            fact_dict[new_key] = fact_dict.pop(old_key)
        return fact_dict

    # TODO/MAYBE: rename to 'collect' and add 'collect_without_namespace'
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

        id_set = set()
        for collector in self.collectors:
            info_set = set()
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


import pprint


def pp(obj, msg=None):
    if msg:
        sys.stderr.write('%s: ' % msg)
    sys.stderr.write('%s\n' % pprint.pformat(obj))
    return



def get_collector_names(valid_subsets=None,
                        minimal_gather_subset=None,
                        gather_subset=None,
                        aliases_map=None,
                        platform_info=None):
    '''return a set of FactCollector names based on gather_subset spec.

    gather_subset is a spec describing which facts to gather.
    valid_subsets is a frozenset of potential matches for gather_subset ('all', 'network') etc
    minimal_gather_subsets is a frozenset of matches to always use, even for gather_subset='!all'
    '''

    # Retrieve module parameters
    gather_subset = gather_subset or ['all']

    valid_subsets = valid_subsets or frozenset()

    # if provided, minimal_gather_subset is always added, even after all negations
    minimal_gather_subset = minimal_gather_subset or frozenset()

    aliases_map = aliases_map or defaultdict(set)


#    pp(platform_info, msg='platform_info:')

    # Retrieve all facts elements
    additional_subsets = set()
    exclude_subsets = set()

#    pp(valid_subsets, msg='get names valid_subsets:')

    #subset_ids = [x[0] for x in valid_subsets]

    #pp(subset_ids, msg='subset_ids')

    for subset in gather_subset:
        subset_id = subset

#        pp(subset, msg='subset name match:')
#        pp(subset_id, msg='subset_id')
        if subset_id == 'all':
            additional_subsets.update(valid_subsets)
            continue
        if subset_id.startswith('!'):
            subset = subset[1:]
            if subset == 'all':
                exclude_subsets.update(valid_subsets)
                continue
            exclude = True
        else:
            exclude = False

        if exclude:
            # include 'devices', 'dmi' etc for '!hardware'
            exclude_subsets.update(aliases_map.get(subset, set()))
            exclude_subsets.add(subset)
        else:
            # NOTE: this only considers adding an unknown gather subsetup an error. Asking to
            #       exclude an unknown gather subset is ignored.
            if subset_id not in valid_subsets:
                raise TypeError("Bad subset '%s' given to Ansible. gather_subset options allowed: all, %s" %
                                (subset, ", ".join(sorted(valid_subsets))))

            additional_subsets.add(subset)

#            platform_subset = find_platform_subset(valid_subsets, platform_info)
#            additional_subsets.add(platform_subset)

#    pp(exclude_subsets, msg='exclude_subset:')
#    pp(additional_subsets, msg='additional_subsets:')
    if not additional_subsets:
        additional_subsets.update(valid_subsets)
    additional_subsets.difference_update(exclude_subsets)

    additional_subsets.update(minimal_gather_subset)

#    pp(additional_subsets, msg='additional_subsets:')
    return additional_subsets


def find_platform_matches(collector_class, this_platform):
    matches = []
    pp(collector_class, msg='\n collector_class')

    pp(collector_class._platform, msg='collector class platform_ids:')

    # Map platform_info to collector fact info, if either isnt specified they are 'Generic'.
    # if neither is specified, both are generic and should match all
    platform_matchers = set()

    # FIXME: PlatformMatch class
    # platform_matchers.update(collector_class._platform_ids)

    # FIXME: PlatformMatch class
    platform_matchers.add(collector_class._platform)

    pp(platform_matchers, msg='platform_matchers:')

    this_platform_matchers = set()
    this_platform_matchers.add(this_platform)

    # pp(platform_match, msg='platform_match:')

    # pp(this_platform, msg='this_platform:')
    pp(this_platform_matchers, msg='this_platform_matchers:')

    # FIXME: PlatformMatcher or at least a method
    matches = this_platform_matchers.intersection(platform_matchers)

    pp(matches, msg='platform specific matches:')
    return matches


def collector_classes_from_gather_subset(all_collector_classes=None,
                                         valid_subsets=None,
                                         minimal_gather_subset=None,
                                         gather_subset=None,
                                         gather_timeout=None,
                                         platform_info=None):
    '''return a list of collector classes that match the args'''

    # use gather_name etc to get the list of collectors

    all_collector_classes = all_collector_classes or []

    minimal_gather_subset = minimal_gather_subset or frozenset()

    platform_info = platform_info or {'system': platform.system()}

    gather_timeout = gather_timeout or timeout.DEFAULT_GATHER_TIMEOUT

    # tweak the modules GATHER_TIMEOUT
    timeout.GATHER_TIMEOUT = gather_timeout

    valid_subsets = valid_subsets or frozenset()

    # build up the set of names we can use to identify facts collection subsets (a fact name, or a gather_subset name)
    id_collector_map = defaultdict(list)

    pp(platform_info, msg='c_g_f_gs platform_info:')

    this_platform = platform_info.get('system', 'Generic')
    pp(this_platform, msg='this_platform:')

    # maps alias names like 'hardware' to the list of names that are part of hardware
    # like 'devices' and 'dmi'
    aliases_map = defaultdict(set)
    # FIXME:  check all the platform specific classes first, then try the generic ones

    compat_platforms = [this_platform, 'Generic']

    # start from specific platform, then try generic
    for compat_platform in compat_platforms:
        for all_collector_class in all_collector_classes:
            matches = []

            matches = find_platform_matches(collector_class=all_collector_class,
                                            this_platform=compat_platform)

        for platform_match in matches:
            pp(platform_match, msg='platform_match (all_collector_class=%s): ' % all_collector_class)
            primary_name = all_collector_class.name
            # id_collector_map[(primary_name, platform_match)] = all_collector_class
            id_collector_map[primary_name].append(all_collector_class)

            for fact_id in all_collector_class._fact_ids:

                # id_collector_map[(fact_id, platform_match)] = all_collector_class
                id_collector_map[fact_id].append(all_collector_class)
                aliases_map[primary_name].add((fact_id, platform_match))

        if matches:
            pp(matches, msg='\n Found compat collector=%s platform=%s' % (all_collector_class,
                                                                          compat_platform))
            break

    # all_facts_subsets maps the subset name ('hardware') to the class that provides it.
    # TODO: should it map to the plural classes that provide it?

    pp(id_collector_map, msg='id_collector_map:')

    all_fact_subsets = {}
    # TODO: name collisions here? are there facts with the same name as a gather_subset (all, network, hardware, virtual, ohai, facter)
    all_fact_subsets.update(id_collector_map)

    pp(all_fact_subsets, msg='all_fact_subsets:')

    all_valid_subsets = frozenset(all_fact_subsets.keys())

    # expand any fact_id/collectorname/gather_subset term ('all', 'env', etc) to the list of names that represents
    collector_names = get_collector_names(valid_subsets=all_valid_subsets,
                                          minimal_gather_subset=minimal_gather_subset,
                                          gather_subset=gather_subset,
                                          aliases_map=aliases_map,
                                          platform_info=platform_info)

#    platform_collectors = get_platform_collector_names()

    # TODO: can be a set()
    seen_collector_classes = []

    selected_collector_classes = []

    pp(all_fact_subsets, msg='all_facts_subsets:')
    pp(collector_names, msg='collector_names:')

    for collector_name in collector_names:
        collector_classes = all_fact_subsets.get(collector_name, None)
        if not collector_classes:
            # FIXME: remove when stable
            raise Exception('collector_name: %s  not found' % repr((collector_name, this_platform)))

        for collector_class in collector_classes:
            if collector_class not in seen_collector_classes:
                selected_collector_classes.append(collector_class)
                seen_collector_classes.append(collector_class)

    return selected_collector_classes
