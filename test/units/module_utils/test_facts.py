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

# Make coding more python3-ish
from __future__ import (absolute_import, division)
#__metaclass__ = type

import os
import re

# for testing
from ansible.compat.tests import unittest
from ansible.compat.tests.mock import MagicMock, Mock, patch

from ansible.module_utils import facts
from ansible.module_utils.facts import hardware
from ansible.module_utils.facts import network
from ansible.module_utils.facts import virtual
from ansible.module_utils.facts.virtual.linux import LinuxVirtual
#import ansible.module_utils.facts.virtual
#from ansible.module_utils.facts.virtual.linux import LinuxVirtual

from ansible.module_utils.facts.system.apparmor import ApparmorFactCollector
from ansible.module_utils.facts.system.fips import FipsFactCollector
from ansible.module_utils.facts.system.lsb import LSBFactCollector
from ansible.module_utils.facts.system.selinux import SelinuxFactCollector
from ansible.module_utils.facts.system.caps import SystemCapabilitiesFactCollector

print(virtual)
print(dir(virtual))
#print(virtual.linux)
#print(virtual.linux.LinuxVirtual)

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
        #res = facts.get_all_facts(mock_module)
        fact_collector = facts.AnsibleFactCollector.from_gather_subset(mock_module,
                                                                       gather_subset=['all'])
        res = fact_collector.collect()
        #print(res)
        self.assertIsInstance(res, dict)
        self.assertIn('ansible_facts', res)
        # just assert it's not almost empty
        self.assertGreater(len(res['ansible_facts']), 30)

    def test_collect_ids(self):
        mock_module = self._mock_module()
        #res = facts.get_all_facts(mock_module)
        fact_collector = facts.AnsibleFactCollector.from_gather_subset(mock_module,
                                                                       gather_subset=['all'])
        res = fact_collector.collect_ids()
        print('collect_ids: %s' % res)

        self.assertIsInstance(res, set)

    def test_facts_class(self):
        mock_module = self._mock_module()
        facts_obj = facts.Facts(mock_module)
        print(facts_obj)

    def test_facts_class_load_on_init_false(self):
        mock_module = self._mock_module()
        facts_obj = facts.Facts(mock_module, load_on_init=False)
        print(facts_obj)

    def test_facts_class_populate(self):
        mock_module = self._mock_module()
        facts_obj = facts.Facts(mock_module)
        res = facts_obj.populate()
        print(res)
        self.assertIsInstance(res, dict)
        self.assertIn('python_version', res)
        # just assert it's not almost empty
        self.assertGreater(len(res), 20)


class TestCollectedFacts(unittest.TestCase):
    def _mock_module(self):
        mock_module = Mock()
        mock_module.params = {'gather_subset': ['all', '!facter', '!ohai'],
                              'gather_timeout': 5,
                              'filter': '*'}
        mock_module.get_bin_path = Mock(return_value=None)
        return mock_module

    def setUp(self):
        mock_module = self._mock_module()
        #res = facts.get_all_facts(mock_module)
        fact_collector = facts.AnsibleFactCollector.from_gather_subset(mock_module,
                                                                       gather_subset=['all'])
        self.facts = fact_collector.collect()
        #print(res)

    def test_basics(self):
        self._assert_basics(self.facts)

    def test_known_facts(self):
        self._assert_known_facts(self.facts)

    def test_has_ansible_namespace(self):
        self._assert_ansible_namespace(self.facts)

    def test_no_ansible_dupe_in_key(self):
        self._assert_no_ansible_dupe(self.facts)

    def _assert_basics(self, facts):
        import pprint
        pprint.pprint(facts)
        pprint.pprint(sorted(facts['ansible_facts'].keys()))
        print(len(facts['ansible_facts']))

        self.assertIsInstance(facts, dict)
        self.assertIn('ansible_facts', facts)
        # just assert it's not almost empty
        self.assertGreater(len(facts['ansible_facts']), 30)

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

    def _assert_known_facts(self, facts):
        subfacts = facts['ansible_facts']

        subfacts_keys = sorted(subfacts.keys())
        self.assertIn('ansible_cmdline', subfacts_keys)
        self.assertIn('ansible_date_time', subfacts_keys)
        self.assertIn('ansible_user_id', subfacts_keys)
        self.assertIn('ansible_distribution', subfacts_keys)

        self.assertIn('ansible_gather_subset', subfacts_keys)
        self.assertIn('module_setup', subfacts_keys)

        self.assertIn('ansible_env', subfacts_keys)
        self.assertIsInstance(subfacts['ansible_env'], dict)

        self._assert_ssh_facts(subfacts)

    def _assert_ssh_facts(self, subfacts):
        self.assertIn('ansible_ssh_host_key_rsa_public', subfacts.keys())


