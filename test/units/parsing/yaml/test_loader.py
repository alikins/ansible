# coding: utf-8
# (c) 2015, Toshio Kuratomi <tkuratomi@ansible.com>
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

from io import StringIO

from six import text_type, binary_type
from collections import Sequence, Set, Mapping

import yaml

from ansible.compat.tests import unittest

from ansible import errors
from ansible.parsing.yaml.loader import AnsibleLoader
from ansible.parsing import vault
from ansible.parsing.yaml.objects import AnsibleVaultEncryptedUnicode
from ansible.parsing.yaml.dumper import AnsibleDumper
from ansible.utils.unicode import to_bytes

try:
    from _yaml import ParserError
except ImportError:
    from yaml.parser import ParserError

import logging
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

class NameStringIO(StringIO):
    """In py2.6, StringIO doesn't let you set name because a baseclass has it
    as readonly property"""
    name = None

    def __init__(self, *args, **kwargs):
        super(NameStringIO, self).__init__(*args, **kwargs)

class TestAnsibleLoaderBasic(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_parse_number(self):
        stream = StringIO(u"""
                1
                """)
        loader = AnsibleLoader(stream, 'myfile.yml')
        data = loader.get_single_data()
        self.assertEqual(data, 1)
        # No line/column info saved yet

    def test_parse_string(self):
        stream = StringIO(u"""
                Ansible
                """)
        loader = AnsibleLoader(stream, 'myfile.yml')
        data = loader.get_single_data()
        self.assertEqual(data, u'Ansible')
        self.assertIsInstance(data, text_type)

        self.assertEqual(data.ansible_pos, ('myfile.yml', 2, 17))

    def test_parse_utf8_string(self):
        stream = StringIO(u"""
                Cafè Eñyei
                """)
        loader = AnsibleLoader(stream, 'myfile.yml')
        data = loader.get_single_data()
        self.assertEqual(data, u'Cafè Eñyei')
        self.assertIsInstance(data, text_type)

        self.assertEqual(data.ansible_pos, ('myfile.yml', 2, 17))

    def test_parse_dict(self):
        stream = StringIO(u"""
                webster: daniel
                oed: oxford
                """)
        loader = AnsibleLoader(stream, 'myfile.yml')
        data = loader.get_single_data()
        self.assertEqual(data, {'webster': 'daniel', 'oed': 'oxford'})
        self.assertEqual(len(data), 2)
        self.assertIsInstance(list(data.keys())[0], text_type)
        self.assertIsInstance(list(data.values())[0], text_type)

        # Beginning of the first key
        self.assertEqual(data.ansible_pos, ('myfile.yml', 2, 17))

        self.assertEqual(data[u'webster'].ansible_pos, ('myfile.yml', 2, 26))
        self.assertEqual(data[u'oed'].ansible_pos, ('myfile.yml', 3, 22))

    def test_parse_list(self):
        stream = StringIO(u"""
                - a
                - b
                """)
        loader = AnsibleLoader(stream, 'myfile.yml')
        data = loader.get_single_data()
        self.assertEqual(data, [u'a', u'b'])
        self.assertEqual(len(data), 2)
        self.assertIsInstance(data[0], text_type)

        self.assertEqual(data.ansible_pos, ('myfile.yml', 2, 17))

        self.assertEqual(data[0].ansible_pos, ('myfile.yml', 2, 19))
        self.assertEqual(data[1].ansible_pos, ('myfile.yml', 3, 19))

    def test_parse_short_dict(self):
        stream = StringIO(u"""{"foo": "bar"}""")
        loader = AnsibleLoader(stream, 'myfile.yml')
        data = loader.get_single_data()
        self.assertEqual(data, dict(foo=u'bar'))

        self.assertEqual(data.ansible_pos, ('myfile.yml', 1, 1))
        self.assertEqual(data[u'foo'].ansible_pos, ('myfile.yml', 1, 9))

        stream = StringIO(u"""foo: bar""")
        loader = AnsibleLoader(stream, 'myfile.yml')
        data = loader.get_single_data()
        self.assertEqual(data, dict(foo=u'bar'))

        self.assertEqual(data.ansible_pos, ('myfile.yml', 1, 1))
        self.assertEqual(data[u'foo'].ansible_pos, ('myfile.yml', 1, 6))

    def test_error_conditions(self):
        stream = StringIO(u"""{""")
        loader = AnsibleLoader(stream, 'myfile.yml')
        self.assertRaises(ParserError, loader.get_single_data)

    def test_front_matter(self):
        stream = StringIO(u"""---\nfoo: bar""")
        loader = AnsibleLoader(stream, 'myfile.yml')
        data = loader.get_single_data()
        self.assertEqual(data, dict(foo=u'bar'))

        self.assertEqual(data.ansible_pos, ('myfile.yml', 2, 1))
        self.assertEqual(data[u'foo'].ansible_pos, ('myfile.yml', 2, 6))

        # Initial indent (See: #6348)
        stream = StringIO(u""" - foo: bar\n   baz: qux""")
        loader = AnsibleLoader(stream, 'myfile.yml')
        data = loader.get_single_data()
        self.assertEqual(data, [{u'foo': u'bar', u'baz': u'qux'}])

        self.assertEqual(data.ansible_pos, ('myfile.yml', 1, 2))
        self.assertEqual(data[0].ansible_pos, ('myfile.yml', 1, 4))
        self.assertEqual(data[0][u'foo'].ansible_pos, ('myfile.yml', 1, 9))
        self.assertEqual(data[0][u'baz'].ansible_pos, ('myfile.yml', 2, 9))


class TestAnsibleLoaderVault(unittest.TestCase):
    def setUp(self):
        self.vault_password = "hunter42"
        self.vault = vault.VaultLib(self.vault_password)

    def test_wrong_password(self):
        plaintext = u"Ansible"
        bob_password = "this is a different password"

        bobs_vault = vault.VaultLib(bob_password)

        ciphertext = bobs_vault.encrypt(plaintext)
        try:
            self.vault.decrypt(ciphertext)
        except Exception as e:
            self.assertIsInstance(e, errors.AnsibleError)
            self.assertEqual(e.message, 'Decryption failed')

    def _encrypt_plaintext(self, plaintext):
        # Construct a yaml repr of a vault by hand
        vaulted_var_bytes = self.vault.encrypt(plaintext)

        # add yaml tag
        vaulted_var = vaulted_var_bytes.decode()
        lines = vaulted_var.splitlines()
        lines2 = []
        for line in lines:
            lines2.append('        %s' % line)

        vaulted_var = '\n'.join(lines2)
        tagged_vaulted_var = u"""!vault-encrypted |\n%s""" % vaulted_var
        return tagged_vaulted_var

    def _build_stream(self, yaml_text):
        stream = NameStringIO(yaml_text)
        stream.name = 'my.yml'
        return stream

    # DEBUG methods

    # show yaml stream parsing events
    def _yaml_events(self, yaml_text):
        stream = self._build_stream(yaml_text)
        for event in yaml.parse(stream):
            log.debug('yaml_parse event: %s', event)

    # show the yaml tree/ast
    def _yaml_compose(self, yaml_text):
        log.debug('yaml_compose: %s', yaml.compose(yaml_text))

    # show the yaml tokens
    def _yaml_scan(self, yaml_text):
        stream = self._build_stream(yaml_text)
        for token in yaml.scan(stream):
            log.debug('yaml.scan token: %s', token)

    def _yaml_innards(self, yaml_text):
        self._yaml_scan(yaml_text)
        self._yaml_events(yaml_text)
        self._yaml_compose(yaml_text)

    def _load_yaml(self, yaml_text, password):
        #print('yaml_text')
        #print('|%s|' % yaml_text.encode('utf-8'))

        # self._yaml_innards(yaml_text)
        stream = self._build_stream(yaml_text)

        loader = AnsibleLoader(stream, vault_password=password)

        data_from_yaml = loader.get_single_data()
        #print('data_from_yaml=|%s|' % data_from_yaml)
        #print('type(dfy)=%s' % type(data_from_yaml))

        return data_from_yaml

    def _dump_load_cycle(self, obj):
        '''Dump the passed in object to yaml, load it back up, dump again, compare.'''
        stream = NameStringIO()
        yaml.dump(obj, stream, Dumper=AnsibleDumper, encoding='utf-8')
        yaml_string = yaml.dump(obj, Dumper=AnsibleDumper)

        yaml_string_from_stream = stream.getvalue()
        dump_equals = yaml_string == yaml_string_from_stream

        # reset stream
        stream.seek(0)

        loader = AnsibleLoader(stream, vault_password=self.vault_password)
        obj_from_stream = loader.get_data()

        stream_from_string = NameStringIO(yaml_string)
        loader2 = AnsibleLoader(stream_from_string, vault_password=self.vault_password)
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

    def test_dump_load_cycle(self):
        avu = AnsibleVaultEncryptedUnicode.from_plaintext('The plaintext for test_dump_load_cycle.', vault=self.vault)
        results = self._dump_load_cycle(avu)
        log.debug('dump_load_results: %s', results)

    def test_embedded_vault_from_dump(self):
        avu = AnsibleVaultEncryptedUnicode.from_plaintext('setec astronomy', vault=self.vault)
        blip = {'stuff1': [{'a dict key': 24},
                           {'shhh-ssh-secrets': avu,
                            'nothing to see here': 'move along'}],
                'another key': 24.1}

        blip = ['some string', 'another string', avu]
        #stream = self._build_stream('')
        stream = NameStringIO(u'')
        yaml.dump(blip, stream, Dumper=AnsibleDumper, encoding='utf-8')
        log.debug('stream: %s', stream.getvalue())
        stream.seek(0)

        for token in yaml.scan(stream):
            log.debug('yaml.scan token: %s', token)
        for event in yaml.parse(stream):
            log.debug('yaml_parse event: %s', event)

        stream.seek(0)
        loader = AnsibleLoader(stream, vault_password=self.vault_password)

        data_from_yaml = loader.get_data()
        #data_from_yaml = loader.get_single_data()
        log.debug('data_from_yaml: %s', data_from_yaml)
        log.debug('data_from_yaml[2]: %s', type(data_from_yaml[2]._ciphertext))
        #vault_string = data_from_yaml['the_secret']
        stream2 = NameStringIO(u'')
        yaml.dump(data_from_yaml, stream2, Dumper=AnsibleDumper, encoding='utf-8')
        log.debug('stream: %s', stream2.getvalue())
        stream2.seek(0)
        #log.debug('vault_string: %s', vault_string)

    def test_embedded_vault(self):
        plaintext_var = u"""This is the plaintext string."""
        tagged_vaulted_var = self._encrypt_plaintext(plaintext_var)
        another_vaulted_var = self._encrypt_plaintext(plaintext_var)

        different_var = u"""A different string that is not the same as the first one."""
        different_vaulted_var = self._encrypt_plaintext(different_var)

        yaml_text = u"""---\nwebster: daniel\noed: oxford\nthe_secret: %s\nanother_secret: %s\ndifferent_secret: %s""" % (tagged_vaulted_var, another_vaulted_var, different_vaulted_var)

        data_from_yaml = self._load_yaml(yaml_text, self.vault_password)
        vault_string = data_from_yaml['the_secret']

        #print('vault_string %s type(vault_string): %s str(vault_string): %s' % (vault_string, type(vault_string), str(vault_string)))

        log.debug('vault_string: %s', vault_string)
        log.debug('type(vault_string): %s', type(vault_string))
        log.debug('str(vault_string): %s', str(vault_string))

        self.assertEquals(plaintext_var, data_from_yaml['the_secret'])

        test_dict = {}
        test_dict[vault_string] = 'did this work?'

        log.debug('test_dict %s', test_dict)
        log.debug('test_dict[vault_string] %s', test_dict[vault_string])
        log.debug('hash(vault_string): %s', hash(vault_string))

        is_eql = vault_string.data == vault_string
        is_eql2 = vault_string == vault_string

        log.debug('vault_string.data == vault_string %s', is_eql)
        log.debug('vault_string == vault_string %s', is_eql2)

        another_vault_string = data_from_yaml['another_secret']
        different_vault_string = data_from_yaml['different_secret']

        is_eql3 = vault_string == another_vault_string
        is_eql4 = vault_string == different_vault_string

        log.debug('vault_string == another_vault_string: %s', is_eql3)
        log.debug('vault_string == different_vault_string: %s', is_eql4)

        str_eq = 'some string' == vault_string
        str_eq2 = plaintext_var == vault_string

        log.debug('\'some string\' == vault_string: %s', str_eq)
        log.debug('plaintext_var == vault_string: %s', str_eq2)

        str_neq = 'some string' != vault_string
        str_neq2 = plaintext_var != vault_string
        
        log.debug('\'some string\' != vault_string: %s', str_neq)
        log.debug('plaintext_var != vault_string: %s', str_neq2)

    # def test_embedded_vault_list(self):
        # sample_list = ['amen break', 'funky drummer']
        # sample_yaml = yaml.dump(sample_list)
        # print('sample_yaml %s' % sample_yaml)

        # tagged_vaulted_var = self._encrypt_plaintext(sample_yaml)
        # yaml_text = u"""---\nwebster: daniel\noed: oxford\nthe_secret_sample_list: %s""" % tagged_vaulted_var

        # data_from_yaml = self._load_yaml(yaml_text, self.vault_password)
        # print('data_from_yaml %s' % data_from_yaml)

    # def test_embedded_vault_map(self):
        # map_map = {'mercator': ['
        # 'peters': ['c', 'f', 'sa']}
        # map_map_yaml = yaml.dump(map_map)
        # print('map_map_yaml: %s' % map_map_yaml)

        # tagged_vaulted_var = self._encrypt_plaintext(map_map_yaml)
        # yaml_text = u"""---\nwebster: daniel\nthe_secret_map_map: %s\noed: exford""" % tagged_vaulted_var

        # data_from_yaml = self._load_yaml(yaml_text, self.vault_password)
        # print('data_from_yaml %s' % data_from_yaml)
        # # verify we get a map of some sort
        # assert not isinstance(data_from_yaml['the_secret_map_map'], (unicode, str, bytes))


class TestAnsibleLoaderPlay(unittest.TestCase):

    def setUp(self):
        stream = NameStringIO(u"""
                - hosts: localhost
                  vars:
                    number: 1
                    string: Ansible
                    utf8_string: Cafè Eñyei
                    dictionary:
                      webster: daniel
                      oed: oxford
                    list:
                      - a
                      - b
                      - 1
                      - 2
                  tasks:
                    - name: Test case
                      ping:
                        data: "{{ utf8_string }}"

                    - name: Test 2
                      ping:
                        data: "Cafè Eñyei"

                    - name: Test 3
                      command: "printf 'Cafè Eñyei\\n'"
                """)
        self.play_filename = '/path/to/myplay.yml'
        stream.name = self.play_filename
        self.loader = AnsibleLoader(stream)
        self.data = self.loader.get_single_data()

    def tearDown(self):
        pass

    def test_data_complete(self):
        self.assertEqual(len(self.data), 1)
        self.assertIsInstance(self.data, list)
        self.assertEqual(frozenset(self.data[0].keys()), frozenset((u'hosts', u'vars', u'tasks')))

        self.assertEqual(self.data[0][u'hosts'], u'localhost')

        self.assertEqual(self.data[0][u'vars'][u'number'], 1)
        self.assertEqual(self.data[0][u'vars'][u'string'], u'Ansible')
        self.assertEqual(self.data[0][u'vars'][u'utf8_string'], u'Cafè Eñyei')
        self.assertEqual(self.data[0][u'vars'][u'dictionary'],
                {u'webster': u'daniel',
                    u'oed': u'oxford'})
        self.assertEqual(self.data[0][u'vars'][u'list'], [u'a', u'b', 1, 2])

        self.assertEqual(self.data[0][u'tasks'],
                [{u'name': u'Test case', u'ping': {u'data': u'{{ utf8_string }}'}},
                 {u'name': u'Test 2', u'ping': {u'data': u'Cafè Eñyei'}},
                 {u'name': u'Test 3', u'command': u'printf \'Cafè Eñyei\n\''},
                 ])

    def walk(self, data):
        # Make sure there's no str in the data
        self.assertNotIsInstance(data, binary_type)

        # Descend into various container types
        if isinstance(data, text_type):
            # strings are a sequence so we have to be explicit here
            return
        elif isinstance(data, (Sequence, Set)):
            for element in data:
                self.walk(element)
        elif isinstance(data, Mapping):
            for k, v in data.items():
                self.walk(k)
                self.walk(v)

        # Scalars were all checked so we're good to go
        return

    def test_no_str_in_data(self):
        # Checks that no strings are str type
        self.walk(self.data)

    def check_vars(self):
        # Numbers don't have line/col information yet
        # self.assertEqual(self.data[0][u'vars'][u'number'].ansible_pos, (self.play_filename, 4, 21))

        self.assertEqual(self.data[0][u'vars'][u'string'].ansible_pos, (self.play_filename, 5, 29))
        self.assertEqual(self.data[0][u'vars'][u'utf8_string'].ansible_pos, (self.play_filename, 6, 34))

        self.assertEqual(self.data[0][u'vars'][u'dictionary'].ansible_pos, (self.play_filename, 8, 23))
        self.assertEqual(self.data[0][u'vars'][u'dictionary'][u'webster'].ansible_pos, (self.play_filename, 8, 32))
        self.assertEqual(self.data[0][u'vars'][u'dictionary'][u'oed'].ansible_pos, (self.play_filename, 9, 28))

        self.assertEqual(self.data[0][u'vars'][u'list'].ansible_pos, (self.play_filename, 11, 23))
        self.assertEqual(self.data[0][u'vars'][u'list'][0].ansible_pos, (self.play_filename, 11, 25))
        self.assertEqual(self.data[0][u'vars'][u'list'][1].ansible_pos, (self.play_filename, 12, 25))
        # Numbers don't have line/col info yet
        # self.assertEqual(self.data[0][u'vars'][u'list'][2].ansible_pos, (self.play_filename, 13, 25))
        # self.assertEqual(self.data[0][u'vars'][u'list'][3].ansible_pos, (self.play_filename, 14, 25))

    def check_tasks(self):
        #
        # First Task
        #
        self.assertEqual(self.data[0][u'tasks'][0].ansible_pos, (self.play_filename, 16, 23))
        self.assertEqual(self.data[0][u'tasks'][0][u'name'].ansible_pos, (self.play_filename, 16, 29))
        self.assertEqual(self.data[0][u'tasks'][0][u'ping'].ansible_pos, (self.play_filename, 18, 25))
        self.assertEqual(self.data[0][u'tasks'][0][u'ping'][u'data'].ansible_pos, (self.play_filename, 18, 31))

        #
        # Second Task
        #
        self.assertEqual(self.data[0][u'tasks'][1].ansible_pos, (self.play_filename, 20, 23))
        self.assertEqual(self.data[0][u'tasks'][1][u'name'].ansible_pos, (self.play_filename, 20, 29))
        self.assertEqual(self.data[0][u'tasks'][1][u'ping'].ansible_pos, (self.play_filename, 22, 25))
        self.assertEqual(self.data[0][u'tasks'][1][u'ping'][u'data'].ansible_pos, (self.play_filename, 22, 31))

        #
        # Third Task
        #
        self.assertEqual(self.data[0][u'tasks'][2].ansible_pos, (self.play_filename, 24, 23))
        self.assertEqual(self.data[0][u'tasks'][2][u'name'].ansible_pos, (self.play_filename, 24, 29))
        self.assertEqual(self.data[0][u'tasks'][2][u'command'].ansible_pos, (self.play_filename, 25, 32))

    def test_line_numbers(self):
        # Check the line/column numbers are correct
        # Note: Remember, currently dicts begin at the start of their first entry
        self.assertEqual(self.data[0].ansible_pos, (self.play_filename, 2, 19))
        self.assertEqual(self.data[0][u'hosts'].ansible_pos, (self.play_filename, 2, 26))
        self.assertEqual(self.data[0][u'vars'].ansible_pos, (self.play_filename, 4, 21))

        self.check_vars()

        self.assertEqual(self.data[0][u'tasks'].ansible_pos, (self.play_filename, 16, 21))

        self.check_tasks()
