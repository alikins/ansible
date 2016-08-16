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
#
# Copyright 2016, Adrian Likins <alikins@redhat.com>

# Make coding more python3-ish
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from io import StringIO
import yaml
from ansible.compat.tests import unittest

# module under test
from ansible.parsing.yaml import objects
from ansible.parsing import vault
from ansible.parsing.yaml.loader import AnsibleLoader
from ansible.parsing.yaml.dumper import AnsibleDumper
# from ansible.utils.unicode import to_unicode, to_bytes, to_str

import logging
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

class NameStringIO(StringIO):
    """In py2.6, StringIO doesn't let you set name because a baseclass has it
    as readonly property"""
    name = None

    def __init__(self, *args, **kwargs):
        super(NameStringIO, self).__init__(*args, **kwargs)

def dump_load_cycle(obj, vault_password):
    '''Dump the passed in object to yaml, load it back up, dump again, compare.'''
    stream = NameStringIO()
    yaml.dump(obj, stream, Dumper=AnsibleDumper, encoding='utf-8')
    yaml_string = yaml.dump(obj, Dumper=AnsibleDumper)

    yaml_string_from_stream = stream.getvalue()
    dump_equals = yaml_string == yaml_string_from_stream

    # reset stream
    stream.seek(0)

    loader = AnsibleLoader(stream, vault_password=vault_password)
    obj_from_stream = loader.get_data()

    stream_from_string = NameStringIO(yaml_string)
    loader2 = AnsibleLoader(stream_from_string, vault_password=vault_password)
    obj_from_string = loader2.get_data()

    obj_equals = obj_from_stream == obj_from_string

    stream_obj_from_stream = NameStringIO()
    stream_obj_from_string = NameStringIO()

    yaml.dump(obj_from_stream, stream_obj_from_stream, Dumper=AnsibleDumper, encoding='utf-8')
    yaml.dump(obj_from_stream, stream_obj_from_string, Dumper=AnsibleDumper, encoding='utf-8')

    yaml_string_stream_obj_from_stream = stream_obj_from_stream.getvalue()
    yaml_string_stream_obj_from_string = stream_obj_from_string.getvalue()

    stream_obj_from_stream.seek(0)
    stream_obj_from_string.seek(0)

    yaml_string_obj_from_stream = yaml.dump(obj_from_stream, Dumper=AnsibleDumper)
    yaml_string_obj_from_string = yaml.dump(obj_from_string, Dumper=AnsibleDumper)

    assert yaml_string == yaml_string_obj_from_stream
    assert yaml_string == yaml_string_obj_from_stream == yaml_string_obj_from_string
    assert yaml_string == yaml_string_obj_from_stream == yaml_string_obj_from_string == yaml_string_stream_obj_from_stream == yaml_string_stream_obj_from_string
    assert obj == obj_from_stream
    assert obj == obj_from_string
    assert obj == yaml_string_obj_from_stream
    assert obj == yaml_string_obj_from_string
    assert obj == obj_from_stream == obj_from_string == yaml_string_obj_from_stream == yaml_string_obj_from_string
    return {'obj': obj,
            'yaml_string': yaml_string,
            'yaml_string_from_stream': yaml_string_from_stream,
            'obj_from_stream': obj_from_stream,
            'obj_from_string': obj_from_string,
            'yaml_string_obj_from_string': yaml_string_obj_from_string}


class TestAnsibleVaultUnicodeNoVault(unittest.TestCase):
    def test_empty_init(self):
        self.assertRaises(TypeError, objects.AnsibleVaultUnencryptedUnicode)

    def test_empty_string_init(self):
        seq = ''
        self.assert_values(seq)

    def _assert_values(self, avu, seq):
        self.assertIsInstance(avu, objects.AnsibleVaultUnencryptedUnicode)
        self.assertEquals(str(avu), seq)
        self.assertTrue(avu.vault is None)

    def assert_values(self, seq):
        avu = objects.AnsibleVaultUnencryptedUnicode(seq)
        self._assert_values(avu, seq)

    def test_single_char(self):
        seq = ''
        self.assert_values(seq)

    def test_string(self):
        seq = 'some letters'
        self.assert_values(seq)

class TestAnsibleVaultUnencryptedUnicode(unittest.TestCase):
    def test(self):
        seq = 'test string'
        avuu = objects.AnsibleVaultUnencryptedUnicode(seq)

        results = dump_load_cycle(avuu, vault_password='hunter42')
        log.debug('results: %s', results)


class TestAnsibleVaultEncryptedUnicode(unittest.TestCase):
    def setUp(self):
        self.vault_password = "hunter42"
        self.good_vault = vault.VaultLib(self.vault_password)

        self.wrong_vault_password = 'not-hunter42'
        self.wrong_vault = vault.VaultLib(self.wrong_vault_password)

        self.vault = self.good_vault

    def assert_values(self, avu, seq):
        self.assertIsInstance(avu, objects.AnsibleVaultEncryptedUnicode)

        self.assertEquals(avu, seq)
        self.assertTrue(avu.vault is self.vault)
        self.assertIsInstance(avu.vault, vault.VaultLib)
        log.debug('asserted')

    def _from_plaintext(self, seq):
        return objects.AnsibleVaultEncryptedUnicode.from_plaintext(seq, vault=self.vault)

    def _from_ciphertext(self, ciphertext):
        avu = objects.AnsibleVaultEncryptedUnicode(ciphertext)
        avu.vault = self.vault
        return avu

    def test_empty_init(self):
        self.assertRaises(TypeError, objects.AnsibleVaultEncryptedUnicode)

    def test_empty_string_init_from_plaintext(self):
        seq = ''
        avu = self._from_plaintext(seq)
        self.assert_values(avu,seq)

    def test_empty_unicode_init_from_plaintext(self):
        seq = u''
        avu = self._from_plaintext(seq)
        self.assert_values(avu,seq)

    def test_string_from_plaintext(self):
        seq = 'some letters'
        avu = self._from_plaintext(seq)
        self.assert_values(avu,seq)

    def test_unicode_from_plaintext(self):
        seq = u'some letters'
        avu = self._from_plaintext(seq)
        self.assert_values(avu,seq)

    # TODO/FIXME: make sure bad password fails differently than 'thats not encrypted'
    def test_empty_string_wrong_password(self):
        seq = ''
        self.vault = self.wrong_vault
        avu = self._from_plaintext(seq)
        self.assert_values(avu, seq)