class BaseFactsTest(unittest.TestCase):
    # just a base class, not an actual test
    __test__ = False

    gather_subset = ['all']
    valid_subsets = None
    fact_namespace = None
    collector_class = None

    def _mock_module(self):
        mock_module = Mock()
        mock_module.params = {'gather_subset': self.gather_subset,
                              'gather_timeout': 5,
                              'filter': '*'}
        mock_module.get_bin_path = Mock(return_value=None)
        return mock_module

    def test_class(self):
        module = self._mock_module()
        fact_collector = self.collector_class(module=module)
        facts_dict = fact_collector.collect()
        self.assertIsInstance(facts_dict, dict)
        return facts_dict


class TestCollectedFipsFacts(BaseFactsTest):
    __test__ = True
    gather_subset = ['!all', 'fips']
    valid_subsets = ['fips']
    fact_namespace = 'ansible_fips'
    collector_class = FipsFactCollector


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
        mock_module.run_command = Mock(return_value=(0,'Current: =ep', ''))
        return mock_module


class TestApparmorFacts(BaseFactsTest):
    __test__ = True
    gather_subset = ['!all', 'apparmor']
    valid_subsets = ['apparmor']
    fact_namespace = 'ansible_apparmor'
    collector_class = ApparmorFactCollector


    def test_class(self):
        facts_dict = super(TestApparmorFacts, self).test_class()
        self.assertIn('status', facts_dict['apparmor'])


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


lsb_release_a_fedora_output = '''
LSB Version:	:core-4.1-amd64:core-4.1-noarch:cxx-4.1-amd64:cxx-4.1-noarch:desktop-4.1-amd64:desktop-4.1-noarch:languages-4.1-amd64:languages-4.1-noarch:printing-4.1-amd64:printing-4.1-noarch
Distributor ID:	Fedora
Description:	Fedora release 25 (Twenty Five)
Release:	25
Codename:	TwentyFive
'''

# FIXME: a
etc_lsb_release_ubuntu14 = '''DISTRIB_ID=Ubuntu
DISTRIB_RELEASE=14.04
DISTRIB_CODENAME=trusty
DISTRIB_DESCRIPTION="Ubuntu 14.04.3 LTS"
'''

class TestLSBFacts(BaseFactsTest):
    __test__ = True
    gather_subset = ['!all', 'lsb']
    valid_subsets = ['lsb']
    fact_namespace = 'ansible_lsb'
    collector_class = LSBFactCollector

    def _mock_module(self):
        mock_module = Mock()
        mock_module.params = {'gather_subset': self.gather_subset,
                              'gather_timeout': 10,
                              'filter': '*'}
        mock_module.get_bin_path = Mock(return_value='/usr/bin/lsb_release')
        mock_module.run_command = Mock(return_value=(0, lsb_release_a_fedora_output, ''))
        return mock_module

    def test_lsb_release_bin(self):
        module = self._mock_module()
        fact_collector = self.collector_class(module=module)
        facts_dict = fact_collector.collect()

        self.assertIsInstance(facts_dict, dict)
        self.assertEqual(facts_dict['lsb']['release'], '25')
        self.assertEqual(facts_dict['lsb']['id'], 'Fedora')
        self.assertEqual(facts_dict['lsb']['description'], 'Fedora release 25 (Twenty Five)')
        self.assertEqual(facts_dict['lsb']['codename'], 'TwentyFive')
        self.assertEqual(facts_dict['lsb']['major_release'], '25')


    def test_etc_lsb_release(self):
        module = self._mock_module()
        module.get_bin_path = Mock(return_value=None)
        with patch('ansible.module_utils.facts.system.lsb.os.path.exists',
                   return_value=True):
            with patch('ansible.module_utils.facts.system.lsb.get_file_lines',
                       return_value=etc_lsb_release_ubuntu14.splitlines()):
                fact_collector = self.collector_class(module=module)
                facts_dict = fact_collector.collect()

        self.assertIsInstance(facts_dict, dict)
        self.assertEqual(facts_dict['lsb']['release'], '14.04')
        self.assertEqual(facts_dict['lsb']['id'], 'Ubuntu')
        self.assertEqual(facts_dict['lsb']['description'], '"Ubuntu 14.04.3 LTS"')
        self.assertEqual(facts_dict['lsb']['codename'], 'trusty')


