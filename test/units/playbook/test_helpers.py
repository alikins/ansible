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

import os

from ansible.compat.tests import unittest
from ansible.compat.tests.mock import MagicMock
from units.mock.loader import DictDataLoader

from ansible.compat.six import string_types
from ansible.errors import AnsibleParserError
from ansible.playbook.attribute import FieldAttribute
from ansible.playbook.block import Block
from ansible.playbook.task import Task
from ansible.playbook.task_include import TaskInclude
from ansible.template import Templar
from ansible.executor import task_result

from ansible.playbook import helpers


class MixinForMocks(object):
    def _setup(self):
        # This is not a very good mixin, lots of side effects
        self.fake_loader = DictDataLoader({'include_test.yml': "",
                                           'other_include_test.yml': ""})
        self.mock_tqm = MagicMock(name='MockTaskQueueManager')

        self.mock_play = MagicMock(name='MockPlay')

        self.mock_iterator = MagicMock(name='MockIterator')
        self.mock_iterator._play = self.mock_play

        self.mock_inventory = MagicMock(name='MockInventory')
        self.mock_inventory._hosts_cache = dict()

        def _get_host(host_name):
            print('_get_host hostname=%s' % host_name)
            return None

        self.mock_inventory.get_host.side_effect = _get_host
        # TODO: can we use a real VariableManager?
        self.mock_variable_manager = MagicMock(name='MockVariableManager')
        self.mock_variable_manager.get_vars.return_value = dict()

        self.mock_block = MagicMock(name='MockBlock')

        self.fake_role_loader = DictDataLoader({"/etc/ansible/roles/bogus_role/tasks/main.yml": """
                                                - shell: echo 'hello world'
                                                """})

        self._test_data_path = os.path.dirname(__file__)
        self.fake_include_loader = DictDataLoader({"/dev/null/includes/test_include.yml": """
                                                   - include: other_test_include.yml
                                                   - shell: echo 'hello world'
                                                   """,
                                                   "/dev/null/includes/static_test_include.yml": """
                                                   - include: other_test_include.yml
                                                   - shell: echo 'hello static world'
                                                   """,
                                                   "/dev/null/includes/other_test_include.yml": """
                                                   - debug:
                                                       msg: other_test_include_debug
                                                   """})


