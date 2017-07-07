# (c) 2017, Adrian Likins <alikins@redhat.com>
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

from ansible.release import __version__
from ansible import cli


class TestCliVersion(unittest.TestCase):

    def test_version(self):
        ver = cli.CLI.version('ansible-cli-test')
        self.assertIn('ansible-cli-test', ver)
        self.assertIn('python version', ver)

    def test_version_info(self):
        version_info = cli.CLI.version_info()
        self.assertEqual(version_info['string'], __version__)

    def test_version_info_gitinfo(self):
        version_info = cli.CLI.version_info(gitinfo=True)
        self.assertIn('python version', version_info['string'])


class TestCliSetupVaultSecrets(unittest.TestCase):
    def test(self):
        res = cli.CLI.setup_vault_secrets(None, None)
        self.assertIsInstance(res, dict)

    @patch('ansible.cli.FileVaultSecret')
    def test_password_file(self, mock_file_secret):
        filename = '/dev/null/secret'
        mock_file_secret.return_value = MagicMock(bytes=b'file1_password',
                                                  vault_id='file1',
                                                  filename=filename)
        res = cli.CLI.setup_vault_secrets(None,
                                          vault_ids=['secret1', 'secret2'],
                                          vault_password_files=[filename])
        self.assertIsInstance(res, dict)
        self.assertIn(filename, res)
        self.assertIn('secret1', res)
        self.assertEqual(res['secret1'].bytes, b'file1_password')

    @patch('ansible.cli.PromptVaultSecret')
    def test_prompt(self, mock_prompt_secret):
        mock_prompt_secret.return_value = MagicMock(bytes=b'prompt1_password',
                                                    vault_id='prompt1')

        res = cli.CLI.setup_vault_secrets(None,
                                          vault_ids=['prompt1', 'secret1'],
                                          ask_vault_pass=True)

        self.assertIsInstance(res, dict)
        self.assertIn('prompt1', res)
        self.assertIn('secret1', res)
        self.assertEqual(res['prompt1'].bytes, b'prompt1_password')