class BaseTestFactsPlatform(unittest.TestCase):
    platform_id = 'Generic'
    fact_class = hardware.base.Hardware

    """Verify that the automagic in Hardware.__new__ selects the right subclass."""
    @patch('platform.system')
    def test_new(self, mock_platform):
        mock_platform.return_value = self.platform_id
        inst = self.fact_class(module=Mock(), load_on_init=False)
        self.assertIsInstance(inst, self.fact_class)
        self.assertEqual(inst.platform, self.platform_id)

    def test_subclass(self):
        # 'Generic' will try to map to platform.system() that we are not mocking here
        if self.platform_id == 'Generic':
            return
        inst = self.fact_class(module=Mock(), load_on_init=False)
        self.assertIsInstance(inst, self.fact_class)
        self.assertEqual(inst.platform, self.platform_id)


class TestLinuxFactsPlatform(BaseTestFactsPlatform):
    platform_id = 'Linux'
    fact_class = hardware.linux.LinuxHardware


class TestHurdFactsPlatform(BaseTestFactsPlatform):
    platform_id = 'GNU'
    fact_class = hardware.hurd.HurdHardware


class TestSunOSHardware(BaseTestFactsPlatform):
    platform_id = 'SunOS'
    fact_class = hardware.sunos.SunOSHardware


class TestOpenBSDHardware(BaseTestFactsPlatform):
    platform_id = 'OpenBSD'
    fact_class = hardware.openbsd.OpenBSDHardware


class TestFreeBSDHardware(BaseTestFactsPlatform):
    platform_id = 'FreeBSD'
    fact_class = hardware.freebsd.FreeBSDHardware


class TestDragonFlyHardware(BaseTestFactsPlatform):
    platform_id = 'DragonFly'
    fact_class = hardware.dragonfly.DragonFlyHardware


class TestNetBSDHardware(BaseTestFactsPlatform):
    platform_id = 'NetBSD'
    fact_class = hardware.netbsd.NetBSDHardware


class TestAIXHardware(BaseTestFactsPlatform):
    platform_id = 'AIX'
    fact_class = hardware.aix.AIXHardware


class TestHPUXHardware(BaseTestFactsPlatform):
    platform_id = 'HP-UX'
    fact_class = hardware.hpux.HPUXHardware


class TestDarwinHardware(BaseTestFactsPlatform):
    platform_id = 'Darwin'
    fact_class = hardware.darwin.DarwinHardware


class TestGenericNetwork(BaseTestFactsPlatform):
    platform_id = 'Generic'
    fact_class = network.base.Network


class TestHurdPfinetNetwork(BaseTestFactsPlatform):
    platform_id = 'GNU'
    fact_class = network.hurd.HurdPfinetNetwork


class TestLinuxNetwork(BaseTestFactsPlatform):
    platform_id = 'Linux'
    fact_class = network.linux.LinuxNetwork


class TestGenericBsdIfconfigNetwork(BaseTestFactsPlatform):
    platform_id = 'Generic_BSD_Ifconfig'
    fact_class = network.generic_bsd.GenericBsdIfconfigNetwork


class TestHPUXNetwork(BaseTestFactsPlatform):
    platform_id = 'HP-UX'
    fact_class = network.hpux.HPUXNetwork


class TestDarwinNetwork(BaseTestFactsPlatform):
    platform_id = 'Darwin'
    fact_class = network.darwin.DarwinNetwork


class TestFreeBSDNetwork(BaseTestFactsPlatform):
    platform_id = 'FreeBSD'
    fact_class = network.freebsd.FreeBSDNetwork


class TestDragonFlyNetwork(BaseTestFactsPlatform):
    platform_id = 'DragonFly'
    fact_class = network.dragonfly.DragonFlyNetwork


