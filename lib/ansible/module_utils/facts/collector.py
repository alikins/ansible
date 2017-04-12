from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import sys

from ansible.module_utils.facts.namespace import PrefixFactNamespace


# TODO: BaseFactCollectors (plural) -> walks over list of collectors
#       BaseFactCollector (singular) -> returns a dict (collectors 'leaf' node)
#       and/or BaseFactCollectorNode etc
# TODO/MAYBE: static/cls method of fact_id/tag matching? Someway for the gather spec
#             matcher to handle semi dynamic names (like networks 'ansible_INTERFACENAME' facts)
#             so gather could match them
class BaseFactCollector:
    _fact_ids = set([])

    def __init__(self, module=None, collectors=None, namespace=None):
        '''Base class for things that collect facts.

        'collectors' is an optional list of other FactCollectors for composing.'''
        self.collectors = collectors or []

        # self.namespace is a object with a 'transform' method that transforms
        # the name to indicate the namespace (ie, adds a prefix or suffix).
        self.namespace = namespace or PrefixFactNamespace(namespace_name='ansible',
                                                          prefix='ansible_')

        self.fact_ids = self._fact_ids or set([])

        # HEADSUP can be None...
        self.module = module

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
    def collect_with_namespace(self, collected_facts=None):
        # collect, then transform the key names if needed
        facts_dict = self.collect(collected_facts=collected_facts)
        if self.namespace:
            facts_dict = self._transform_dict_keys(facts_dict)
        return facts_dict

    def collect(self, collected_facts=None):
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


class CollectorMetaDataCollector(BaseFactCollector):
    '''Collector that provides a facts with the gather_subset metadata.'''

    _fact_ids = set(['gather_subset'])

    def __init__(self, module=None, collectors=None, namespace=None, gather_subset=None):
        super(CollectorMetaDataCollector, self).__init__(module, collectors, namespace)
        self.gather_subset = gather_subset

    def collect(self, collected_facts=None):
        return {'gather_subset': self.gather_subset}


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
