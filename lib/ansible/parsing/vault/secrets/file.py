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

import subprocess
import os


from ansible.errors import AnsibleError
from ansible.utils.unicode import to_bytes

from ansible.parsing.vault.secrets import VaultSecrets

class Executable:
    def __init__(self, path):
        self.path = path

    def _just_run_script(self):
        # STDERR not captured to make it easier for users to prompt for input in their scripts
        p = subprocess.Popen(self.path, stdout=subprocess.PIPE)
        stdout, stderr = p.communicate()
        return p.returncode, stdout, stderr

    def run(self):
        try:
            returncode, stdout, stderr = self._just_run_script()
        except OSError as e:
            raise AnsibleError("Problem running vault password script %s (%s). If this is not a script, remove the executable bit from the file." % (' '.join(self.path), e))

        if returncode != 0:
            raise AnsibleError("Vault password script %s returned non-zero (%s): %s" % (self.path, returncode, stderr))

        vault_pass = stdout.strip('\r\n')
        return vault_pass

class SecretFile:
    def __init__(self, path):
        self.path = path

    def read(self):
        try:
            f = open(self.path, "rb")
            vault_pass = f.read().strip()
            f.close()
        except (OSError, IOError) as e:
            raise AnsibleError("Could not read vault password file %s: %s" % (this_path, e))

    return vault_pass

# FIXME: If VaultSecrets doesn't ever do much, these classes don't really need to subclass
# TODO: mv these classes to a seperate file so we don't pollute vault with 'subprocess' etc
class FileVaultSecrets(VaultSecrets):
    def __init__(self, name=None, filename=None, loader=None):
        self.name = name
        self.filename = filename
        self.loader = loader

        self.executable = None
        # load secrets from file
        self._secret = FileVaultSecrets.read_vault_password_file(self.filename, self.loader)

    @staticmethod
    def read_vault_password_file(vault_password_file, loader):
        """
        Read a vault password from a file or if executable, execute the script and
        retrieve password from STDOUT
        """

        this_path = os.path.realpath(os.path.expanduser(vault_password_file))
        if not os.path.exists(this_path):
            raise AnsibleError("The vault password file %s was not found" % this_path)

        if loader.is_executable(this_path):
            try:
                # STDERR not captured to make it easier for users to prompt for input in their scripts
                p = subprocess.Popen(this_path, stdout=subprocess.PIPE)
            except OSError as e:
                raise AnsibleError("Problem running vault password script %s (%s). If this is not a script, remove the executable bit from the file." % (' '.join(this_path), e))
            stdout, stderr = p.communicate()
            if p.returncode != 0:
                raise AnsibleError("Vault password script %s returned non-zero (%s): %s" % (this_path, p.returncode, p.stderr))
            vault_pass = stdout.strip('\r\n')
        else:
            try:
                f = open(this_path, "rb")
                vault_pass = f.read().strip()
                f.close()
            except (OSError, IOError) as e:
                raise AnsibleError("Could not read vault password file %s: %s" % (this_path, e))

        return vault_pass