class TestAIXNetwork(BaseTestFactsPlatform):
    platform_id = 'AIX'
    fact_class = network.aix.AIXNetwork


class TestNetBSDNetwork(BaseTestFactsPlatform):
    platform_id = 'NetBSD'
    fact_class = network.netbsd.NetBSDNetwork


class TestOpenBSDNetwork(BaseTestFactsPlatform):
    platform_id = 'OpenBSD'
    fact_class = network.openbsd.OpenBSDNetwork


class TestSunOSNetwork(BaseTestFactsPlatform):
    platform_id = 'SunOS'
    fact_class = network.sunos.SunOSNetwork


class TestLinuxVirtual(BaseTestFactsPlatform):
    platform_id = 'Linux'
    fact_class = LinuxVirtual


class TestFreeBSDVirtual(BaseTestFactsPlatform):
    platform_id = 'FreeBSD'
    fact_class = virtual.freebsd.FreeBSDVirtual


class TestDragonFlyVirtual(BaseTestFactsPlatform):
    platform_id = 'DragonFly'
    fact_class = virtual.dragonfly.DragonFlyVirtual


class TestNetBSDVirtual(BaseTestFactsPlatform):
    platform_id = 'NetBSD'
    fact_class = virtual.netbsd.NetBSDVirtual


class TestOpenBSDVirtual(BaseTestFactsPlatform):
    platform_id = 'OpenBSD'
    fact_class = virtual.openbsd.OpenBSDVirtual


class TestHPUXVirtual(BaseTestFactsPlatform):
    platform_id = 'HP-UX'
    fact_class = virtual.hpux.HPUXVirtual


class TestSunOSVirtual(BaseTestFactsPlatform):
    platform_id = 'SunOS'
    fact_class = virtual.sunos.SunOSVirtual


LSBLK_OUTPUT = b"""
/dev/sda
/dev/sda1                             32caaec3-ef40-4691-a3b6-438c3f9bc1c0
/dev/sda2                             66Ojcd-ULtu-1cZa-Tywo-mx0d-RF4O-ysA9jK
/dev/mapper/fedora_dhcp129--186-swap  eae6059d-2fbe-4d1c-920d-a80bbeb1ac6d
/dev/mapper/fedora_dhcp129--186-root  d34cf5e3-3449-4a6c-8179-a1feb2bca6ce
/dev/mapper/fedora_dhcp129--186-home  2d3e4853-fa69-4ccf-8a6a-77b05ab0a42d
/dev/sr0
/dev/loop0                            0f031512-ab15-497d-9abd-3a512b4a9390
/dev/loop1                            7c1b0f30-cf34-459f-9a70-2612f82b870a
/dev/loop9                            0f031512-ab15-497d-9abd-3a512b4a9390
/dev/loop9                            7c1b4444-cf34-459f-9a70-2612f82b870a
/dev/mapper/docker-253:1-1050967-pool
/dev/loop2
/dev/mapper/docker-253:1-1050967-pool
"""

LSBLK_OUTPUT_2  = b"""
/dev/sda
/dev/sda1                            32caaec3-ef40-4691-a3b6-438c3f9bc1c0
/dev/sda2                            66Ojcd-ULtu-1cZa-Tywo-mx0d-RF4O-ysA9jK
/dev/mapper/fedora_dhcp129--186-swap eae6059d-2fbe-4d1c-920d-a80bbeb1ac6d
/dev/mapper/fedora_dhcp129--186-root d34cf5e3-3449-4a6c-8179-a1feb2bca6ce
/dev/mapper/fedora_dhcp129--186-home 2d3e4853-fa69-4ccf-8a6a-77b05ab0a42d
/dev/mapper/an-example-mapper with a space in the name 84639acb-013f-4d2f-9392-526a572b4373
/dev/sr0
/dev/loop0                           0f031512-ab15-497d-9abd-3a512b4a9390
"""

LSBLK_UUIDS = {'/dev/sda1': '66Ojcd-ULtu-1cZa-Tywo-mx0d-RF4O-ysA9jK'}

