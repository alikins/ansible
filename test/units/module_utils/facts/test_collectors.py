# unit tests for ansible fact collectors
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

from ansible.compat.tests.mock import Mock, patch

from . base import BaseFactsTest

from ansible.module_utils.facts.system.apparmor import ApparmorFactCollector
from ansible.module_utils.facts.system.caps import SystemCapabilitiesFactCollector
from ansible.module_utils.facts.system.distribution import DistributionFactCollector
from ansible.module_utils.facts.system.env import EnvFactCollector
from ansible.module_utils.facts.system.fips import FipsFactCollector
from ansible.module_utils.facts.system.pkg_mgr import PkgMgrFactCollector
from ansible.module_utils.facts.system.selinux import SelinuxFactCollector
from ansible.module_utils.facts.system.service_mgr import ServiceMgrFactCollector

from ansible.module_utils.facts.virtual.base import VirtualCollector
from ansible.module_utils.facts.network.base import NetworkCollector


class TestApparmorFacts(BaseFactsTest):
    __test__ = True
    gather_subset = ['!all', 'apparmor']
    valid_subsets = ['apparmor']
    fact_namespace = 'ansible_apparmor'
    collector_class = ApparmorFactCollector

    def test_collect(self):
        facts_dict = super(TestApparmorFacts, self).test_collect()
        self.assertIn('status', facts_dict['apparmor'])


class TestCollectedCapsFacts(BaseFactsTest):
    __test__ = True
    gather_subset = ['!all', 'caps']
    valid_subsets = ['caps']
    fact_namespace = 'ansible_system_capabilities'
    collector_class = SystemCapabilitiesFactCollector

    def _mock_module(self):
        mock_module = Mock()
        mock_module.params = {'gather_subset': self.gather_subset,
                              'gather_timeout': 10,
                              'filter': '*'}
        mock_module.get_bin_path = Mock(return_value='/usr/sbin/capsh')
        mock_module.run_command = Mock(return_value=(0, 'Current: =ep', ''))
        return mock_module


class TestDistributionFacts(BaseFactsTest):
    __test__ = True
    gather_subset = ['!all', 'distribution']
    valid_subsets = ['distribution']
    fact_namespace = 'ansible_distribution'
    collector_class = DistributionFactCollector


class TestEnvFacts(BaseFactsTest):

    __test__ = True
    gather_subset = ['!all', 'env']
    valid_subsets = ['env']
    fact_namespace = 'ansible_env'
    collector_class = EnvFactCollector

    def test_collect(self):
        facts_dict = super(TestEnvFacts, self).test_collect()
        self.assertIn('HOME', facts_dict['env'])


class TestCollectedFipsFacts(BaseFactsTest):
    __test__ = True
    gather_subset = ['!all', 'fips']
    valid_subsets = ['fips']
    fact_namespace = 'ansible_fips'
    collector_class = FipsFactCollector


class TestNetworkCollector(BaseFactsTest):
    __test__ = True
    gather_subset = ['!all', 'network']
    valid_subsets = ['network']
    fact_namespace = 'ansible_network'
    collector_class = NetworkCollector


class TestPkgMgrFacts(BaseFactsTest):
    __test__ = True
    gather_subset = ['!all', 'pkg_mgr']
    valid_subsets = ['pkg_mgr']
    fact_namespace = 'ansible_pkgmgr'
    collector_class = PkgMgrFactCollector


class TestSelinuxFacts(BaseFactsTest):
    __test__ = True
    gather_subset = ['!all', 'selinux']
    valid_subsets = ['selinux']
    fact_namespace = 'ansible_selinux'
    collector_class = SelinuxFactCollector

    def test_no_selinux(self):
        with patch('ansible.module_utils.facts.system.selinux.HAVE_SELINUX', False):
            module = self._mock_module()
            fact_collector = self.collector_class(module=module)
            facts_dict = fact_collector.collect()
            self.assertIsInstance(facts_dict, dict)
            self.assertFalse(facts_dict['selinux'])
            return facts_dict


