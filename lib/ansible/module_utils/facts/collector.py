
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


class BaseFactCollector:
    def __init__(self, collectors=None):
        '''Base class for things that collect facts.

        'collectors' is an optional list of other FactCollectors for composing.'''
        self.collectors = collectors or []

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
                import sys
                sys.stderr.write(e)
                sys.stderr.write('\n')
                pass

            # NOTE: If we want complicated fact dict merging, this is where it would hook in
            facts_dict.update(info_dict)

        return facts_dict
