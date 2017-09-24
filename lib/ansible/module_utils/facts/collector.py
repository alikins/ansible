# This code is part of Ansible, but is an independent component.
# This particular file snippet, and this file snippet only, is BSD licensed.
# Modules you write using this snippet, which is embedded dynamically by Ansible
# still belong to the author of the module, and may assign their own license
# to the complete work.
#
# (c) 2017 Red Hat Inc.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
# USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from collections import defaultdict

import pprint
import platform

from ansible.module_utils.facts import timeout


class BaseFactCollector:
    _fact_ids = set()
    required_facts = set()
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

    @classmethod
    def platform_match(cls, platform_info):
        if platform_info.get('system', None) == cls._platform:
            return cls
        return None

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


def get_collector_names(valid_subsets=None,
                        minimal_gather_subset=None,
                        gather_subset=None,
                        aliases_map=None,
                        platform_info=None,
                        deps_map=None,
                        requires_map=None):
    '''return a set of FactCollector names based on gather_subset spec.

    gather_subset is a spec describing which facts to gather.
    valid_subsets is a frozenset of potential matches for gather_subset ('all', 'network') etc
    minimal_gather_subsets is a frozenset of matches to always use, even for gather_subset='!all'
    '''

    # Retrieve module parameters
    gather_subset = gather_subset or ['all']

    # the list of everything that 'all' expands to
    valid_subsets = valid_subsets or frozenset()

    # if provided, minimal_gather_subset is always added, even after all negations
    minimal_gather_subset = minimal_gather_subset or frozenset()

    aliases_map = aliases_map or defaultdict(set)

    deps_map = deps_map or defaultdict(set)
    requires_map = requires_map or defaultdict(list)

    # Retrieve all facts elements
    additional_subsets = set()
    exclude_subsets = set()

    pprint.pprint(('gather_subset', gather_subset))
    pprint.pprint(('minimal_gather_subset', minimal_gather_subset))
    # pprint.pprint(('deps_map', dict(deps_map)))
    pprint.pprint(('requiers_map', dict(requires_map)))
    # total always starts with the min set, then
    # adds of the additions in gather_subset, then
    # excludes all of the excludes, then add any explicitly
    # requested subsets.
    gather_subset_with_min = ['min']
    gather_subset_with_min.extend(gather_subset)

    # deps_map = build_dep_map_from_requires_map(requires_map, valid_subsets)
    pprint.pprint(('deps_map', dict(deps_map)))

    pprint.pprint(('aliases_map1', dict(aliases_map)))
    aliases_map['min'] = minimal_gather_subset
    aliases_map['all'] = valid_subsets
    pprint.pprint(('aliases_map2', dict(aliases_map)))
    #deps_subset = set()
    #for value in requires_map.values():
    #    deps_subset.update(set(value))
    deps_subset = []
    #for fact_name_that_requires, what_the_fact_requires_set in deps_map.items():
    #    deps_subset.extend(what_the_fact_requires_set)

    pprint.pprint(('deps_subset', deps_subset))
    # add one level of deps in
    pprint.pprint(('gather_subset_with_min before', gather_subset_with_min))

    gather_subset_with_min.extend(deps_subset)
    pprint.pprint(('gather_subset after', gather_subset_with_min))

    # subsets we mention in gather_subset explicitly, except for 'all'/'min'
    explicitly_added = set()

    #foo = expand_gather_spec_elements(gather_subset_with_min, aliases_map, valid_subsets)
    foo = expand_gather_spec(gather_subset_with_min, aliases_map, valid_subsets)

    gather_subset_with_min = []
    for subset in gather_subset_with_min:
        # expand_gather_spec_element(subset, aliases_map, valid_subsets)
        subset_id = subset
        if subset_id == 'min':
            additional_subsets.update(minimal_gather_subset)
            continue
        if subset_id == 'all':
            additional_subsets.update(valid_subsets)
            continue
        if subset_id.startswith('!'):
            subset = subset[1:]
            if subset == 'min':
                exclude_subsets.update(minimal_gather_subset)
                continue
            if subset == 'all':
                exclude_subsets.update(valid_subsets - minimal_gather_subset)
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

            print('\nsubset: %s' % subset)
            pprint.pprint(('deps_map', dict(deps_map)))
            to_add = aliases_map.get(subset, set([subset]))
            deps_required = deps_map.get(subset, set())
            print('to_add: %s subset: %s' % (to_add, subset))
            print('deps_required: %s subset: %s' % (deps_required, subset))
            explicitly_added.add(subset)
            additional_subsets.add(subset)
            # additional_subsets.update(to_add)
            additional_subsets.update(deps_required)


    additional_subsets, exclude_subsets, explicitly_added = foo
    if not additional_subsets:
        additional_subsets.update(valid_subsets)

    additional_subsets.difference_update(exclude_subsets - explicitly_added)

    pprint.pprint(('additiona_subsets', additional_subsets))
    return additional_subsets


