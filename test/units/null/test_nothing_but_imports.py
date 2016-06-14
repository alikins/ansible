# (c) 2016 Red Hat
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

from operator import attrgetter


class TestNothingButImports(unittest.TestCase):
    def test_cli_import(self):
        from ansible import cli

    def test_compat_import(self):
        from ansible import compat

    def test_config_import(self):
        from ansible import config

    def test_constants_import(self):
        from ansible import constants

    def test_errors_import(self):
        from ansible import errors

    def test_executor_import(self):
        from ansible import executor

    def test_executor_process_import(self):
        from ansible.executor import process

    def test_galaxy_import(self):
        from ansible import galaxy

    def test_inventory_import(self):
        from ansible import inventory

    def test_inventory_vars_plugins_import(self):
        from ansible.inventory import vars_plugins

    def test_module_utils_import(self):
        from ansible import module_utils

    def test_new_inventory_import(self):
        from ansible import new_inventory

    def test_parsing_import(self):
        from ansible import parsing

    def test_parsing_vault_import(self):
        from ansible.parsing import vault

    def test_parsing_utils_import(self):
        from ansible.parsing import utils

    def test_parsing_yaml_import(self):
        from ansible.parsing import yaml

    def test_playbook_import(self):
        from ansible import playbook

    def test_playbook_role_import(self):
        from ansible.playbook import role

    def test_plugins_import(self):
        from ansible import plugins
        from ansible.plugins import callback
        from ansible.plugins import cache
        from ansible.plugins import connection
        from ansible.plugins import filter
        from ansible.plugins import inventory
        from ansible.plugins import lookup
        from ansible.plugins import shell
        from ansible.plugins import strategy
        from ansible.plugins import test
        from ansible.plugins import vars

    def test_plugins_import_actions(self):
        from ansible.plugins import action
        from ansible.plugins.action import add_host, assemble, copy, debug, eos_template, fail, fetch
        from ansible.plugins.action import group_by, include_vars, ios_template, iosxr_template, junos_template, net_template, normal
        from ansible.plugins.action import nxos_template, ops_template, package, patch, pause, raw, script, service, set_fact
        from ansible.plugins.action import synchronize, template, unarchive, win_copy, win_reboot, win_template
        from ansible.plugins.action import async as async_action
        #from ansible.plugins.actions import assert as assert_action

    def test_release_import(self):
        from ansible import release

    def test_template_import(self):
        from ansible import template
        from ansible.template import safe_eval, template, vars

    def test_utils_import(self):
        from ansible import utils
        from ansible.utils import boolean, cmd_functions, color, display, encrypt, hashing, listify, module_docs, path, shlex, unicode, vars

    def test_vars_import(self):
        from ansible import vars
        from ansible.vars import unsafe_proxy
        from ansible.vars import hostvars


def tearDown():
    modset = set([])
    import sys
    for name, mod in sys.modules.items():
        if not mod:
            continue
        if hasattr(mod, '__file__'):
            path = mod.__file__
            if path.startswith('/Users/adrian/src/ansible/'):
                continue
            if path.startswith('/System/Library/Frameworks/Python.framework/Versions/2.7/lib/python2.7/'):
                continue
            modset.add(mod)

    for mod in sorted(list(modset), key=attrgetter('__name__')):
        print('%s %s %s' % (mod.__name__, mod.__package__, mod.__file__))
