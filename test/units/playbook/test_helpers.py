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
from ansible.compat.tests.mock import MagicMock
from units.mock.loader import DictDataLoader

from ansible.compat.six import string_types
from ansible.errors import AnsibleParserError
from ansible.playbook.attribute import FieldAttribute
from ansible.playbook.task import Task
from ansible.playbook.task_include import TaskInclude
from ansible.template import Templar
from ansible.executor import task_result

from ansible.playbook import helpers


class TestLoadListOfTasks(unittest.TestCase):
    def test_ds_not_list(self):
        ds = {}
        mock_play = MagicMock(name='MockPlay')
        self.assertRaises(AssertionError, helpers.load_list_of_tasks,
                          ds, mock_play, block=None, role=None, task_include=None, use_handlers=False, variable_manager=None, loader=None)

    def test_empty_task(self):
        ds = [{}]
        mock_play = MagicMock(name='MockPlay')
        res = helpers.load_list_of_tasks(ds, mock_play, block=None, role=None, task_include=None, use_handlers=False, variable_manager=None, loader=None)
        print(res)

    def test_empty_task_use_handlers(self):
        ds = [{}]
        mock_play = MagicMock(name='MockPlay')
        res = helpers.load_list_of_tasks(ds, mock_play, block=None, role=None, task_include=None, use_handlers=True, variable_manager=None, loader=None)
        print(res)

    def test_one_bogus_block(self):
        ds = [{'block': True}]
        mock_play = MagicMock(name='MockPlay')
        res = helpers.load_list_of_tasks(ds, mock_play, block=None, role=None, task_include=None, use_handlers=False, variable_manager=None, loader=None)
        print(res)

    def test_block_unknown_action(self):
        ds = [{'action': 'foo'}]
        mock_play = MagicMock(name='MockPlay')
        res = helpers.load_list_of_tasks(ds, mock_play, block=None, role=None, task_include=None, use_handlers=False, variable_manager=None, loader=None)
        print(res)

    def test_one_bogus_block_use_handlers(self):
        ds = [{'block': True}]
        mock_play = MagicMock(name='MockPlay')
        res = helpers.load_list_of_tasks(ds, mock_play, block=None, role=None, task_include=None, use_handlers=True, variable_manager=None, loader=None)
        print(res)

    def test_one_bogus_include(self):
        ds = [{'include': 'somefile.yml'}]
        mock_play = MagicMock(name='MockPlay')
        res = helpers.load_list_of_tasks(ds, mock_play, block=None, role=None, task_include=None, use_handlers=False, variable_manager=None, loader=None)
        print(res)

    def test_one_bogus_include_use_handlers(self):
        ds = [{'include': 'somefile.yml'}]
        mock_play = MagicMock(name='MockPlay')
        res = helpers.load_list_of_tasks(ds, mock_play, block=None, role=None, task_include=None, use_handlers=True, variable_manager=None, loader=None)
        print(res)

    def test_one_bogus_include_role(self):
        ds = [{'include_role': {'name': 'bogus_role'}}]
        mock_play = MagicMock(name='MockPlay')
        res = helpers.load_list_of_tasks(ds, mock_play, block=None, role=None, task_include=None, use_handlers=False, variable_manager=None, loader=None)
        print(res)

    def test_one_bogus_include_role_use_handlers(self):
        ds = [{'include_role': {'name': 'bogus_role'}}]
        mock_play = MagicMock(name='MockPlay')
        res = helpers.load_list_of_tasks(ds, mock_play, block=None, role=None, task_include=None, use_handlers=True, variable_manager=None, loader=None)
        print(res)


class TestLoadListOfRoles(unittest.TestCase):
    def test_ds_not_list(self):
        ds = {}
        mock_play = MagicMock(name='MockPlay')
        self.assertRaises(AssertionError, helpers.load_list_of_roles,
                          ds, mock_play)

    def test_empty_role(self):
        ds = [{}]
        mock_play = MagicMock(name='MockPlay')
        res = helpers.load_list_of_roles(ds, mock_play)
        print(res)

    def test_empty_role_just_name(self):
        ds = [{'name': 'testrole'}]
        mock_play = MagicMock(name='MockPlay')
        res = helpers.load_list_of_roles(ds, mock_play)
        print(res)


class TestLoadListOfBlocks(unittest.TestCase):
    def test_ds_not_list(self):
        ds = {}
        mock_play = MagicMock(name='MockPlay')
        self.assertRaises(AssertionError, helpers.load_list_of_blocks,
                          ds, mock_play, parent_block=None, role=None, task_include=None, use_handlers=False, variable_manager=None, loader=None)

    def test_empty_block(self):
        ds = [{}]
        mock_play = MagicMock(name='MockPlay')
        res = helpers.load_list_of_blocks(ds, mock_play, parent_block=None, role=None, task_include=None, use_handlers=False, variable_manager=None, loader=None)
        print(res)

    def test_block_unknown_action(self):
        ds = [{'action': 'foo'}]
        mock_play = MagicMock(name='MockPlay')
        res = helpers.load_list_of_blocks(ds, mock_play, parent_block=None, role=None, task_include=None, use_handlers=False, variable_manager=None, loader=None)
        print(res)
