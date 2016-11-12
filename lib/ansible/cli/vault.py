# (c) 2014, James Tanner <tanner.jc@gmail.com>
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
# ansible-vault is a script that encrypts/decrypts YAML files. See
# http://docs.ansible.com/playbooks_vault.html for more details.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os
import sys

from ansible.errors import AnsibleError, AnsibleOptionsError
from ansible.parsing.dataloader import DataLoader
from ansible.parsing.vault import VaultEditor, VaultSecrets, FileVaultSecrets, PromptVaultSecrets
from ansible.cli import CLI
from ansible.module_utils._text import to_text

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class VaultCLI(CLI):
    """ Vault command line class """

    VALID_ACTIONS = ("create", "decrypt", "edit", "encrypt", "rekey", "view")

    def __init__(self, args):

        self.vault_pass = None
        self.new_vault_pass = None
        super(VaultCLI, self).__init__(args)

    def parse(self):

        self.parser = CLI.base_parser(
            vault_opts=True,
            usage = "usage: %%prog [%s] [--help] [options] vaultfile.yml" % "|".join(self.VALID_ACTIONS),
            epilog = "\nSee '%s <command> --help' for more information on a specific command.\n\n" % os.path.basename(sys.argv[0])
        )

        self.set_action()

        # options specific to self.actions
        if self.action == "create":
            self.parser.set_usage("usage: %prog create [options] file_name")
        elif self.action == "decrypt":
            self.parser.set_usage("usage: %prog decrypt [options] file_name")
        elif self.action == "edit":
            self.parser.set_usage("usage: %prog edit [options] file_name")
        elif self.action == "view":
            self.parser.set_usage("usage: %prog view [options] file_name")
        elif self.action == "encrypt":
            self.parser.set_usage("usage: %prog encrypt [options] file_name")
        elif self.action == "rekey":
            self.parser.set_usage("usage: %prog rekey [options] file_name")

        super(VaultCLI, self).parse()

        display.verbosity = self.options.verbosity

        can_output = ['encrypt', 'decrypt']

        if self.action not in can_output:
            if self.options.output_file:
                raise AnsibleOptionsError("The --output option can be used only with ansible-vault %s" % '/'.join(can_output))
            if len(self.args) == 0:
                raise AnsibleOptionsError("Vault requires at least one filename as a parameter")
        else:
            # This restriction should remain in place until it's possible to
            # load multiple YAML records from a single file, or it's too easy
            # to create an encrypted file that can't be read back in. But in
            # the meanwhile, "cat a b c|ansible-vault encrypt --output x" is
            # a workaround.
            if self.options.output_file and len(self.args) > 1:
                raise AnsibleOptionsError("At most one input file may be used with the --output option")

    def run(self):

        super(VaultCLI, self).run()
        loader = DataLoader()

        # set default restrictive umask
        old_umask = os.umask(0o077)

        if self.vault_pass:
            vault_secrets = VaultSecrets()
            vault_secrets.set_secret('default', self.vault_pass)

        if self.options.vault_password_file:
            vault_secrets = FileVaultSecrets(filename=self.options.vault_password_file,
                                             loader=loader)

        if not self.vault_pass or self.options.ask_vault_pass:
            vault_secrets = PromptVaultSecrets()
            vault_secrets.ask_vault_passwords()

        newpass = False
        rekey = False
        # TODO: fix rekey later
        newpass = (self.action in ['create', 'rekey', 'encrypt'])
        rekey = (self.action == 'rekey')

        if rekey or newpass:
            if self.vault_pass:
                new_vault_secrets = VaultSecrets()
                new_vault_secrets.set_secret('default', self.vault_pass)

            if self.options.new_vault_password_file:
                new_vault_secrets = FileVaultSecrets(filename=self.options.vault_password_file,
                                                     loader=loader)

            if not self.vault_pass or self.options.ask_vault_pass:
                new_vault_secrets = PromptVaultSecrets()
                new_vault_secrets.ask_new_vault_passwords()

            if not new_vault_secrets:
                raise AnsibleOptionsError("A password is required to use Ansible's Vault")
            self.new_vault_secrets = new_vault_secrets
        else:
            if not vault_secrets:
                raise AnsibleOptionsError("A password is required to use Ansible's Vault")

        # FIXME: revist the 'rekey' ask-vault-password bug and verify
        self.editor = VaultEditor(vault_secrets)

        self.execute()

        # and restore umask
        os.umask(old_umask)

    def execute_encrypt(self):

        if len(self.args) == 0 and sys.stdin.isatty():
            display.display("Reading plaintext input from stdin", stderr=True)

        for f in self.args or ['-']:
            self.editor.encrypt_file(f, output_file=self.options.output_file)

        if sys.stdout.isatty():
            display.display("Encryption successful", stderr=True)

    def execute_decrypt(self):

        if len(self.args) == 0 and sys.stdin.isatty():
            display.display("Reading ciphertext input from stdin", stderr=True)

        for f in self.args or ['-']:
            self.editor.decrypt_file(f, output_file=self.options.output_file)

        if sys.stdout.isatty():
            display.display("Decryption successful", stderr=True)

    def execute_create(self):

        if len(self.args) > 1:
            raise AnsibleOptionsError("ansible-vault create can take only one filename argument")

        self.editor.create_file(self.args[0])

    def execute_edit(self):
        for f in self.args:
            self.editor.edit_file(f)

    def execute_view(self):

        for f in self.args:
            # Note: vault should return byte strings because it could encrypt
            # and decrypt binary files.  We are responsible for changing it to
            # unicode here because we are displaying it and therefore can make
            # the decision that the display doesn't have to be precisely what
            # the input was (leave that to decrypt instead)
            self.pager(to_text(self.editor.plaintext(f)))

    def execute_rekey(self):
        for f in self.args:
            if not (os.path.isfile(f)):
                raise AnsibleError(f + " does not exist")

        for f in self.args:
            # FIXME: plumb in vault_id
            self.editor.rekey_file(f, self.new_vault_secrets)

        display.display("Rekey successful", stderr=True)
