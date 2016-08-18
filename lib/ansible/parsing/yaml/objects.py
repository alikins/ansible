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

from ansible.compat.six import text_type
from ansible.errors import AnsibleError
from ansible.utils.unicode import to_bytes

import logging
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class AnsibleBaseYAMLObject(object):
    '''
    the base class used to sub-class python built-in objects
    so that we can add attributes to them during yaml parsing

    '''
    _data_source = None
    _line_number = 0
    _column_number = 0

    def _get_ansible_position(self):
        return (self._data_source, self._line_number, self._column_number)

    def _set_ansible_position(self, obj):
        try:
            (src, line, col) = obj
        except (TypeError, ValueError):
            raise AssertionError(
                'ansible_pos can only be set with a tuple/list '
                'of three values: source, line number, column number'
            )
        self._data_source = src
        self._line_number = line
        self._column_number = col

    ansible_pos = property(_get_ansible_position, _set_ansible_position)


class AnsibleMapping(AnsibleBaseYAMLObject, dict):
    ''' sub class for dictionaries '''
    pass


class AnsibleUnicode(AnsibleBaseYAMLObject, text_type):
    ''' sub class for unicode objects '''
    pass


class AnsibleSequence(AnsibleBaseYAMLObject, list):
    ''' sub class for lists '''
    pass


class AnsibleVault(AnsibleBaseYAMLObject, bytes):
    pass


class AnsibleVaultUnencryptedUnicode(AnsibleUnicode):
    """A object created from a !vault-unencrypted yaml object.

    This will be used to allow 'ansible-vault edit' to find yaml objects that
    should be encrypted.

    WARNING: This should only be used by 'ansible-vault edit'. Normal ansible
    tools should throw an error if they see this in a yaml file."""

    # This should never get called from ansible/ansible-playbook so maybe
    # not needed.
    __UNSAFE__ = True
    yaml_tag = u'!vault-unencrypted'

    def __init__(self, plaintext):
        super(AnsibleVaultUnencryptedUnicode, self).__init__()
        # after construction, calling code has to set the .vault attribute to a vaultlib object
        self.vault = None
        self.plaintext = plaintext

    def __str__(self):
        return str(self.plaintext)

    def __unicode__(self):
        return unicode(self.plaintext)

# Unicode like object that is not evaluated (decrypted) until it needs to be
# TODO: is there a reason these objects are subclasses for YAMLObject?
#@pdb.break_on_setattr('data')
#@pdb.break_on_setattr('_ciphertext')
#@pdb.break_on_setattr('vault')
#@pdb.break_on_setattr('__eq__')
class AnsibleVaultEncryptedUnicode(yaml.YAMLObject, AnsibleUnicode):
    __UNSAFE__ = True
    __ENCRYPTED__ = True
    yaml_tag = u'!vault-encrypted'

    @classmethod
    def from_plaintext(cls, seq, vault):
        log.debug('from_plaintext')
        if not vault:
            raise vault.AnsibleVaultError('Error creating AnsibleVaultEncryptedUnicode, invalid vault (%s) provided' % vault)

        ciphertext = vault.encrypt(seq)
        avu = cls(ciphertext)
        avu.vault = vault
        return avu

    def __init__(self, ciphertext):
        '''A AnsibleUnicode with a Vault attribute that can decrypt it.

        ciphertext is a byte string (str on PY2, bytestring on PY3).

        The .data atttribute is a property that returns the decrypted plaintext
        of the ciphertext as a PY2 unicode or PY3 string object.
        '''
        log.debug("__init__")

        super(AnsibleVaultEncryptedUnicode, self).__init__(ciphertext)
        # after construction, calling code has to set the .vault attribute to a vaultlib object
        self.vault = None
        self._ciphertext = to_bytes(ciphertext)
        assert type(ciphertext) == type(b'')
        #super(AnsibleVaultEncryptedUnicode, self).__init__(ciphertext)
        log.debug('vault=%s', self.vault)
        log.debug('id(self)=%s', id(self))
        log.debug('self=%s', self)
        ## remove



#        import pdb; pdb.set_trace()
        # import ptpdb; ptpdb.set_trace()##remove



    @property
    def data(self):
        log.debug('data getter')
        if not self.vault:
            # FIXME: raise exception?
            return self._ciphertext
        return self.vault.decrypt(self._ciphertext).decode()


    @data.setter
    def data(self, value):
        log.debug('data.setter %s', value)
        self._ciphertext = value

    def __repr__(self):
        return 'AnsibleVaultEncryptedUnicode(\"%s\')' % self._ciphertext

    # Compare a regular str/text_type with the decrypted hypertext
    def __eq__(self, other):
        log.debug('__eq__ %s == %s', self, other)
        return other == self.data

    def __hash__(self):
        return id(self)

    def __ne__(self, other):
        logger.debug('__ne__ %s != %s', self, other)
        return other != self.data

    def __str__(self):
        log.debug('__str__')
        return str(self.data)

    def __unicode__(self):
        log.debug('__unicode__')
        return unicode(self.data)