MTAB = """
sysfs /sys sysfs rw,seclabel,nosuid,nodev,noexec,relatime 0 0
proc /proc proc rw,nosuid,nodev,noexec,relatime 0 0
devtmpfs /dev devtmpfs rw,seclabel,nosuid,size=8044400k,nr_inodes=2011100,mode=755 0 0
securityfs /sys/kernel/security securityfs rw,nosuid,nodev,noexec,relatime 0 0
tmpfs /dev/shm tmpfs rw,seclabel,nosuid,nodev 0 0
devpts /dev/pts devpts rw,seclabel,nosuid,noexec,relatime,gid=5,mode=620,ptmxmode=000 0 0
tmpfs /run tmpfs rw,seclabel,nosuid,nodev,mode=755 0 0
tmpfs /sys/fs/cgroup tmpfs ro,seclabel,nosuid,nodev,noexec,mode=755 0 0
cgroup /sys/fs/cgroup/systemd cgroup rw,nosuid,nodev,noexec,relatime,xattr,release_agent=/usr/lib/systemd/systemd-cgroups-agent,name=systemd 0 0
pstore /sys/fs/pstore pstore rw,seclabel,nosuid,nodev,noexec,relatime 0 0
cgroup /sys/fs/cgroup/devices cgroup rw,nosuid,nodev,noexec,relatime,devices 0 0
cgroup /sys/fs/cgroup/freezer cgroup rw,nosuid,nodev,noexec,relatime,freezer 0 0
cgroup /sys/fs/cgroup/memory cgroup rw,nosuid,nodev,noexec,relatime,memory 0 0
cgroup /sys/fs/cgroup/pids cgroup rw,nosuid,nodev,noexec,relatime,pids 0 0
cgroup /sys/fs/cgroup/blkio cgroup rw,nosuid,nodev,noexec,relatime,blkio 0 0
cgroup /sys/fs/cgroup/cpuset cgroup rw,nosuid,nodev,noexec,relatime,cpuset 0 0
cgroup /sys/fs/cgroup/cpu,cpuacct cgroup rw,nosuid,nodev,noexec,relatime,cpu,cpuacct 0 0
cgroup /sys/fs/cgroup/hugetlb cgroup rw,nosuid,nodev,noexec,relatime,hugetlb 0 0
cgroup /sys/fs/cgroup/perf_event cgroup rw,nosuid,nodev,noexec,relatime,perf_event 0 0
cgroup /sys/fs/cgroup/net_cls,net_prio cgroup rw,nosuid,nodev,noexec,relatime,net_cls,net_prio 0 0
configfs /sys/kernel/config configfs rw,relatime 0 0
/dev/mapper/fedora_dhcp129--186-root / ext4 rw,seclabel,relatime,data=ordered 0 0
selinuxfs /sys/fs/selinux selinuxfs rw,relatime 0 0
systemd-1 /proc/sys/fs/binfmt_misc autofs rw,relatime,fd=24,pgrp=1,timeout=0,minproto=5,maxproto=5,direct 0 0
debugfs /sys/kernel/debug debugfs rw,seclabel,relatime 0 0
hugetlbfs /dev/hugepages hugetlbfs rw,seclabel,relatime 0 0
tmpfs /tmp tmpfs rw,seclabel 0 0
mqueue /dev/mqueue mqueue rw,seclabel,relatime 0 0
/dev/loop0 /var/lib/machines btrfs rw,seclabel,relatime,space_cache,subvolid=5,subvol=/ 0 0
/dev/sda1 /boot ext4 rw,seclabel,relatime,data=ordered 0 0
/dev/mapper/fedora_dhcp129--186-home /home ext4 rw,seclabel,relatime,data=ordered 0 0
tmpfs /run/user/1000 tmpfs rw,seclabel,nosuid,nodev,relatime,size=1611044k,mode=700,uid=1000,gid=1000 0 0
gvfsd-fuse /run/user/1000/gvfs fuse.gvfsd-fuse rw,nosuid,nodev,relatime,user_id=1000,group_id=1000 0 0
fusectl /sys/fs/fuse/connections fusectl rw,relatime 0 0
grimlock.g.a: /home/adrian/sshfs-grimlock fuse.sshfs rw,nosuid,nodev,relatime,user_id=1000,group_id=1000 0 0
grimlock.g.a:test_path/path_with'single_quotes /home/adrian/sshfs-grimlock-single-quote fuse.sshfs rw,nosuid,nodev,relatime,user_id=1000,group_id=1000 0 0
grimlock.g.a:path_with'single_quotes /home/adrian/sshfs-grimlock-single-quote-2 fuse.sshfs rw,nosuid,nodev,relatime,user_id=1000,group_id=1000 0 0
grimlock.g.a:/mnt/data/foto's /home/adrian/fotos fuse.sshfs rw,nosuid,nodev,relatime,user_id=1000,group_id=1000 0 0
"""

