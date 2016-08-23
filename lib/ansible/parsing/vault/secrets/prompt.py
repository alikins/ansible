# (c) 2016, Adrian Likins <alikins@redhat.com>
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

import getpass

from ansible.errors import AnsibleError
from ansible.utils.unicode import to_bytes

from ansible.parsing.vault.secrets import VaultSecrets


class PromptVaultSecrets(VaultSecrets):
    @staticmethod
    def ask_vault_passwords(ask_new_vault_pass=False, rekey=False):
        ''' prompt for vault password and/or password change '''

        vault_pass = None
        new_vault_pass = None
        try:
            if rekey or not ask_new_vault_pass:
                vault_pass = getpass.getpass(prompt="Vault password: ")

            if ask_new_vault_pass:
                new_vault_pass = getpass.getpass(prompt="New Vault password: ")
                new_vault_pass2 = getpass.getpass(prompt="Confirm New Vault password: ")
                if new_vault_pass != new_vault_pass2:
                    raise AnsibleError("Passwords do not match")
        except EOFError:
            pass

        # enforce no newline chars at the end of passwords
        if vault_pass:
            vault_pass = to_bytes(vault_pass, errors='strict', nonstring='simplerepr').strip()
        if new_vault_pass:
            new_vault_pass = to_bytes(new_vault_pass, errors='strict', nonstring='simplerepr').strip()

        if ask_new_vault_pass and not rekey:
            vault_pass = new_vault_pass

        return vault_pass, new_vault_pass
