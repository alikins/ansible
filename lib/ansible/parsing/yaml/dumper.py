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

import yaml
from ansible.compat.six import PY3

from ansible.parsing.yaml.objects import AnsibleUnicode, AnsibleSequence, AnsibleMapping, AnsibleByteString
#from ansible.parsing.yaml.objects import AnsibleVault
from ansible.parsing.yaml.objects import AnsibleVaultEncryptedUnicode, AnsibleVaultUnencryptedUnicode
from ansible.vars.hostvars import HostVars

import logging
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

class AnsibleDumper(yaml.SafeDumper):
    '''
    A simple stub class that allows us to add representers
    for our overridden object types.
    '''
    pass

def represent_hostvars(self, data):
    return self.represent_dict(dict(data))

#def represent_vault(self, data):
#    return self.represent_scalar(data)
#    return self.represent_unicode(data)

# Note: only want to represent the encrypted data
def represent_vault_encrypted_unicode(self, data):
    log.debug('rep v_e_u data=%s', data)
    log.debug('rep_vault_enc_unicode data._ciphertext %s', data._ciphertext)
    log.debug('rep_vault_enc_unicode data._ciphertext type %s', type(data._ciphertext))
    # add yaml tag
    return self.represent_scalar(u'!vault-encrypted', data._ciphertext.decode(), style='|')

def represent_vault_unencrypted_unicode(self, data):
    return self.represent_scalar(u'!vault-unencrypted', data.plaintext, style='|')

if PY3:
    represent_unicode = yaml.representer.SafeRepresenter.represent_str
else:
    represent_unicode = yaml.representer.SafeRepresenter.represent_unicode

AnsibleDumper.add_representer(
    AnsibleUnicode,
    represent_unicode,
)

AnsibleDumper.add_representer(
    HostVars,
    represent_hostvars,
)

AnsibleDumper.add_representer(
    AnsibleSequence,
    yaml.representer.SafeRepresenter.represent_list,
)

AnsibleDumper.add_representer(
    AnsibleMapping,
    yaml.representer.SafeRepresenter.represent_dict,
)

AnsibleDumper.add_representer(
    AnsibleByteString,
    yaml.representer.SafeRepresenter.represent_str,
)

#AnsibleDumper.add_representer(
#    AnsibleVault,
#    represent_vault,
#)

AnsibleDumper.add_representer(
    AnsibleVaultEncryptedUnicode,
    represent_vault_encrypted_unicode,
)

AnsibleDumper.add_representer(
    AnsibleVaultUnencryptedUnicode,
    represent_vault_unencrypted_unicode,
)
