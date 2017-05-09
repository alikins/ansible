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
# TODO: mv system/distribution.py to distribution/ and split into modules/classes
#       - could be tough, since parts of Distribution needs to run several methods/classes to
#         find the best fit
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
