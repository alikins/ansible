
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

# almost gone now...


# NOTE: This Facts class is mostly facts gathering implementation.
#       A FactsModel data structure class would be useful, especially
#       if we ever plan on documenting what various facts mean. This would
#       also be a good place to map fact label to fact class -akl
# NOTE: And a class similar to this one that composites a set or tree of
#       other fact gathering classes. Potentially driven by run time passing
#       of a list of the fact gather classes to include (finer grained gather_facts)
#       Or, possibly even a list or dict of fact labels 'ansible_lvm' for ex, that
#       the driver class would use to determine which fact gathering classes to load
class Facts:
    """
    This class should only attempt to populate those facts that
    are mostly generic to all systems.  This includes platform facts,
    service facts (e.g. ssh keys or selinux), and distribution facts.
    Anything that requires extensive code or may have more than one
    possible implementation to establish facts for a given topic should
    subclass Facts.
    """

    # For the most part, we assume that platform.dist() will tell the truth.
    # This is the fallback to handle unknowns or exceptions

    # NOTE: load_on_init is changed for ohai/facter classes. Ideally, all facts
    #       would be load_on_init=False and this could be removed. -akl
    # NOTE: cached_facts seems like a misnomer. Seems to be used more like an accumulator -akl
    def __init__(self, module, load_on_init=True, cached_facts=None):

        self.module = module
        if not cached_facts:
            self.facts = {}
        else:
            self.facts = cached_facts

        # FIXME: tmp workaround
        self.collected_facts = cached_facts
        # FIXME: This is where Facts() should end, with the rest being left to some
        #        composed fact gathering classes.

        # TODO: Eventually, these should all get moved to populate().  But
        # some of the values are currently being used by other subclasses (for
        # instance, os_family and distribution).  Have to sort out what to do
        # about those first.
        # NOTE: if the various gathering methods take a arg that is the 'accumulated' facts
        #       then this wouldn't need to happen on init. There would still be some ordering required
        #       though. If the gather methods return a dict of the new facts, then the accumulated facts
        #       can be read-only to avoid manipulating it by side effect. -akl

        # TODO: to avoid hard coding this, something like
        # list so we can imply some order suggestions
        # fact_providers is a map or lookup of fact label -> fact gather class/inst that provides it
        #  - likely will also involve a fact plugin lookup
        #    ( could fact providing modules include the list of fact labels in their metadata? so we could determine
        #      with plugin to load before we actually load and inst it?)
        # fact_gatherers = []
        # for requested_fact in requested_facts:
        #    fact_gatherer = self.fact_providers.get('requested_fact', None)
        #    if not fact_gatherer:
        #        continue
        #    fact_gatherers.append(fact_gatherer)

        # TODO: de-dup fact_gatherers
        # for gatherer in fact_gatherers:
        #    data = gatherer.gather()
        #    self.facts.update(data)

    def populate(self):
        return self.facts