MTAB_ENTRIES = \
    [
        ['sysfs',
         '/sys',
         'sysfs',
         'rw,seclabel,nosuid,nodev,noexec,relatime',
         '0',
         '0'],
        ['proc', '/proc', 'proc', 'rw,nosuid,nodev,noexec,relatime', '0', '0'],
        ['devtmpfs',
         '/dev',
         'devtmpfs',
         'rw,seclabel,nosuid,size=8044400k,nr_inodes=2011100,mode=755',
         '0',
         '0'],
        ['securityfs',
         '/sys/kernel/security',
         'securityfs',
         'rw,nosuid,nodev,noexec,relatime',
         '0',
         '0'],
        ['tmpfs', '/dev/shm', 'tmpfs', 'rw,seclabel,nosuid,nodev', '0', '0'],
        ['devpts',
         '/dev/pts',
         'devpts',
         'rw,seclabel,nosuid,noexec,relatime,gid=5,mode=620,ptmxmode=000',
         '0',
         '0'],
        ['tmpfs', '/run', 'tmpfs', 'rw,seclabel,nosuid,nodev,mode=755', '0', '0'],
        ['tmpfs',
         '/sys/fs/cgroup',
         'tmpfs',
         'ro,seclabel,nosuid,nodev,noexec,mode=755',
         '0',
         '0'],
        ['cgroup',
         '/sys/fs/cgroup/systemd',
         'cgroup',
         'rw,nosuid,nodev,noexec,relatime,xattr,release_agent=/usr/lib/systemd/systemd-cgroups-agent,name=systemd',
         '0',
         '0'],
        ['pstore',
         '/sys/fs/pstore',
         'pstore',
         'rw,seclabel,nosuid,nodev,noexec,relatime',
         '0',
         '0'],
        ['cgroup',
         '/sys/fs/cgroup/devices',
         'cgroup',
         'rw,nosuid,nodev,noexec,relatime,devices',
         '0',
         '0'],
        ['cgroup',
        '/sys/fs/cgroup/freezer',
        'cgroup',
        'rw,nosuid,nodev,noexec,relatime,freezer',
        '0',
        '0'],
        ['cgroup',
        '/sys/fs/cgroup/memory',
        'cgroup',
        'rw,nosuid,nodev,noexec,relatime,memory',
        '0',
        '0'],
        ['cgroup',
        '/sys/fs/cgroup/pids',
        'cgroup',
        'rw,nosuid,nodev,noexec,relatime,pids',
        '0',
        '0'],
        ['cgroup',
        '/sys/fs/cgroup/blkio',
        'cgroup',
        'rw,nosuid,nodev,noexec,relatime,blkio',
        '0',
        '0'],
        ['cgroup',
        '/sys/fs/cgroup/cpuset',
        'cgroup',
        'rw,nosuid,nodev,noexec,relatime,cpuset',
        '0',
        '0'],
        ['cgroup',
        '/sys/fs/cgroup/cpu,cpuacct',
        'cgroup',
        'rw,nosuid,nodev,noexec,relatime,cpu,cpuacct',
        '0',
        '0'],
        ['cgroup',
        '/sys/fs/cgroup/hugetlb',
        'cgroup',
        'rw,nosuid,nodev,noexec,relatime,hugetlb',
        '0',
        '0'],
        ['cgroup',
        '/sys/fs/cgroup/perf_event',
        'cgroup',
        'rw,nosuid,nodev,noexec,relatime,perf_event',
        '0',
        '0'],
        ['cgroup',
        '/sys/fs/cgroup/net_cls,net_prio',
        'cgroup',
        'rw,nosuid,nodev,noexec,relatime,net_cls,net_prio',
        '0',
        '0'],
        ['configfs', '/sys/kernel/config', 'configfs', 'rw,relatime', '0', '0'],
        ['/dev/mapper/fedora_dhcp129--186-root',
        '/',
        'ext4',
        'rw,seclabel,relatime,data=ordered',
        '0',
        '0'],
        ['selinuxfs', '/sys/fs/selinux', 'selinuxfs', 'rw,relatime', '0', '0'],
        ['systemd-1',
        '/proc/sys/fs/binfmt_misc',
        'autofs',
        'rw,relatime,fd=24,pgrp=1,timeout=0,minproto=5,maxproto=5,direct',
        '0',
        '0'],
        ['debugfs', '/sys/kernel/debug', 'debugfs', 'rw,seclabel,relatime', '0', '0'],
        ['hugetlbfs',
        '/dev/hugepages',
        'hugetlbfs',
        'rw,seclabel,relatime',
        '0',
        '0'],
        ['tmpfs', '/tmp', 'tmpfs', 'rw,seclabel', '0', '0'],
        ['mqueue', '/dev/mqueue', 'mqueue', 'rw,seclabel,relatime', '0', '0'],
        ['/dev/loop0',
        '/var/lib/machines',
        'btrfs',
        'rw,seclabel,relatime,space_cache,subvolid=5,subvol=/',
        '0',
        '0'],
        ['/dev/sda1', '/boot', 'ext4', 'rw,seclabel,relatime,data=ordered', '0', '0'],
        # A 'none' fstype
        ['/dev/sdz3', '/not/a/real/device', 'none', 'rw,seclabel,relatime,data=ordered', '0', '0'],
        # lets assume this is a bindmount
        ['/dev/sdz4', '/not/a/real/bind_mount', 'ext4', 'rw,seclabel,relatime,data=ordered', '0', '0'],
        ['/dev/mapper/fedora_dhcp129--186-home',
        '/home',
        'ext4',
        'rw,seclabel,relatime,data=ordered',
        '0',
        '0'],
        ['tmpfs',
        '/run/user/1000',
        'tmpfs',
        'rw,seclabel,nosuid,nodev,relatime,size=1611044k,mode=700,uid=1000,gid=1000',
        '0',
        '0'],
        ['gvfsd-fuse',
        '/run/user/1000/gvfs',
        'fuse.gvfsd-fuse',
        'rw,nosuid,nodev,relatime,user_id=1000,group_id=1000',
        '0',
        '0'],
        ['fusectl', '/sys/fs/fuse/connections', 'fusectl', 'rw,relatime', '0', '0']]

