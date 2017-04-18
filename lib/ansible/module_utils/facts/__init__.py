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
# TODO: general pep8/style clean ups
# TODO: tiny bit of abstractions for run_command() and get_file_content() use
#       ie, code like self.module.run_command('some_netinfo_tool
#                                             --someoption')[1].splitlines[][0].split()[1] ->
#          netinfo_output = self._netinfo_provider()
#          netinfo_data = self._netinfo_parse(netinfo_output)
#       why?
#          - much much easier to test
# TODO: replace Facts and subclasses with FactCollector subclasses
# TODO: empty out this __init__
# TODO: hook up fact filtering again
# TODO: mv imports of collectors to a common loader module
#        - offers a place to use a fact_collector plugin loader
#        - can be shared by remote client side module and controller side ansiballz builder
# TODO: mv collectors from system,hardware,network,virtual to collectors/
#       - one file collectors (say, env.py or cmdline.py) can live in collectors/
#       - collectors with interdeps (Network or Hardware for ex, may live in collectors/network/)
#       - or could flatten to collectors/linux_hardware.py, collectors/sunos_hardware.py etc
# IDEA: gather 'tags' in addition to gather 'ids'
#       - ids identify _a_ fact collector uniquely
#       - tags can identify multiple facts collectors
#       - gather tag for 'hardware' for all 'hardware' tagged collectors
#       - id could be a namespaced tag (ie, 'id:ansible.module_utils.facts.system.env.EnvFactCollector')
#       - arch/system/dist could also be namespaced tags
#           - 'system:Linux'
#           - 'arch: x86_64'
# IDEA: once Collector api is used, it wouldn't be that hard to add a collect_iter()
#       that would return a generator that would yield facts
#       ... top level Collector could 'emit' facts as found (or changed) which would
#           make it possibly to watch a fact (or attach a callback to be called when changed)
#            (more useful for controller side _info than client/remote _facts though given the
#             controler->remote interface is not really async or non-blocking at all)
# IDEA: parallel/threaded/multiprocess fact collection
#       ... the collect_iter() approach above would make that easier, but even for blocking
#           fact collection, a given Collector could choose to run its sub collectors concurrently.
#           Might improve latency/total time to collect facts, since fact collection is currently very
#           serial with lots of things that block and can be slow (more or less every run_command() for
#           ex). In theory fact collection should be entirely 'read-only' (and with Collector api, with
#           very few side effects) so might be a reasonable place for some concurency.
# TODO: possibly rename FooCollector to just FooFacts, esp once the existing Facts() class is barebones/unneeded
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.module_utils.facts import timeout


# FIXME: split 'build list of fact subset names' from 'inst those classes' and 'run those classes'
# FIXME: decouple from 'module'
# FIXME: make sure get_collector_names returns a useful ordering
# TODO: may need some form of AnsibleFactNameResolver
# NOTE: This maps the gather_subset module param to a list of classes that provide them -akl
# def get_all_facts(module):
def get_collector_names(valid_subsets=None,
                        minimal_gather_subset=None,
                        gather_subset=None):
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

    for all_collector_class in all_collector_classes:
        for fact_id in all_collector_class._fact_ids:
            id_collector_map[fact_id] = all_collector_class

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
                                          gather_subset=gather_subset)

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
