# unit tests for ansible/module_utils/facts/__init__.py
# -*- coding: utf-8 -*-
#
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
#

# Make coding more python3-ish
from __future__ import (absolute_import, division)
__metaclass__ = type

import re

# for testing
from ansible.compat.tests import unittest
from ansible.compat.tests.mock import Mock

from ansible.module_utils import facts
from ansible.module_utils.facts.collector import CollectorMetaDataCollector

from ansible.module_utils.facts.other.facter import FacterFactCollector
from ansible.module_utils.facts.other.ohai import OhaiFactCollector

from ansible.module_utils.facts.system.apparmor import ApparmorFactCollector
from ansible.module_utils.facts.system.caps import SystemCapabilitiesFactCollector
from ansible.module_utils.facts.system.date_time import DateTimeFactCollector
from ansible.module_utils.facts.system.env import EnvFactCollector
from ansible.module_utils.facts.system.distribution import DistributionFactCollector
from ansible.module_utils.facts.system.dns import DnsFactCollector
from ansible.module_utils.facts.system.fips import FipsFactCollector
from ansible.module_utils.facts.system.local import LocalFactCollector
from ansible.module_utils.facts.system.lsb import LSBFactCollector
from ansible.module_utils.facts.system.pkg_mgr import PkgMgrFactCollector
from ansible.module_utils.facts.system.platform import PlatformFactCollector
from ansible.module_utils.facts.system.python import PythonFactCollector
from ansible.module_utils.facts.system.selinux import SelinuxFactCollector
from ansible.module_utils.facts.system.service_mgr import ServiceMgrFactCollector
from ansible.module_utils.facts.system.user import UserFactCollector

# from ansible.module_utils.facts.hardware.base import HardwareCollector
from ansible.module_utils.facts.network.base import NetworkCollector
from ansible.module_utils.facts.virtual.base import VirtualCollector

# module under test
from ansible.modules.system import setup


ALL_COLLECTOR_CLASSES = \
    [PlatformFactCollector,
     DistributionFactCollector,
     SelinuxFactCollector,
     ApparmorFactCollector,
     SystemCapabilitiesFactCollector,
     FipsFactCollector,
     PkgMgrFactCollector,
     ServiceMgrFactCollector,
     LSBFactCollector,
     DateTimeFactCollector,
     UserFactCollector,
     LocalFactCollector,
     EnvFactCollector,
     DnsFactCollector,
     PythonFactCollector,
     # FIXME: re-enable when hardware doesnt Hardware() doesnt munge self.facts
     #                         HardwareCollector
     NetworkCollector,
     VirtualCollector,
     OhaiFactCollector,
     FacterFactCollector]


def mock_module(gather_subset=None):
    if gather_subset is None:
        gather_subset = ['all', '!facter', '!ohai']
    mock_module = Mock()
    mock_module.params = {'gather_subset': gather_subset,
                          'gather_timeout': 5,
                          'filter': '*'}
    mock_module.get_bin_path = Mock(return_value=None)
    return mock_module


def _collectors(module,
                all_collector_classes=None,
                minimal_gather_subset=None):
    gather_subset = module.params.get('gather_subset')
    if all_collector_classes is None:
        all_collector_classes = ALL_COLLECTOR_CLASSES
    if minimal_gather_subset is None:
        minimal_gather_subset = frozenset([])

    collector_classes = \
        facts.collector_classes_from_gather_subset(all_collector_classes=all_collector_classes,
                                                   minimal_gather_subset=minimal_gather_subset,
                                                   gather_subset=gather_subset)

    collectors = []
    for collector_class in collector_classes:
        collector_obj = collector_class()
        collectors.append(collector_obj)

    # Add a collector that knows what gather_subset we used so it it can provide a fact
    collector_meta_data_collector = \
        CollectorMetaDataCollector(gather_subset=gather_subset)
    collectors.append(collector_meta_data_collector)

    return collectors


# FIXME: this is brute force, but hopefully enough to get some refactoring to make facts testable
class TestInPlace(unittest.TestCase):
    def _mock_module(self, gather_subset=None):
        return mock_module(gather_subset=gather_subset)

    def _collectors(self, module,
                    all_collector_classes=None,
                    minimal_gather_subset=None):
        return _collectors(module=module,
                           all_collector_classes=all_collector_classes,
                           minimal_gather_subset=minimal_gather_subset)

    def test(self):
        gather_subset = ['all']
        mock_module = self._mock_module(gather_subset=gather_subset)
        all_collector_classes = [EnvFactCollector]
        collectors = self._collectors(mock_module,
                                      all_collector_classes=all_collector_classes)

        fact_collector = \
            setup.AnsibleFactCollector(collectors=collectors)

        res = fact_collector.collect(module=mock_module)
        self.assertIsInstance(res, dict)
        self.assertIn('ansible_facts', res)
        import pprint
        pprint.pprint(res)
        self.assertIsInstance(res['ansible_facts'], dict)
        self.assertIn('ansible_env', res['ansible_facts'])
        self.assertIn('ansible_gather_subset', res['ansible_facts'])
        self.assertEqual(res['ansible_facts']['ansible_gather_subset'], ['all'])

    def test1(self):
        gather_subset = ['all']
        mock_module = self._mock_module(gather_subset=gather_subset)
        collectors = self._collectors(mock_module)

        fact_collector = \
            setup.AnsibleFactCollector(collectors=collectors)

        res = fact_collector.collect(module=mock_module)
        self.assertIsInstance(res, dict)
        self.assertIn('ansible_facts', res)
        # just assert it's not almost empty
        # with run_command and get_file_content mock, many facts are empty, like network
        self.assertGreater(len(res['ansible_facts']), 20)

    def test_empty_all_collector_classes(self):
        mock_module = self._mock_module()
        all_collector_classes = []

        collectors = self._collectors(mock_module,
                                      all_collector_classes=all_collector_classes)

        fact_collector = \
            setup.AnsibleFactCollector(collectors=collectors)

        res = fact_collector.collect()
        self.assertIsInstance(res, dict)
        self.assertIn('ansible_facts', res)
        # just assert it's not almost empty
        self.assertLess(len(res['ansible_facts']), 3)

    def test_collect_ids(self):
        mock_module = self._mock_module()
        collectors = self._collectors(mock_module)

        fact_collector = \
            setup.AnsibleFactCollector(collectors=collectors)

        res = fact_collector.collect_ids()

        self.assertIsInstance(res, set)

    def test_collect_ids_minimal(self):
        mock_module = self._mock_module(gather_subset=['!all'])

        collectors = self._collectors(mock_module)

        fact_collector = \
            setup.AnsibleFactCollector(collectors=collectors)

        res = fact_collector.collect_ids()

        self.assertIsInstance(res, set)
        not_expected_facts = ['facter', 'lsb', 'virtual']
        for not_expected_fact in not_expected_facts:
            self.assertNotIn(not_expected_fact, res)

