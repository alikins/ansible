
class BaseFactCollector:
    def __init__(self, collectors=None, collected_facts=None):
        '''Base class for things that collect facts.

        'collectors' is an optional list of other FactCollectors for composing.
        'collected_facts' is a object (a dict, likely) that holds all previously
          facts. This is intended to be used if a FactCollector needs to reference
          another fact (for ex, the system arch) and should not be modified (usually).'''
        self.collectors = collectors or []
        self.collected_facts = collected_facts or {}

    def collect(self):
        facts_dict = {}
        for collector in self.collectors:
            info_dict = {}
            try:
                info_dict = collector.collect()
            except Exception as e:
                # FIXME: do fact collection exception warning/logging
                print(e)
                pass

            # NOTE: If we want complicated fact dict merging, this is where it would hook in
            facts_dict.update(info_dict)

        return facts_dict
