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
__metaclass__ = type

# for testing
from ansible.compat.tests import unittest
from ansible.compat.tests.mock import Mock, patch

from ansible.module_utils import facts

import logging
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

LSBLK_OUTPUT = """
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

FINDMNT_OUTPUT = """
/sys                            sysfs                                sysfs           rw,nosuid,nodev,noexec,relatime,seclabel
/proc                           proc                                 proc            rw,nosuid,nodev,noexec,relatime
/dev                            devtmpfs                             devtmpfs        rw,nosuid,seclabel,size=8044400k,nr_inodes=2011100,mode=755
/sys/kernel/security            securityfs                           securityfs      rw,nosuid,nodev,noexec,relatime
/dev/shm                        tmpfs                                tmpfs           rw,nosuid,nodev,seclabel
/dev/pts                        devpts                               devpts          rw,nosuid,noexec,relatime,seclabel,gid=5,mode=620,ptmxmode=000
/run                            tmpfs                                tmpfs           rw,nosuid,nodev,seclabel,mode=755
/sys/fs/cgroup                  tmpfs                                tmpfs           ro,nosuid,nodev,noexec,seclabel,mode=755
/sys/fs/cgroup/systemd          cgroup                               cgroup          rw,nosuid,nodev,noexec,relatime,xattr,release_agent=/usr/lib/systemd/systemd-cgroups-agent,name=systemd
/sys/fs/pstore                  pstore                               pstore          rw,nosuid,nodev,noexec,relatime,seclabel
/sys/fs/cgroup/devices          cgroup                               cgroup          rw,nosuid,nodev,noexec,relatime,devices
/sys/fs/cgroup/freezer          cgroup                               cgroup          rw,nosuid,nodev,noexec,relatime,freezer
/sys/fs/cgroup/memory           cgroup                               cgroup          rw,nosuid,nodev,noexec,relatime,memory
/sys/fs/cgroup/pids             cgroup                               cgroup          rw,nosuid,nodev,noexec,relatime,pids
/sys/fs/cgroup/blkio            cgroup                               cgroup          rw,nosuid,nodev,noexec,relatime,blkio
/sys/fs/cgroup/cpuset           cgroup                               cgroup          rw,nosuid,nodev,noexec,relatime,cpuset
/sys/fs/cgroup/cpu,cpuacct      cgroup                               cgroup          rw,nosuid,nodev,noexec,relatime,cpu,cpuacct
/sys/fs/cgroup/hugetlb          cgroup                               cgroup          rw,nosuid,nodev,noexec,relatime,hugetlb
/sys/fs/cgroup/perf_event       cgroup                               cgroup          rw,nosuid,nodev,noexec,relatime,perf_event
/sys/fs/cgroup/net_cls,net_prio cgroup                               cgroup          rw,nosuid,nodev,noexec,relatime,net_cls,net_prio
/sys/kernel/config              configfs                             configfs        rw,relatime
/                               /dev/mapper/fedora_dhcp129--186-root ext4            rw,relatime,seclabel,data=ordered
/sys/fs/selinux                 selinuxfs                            selinuxfs       rw,relatime
/proc/sys/fs/binfmt_misc        systemd-1                            autofs          rw,relatime,fd=24,pgrp=1,timeout=0,minproto=5,maxproto=5,direct
/sys/kernel/debug               debugfs                              debugfs         rw,relatime,seclabel
/dev/hugepages                  hugetlbfs                            hugetlbfs       rw,relatime,seclabel
/tmp                            tmpfs                                tmpfs           rw,seclabel
/dev/mqueue                     mqueue                               mqueue          rw,relatime,seclabel
/var/lib/machines               /dev/loop0                           btrfs           rw,relatime,seclabel,space_cache,subvolid=5,subvol=/
/boot                           /dev/sda1                            ext4            rw,relatime,seclabel,data=ordered
/home                           /dev/mapper/fedora_dhcp129--186-home ext4            rw,relatime,seclabel,data=ordered
/run/user/1000                  tmpfs                                tmpfs           rw,nosuid,nodev,relatime,seclabel,size=1611044k,mode=700,uid=1000,gid=1000
/run/user/1000/gvfs             gvfsd-fuse                           fuse.gvfsd-fuse rw,nosuid,nodev,relatime,user_id=1000,group_id=1000
/sys/fs/fuse/connections        fusectl                              fusectl         rw,relatime
/not/a/real/bind_mount          /dev/sdz4[/some/other/path]     ext4    rw,relatime,seclabel,data=ordered
"""

class TestFactsLinuxHardware(unittest.TestCase):

    # FIXME: mock.patch instead
    def setUp(self):
        # The @timeout tracebacks if there isn't a GATHER_TIMEOUT is None (the default until get_all_facts sets it via global)
        facts.GATHER_TIMEOUT = 10

    def tearDown(self):
        facts.GATHER_TIMEOUT = None

    # The Hardware subclasses freakout if instaniated directly, so
    # mock platform.system and inst Hardware() so we get a LinuxHardware()
    # we can test.
    @patch('ansible.module_utils.facts.LinuxHardware._mtab_entries', return_value=MTAB_ENTRIES)
    @patch('ansible.module_utils.facts.LinuxHardware._find_bind_mounts', return_value=BIND_MOUNTS)
    @patch('ansible.module_utils.facts.LinuxHardware._lsblk_uuid', return_value=LSBLK_UUIDS)
    def test_get_mount_facts(self,
                             mock_lsblk_uuid,
                             mock_find_bind_mounts,
                             mock_mtab_entries):
        module = Mock()
        # Returns a LinuxHardware-ish
        lh = facts.LinuxHardware(module=module, load_on_init=False)

        # Nothing returned, just self.facts modified as a side effect
        lh.get_mount_facts()
        self.assertIsInstance(lh.facts, dict)
        assert 'mounts' in lh.facts, "Expected a 'mounts' key on the facts dict"
        self.assertIsInstance(lh.facts['mounts'], list)
        self.assertIsInstance(lh.facts['mounts'][0], dict)

    @patch('ansible.module_utils.facts.get_file_content', return_value=MTAB)
    def test_get_mtab_entries(self, mock_get_file_content):

        module = Mock()
        lh = facts.LinuxHardware(module=module, load_on_init=False)
        mtab_entries = lh._mtab_entries()
        self.assertIsInstance(mtab_entries, list)
        self.assertIsInstance(mtab_entries[0], list)
        assert len(mtab_entries) == 34, 'expected len(mtab_entries) to be 34'

    @patch('ansible.module_utils.facts.LinuxHardware._run_findmnt', return_value=(0, FINDMNT_OUTPUT,''))
    def test_find_bind_mounts(self, mock_run_findmnt):
        module = Mock()
        lh = facts.LinuxHardware(module=module, load_on_init=False)
        bind_mounts = lh._find_bind_mounts()

        # If bind_mounts becomes another seq type, feel free to change
        self.assertIsInstance(bind_mounts, list)
        assert len(bind_mounts) == 1, 'only one bind mount expected to be found'
        assert '/not/a/real/bind_mount' in bind_mounts, 'expected /not/a/real/bind_mount in bind_mounts but it is missing'

    @patch('ansible.module_utils.facts.LinuxHardware._run_lsblk', return_value=(0, LSBLK_OUTPUT,''))
    def test_lsblk_uuid(self, mock_run_lsblk):
        module = Mock()
        lh = facts.LinuxHardware(module=module, load_on_init=False)
        lsblk_uuids = lh._lsblk_uuid()
        self.assertIsInstance(lsblk_uuids, dict)
        assert '/dev/loop9' in lsblk_uuids
        assert '/dev/sda1' in lsblk_uuids
        self.assertEquals(lsblk_uuids['/dev/sda1'], '32caaec3-ef40-4691-a3b6-438c3f9bc1c0')