class TestServiceMgrFacts(BaseFactsTest):
    __test__ = True
    gather_subset = ['!all', 'service_mgr']
    valid_subsets = ['service_mgr']
    fact_namespace = 'ansible_service_mgr'
    collector_class = ServiceMgrFactCollector

    # TODO: dedupe some of this test code

    @patch('ansible.module_utils.facts.system.service_mgr.get_file_content', return_value=None)
    def test_no_proc1(self, mock_gfc):
        # no /proc/1/comm, ps returns non-0
        # should fallback to 'service'
        module = self._mock_module()
        module.run_command = Mock(return_value=(1, '', 'wat'))
        fact_collector = self.collector_class(module=module)
        facts_dict = fact_collector.collect()
        self.assertIsInstance(facts_dict, dict)
        self.assertEqual(facts_dict['service_mgr'], 'service')

    @patch('ansible.module_utils.facts.system.service_mgr.get_file_content', return_value=None)
    def test_no_proc1_ps_random_init(self, mock_gfc):
        # no /proc/1/comm, ps returns '/sbin/sys11' which we dont know
        # should end up return 'sys11'
        module = self._mock_module()
        module.run_command = Mock(return_value=(0, '/sbin/sys11', ''))
        fact_collector = self.collector_class(module=module)
        facts_dict = fact_collector.collect()
        self.assertIsInstance(facts_dict, dict)
        self.assertEqual(facts_dict['service_mgr'], 'sys11')

    @patch('ansible.module_utils.facts.system.service_mgr.get_file_content', return_value=None)
    def test_clowncar(self, mock_gfc):
        # no /proc/1/comm, ps fails, distro and system are clowncar
        # should end up return 'sys11'
        module = self._mock_module()
        module.run_command = Mock(return_value=(1, '', ''))
        collected_facts = {'distribution': 'clowncar',
                           'system': 'ClownCarOS'}
        fact_collector = self.collector_class(module=module)
        facts_dict = fact_collector.collect(collected_facts=collected_facts)
        self.assertIsInstance(facts_dict, dict)
        self.assertEqual(facts_dict['service_mgr'], 'service')

    # TODO: reenable these tests when we can mock more easily

#    @patch('ansible.module_utils.facts.system.service_mgr.get_file_content', return_value=None)
#    def test_sunos_fallback(self, mock_gfc):
#        # no /proc/1/comm, ps fails, 'system' is SunOS
#        # should end up return 'smf'?
#        module = self._mock_module()
#        # FIXME: the result here is a kluge to at least cover more of service_mgr.collect
#        # TODO: remove
#        # FIXME: have to force a pid for results here to get into any of the system/distro checks
#        module.run_command = Mock(return_value=(1, ' 37 ', ''))
#        collected_facts = {'system': 'SunOS'}
#        fact_collector = self.collector_class(module=module)
#        facts_dict = fact_collector.collect(collected_facts=collected_facts)
#        print('facts_dict: %s' % facts_dict)
#        self.assertIsInstance(facts_dict, dict)
#        self.assertEqual(facts_dict['service_mgr'], 'smf')

#    @patch('ansible.module_utils.facts.system.service_mgr.get_file_content', return_value=None)
#    def test_aix_fallback(self, mock_gfc):
#        # no /proc/1/comm, ps fails, 'system' is SunOS
#        # should end up return 'smf'?
#        module = self._mock_module()
#        module.run_command = Mock(return_value=(1, '', ''))
#        collected_facts = {'system': 'AIX'}
#        fact_collector = self.collector_class(module=module)
#        facts_dict = fact_collector.collect(collected_facts=collected_facts)
#        print('facts_dict: %s' % facts_dict)
#        self.assertIsInstance(facts_dict, dict)
#        self.assertEqual(facts_dict['service_mgr'], 'src')

#    @patch('ansible.module_utils.facts.system.service_mgr.get_file_content', return_value=None)
#    def test_linux_fallback(self, mock_gfc):
#        # no /proc/1/comm, ps fails, 'system' is SunOS
#        # should end up return 'smf'?
#        module = self._mock_module()
#        module.run_command = Mock(return_value=(1, '  37 ', ''))
#        collected_facts = {'system': 'Linux'}
#        fact_collector = self.collector_class(module=module)
#        facts_dict = fact_collector.collect(collected_facts=collected_facts)
#        print('facts_dict: %s' % facts_dict)
#        self.assertIsInstance(facts_dict, dict)
#        self.assertEqual(facts_dict['service_mgr'], 'sdfadf')


class TestVirtualFacts(BaseFactsTest):
    __test__ = True
    gather_subset = ['!all', 'virtual']
    valid_subsets = ['virtual']
    fact_namespace = 'ansible_virtual'
    collector_class = VirtualCollector
