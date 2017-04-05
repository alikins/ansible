from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import sys


# TODO: BaseFactCollectors (plural) -> walks over list of collectors
#       BaseFactCollector (singular) -> returns a dict (collectors 'leaf' node)
#       and/or BaseFactCollectorNode etc
class BaseFactCollector:
    _fact_ids = set([])

    def __init__(self, module=None, collectors=None, namespace=None):
        '''Base class for things that collect facts.

        'collectors' is an optional list of other FactCollectors for composing.'''
        self.collectors = collectors or []

        # self.namespace is a object with a 'transform' method that transforms
        # the name to indicate the namespace (ie, adds a prefix or suffix).
        self.namespace = namespace

        self.fact_ids = self._fact_ids or set([])

        # HEADSUP can be None...
        self.module = module

    def _transform_name(self, key_name):
        if self.namespace:
            return self.namespace.transform(key_name)
        return key_name

    def _transform_dict_keys(self, fact_dict):
        '''update a dicts keys to use new names as transformed by self._transform_name'''

        for old_key in fact_dict.keys():
            new_key = self._transform_name(old_key)
            # pop the item by old_key and replace it using new_key
            fact_dict[new_key] = fact_dict.pop(old_key)
        return fact_dict

    def collect(self, collected_facts=None):
        '''do the fact collection

        'collected_facts' is a object (a dict, likely) that holds all previously
          facts. This is intended to be used if a FactCollector needs to reference
          another fact (for ex, the system arch) and should not be modified (usually).

          Returns a dict of facts.

          '''
        facts_dict = {}
        for collector in self.collectors:
            info_dict = {}
            try:
                info_dict = collector.collect(collected_facts=collected_facts)
            except Exception as e:
                # FIXME: do fact collection exception warning/logging
                sys.stderr.write(repr(e))
                sys.stderr.write('\n')

                raise

            # NOTE: If we want complicated fact dict merging, this is where it would hook in
            facts_dict.update(info_dict)

        # FIXME: maybe deserves a subclass
        # transform all key names, or ex 'foo-baz-blip' -> 'ansible_foo_baz_blip'
        if self.namespace:
            facts_dict = self._transform_dict_keys(facts_dict)

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


class WrapperCollector(BaseFactCollector):
    facts_class = None

    def __init__(self, module=None, collectors=None, namespace=None):
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

        if self.namespace:
            facts_dict = self._transform_dict_keys(facts_dict)

        return facts_dict
