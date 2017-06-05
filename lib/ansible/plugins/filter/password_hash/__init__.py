
# Make coding more python3-ish
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import crypt
import string
import sys

from random import SystemRandom

try:
    import passlib.hash
    HAS_PASSLIB = True
except:
    HAS_PASSLIB = False

from ansible import errors


def get_encrypted_password(password, hashtype='sha512', salt=None):

    # TODO: find a way to construct dynamically from system
    cryptmethod = {
        'md5': '1',
        'blowfish': '2a',
        'sha256': '5',
        'sha512': '6',
    }

    if hashtype in cryptmethod:
        if salt is None:
            r = SystemRandom()
            if hashtype in ['md5']:
                saltsize = 8
            else:
                saltsize = 16
            saltcharset = string.ascii_letters + string.digits + '/.'
            salt = ''.join([r.choice(saltcharset) for _ in range(saltsize)])

        if not HAS_PASSLIB:
            if sys.platform.startswith('darwin'):
                raise errors.AnsibleFilterError('|password_hash requires the passlib python module to generate password hashes on Mac OS X/Darwin')
            saltstring = "$%s$%s" % (cryptmethod[hashtype], salt)
            encrypted = crypt.crypt(password, saltstring)
        else:
            if hashtype == 'blowfish':
                cls = passlib.hash.bcrypt
            else:
                cls = getattr(passlib.hash, '%s_crypt' % hashtype)

            encrypted = cls.encrypt(password, salt=salt)

        return encrypted

    return None


class FilterModule(object):
        ''' Ansible jinja2 password_hash filter '''

        def filters(self):
            return {'password_hash': get_encrypted_password}
