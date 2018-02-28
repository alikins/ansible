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

# Make coding more python3-ish
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import pprint
import string

from ansible.compat.tests import unittest

from ansible.inventory.manager import InventoryManager, split_host_pattern

from units.mock.loader import DictDataLoader


class TestInventoryManager(unittest.TestCase):
    def setUp(self):
        self.fake_loader = DictDataLoader({})

    def test(self):
        inventory_manager = InventoryManager(loader=self.fake_loader, sources=[None])
        self.assertIsInstance(inventory_manager, InventoryManager)

# 'sources' for inventoryManager can be:
# - None or not include
# - a string or text
# - a list
#   Each element in the list can be:
#     - None
#     - a comma seperated string ?
#     - a string no commas
#
#     For the string types, the string itself can refer to
#        - (str) a path to a directory that exists
#        - (str) a path to a file
#        - (str) a hostname string
#        - or really, anything a inventory plugin can try to figure out
#
#       For the path to a file cases the file can be at least:
#         - hosts list (ini)
#         - yaml
#         - a script
#
#       For the hostname string case, the string can be at least:
#         - a plain hostname (www.example.com)
#         - an 'advanced_host_list' (comma separated with ranges/slices)
#         - a template string

class TestInventoryManagerGetHosts:
    test_hosts_csv = ['testhost1,testhost2,testhost3']
    test_hosts_list = ['testhost_l1', 'testhost_l2', 'testhost_l3']

    def test(self):
        fake_loader = DictDataLoader({})
        inventory_manager = InventoryManager(loader=fake_loader, sources=[None])
        get_hosts = inventory_manager.get_hosts()
        assert isinstance(get_hosts, list)

    def test_order_sorted(self):
        fake_loader = DictDataLoader({})
        inventory_manager = InventoryManager(loader=fake_loader, sources=self.test_hosts_list)
        hosts = inventory_manager.get_hosts(order='sorted')
        assert isinstance(hosts, list)
        pprint.pprint(hosts)
        assert hosts.index('testhost_l1') < hosts.index('testhost_l2')


class TestSplitHostPattern(unittest.TestCase):
    patterns = {
        'a': ['a'],
        'a, b': ['a', 'b'],
        'a , b': ['a', 'b'],
        ' a,b ,c[1:2] ': ['a', 'b', 'c[1:2]'],
        '9a01:7f8:191:7701::9': ['9a01:7f8:191:7701::9'],
        '9a01:7f8:191:7701::9,9a01:7f8:191:7701::9': ['9a01:7f8:191:7701::9', '9a01:7f8:191:7701::9'],
        '9a01:7f8:191:7701::9,9a01:7f8:191:7701::9,foo': ['9a01:7f8:191:7701::9', '9a01:7f8:191:7701::9', 'foo'],
        'foo[1:2]': ['foo[1:2]'],
        'a::b': ['a::b'],
        'a:b': ['a', 'b'],
        ' a : b ': ['a', 'b'],
        'foo:bar:baz[1:2]': ['foo', 'bar', 'baz[1:2]'],
    }

    pattern_lists = [
        [['a'], ['a']],
        [['a', 'b'], ['a', 'b']],
        [['a, b'], ['a', 'b']],
        [['9a01:7f8:191:7701::9', '9a01:7f8:191:7701::9,foo'],
         ['9a01:7f8:191:7701::9', '9a01:7f8:191:7701::9', 'foo']]
    ]

    def test_split_patterns(self):

        for p in self.patterns:
            r = self.patterns[p]
            self.assertEqual(r, split_host_pattern(p))

        for p, r in self.pattern_lists:
            self.assertEqual(r, split_host_pattern(p))


class TestSplitSubscripts(unittest.TestCase):

    # pattern_string: [ ('base_pattern', (a,b)), ['x','y','z'] ]
    # a,b are the bounds of the subscript; x..z are the results of the subscript
    # when applied to string.ascii_letters.

    subscripts = {
        'a': [('a', None), list(string.ascii_letters)],
        'a[0]': [('a', (0, None)), ['a']],
        'a[1]': [('a', (1, None)), ['b']],
        'a[2:3]': [('a', (2, 3)), ['c', 'd']],
        'a[-1]': [('a', (-1, None)), ['Z']],
        'a[-2]': [('a', (-2, None)), ['Y']],
        'a[48:]': [('a', (48, -1)), ['W', 'X', 'Y', 'Z']],
        'a[49:]': [('a', (49, -1)), ['X', 'Y', 'Z']],
        'a[1:]': [('a', (1, -1)), list(string.ascii_letters[1:])],
    }

    ranges_to_expand = {
        'a[1:2]': ['a1', 'a2'],
        'a[1:10:2]': ['a1', 'a3', 'a5', 'a7', 'a9'],
        'a[a:b]': ['aa', 'ab'],
        'a[a:i:3]': ['aa', 'ad', 'ag'],
        'a[a:b][c:d]': ['aac', 'aad', 'abc', 'abd'],
        'a[0:1][2:3]': ['a02', 'a03', 'a12', 'a13'],
        'a[a:b][2:3]': ['aa2', 'aa3', 'ab2', 'ab3'],
    }

    def setUp(self):
        fake_loader = DictDataLoader({})

        self.i = InventoryManager(loader=fake_loader, sources=[None])

    def test_ranges(self):

        for s in self.subscripts:
            r = self.subscripts[s]
            self.assertEqual(r[0], self.i._split_subscript(s))
            self.assertEqual(
                r[1],
                self.i._apply_subscript(
                    list(string.ascii_letters),
                    r[0][1]
                )
            )
