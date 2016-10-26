# (c) 2016, Adrian Likins <alikins@redhat.com>
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

from ansible.compat.tests import unittest

from ansible.utils import deprecation


class TestDeprecation(unittest.TestCase):
    def test(self):
        res = deprecation.check(deprecation.ALWAYS)
        self.assertEquals(res, deprecation.Results.FUTURE)

    def test_now(self):
        res = deprecation.check(deprecation.NOW)
        self.assertEquals(res, deprecation.Results.VERSION)

    def test_removed_now(self):
        self.assertRaises(deprecation.AnsibleDeprecation,
                          deprecation.check,
                          deprecation.REMOVED_NOW)

    def test_unknown(self):
        res = deprecation.check('THIS_DEPRECATION_DOESNT_EXIST')
        self.assertEquals(res, 0)

    def test_future(self):
        res = deprecation.check(deprecation.FUTURE)
        self.assertEquals(res, deprecation.Results.FUTURE)

    def test_accelerated_mode(self):
        res = deprecation.check(deprecation.ACCELERATED_MODE)
        self.assertEquals(res, deprecation.Results.FUTURE)

    def test_list(self):
        res = deprecation.list_deprecations()
        print(res)
