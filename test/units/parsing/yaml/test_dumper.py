# coding: utf-8
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

import io
import yaml

try:
    from _yaml import ParserError
except ImportError:
    from yaml.parser import ParserError

from ansible.parsing.yaml import dumper
from ansible.parsing.yaml.loader import AnsibleLoader

from ansible.compat.tests import unittest
from ansible.parsing.yaml import objects
from ansible.parsing import vault
from ansible.compat.six import PY3

import logging
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

# FIXME: move somewhere shared
class NameStringIO(io.StringIO):
    """In py2.6, StringIO doesn't let you set name because a baseclass has it
    as readonly property"""
    name = None

    def __init__(self, *args, **kwargs):
        super(NameStringIO, self).__init__(*args, **kwargs)

class TestAnsibleDumper(unittest.TestCase):
    def setUp(self):
        self.vault_password = "hunter42"
        self.good_vault = vault.VaultLib(self.vault_password)
        self.vault = self.good_vault
        self.stream = self._build_stream()
        self.dumper = dumper.AnsibleDumper

    def _build_stream(self,yaml_text=None):
        text = yaml_text or u''
        stream = NameStringIO(text)
        stream.name = 'my.yml'
        return stream

    def _dump(self, obj, Dumper=None):
        if PY3:
            return yaml.dump(obj, Dumper=Dumper)
        else:
            return yaml.dump(obj, Dumper=Dumper, encoding=None)

    def test(self):
        plaintext = 'This is a string we are going to encrypt.'
        avu = objects.AnsibleVaultEncryptedUnicode.from_plaintext(plaintext, vault=self.vault)
        log.debug('avu: %s', avu)
        log.debug('type(avu): %s', type(avu))

        yaml_out = self._dump(avu, Dumper=self.dumper)
        log.debug('yaml_out: %s', yaml_out)

        stream = self._build_stream(yaml_out)
        log.debug('self.stream: %s', self.stream.getvalue())
        loader = AnsibleLoader(stream, vault_password=self.vault_password)
        data_from_yaml = loader.get_single_data()
        log.debug('data_from_yaml %s', data_from_yaml)

