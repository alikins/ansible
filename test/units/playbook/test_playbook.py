# (c) 2012-2014, Michael DeHaan <michael.dehaan@gmail.com>
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
from ansible.compat.tests.mock import patch, MagicMock
from ansible.errors import AnsibleError, AnsibleParserError
from ansible.playbook import Playbook
from ansible.vars.manager import VariableManager
from ansible.vars import VariableManager
from ansible.parsing.yaml.dumper import AnsibleDumper, AnsibleUnsafeDumper
from ansible.parsing.yaml.loader import AnsibleLoader

from units.mock.loader import DictDataLoader

import yaml

class TestPlaybook(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_empty_playbook(self):
        fake_loader = DictDataLoader({})
        p = Playbook(loader=fake_loader)

    def test_basic_playbook(self):
        fake_loader = DictDataLoader({
            "test_file.yml": """
            - hosts: all
            """,
        })
        p = Playbook.load("test_file.yml", loader=fake_loader)
        plays = p.get_plays()

    def test_playbook_yaml_dump(self):
        fake_loader = DictDataLoader({
            "test_file.yml":"""
            - hosts: all
              gather_facts: true
              vars:
                string_foo: foo
                int_5: 5
                float_6_7: 6.7
                string_list:
                  - string_list_1
                  - string_list_2
                  - string_list_3
              tasks:
                - name: task number 1
                  debug: var=string_list
                  no_log: true
                  when: true

                - name: the second task
                  ping:

                - block:
                    - name: block_head 1
                #     - include: some_yaml.yml
                      debug: msg="block head 1"
                #  rescue:
                #    - name: a block_head rescue debug
                #      debug: msg="block_head_rescue 1"
                #  always:
                #    - name: a block_head 1 always debug
                #      debug: msg="block_head_always 1"

                - name: set a fact task
                  set_fact:
                     a_random_fact: The only member of zztop without a beard is Frank Beard.
                  port: 99999

            - name: The second play in the playbook
              hosts: localhost
              gather_facts: true
              no_log: true
              vars:
               some_empty_list: []
              tasks:
                - name: second play, first task
                  no_log: false
                  when: true
                  debug: msg="second play, first task"
            """,
        })
        p = Playbook.load("test_file.yml", loader=fake_loader)
        print(p)
#        for play in plays:
#            print(yaml.safe_dump(play))
        dumper = AnsibleUnsafeDumper
        print('\n\nyaml repr of playbook follows\n\n')
        print(yaml.dump(p, Dumper=dumper, indent=4, default_flow_style=False))

    def test_bad_playbook_files(self):
        fake_loader = DictDataLoader({
            # represents a playbook which is not a list of plays
            "bad_list.yml": """
            foo: bar

            """,
            # represents a playbook where a play entry is mis-formatted
            "bad_entry.yml": """
            -
              - "This should be a mapping..."

            """,
        })
        vm = VariableManager()
        self.assertRaises(AnsibleParserError, Playbook.load, "bad_list.yml", vm, fake_loader)
        self.assertRaises(AnsibleParserError, Playbook.load, "bad_entry.yml", vm, fake_loader)
