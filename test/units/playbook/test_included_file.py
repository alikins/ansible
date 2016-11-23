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

from ansible.compat.six import string_types
from ansible.errors import AnsibleParserError
from ansible.playbook.attribute import FieldAttribute
from ansible.playbook.task import Task
from ansible.playbook.task_include import TaskInclude
from ansible.template import Templar
from ansible.executor import task_result

from ansible.playbook import included_file


from units.mock.loader import DictDataLoader


class TestIncludedFile(unittest.TestCase):
    def test(self):
        inc_file = included_file.IncludedFile(filename='somefile.yml', args=[], task=None)
        print(inc_file)

    def test_process_include_results(self):

        hostname = "testhost1"
        hostname2 = "testhost2"
        parent_task_ds = {'debug': 'msg=foo'}
        parent_task = Task()
        parent_task.load(parent_task_ds)

        task_ds = {'include': 'include_test.yml'}
        task_include = TaskInclude()
        loaded_task = task_include.load(task_ds, task_include=parent_task)
        child_task_ds = task_ds
        child_task_include = TaskInclude()
        loaded_child_task = child_task_include.load(child_task_ds, task_include=loaded_task)

        return_data = {'include': 'include_test.yml'}
        # The task in the TaskResult has to be a TaskInclude so it has a .static attr
        result1 = task_result.TaskResult(host=hostname, task=loaded_task, return_data=return_data)
        result2 = task_result.TaskResult(host=hostname2, task=loaded_child_task, return_data=return_data)
        results = [result1, result2]

        fake_loader = DictDataLoader({'include_test.yml': ""})

        mock_tqm = MagicMock(name='MockTaskQueueManager')

        mock_play = MagicMock(name='MockPlay')

        mock_iterator = MagicMock(name='MockIterator')
        mock_iterator._play = mock_play
        #mock_iterator.mark_host_failed.return_value = None
        #mock_iterator.get_next_task_for_host.return_value = (None, None)
        #mock_iterator.get_original_task.return_value = mock_task

        mock_inventory = MagicMock(name='MockInventory')
        mock_inventory._hosts_cache = dict()

        def _get_host(host_name):
            print('_get_host hostname=%s' % host_name)
            return None

        mock_inventory.get_host.side_effect = _get_host
        #mock_inventory.get_group.side_effect = _get_group
        #mock_inventory.clear_pattern_cache.return_value = None
        #mock_inventory.clear_group_dict_cache.return_value = None
        #mock_inventory.get_host_vars.return_value = {}

        # TODO: can we use a real VariableManager?
        mock_variable_manager = MagicMock(name='MockVariableManager')
        mock_variable_manager.get_vars.return_value = dict()

        res = included_file.IncludedFile.process_include_results(results, mock_tqm, mock_iterator,
                                                                 mock_inventory, fake_loader,
                                                                 mock_variable_manager)
        print(res)
        for inc_file in res:
            print('included_file=%s' % inc_file)
            print(type(inc_file))
            print(dir(inc_file))
            print('_filename=%s' % inc_file._filename)
            print('_args=%s' % inc_file._args)
            print('_tasks=%s' % inc_file._task)
            self.assertIn(hostname, inc_file._hosts)