#    def test_facts_class(self):
#        mock_module = self._mock_module()
#        Facts(mock_module)

#    def test_facts_class_load_on_init_false(self):
#        mock_module = self._mock_module()
#        Facts(mock_module, load_on_init=False)
#        # FIXME: assert something


class TestCollectedFacts(unittest.TestCase):
    gather_subset = ['all', '!facter', '!ohai']
    min_fact_count = 30
    max_fact_count = 1000

    # TODO: add ansible_cmdline, ansible_*_pubkey* back when TempFactCollector goes away
    expected_facts = ['ansible_date_time',
                      'ansible_user_id', 'ansible_distribution',
                      'ansible_gather_subset', 'module_setup',
                      'ansible_env']
    not_expected_facts = ['facter', 'ohai']

    def _mock_module(self, gather_subset=None):
        return mock_module(gather_subset=self.gather_subset)

    def setUp(self):
        mock_module = self._mock_module()
        collectors = self._collectors(mock_module)

        fact_collector = \
            setup.AnsibleFactCollector(collectors=collectors)
        self.facts = fact_collector.collect(module=mock_module)

    def _collectors(self, module,
                    all_collector_classes=None,
                    minimal_gather_subset=None):
        return _collectors(module=module,
                           all_collector_classes=all_collector_classes,
                           minimal_gather_subset=minimal_gather_subset)

    def test_basics(self):
        self._assert_basics(self.facts)

    def test_expected_facts(self):
        self._assert_expected_facts(self.facts)

    def test_not_expected_facts(self):
        self._assert_not_expected_facts(self.facts)

    def test_has_ansible_namespace(self):
        self._assert_ansible_namespace(self.facts)

    def test_no_ansible_dupe_in_key(self):
        self._assert_no_ansible_dupe(self.facts)

    def _assert_basics(self, facts):
        self.assertIsInstance(facts, dict)
        self.assertIn('ansible_facts', facts)
        # just assert it's not almost empty
        self.assertGreater(len(facts['ansible_facts']), self.min_fact_count)
        # and that is not huge number of keys
        self.assertLess(len(facts['ansible_facts']), self.max_fact_count)

    # everything starts with ansible_ namespace
    def _assert_ansible_namespace(self, facts):
        subfacts = facts['ansible_facts']

        # FIXME: kluge for non-namespace fact
        subfacts.pop('module_setup', None)

        for fact_key in subfacts:
            self.assertTrue(fact_key.startswith('ansible_'),
                            'The fact name "%s" does not startwith "ansible_"' % fact_key)

    # verify that we only add one 'ansible_' namespace
    def _assert_no_ansible_dupe(self, facts):
        subfacts = facts['ansible_facts']
        re_ansible = re.compile('ansible')
        re_ansible_underscore = re.compile('ansible_')

        # FIXME: kluge for non-namespace fact
        subfacts.pop('module_setup', None)

        for fact_key in subfacts:
            ansible_count = re_ansible.findall(fact_key)
            self.assertEqual(len(ansible_count), 1,
                             'The fact name "%s" should have 1 "ansible" substring in it.' % fact_key)
            ansible_underscore_count = re_ansible_underscore.findall(fact_key)
            self.assertEqual(len(ansible_underscore_count), 1,
                             'The fact name "%s" should have 1 "ansible_" substring in it.' % fact_key)

    def _assert_expected_facts(self, facts):
        subfacts = facts['ansible_facts']

        subfacts_keys = sorted(subfacts.keys())
        for expected_fact in self.expected_facts:
            self.assertIn(expected_fact, subfacts_keys)
        #    self.assertIsInstance(subfacts['ansible_env'], dict)

        # self.assertIsInstance(subfacts['ansible_env'], dict)

        # self._assert_ssh_facts(subfacts)

    def _assert_not_expected_facts(self, facts):
        subfacts = facts['ansible_facts']

        subfacts_keys = sorted(subfacts.keys())
        for not_expected_fact in self.not_expected_facts:
            self.assertNotIn(not_expected_fact, subfacts_keys)

    def _assert_ssh_facts(self, subfacts):
        self.assertIn('ansible_ssh_host_key_rsa_public', subfacts.keys())


class TestMinimalCollectedFacts(TestCollectedFacts):
    gather_subset = ['!all']
    min_fact_count = 1
    max_fact_count = 10
    expected_facts = ['ansible_gather_subset',
                      'module_setup']
    not_expected_facts = ['ansible_lsb']
