# unit tests for 'setup' ansible module (facts)
# -*- coding: utf-8 -*-
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

from ansible.compat.tests import unittest
from ansible.compat.tests.mock import Mock

from ansible.module_utils.facts.system.env import EnvFactCollector

from ansible.module_utils import facts
from ansible.modules.system import setup


class TestFactSetup(unittest.TestCase):
    def _mock_module(self, gather_subset=None):
        if gather_subset is None:
            gather_subset = ['all', '!facter', '!ohai']
        mock_module = Mock()
        mock_module.params = {'gather_subset': gather_subset,
                              'gather_timeout': 5,
                              'filter': '*'}
        mock_module.get_bin_path = Mock(return_value=None)
        return mock_module

    def test(self):
        gather_subset = ['all']
        mock_module = self._mock_module(gather_subset=gather_subset)
        all_collector_classes = [EnvFactCollector]
        collector_classes = \
            facts.collector_classes_from_gather_subset(all_collector_classes=all_collector_classes,
                                                       minimal_gather_subset=frozenset([]),
                                                       gather_subset=gather_subset)

        fact_collector = \
            setup.AnsibleFactCollector.from_collector_classes(collector_classes,
                                                              mock_module,
                                                              gather_subset=gather_subset)
        res = fact_collector.collect()
        self.assertIsInstance(res, dict)
        self.assertIn('ansible_facts', res)
        import pprint
        pprint.pprint(res)
        self.assertIsInstance(res['ansible_facts'], dict)
        self.assertIn('ansible_env', res['ansible_facts'])
        self.assertIn('ansible_gather_subset', res['ansible_facts'])
        self.assertEqual(res['ansible_facts']['ansible_gather_subset'], ['all'])

        # just assert it's not almost empty
        # with run_command and get_file_content mock, many facts are empty, like network
        # self.assertGreater(len(res['ansible_facts']), 20)