class TestLoadListOfTasks(unittest.TestCase, MixinForMocks):
    def setUp(self):
        self._setup()

    def test_ds_not_list(self):
        ds = {}
        self.assertRaises(AssertionError, helpers.load_list_of_tasks,
                          ds, self.mock_play, block=None, role=None, task_include=None, use_handlers=False, variable_manager=None, loader=None)

    def test_empty_task(self):
        ds = [{}]
        res = helpers.load_list_of_tasks(ds, play=self.mock_play,
                                         variable_manager=self.mock_variable_manager, loader=self.fake_loader)
        print(res)

    def test_empty_task_use_handlers(self):
        ds = [{}]
        res = helpers.load_list_of_tasks(ds, play=self.mock_play, use_handlers=True,
                                         variable_manager=self.mock_variable_manager, loader=self.fake_loader)
        print(res)

    def test_one_bogus_block(self):
        ds = [{'block': None}]
        res = helpers.load_list_of_tasks(ds, play=self.mock_play,
                                         variable_manager=self.mock_variable_manager, loader=self.fake_loader)
        print(res)

    def test_unknown_action(self):
        ds = [{'action': 'foo_test_unknown_action'}]
        res = helpers.load_list_of_tasks(ds, play=self.mock_play,
                                         variable_manager=self.mock_variable_manager, loader=self.fake_loader)
        print(res)

    def test_block_unknown_action(self):
        ds = [{
            'block': [{'action': 'foo_test_block_unknown_action'}]
        }]
        res = helpers.load_list_of_tasks(ds, play=self.mock_play,
                                         variable_manager=self.mock_variable_manager, loader=self.fake_loader)
        print(res)

    def test_block_unknown_action_use_handlers(self):
        ds = [{
            'block': [{'action': 'foo_test_block_unknown_action'}]
        }]
        res = helpers.load_list_of_tasks(ds, play=self.mock_play, use_handlers=True,
                                         variable_manager=self.mock_variable_manager, loader=self.fake_loader)
        print(res)

    def test_one_bogus_block_use_handlers(self):
        ds = [{'block': True}]
        res = helpers.load_list_of_tasks(ds, play=self.mock_play, use_handlers=True,
                                         variable_manager=self.mock_variable_manager, loader=self.fake_loader)
        print(res)

    def test_one_bogus_include(self):
        ds = [{'include': 'somefile.yml'}]
        res = helpers.load_list_of_tasks(ds, play=self.mock_play,
                                         variable_manager=self.mock_variable_manager, loader=self.fake_loader)
        print(res)

    def test_one_bogus_include_use_handlers(self):
        ds = [{'include': 'somefile.yml'}]
        res = helpers.load_list_of_tasks(ds, play=self.mock_play, use_handlers=True,
                                         variable_manager=self.mock_variable_manager, loader=self.fake_loader)
        print(res)

    def test_one_bogus_include_static(self):
        ds = [{'include': 'somefile.yml',
               'static': 'true'}]
        res = helpers.load_list_of_tasks(ds, play=self.mock_play,
                                         variable_manager=self.mock_variable_manager, loader=self.fake_loader)
        print(res)

    def test_one_include(self):
        ds = [{'include': '/dev/null/includes/other_test_include.yml'}]
        res = helpers.load_list_of_tasks(ds, play=self.mock_play,
                                         variable_manager=self.mock_variable_manager, loader=self.fake_include_loader)
        print(res)

    def test_one_parent_include(self):
        ds = [{'include': '/dev/null/includes/test_include.yml'}]
        res = helpers.load_list_of_tasks(ds, play=self.mock_play,
                                         variable_manager=self.mock_variable_manager, loader=self.fake_include_loader)
        print(res)

    # TODO/FIXME: do this non deprecated way
    def test_one_include_tags(self):
        ds = [{'include': '/dev/null/includes/other_test_include.yml',
               'tags': ['test_one_include_tags_tag1', 'and_another_tagB']
               }]
        res = helpers.load_list_of_tasks(ds, play=self.mock_play,
                                         variable_manager=self.mock_variable_manager, loader=self.fake_include_loader)
        print(res)

    # TODO/FIXME: do this non deprecated way
    def test_one_parent_include_tags(self):
        ds = [{'include': '/dev/null/includes/test_include.yml',
               #'vars': {'tags': ['test_one_parent_include_tags_tag1', 'and_another_tag2']}
               'tags': ['test_one_parent_include_tags_tag1', 'and_another_tag2']
               }
              ]
        res = helpers.load_list_of_tasks(ds, play=self.mock_play,
                                         variable_manager=self.mock_variable_manager, loader=self.fake_include_loader)
        print(res)

    # It would be useful to be able to tell what kind of deprecation we encountered and where we encountered it.
    def test_one_include_tags_deprecated_mixed(self):
        ds = [{'include': "/dev/null/includes/other_test_include.yml",
               'vars': {'tags': "['tag_on_include1', 'tag_on_include2']"},
               'tags': 'mixed_tag1, mixed_tag2'
               }]
        self.assertRaisesRegexp(AnsibleParserError, 'Mixing styles',
                                helpers.load_list_of_tasks,
                                ds, play=self.mock_play,
                                variable_manager=self.mock_variable_manager, loader=self.fake_include_loader)

    def test_one_include_tags_deprecated_include(self):
        ds = [{'include': '/dev/null/includes/other_test_include.yml',
               'vars': {'tags': ['include_tag1_deprecated', 'and_another_tagB_deprecated']}
               }]
        res = helpers.load_list_of_tasks(ds, play=self.mock_play,
                                         variable_manager=self.mock_variable_manager, loader=self.fake_include_loader)
        print(res)

    def test_one_include_use_handlers(self):
        ds = [{'include': '/dev/null/includes/other_test_include.yml'}]
        res = helpers.load_list_of_tasks(ds, play=self.mock_play,
                                         use_handlers=True,
                                         variable_manager=self.mock_variable_manager, loader=self.fake_include_loader)
        print(res)

    def test_one_parent_include_use_handlers(self):
        ds = [{'include': '/dev/null/includes/test_include.yml'}]
        res = helpers.load_list_of_tasks(ds, play=self.mock_play,
                                         use_handlers=True,
                                         variable_manager=self.mock_variable_manager, loader=self.fake_include_loader)
        print(res)

    # TODO/FIXME: this doesn't seen right
    #  figure out how to get the non-static errors to be raised, this seems to just ignore everything
    def test_one_include_not_static(self):
        ds = [{
            'include': '/dev/null/includes/static_test_include.yml',
            'static': False
        }]
        #a_block = Block()
        ti_ds = {'include': '/dev/null/includes/ssdftatic_test_include.yml'}
        a_task_include = TaskInclude()
        ti = a_task_include.load(ti_ds)
        res = helpers.load_list_of_tasks(ds, play=self.mock_play,
                                         block=ti,
                                         variable_manager=self.mock_variable_manager, loader=self.fake_include_loader)
        print(res)

    # TODO/FIXME: This two get stuck trying to make a mock_block into a TaskInclude
