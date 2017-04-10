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

from ansible.module_utils.facts.facts import Facts
from ansible.module_utils.facts.other.facter import FacterFactCollector

from ansible.module_utils.facts.system.apparmor import ApparmorFactCollector
from ansible.module_utils.facts.system.caps import SystemCapabilitiesFactCollector
from ansible.module_utils.facts.system.date_time import DateTimeFactCollector
from ansible.module_utils.facts.system.env import EnvFactCollector
from ansible.module_utils.facts.system.dns import DnsFactCollector
from ansible.module_utils.facts.system.fips import FipsFactCollector
from ansible.module_utils.facts.system.local import LocalFactCollector
from ansible.module_utils.facts.system.lsb import LSBFactCollector
from ansible.module_utils.facts.system.pkg_mgr import PkgMgrFactCollector
from ansible.module_utils.facts.system.python import PythonFactCollector
from ansible.module_utils.facts.system.selinux import SelinuxFactCollector
from ansible.module_utils.facts.system.service_mgr import ServiceMgrFactCollector
from ansible.module_utils.facts.system.user import UserFactCollector

from ansible.module_utils.facts.virtual.base import VirtualCollector

# module under test
from ansible.module_utils import facts


all_collector_classes = [  # TempFactCollector,
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
#                         HardwareCollector,
#                         NetworkCollector,
                         VirtualCollector,
#                         OhaiCollector,
                         FacterFactCollector]


# FIXME: this is brute force, but hopefully enough to get some refactoring to make facts testable
class TestInPlace(unittest.TestCase):
    def _mock_module(self):
        mock_module = Mock()
        mock_module.params = {'gather_subset': ['all', '!facter', '!ohai'],
                              'gather_timeout': 5,
                              'filter': '*'}
        mock_module.get_bin_path = Mock(return_value=None)
        return mock_module

    def test(self):
        mock_module = self._mock_module()
        fact_collector = facts.AnsibleFactCollector.from_gather_subset(mock_module,
                                                                       gather_subset=['all'])
        res = fact_collector.collect()
        self.assertIsInstance(res, dict)
        self.assertIn('ansible_facts', res)
        # just assert it's not almost empty
        self.assertGreater(len(res['ansible_facts']), 30)

    def test_collect_ids(self):
        mock_module = self._mock_module()
        fact_collector = facts.AnsibleFactCollector.from_gather_subset(mock_module,
                                                                       gather_subset=['all'])
        res = fact_collector.collect_ids()

        self.assertIsInstance(res, set)

    def test_collect_ids_minimal(self):
        mock_module = self._mock_module()
        gather_subset = ['!all']
        mock_module.params['gather_subset'] = gather_subset

        fact_collector = facts.AnsibleFactCollector.from_gather_subset(mock_module,
                                                                       gather_subset=gather_subset)
        res = fact_collector.collect_ids()

        self.assertIsInstance(res, set)
        not_expected_facts = ['facter', 'lsb', 'virtual']
        for not_expected_fact in not_expected_facts:
            self.assertNotIn(not_expected_fact, res)

    def test_facts_class(self):
        mock_module = self._mock_module()
        Facts(mock_module)

    def test_facts_class_load_on_init_false(self):
        mock_module = self._mock_module()
        Facts(mock_module, load_on_init=False)
        # FIXME: assert something

    def test_facts_class_populate(self):
        mock_module = self._mock_module()
        facts_obj = Facts(mock_module)
        res = facts_obj.populate()
        self.assertIsInstance(res, dict)
        self.assertIn('python_version', res)
        # just assert it's not almost empty
        self.assertGreater(len(res), 5)


class TestCollectedFacts(unittest.TestCase):
    gather_subset = ['all', '!facter', '!ohai']
    min_fact_count = 30
    max_fact_count = 1000
    expected_facts = ['ansible_cmdline', 'ansible_date_time',
                      'ansible_user_id', 'ansible_distribution',
                      'ansible_gather_subset', 'module_setup',
                      'ansible_env',
                      'ansible_ssh_host_key_rsa_public']
    not_expected_facts = ['facter', 'ohai']

    def _mock_module(self):
        mock_module = Mock()
        mock_module.params = {'gather_subset': self.gather_subset,
                              'gather_timeout': 5,
                              'filter': '*'}
        mock_module.get_bin_path = Mock(return_value=None)
        return mock_module

    def setUp(self):
        mock_module = self._mock_module()
        fact_collector = facts.AnsibleFactCollector.from_gather_subset(mock_module,
                                                                       all_collector_classes=all_collector_classes,
                                                                       gather_subset=self.gather_subset)
        self.facts = fact_collector.collect()

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