def expand_gather_spec(gather_spec, aliases_map, valid_subsets):
    exclude_set = set()
    add_set = set()
    explicitly_added_set = set()

    for element in gather_spec:
        if element.startswith('!'):
            bare_element = element[1:]
            expanded_exclude_set = expand_gather_spec_element(bare_element, aliases_map, valid_subsets)
            exclude_set.update(expanded_exclude_set)
        else:
            explicitly_added_set.add(element)
            expanded_add_set = expand_gather_spec_element(element, aliases_map, valid_subsets)
            add_set.update(expanded_add_set)

    print('')
    pprint.pprint(('add_set', add_set))
    print('')
    pprint.pprint(('exclude_set', exclude_set))
    print('')
    pprint.pprint(('explicityly_added_set', explicitly_added_set))
    return add_set, exclude_set, explicitly_added_set


def expand_gather_spec_elements(gather_spec_elements, aliases_map, valid_subsets):
    expanded_specs = set()
    for gather_spec_element in gather_spec_elements:
        expanded_specs.update(expand_gather_spec_element(gather_spec_element, aliases_map, valid_subsets))

    print('SPECS expanded "%s" to: %s' % (pprint.pformat(gather_spec_elements),
                                          pprint.pformat(expanded_specs)))
    pprint.pprint(('expanded_specs2', expanded_specs))
    return expanded_specs

def expand_gather_spec_element(gather_spec_element, aliases_map, valid_subsets):
    expanded_specs = set()

    print('\ngather_spec_elemenet: %s' % gather_spec_element)

    possible_aliases = aliases_map.get(gather_spec_element, set())
    print('possible_aliases: %s' % possible_aliases)

    if possible_aliases:
        if possible_aliases.issuperset(set([gather_spec_element])):
            print('superset: %s ' % gather_spec_element)
            expanded_specs.add(gather_spec_element)
        else:
            print('expanding alias %s' % gather_spec_element)
            expanded_specs.update(expand_gather_spec_elements(possible_aliases, aliases_map, valid_subsets))

    else:
        print('no aliases for %s' % gather_spec_element)
        expanded_specs.add(gather_spec_element)
        # return expanded_specs

    print('EXPANDED "%s":' % (gather_spec_element))
    print('TO: %s' % pprint.pformat(expanded_specs))
    pprint.pprint(('expand_specs', expanded_specs))
    return expanded_specs

def find_collectors_for_platform(all_collector_classes, compat_platforms):
    found_collectors = []
    found_collectors_names = set()

    # start from specific platform, then try generic
    for compat_platform in compat_platforms:
        platform_match = None
        for all_collector_class in all_collector_classes:

            # ask the class if it is compatible with the platform info
            platform_match = all_collector_class.platform_match(compat_platform)

            if not platform_match:
                continue

            primary_name = all_collector_class.name

            if primary_name not in found_collectors_names:
                found_collectors.append(all_collector_class)
                found_collectors_names.add(all_collector_class.name)

    return found_collectors


def build_required_fact_ids(collectors_for_platform):
    required_facts = []
    for collector_class in collectors_for_platform:
        for fact_id in collector_class.required_facts:
            required_facts.append(fact_id)

    return required_facts


def build_fact_id_to_collector_map(collectors_for_platform):
    fact_id_to_collector_map = defaultdict(list)
    aliases_map = defaultdict(set)
    requires_map = defaultdict(list)

    for collector_class in collectors_for_platform:
        primary_name = collector_class.name

        fact_id_to_collector_map[primary_name].append(collector_class)

        for requires_fact_id in collector_class.required_facts:
            # print('requires_fact_id: %s' % requires_fact_id)
            requires_map[primary_name].append(requires_fact_id)

        for fact_id in collector_class._fact_ids:
            fact_id_to_collector_map[fact_id].append(collector_class)
            aliases_map[primary_name].add(fact_id)

    return fact_id_to_collector_map, aliases_map, requires_map


