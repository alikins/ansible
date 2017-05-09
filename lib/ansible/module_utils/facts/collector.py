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

import sys


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