BIND_MOUNTS = ['/not/a/real/bind_mount']

with open(os.path.join(os.path.dirname(__file__), 'fixtures/findmount_output.txt')) as f:
    FINDMNT_OUTPUT = f.read()


class TestFactsLinuxHardwareGetMountFacts(unittest.TestCase):

    # FIXME: mock.patch instead
    def setUp(self):
        # The @timeout tracebacks if there isn't a GATHER_TIMEOUT is None (the default until get_all_facts sets it via global)
        facts.GATHER_TIMEOUT = 10

    def tearDown(self):
        facts.GATHER_TIMEOUT = None

    # The Hardware subclasses freakout if instaniated directly, so
    # mock platform.system and inst Hardware() so we get a LinuxHardware()
    # we can test.
    @patch('ansible.module_utils.facts.hardware.linux.LinuxHardware._mtab_entries', return_value=MTAB_ENTRIES)
    @patch('ansible.module_utils.facts.hardware.linux.LinuxHardware._find_bind_mounts', return_value=BIND_MOUNTS)
    @patch('ansible.module_utils.facts.hardware.linux.LinuxHardware._lsblk_uuid', return_value=LSBLK_UUIDS)
    def test_get_mount_facts(self,
                             mock_lsblk_uuid,
                             mock_find_bind_mounts,
                             mock_mtab_entries):
        module = Mock()
        # Returns a LinuxHardware-ish
        lh = hardware.linux.LinuxHardware(module=module, load_on_init=False)

        # Nothing returned, just self.facts modified as a side effect
        lh.get_mount_facts()
        self.assertIsInstance(lh.facts, dict)
        self.assertIn('mounts', lh.facts)
        self.assertIsInstance(lh.facts['mounts'], list)
        self.assertIsInstance(lh.facts['mounts'][0], dict)

    @patch('ansible.module_utils.facts.hardware.linux.get_file_content', return_value=MTAB)
    def test_get_mtab_entries(self, mock_get_file_content):

        module = Mock()
        lh = hardware.linux.LinuxHardware(module=module, load_on_init=False)
        mtab_entries = lh._mtab_entries()
        self.assertIsInstance(mtab_entries, list)
        self.assertIsInstance(mtab_entries[0], list)
        self.assertEqual(len(mtab_entries), 38)

    @patch('ansible.module_utils.facts.hardware.linux.LinuxHardware._run_findmnt', return_value=(0, FINDMNT_OUTPUT, ''))
    def test_find_bind_mounts(self, mock_run_findmnt):
        module = Mock()
        lh = hardware.linux.LinuxHardware(module=module, load_on_init=False)
        bind_mounts = lh._find_bind_mounts()

        # If bind_mounts becomes another seq type, feel free to change
        self.assertIsInstance(bind_mounts, set)
        self.assertEqual(len(bind_mounts), 1)
        self.assertIn('/not/a/real/bind_mount', bind_mounts)

    @patch('ansible.module_utils.facts.hardware.linux.LinuxHardware._run_findmnt', return_value=(37, '', ''))
    def test_find_bind_mounts_non_zero(self, mock_run_findmnt):
        module = Mock()
        lh = hardware.linux.LinuxHardware(module=module, load_on_init=False)
        bind_mounts = lh._find_bind_mounts()

        self.assertIsInstance(bind_mounts, set)
        self.assertEqual(len(bind_mounts), 0)

    def test_find_bind_mounts_no_findmnts(self):
        module = Mock()
        module.get_bin_path = Mock(return_value=None)
        lh = hardware.linux.LinuxHardware(module=module, load_on_init=False)
        bind_mounts = lh._find_bind_mounts()

        self.assertIsInstance(bind_mounts, set)
        self.assertEqual(len(bind_mounts), 0)

    @patch('ansible.module_utils.facts.hardware.linux.LinuxHardware._run_lsblk', return_value=(0, LSBLK_OUTPUT,''))
    def test_lsblk_uuid(self, mock_run_lsblk):
        module = Mock()
        lh = hardware.linux.LinuxHardware(module=module, load_on_init=False)
        lsblk_uuids = lh._lsblk_uuid()

        self.assertIsInstance(lsblk_uuids, dict)
        self.assertIn(b'/dev/loop9', lsblk_uuids)
        self.assertIn(b'/dev/sda1', lsblk_uuids)
        self.assertEquals(lsblk_uuids[b'/dev/sda1'], b'32caaec3-ef40-4691-a3b6-438c3f9bc1c0')

    @patch('ansible.module_utils.facts.hardware.linux.LinuxHardware._run_lsblk', return_value=(37, LSBLK_OUTPUT,''))
    def test_lsblk_uuid_non_zero(self, mock_run_lsblk):
        module = Mock()
        lh = hardware.linux.LinuxHardware(module=module, load_on_init=False)
        lsblk_uuids = lh._lsblk_uuid()

        self.assertIsInstance(lsblk_uuids, dict)
        self.assertEquals(len(lsblk_uuids), 0)

    def test_lsblk_uuid_no_lsblk(self):
        module = Mock()
        module.get_bin_path = Mock(return_value=None)
        lh = hardware.linux.LinuxHardware(module=module, load_on_init=False)
        lsblk_uuids = lh._lsblk_uuid()

        self.assertIsInstance(lsblk_uuids, dict)
        self.assertEquals(len(lsblk_uuids), 0)

    @patch('ansible.module_utils.facts.hardware.linux.LinuxHardware._run_lsblk', return_value=(0, LSBLK_OUTPUT_2,''))
    def test_lsblk_uuid_dev_with_space_in_name(self, mock_run_lsblk):
        module = Mock()
        lh = hardware.linux.LinuxHardware(module=module, load_on_init=False)
        lsblk_uuids = lh._lsblk_uuid()
        self.assertIsInstance(lsblk_uuids, dict)
        self.assertIn(b'/dev/loop0', lsblk_uuids)
        self.assertIn(b'/dev/sda1', lsblk_uuids)
        self.assertEquals(lsblk_uuids[b'/dev/mapper/an-example-mapper with a space in the name'], b'84639acb-013f-4d2f-9392-526a572b4373')
        self.assertEquals(lsblk_uuids[b'/dev/sda1'], b'32caaec3-ef40-4691-a3b6-438c3f9bc1c0')
