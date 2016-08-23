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

import os

from ansible.errors import AnsibleError
from ansible.utils.unicode import to_bytes

class VaultSecrets(object):
    def __init__(self, name=None):
        self.name = name
        self._secret = None

    # TODO: Note this is not really the proposed interface/api
    #       This is more to sort out where all we pass passwords around.
    #       A better version would be passed deep into the decrypt/encrypt code
    #       and VaultSecrets could potentially do the key stretching and
    #       HMAC checks itself. Or for that matter, the Cipher objects could
    #       be provided by VaultSecrets.
    def get_secret(self, secret_name=None):
        # given some id, provide the right secret
        # secret_name could be None for the default,
        # or a filepath, or a label used for prompting users
        # interactively  (like a ssh key id arg to ssh-add...)
        return to_bytes(self._secret, errors='strict', encoding='utf-8')


# A vault with just a plaintext password
class PasswordVaultSecrets(VaultSecrets):
    def __init__(self, name='default', password=None):
        super(PasswordVaultSecrets, self).__init__(name)
        self._secret = password


# FIXME: If VaultSecrets doesn't ever do much, these classes don't really need to subclass
# TODO: mv these classes to a seperate file so we don't pollute vault with 'subprocess' etc
class FileVaultSecrets(VaultSecrets):
    def __init__(self, name=None, filename=None, loader=None):
        self.name = name
        self.filename = filename
        self.loader = loader

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


class DirVaultSecrets(VaultSecrets):
    def __init__(self, directory=None, loader=None):
        self.directory = directory
        self.loader = loader

        self._secrets = {}

    def get_secret(self, name=None):
        if name:
            return self._secrets[name]
        return None