def build_dep_map_from_requires_map(requires_map, fact_id_to_collector_map):
    #deps_subset = []
    #for fact_name_that_requires, what_the_fact_requires_set in requires_map.items():
    #    deps_subset.extend(what_the_fact_requires_set)
    deps_subset = set()
    for value in requires_map.values():
        deps_subset.update(set(value))
    pprint.pprint(('deps_subset', deps_subset))
    pprint.pprint(('requires_map', dict(requires_map)))
    # map the required fact_id to the collector name that provides it. resolve the dep.
    dmap = defaultdict(set)

    for required_fact in deps_subset:
        solution_collectors = fact_id_to_collector_map.get(required_fact, None)
        if solution_collectors is None:
            print('could not find required_fact dep %s' % required_fact)
            continue
        dmap[required_fact].update(set([col.name for col in solution_collectors]))

    # TODO: should be able to do this within the main collector_class above
    #for collector_class in collectors_for_platform:
    #    for required_fact in deps_subset:
    #        if required_fact == collector_class.name:
    #            dmap[required_fact].add(collector_class.name)
    #        if required_fact in collector_class._fact_ids:
    #            dmap[required_fact].add(collector_class.name)

    pprint.pprint(('dmap', dict(dmap)))
    return dmap


def select_collector_classes(collector_names, all_fact_subsets, all_collector_classes):
    # TODO: can be a set()
    seen_collector_classes = []

    selected_collector_classes = []

    # pprint.pprint(('all_collector_classes', all_collector_classes))
    pprint.pprint(('collector_names', collector_names))
    for candidate_collector_class in all_collector_classes:
        candidate_collector_name = candidate_collector_class.name
        #print('candidate_collector_name: %s' % candidate_collector_name)
        #print('candidate_collector_class: %s' % candidate_collector_class)

        if candidate_collector_name not in collector_names:
            # print('Did not find collector for candidate_collector_name=%s' % candidate_collector_name)
            continue

        collector_classes = all_fact_subsets.get(candidate_collector_name, [])
        print('collector_classes: %s' % collector_classes)

        for collector_class in collector_classes:
            if collector_class not in seen_collector_classes:
                selected_collector_classes.append(collector_class)
                seen_collector_classes.append(collector_class)

    pprint.pprint(('selected_collector_classes', selected_collector_classes))
    return selected_collector_classes


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

    # maps alias names like 'hardware' to the list of names that are part of hardware
    # like 'devices' and 'dmi'
    aliases_map = defaultdict(set)

    compat_platforms = [platform_info, {'system': 'Generic'}]

    collectors_for_platform = find_collectors_for_platform(all_collector_classes, compat_platforms)

    # all_facts_subsets maps the subset name ('hardware') to the class that provides it.

    # TODO: name collisions here? are there facts with the same name as a gather_subset (all, network, hardware, virtual, ohai, facter)
    all_fact_subsets, aliases_map, requires_map = build_fact_id_to_collector_map(collectors_for_platform)
    deps_map = build_dep_map_from_requires_map(requires_map, all_fact_subsets)

    #pprint.pprint(('all_fact_subsets', dict(all_fact_subsets)))
    all_valid_subsets = frozenset(all_fact_subsets.keys())
    #pprint.pprint(('all_valid_subsets', all_valid_subsets))
    #pprint.pprint(('aliaes_map', dict(aliases_map)))
    pprint.pprint(('deps_map', dict(deps_map)))
    # ['lsb', 'selinux', 'system', 'machine', 'env', 'distribution'])
    # expand any fact_id/collectorname/gather_subset term ('all', 'env', etc) to the list of names that represents
    pprint.pprint(('gather_subset', gather_subset))
    collector_names = get_collector_names(valid_subsets=all_valid_subsets,
                                          minimal_gather_subset=minimal_gather_subset,
                                          gather_subset=gather_subset,
                                          aliases_map=aliases_map,
                                          platform_info=platform_info,
                                          requires_map=requires_map,
                                          deps_map=deps_map)

    pprint.pprint(('collector_names', collector_names))
    # pprint.pprint(('all_fact_subsets', dict(all_fact_subsets)))
    selected_collector_classes = select_collector_classes(collector_names,
                                                          all_fact_subsets,
                                                          all_collector_classes)

    required_facts = build_required_fact_ids(selected_collector_classes)
    pprint.pprint(('required_facts', required_facts))
    required_collectors = []
    if False:
    #if required_facts:
        # pprint.pprint(('all_valid_subsets', all_valid_subsets))
        solution_collector_names = get_collector_names(valid_subsets=all_valid_subsets,
                                                       minimal_gather_subset=minimal_gather_subset,
                                                       gather_subset=required_facts,
                                                       aliases_map=aliases_map,
                                                       platform_info=platform_info)
        pprint.pprint(('solution_collector_names', solution_collector_names))
        solution_collectors = select_collector_classes(solution_collector_names,
                                                       all_fact_subsets,
                                                       all_collector_classes)
        if solution_collectors:
            required_collectors.extend(solution_collectors)
        # for required_fact in required_facts:
        #     solution_collectors = all_fact_subsets.get(required_fact, None)

    pprint.pprint(('required_collectors', required_collectors))

    final = required_collectors + selected_collector_classes
    pprint.pprint(('final', final))

    return selected_collector_classes