#    def test_one_include(self):
#        ds = [{'include': 'other_test_include.yml'}]
#        res = helpers.load_list_of_tasks(ds, play=self.mock_play,
#                                         block=self.mock_block,
#                                         variable_manager=self.mock_variable_manager, loader=self.fake_include_loader)
#        print(res)

#    def test_one_parent_include(self):
#        ds = [{'include': 'test_include.yml'}]
#        res = helpers.load_list_of_tasks(ds, play=self.mock_play,
#                                         block=self.mock_block,
#                                         variable_manager=self.mock_variable_manager, loader=self.fake_include_loader)
#        print(res)

    def test_one_bogus_include_role(self):

        ds = [{'include_role': {'name': 'bogus_role'}}]
        res = helpers.load_list_of_tasks(ds, play=self.mock_play,
                                         block=self.mock_block,
                                         variable_manager=self.mock_variable_manager, loader=self.fake_role_loader)
        print(res)

    def test_one_bogus_include_role_use_handlers(self):
        ds = [{'include_role': {'name': 'bogus_role'}}]
        res = helpers.load_list_of_tasks(ds, play=self.mock_play, use_handlers=True,
                                         block=self.mock_block,
                                         variable_manager=self.mock_variable_manager, loader=self.fake_role_loader)
        print(res)


class TestLoadListOfRoles(unittest.TestCase, MixinForMocks):
    def setUp(self):
        self._setup()

    def test_ds_not_list(self):
        ds = {}
        self.assertRaises(AssertionError, helpers.load_list_of_roles,
                          ds, self.mock_play)

    def test_empty_role(self):
        ds = [{}]
        res = helpers.load_list_of_roles(ds, self.mock_play,
                                         variable_manager=self.mock_variable_manager, loader=self.fake_role_loader)
        print(res)

    def test_empty_role_just_name(self):
        ds = [{'name': 'bogus_role'}]
        res = helpers.load_list_of_roles(ds, self.mock_play,
                                         variable_manager=self.mock_variable_manager, loader=self.fake_role_loader)
        print(res)

    def test_block_unknown_action(self):
        ds = [{
            'block': [{'action': 'foo_test_block_unknown_action'}]
        }]
        ds = [{'name': 'bogus_role'}]
        res = helpers.load_list_of_roles(ds, self.mock_play,
                                         variable_manager=self.mock_variable_manager, loader=self.fake_role_loader)
        print(res)


class TestLoadListOfBlocks(unittest.TestCase, MixinForMocks):
    def setUp(self):
        self._setup()

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
