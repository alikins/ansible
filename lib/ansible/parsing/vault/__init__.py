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

# Make coding more python3-ish
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import getpass
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import random
from io import BytesIO
from subprocess import call
from ansible.errors import AnsibleError
from hashlib import sha256
from binascii import hexlify
from binascii import unhexlify

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()

# Note: Only used for loading obsolete VaultAES files.  All files are written
# using the newer VaultAES256 which does not require md5
from hashlib import md5

try:
    from Crypto.Hash import SHA256, HMAC
    HAS_HASH = True
except ImportError:
    HAS_HASH = False

# Counter import fails for 2.0.1, requires >= 2.6.1 from pip
try:
    from Crypto.Util import Counter
    HAS_COUNTER = True
except ImportError:
    HAS_COUNTER = False

# KDF import fails for 2.0.1, requires >= 2.6.1 from pip
try:
    from Crypto.Protocol.KDF import PBKDF2
    HAS_PBKDF2 = True
except ImportError:
    HAS_PBKDF2 = False

# AES IMPORTS
try:
    from Crypto.Cipher import AES as AES
    HAS_AES = True
except ImportError:
    HAS_AES = False

# OpenSSL pbkdf2_hmac
HAS_PBKDF2HMAC = False
try:
    from cryptography.hazmat.primitives.hashes import SHA256 as c_SHA256
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.backends import default_backend
    HAS_PBKDF2HMAC = True
except ImportError:
    pass
except Exception as e:
    display.warning("Optional dependency 'cryptography' raised an exception, falling back to 'Crypto'")
    import traceback
    display.debug("Traceback from import of cryptography was {0}".format(traceback.format_exc()))

from ansible.compat.six import PY3
from ansible.utils.unicode import to_unicode, to_bytes

HAS_ANY_PBKDF2HMAC = HAS_PBKDF2 or HAS_PBKDF2HMAC

CRYPTO_UPGRADE = "ansible-vault requires a newer version of pycrypto than the one installed on your platform. You may fix this with OS-specific commands such as: yum install python-devel; rpm -e --nodeps python-crypto; pip install pycrypto"

b_HEADER = b'$ANSIBLE_VAULT'
HEADER = '$ANSIBLE_VAULT'
CIPHER_WHITELIST = frozenset((u'AES', u'AES256'))
CIPHER_WRITE_WHITELIST = frozenset((u'AES256',))
# See also CIPHER_MAPPING at the bottom of the file which maps cipher strings
# (used in VaultFile header) to a cipher class


def check_prereqs():

    if not HAS_AES or not HAS_COUNTER or not HAS_ANY_PBKDF2HMAC or not HAS_HASH:
        raise AnsibleError(CRYPTO_UPGRADE)


class AnsibleVaultError(AnsibleError):
    pass

def is_encrypted(b_data):
    """ Test if this is vault encrypted data blob

    :arg data: a python2 str or a python3 'bytes' to test whether it is
        recognized as vault encrypted data
    :returns: True if it is recognized.  Otherwise, False.
    """
    if b_data.startswith(b_HEADER):
        return True
    return False

def is_encrypted_file(file_obj):
    """Test if the contents of a file obj are a vault encrypted data blob.

    The data read from the file_obj is expected to be bytestrings (py2 'str' or
    python3 'bytes'). This more or less expects 'utf-8' encoding.

    :arg file_obj: A file object that will be read from.
    :returns: True if the file is a vault file. Otherwise, False.
    """
    # read the header and reset the file stream to where it started
    current_position = file_obj.tell()
    b_header_part = file_obj.read(len(b_HEADER))
    file_obj.seek(current_position)
    return is_encrypted(b_header_part)

# VaultLib split into
#  VaultContext
#      - key/passphrase
#      - algo
#         - name
#         - type
#         - version
#      - context_id
#  VaultEnvelope  (maybe)
#     - render / format_output
#     - parse / split_header
class VaultData(object):
    vault_data = True

    def __init__(self, data):
        self.data = data


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
        #return to_bytes(self._secret)
        return to_bytes(self._secret, errors='strict', encoding='utf-8')


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





class VaultLib:

    def __init__(self, secrets=None):
        #self.b_password = to_bytes(password, errors='strict', encoding='utf-8')
        self.secrets = secrets
        self.cipher_name = None
        # Add key_id to header
        self.b_version = b'1.2'

    # really b_data, but for compat
    def is_encrypted(self, data):
        """ Test if this is vault encrypted data

        :arg data: a python2 utf-8 string or a python3 'bytes' to test whether it is
            recognized as vault encrypted data
        :returns: True if it is recognized.  Otherwise, False.
        """

        # This could check to see if the data is a vault blob and is encrypted with a key associated with this vault
        # instead of just checking the format.
        return is_encrypted(data)

    def is_encrypted_file(self, file_obj):
        return is_encrypted_file(file_obj)

    def encrypt(self, data):
        """Vault encrypt a piece of data.

        :arg data: a PY2 unicode string or PY3 string to encrypt.
        :returns: a utf-8 encoded byte str of encrypted data.  The string
            contains a header identifying this as vault encrypted data and
            formatted to newline terminated lines of 80 characters.  This is
            suitable for dumping as is to a vault file.

        The unicode or string passed in as data will encoded to UTF-8 before
        encryption. If the a already encoded string or PY2 bytestring needs to
        be encrypted, use encrypt_bytestring().
        """
        plaintext = data
        b_plaintext = plaintext.encode('utf-8')

        return self.encrypt_bytestring(b_plaintext)

    def encrypt_bytestring(self, b_plaintext):
        '''Encrypt a PY2 bytestring.

        Like encrypt(), except b_plaintext is not encoded to UTF-8
        before encryption.'''

        if self.is_encrypted(b_plaintext):
            raise AnsibleError("input is already encrypted")

        if not self.cipher_name or self.cipher_name not in CIPHER_WRITE_WHITELIST:
            self.cipher_name = u"AES256"

        # could move creation of the cipher object to vaultSecrets to
        # decouple vaultLib from the impl
        this_cipher_class = cipher_factory(self.cipher_name)
        this_cipher = this_cipher_class()

        # encrypt data
        b_ciphertext = this_cipher.encrypt(b_plaintext, self.secrets)

        # format the data for output to the file
        b_ciphertext_envelope = self._format_output(b_ciphertext)
        return b_ciphertext_envelope

    # TODO: split to decrypt/decrypt_bytes/decrypt_file
    def decrypt(self, data, filename=None):
        """Decrypt a piece of vault encrypted data.

        :arg data: a string to decrypt.  Since vault encrypted data is an
            ascii text format this can be either a byte str or unicode string.
        :returns: a byte string containing the decrypted data
        """
        b_data = to_bytes(data, errors='strict', encoding='utf-8')

        # could provide a default or NullSecrets if this needs to be smarter about when it's ready
        if self.secrets is None:
            raise AnsibleError("A vault password must be specified to decrypt data")

        # TODO: move to a is_vault() of validate_format()
        # TODO: raise some NotEncryptedError(AnsibleVaultError) here or in validate_format()
        if not self.is_encrypted(b_data):
            msg = "input is not vault encrypted data"
            if filename:
                msg += "%s is not a vault encrypted file" % filename
            raise AnsibleError(msg)

        # clean out header
        b_data = self._split_header(b_data)

        # create the cipher object
        cipher_class_name = u'Vault{0}'.format(self.cipher_name)
        # cipher metaclass that registered subclasses could be used here and in place of cipher_factory()
        if cipher_class_name in globals() and self.cipher_name in CIPHER_WHITELIST:
            cipher_class = globals()[cipher_class_name]
            this_cipher = cipher_class()
        else:
            raise AnsibleError("{0} cipher could not be found".format(self.cipher_name))

        # try to unencrypt data

        # The key_id is known at this point from parsing the vault envelope
        # Add a VaultContext(secrets, key_id, cipher) ?
        # vault_context = VaultContext(self.secrets, self.key_id, this_cipher)
        # b_data = vault_context.decrypt(b_data)
        # vault_context could be an interface to an agent of some sort
        b_data = this_cipher.decrypt(b_data, self.secrets)
        if b_data is None:
            msg = "Decryption failed"
            if filename:
                msg += " on %s" % filename
            raise AnsibleError(msg)

        return b_data

    def _format_output(self, b_data):
        """ Add header and format to 80 columns

            :arg b_data: the encrypted and hexlified data as a byte string
            :returns: a byte str that should be dumped into a file.  It's
                formatted to 80 char columns and has the header prepended
        """

        b_ciphertext = b_data
        if not self.cipher_name:
            raise AnsibleError("the cipher must be set before adding a header")

        b_header = HEADER.encode('utf-8')
        b_header = b';'.join([b_header, self.b_version,
                        to_bytes(self.cipher_name, 'utf-8',errors='strict')])
        b_tmpdata = [b_header]
        b_tmpdata += [b_ciphertext[i:i + 80] for i in range(0, len(b_ciphertext), 80)]
        b_tmpdata += [b'']
        b_tmpdata = b'\n'.join(b_tmpdata)

        return b_tmpdata

    def _split_header(self, b_data):
        """Retrieve information about the Vault and  clean the data

        When data is saved, it has a header prepended and is formatted into 80
        character lines.  This method extracts the information from the header
        and then removes the header and the inserted newlines.  The string returned
        is suitable for processing by the Cipher classes.

        :arg b_data: byte str containing the data from a save file
        :returns: a byte str suitable for passing to a Cipher class's
            decrypt() function.
        """
        # used by decrypt

        b_tmp_data = b_data.split(b'\n')
        b_tmp_header = b_tmp_data[0].strip().split(b';')

        self.b_version = b_tmp_header[1].strip()
        self.cipher_name = to_unicode(b_tmp_header[2].strip())
        b_clean_data = b''.join(b_tmp_data[1:])
        self.key_id = 'version_1_1_default_key'
        # Only attempt to find key_id if the vault file is version 1.2 or newer
        if self.b_version == b'1.2':
            self.key_id = to_unicode(tmpheader[3].strip())

        return b_clean_data


class VaultEditor:

    def __init__(self, secrets):
        self.vault = VaultLib(secrets)

    # TODO: mv shred file stuff to it's own class
    def _shred_file_custom(self, tmp_path):
        """"Destroy a file, when shred (core-utils) is not available

        Unix `shred' destroys files "so that they can be recovered only with great difficulty with
        specialised hardware, if at all". It is based on the method from the paper
        "Secure Deletion of Data from Magnetic and Solid-State Memory",
        Proceedings of the Sixth USENIX Security Symposium (San Jose, California, July 22-25, 1996).

        We do not go to that length to re-implement shred in Python; instead, overwriting with a block
        of random data should suffice.

        See https://github.com/ansible/ansible/pull/13700 .
        """

        file_len = os.path.getsize(tmp_path)

        if file_len > 0:  # avoid work when file was empty
            # 2 MB
            max_chunk_len = min(1024 * 1024 * 2, file_len)

            passes = 3
            with open(tmp_path,  "wb") as fh:
                for _ in range(passes):
                    fh.seek(0,  0)
                    # get a random chunk of data, each pass with other length
                    chunk_len = random.randint(max_chunk_len // 2, max_chunk_len)
                    b_data = os.urandom(chunk_len)

                    for _ in range(0, file_len // chunk_len):
                        fh.write(b_data)
                    fh.write(b_data[:file_len % chunk_len])

                    assert(fh.tell() == file_len)  # FIXME remove this assert once we have unittests to check its accuracy
                    os.fsync(fh)

    def _shred_file(self, tmp_path):
        """Securely destroy a decrypted file

        Note standard limitations of GNU shred apply (For flash, overwriting would have no effect
        due to wear leveling; for other storage systems, the async kernel->filesystem->disk calls never
        guarantee data hits the disk; etc). Furthermore, if your tmp dirs is on tmpfs (ramdisks),
        it is a non-issue.

        Nevertheless, some form of overwriting the data (instead of just removing the fs index entry) is
        a good idea. If shred is not available (e.g. on windows, or no core-utils installed), fall back on
        a custom shredding method.
        """

        if not os.path.isfile(tmp_path):
            # file is already gone
            return

        try:
            r = call(['shred', tmp_path])
        except (OSError, ValueError):
            # shred is not available on this system, or some other error occured.
            # ValueError caught because OS X El Capitan is raising an
            # exception big enough to hit a limit in python2-2.7.11 and below.
            # Symptom is ValueError: insecure pickle when shred is not
            # installed there.
            r = 1

        if r != 0:
            # we could not successfully execute unix shred; therefore, do custom shred.
            self._shred_file_custom(tmp_path)

        os.remove(tmp_path)

    def _edit_file_helper(self, filename, existing_data=None, force_save=False):

        # Create a tempfile
        _, tmp_path = tempfile.mkstemp()

        if existing_data:
            self.write_data(existing_data, tmp_path, shred=False)

        # drop the user into an editor on the tmp file
        try:
            call(self._editor_shell_command(tmp_path))
        except:
            # whatever happens, destroy the decrypted file
            self._shred_file(tmp_path)
            raise

        b_tmpdata = self.read_data(tmp_path)

        # Do nothing if the content has not changed
        if existing_data == b_tmpdata and not force_save:
            self._shred_file(tmp_path)
            return

        # encrypt new data and write out to tmp
        # An existing vaultfile will always be UTF-8,
        # so decode to unicode here
        b_enc_data = self.vault.encrypt(b_tmpdata.decode())
        self.write_data(b_enc_data, tmp_path)

        # shuffle tmp file into place
        self.shuffle_files(tmp_path, filename)

    def encrypt_file(self, filename, output_file=None):

        check_prereqs()

        # A file to be encrypted into a vaultfile could be any encoding
        # so treat the contents as a byte string.
        b_plaintext = self.read_data(filename)
        b_ciphertext = self.vault.encrypt_bytestring(b_plaintext)
        self.write_data(b_ciphertext, output_file or filename)

    def decrypt_file(self, filename, output_file=None):

        check_prereqs()

        b_ciphertext = self.read_data(filename)

        try:
            plaintext = self.vault.decrypt(b_ciphertext)
        except AnsibleError as e:
            raise AnsibleError("%s for %s" % (to_bytes(e),to_bytes(filename)))
        self.write_data(plaintext, output_file or filename, shred=False)

    def create_file(self, filename):
        """ create a new encrypted file """

        check_prereqs()

        # FIXME: If we can raise an error here, we can probably just make it
        # behave like edit instead.
        if os.path.isfile(filename):
            raise AnsibleError("%s exists, please use 'edit' instead" % filename)

        self._edit_file_helper(filename)

    def edit_file(self, filename):

        check_prereqs()

        b_ciphertext = self.read_data(filename)
        try:
            plaintext = self.vault.decrypt(b_ciphertext)
        except AnsibleError as e:
            raise AnsibleError("%s for %s" % (to_bytes(e),to_bytes(filename)))

        if self.vault.cipher_name not in CIPHER_WRITE_WHITELIST:
            # we want to get rid of files encrypted with the AES cipher
            self._edit_file_helper(filename, existing_data=plaintext, force_save=True)
        else:
            self._edit_file_helper(filename, existing_data=plaintext, force_save=False)

    def plaintext(self, filename):

        check_prereqs()
        b_ciphertext = self.read_data(filename)

        try:
            plaintext = self.vault.decrypt(b_ciphertext)
        except AnsibleError as e:
            raise AnsibleError("%s for %s" % (to_bytes(e),to_bytes(filename)))

        return plaintext

    def rekey_file(self, filename, new_password):

        check_prereqs()

        prev = os.stat(filename)
        b_ciphertext = self.read_data(filename)
        try:
            plaintext = self.vault.decrypt(b_ciphertext)
        except AnsibleError as e:
            raise AnsibleError("%s for %s" % (to_bytes(e),to_bytes(filename)))

        new_vault = VaultLib(new_password)
        b_new_ciphertext = new_vault.encrypt(plaintext)

        self.write_data(b_new_ciphertext, filename)

        # preserve permissions
        os.chmod(filename, prev.st_mode)
        os.chown(filename, prev.st_uid, prev.st_gid)

    def read_data(self, filename):

        try:
            if filename == '-':
                b_data = sys.stdin.read()
            else:
                with open(filename, "rb") as fh:
                    b_data = fh.read()
        except Exception as e:
            raise AnsibleError(str(e))

        return b_data

    # TODO: add docstrings for arg types since this code is picky about that
    def write_data(self, data_bytes, filename, shred=True):
        """write data to given path

        :arg data: the encrypted and hexlified data as a utf-8 byte string
        :arg filename: filename to save 'data' to.
        :arg shred: if shred==True, make sure that the original data is first shredded so
        that is cannot be recovered.
        """
        # FIXME: do we need this now? data_bytes should always be a utf-8 byte string
        b_file_data = to_bytes(data_bytes, errors='strict')

        if filename == '-':
            sys.stdout.write(b_file_data)
        else:
            if os.path.isfile(filename):
                if shred:
                    self._shred_file(filename)
                else:
                    os.remove(filename)
            with open(filename, "wb") as fh:
                fh.write(b_file_data)

    def shuffle_files(self, src, dest):
        prev = None
        # overwrite dest with src
        if os.path.isfile(dest):
            prev = os.stat(dest)
            # old file 'dest' was encrypted, no need to _shred_file
            os.remove(dest)
        shutil.move(src, dest)

        # reset permissions if needed
        if prev is not None:
            # TODO: selinux, ACLs, xattr?
            os.chmod(dest, prev.st_mode)
            os.chown(dest, prev.st_uid, prev.st_gid)

    def _editor_shell_command(self, filename):
        env_editor = os.environ.get('EDITOR','vi')
        editor = shlex.split(env_editor)
        editor.append(filename)

        return editor

# TODO: does anything use this?
class VaultFile(object):

    def __init__(self, password, filename):
        self.password = password

        self.filename = filename
        if not os.path.isfile(self.filename):
            raise AnsibleError("%s does not exist" % self.filename)
        try:
            self.filehandle = open(filename, "rb")
        except Exception as e:
            raise AnsibleError("Could not open %s: %s" % (self.filename, str(e)))

        _, self.tmpfile = tempfile.mkstemp()

    # TODO:
    # __del__ can be problematic in python... For this use case, make
    # VaultFile a context manager instead (implement __enter__ and __exit__)
    def __del__(self):
        self.filehandle.close()
        os.unlink(self.tmpfile)

    def is_encrypted(self):
        return is_encrypted_file(self.filehandle)

    def get_decrypted(self):
        check_prereqs()

        if self.is_encrypted():
            tmpdata = self.filehandle.read()
            this_vault = VaultLib(self.password)
            dec_data = this_vault.decrypt(tmpdata)
            if dec_data is None:
                raise AnsibleError("Failed to decrypt: %s" % self.filename)
            else:
                self.tmpfile.write(dec_data)
                return self.tmpfile
        else:
            return self.filename

########################################
#               CIPHERS                #
########################################


class VaultAES:

    # this version has been obsoleted by the VaultAES256 class
    # which uses encrypt-then-mac (fixing order) and also improving the KDF used
    # code remains for upgrade purposes only
    # http://stackoverflow.com/a/16761459

    # Note: strings in this class should be byte strings by default.

    def __init__(self):
        if not HAS_AES:
            raise AnsibleError(CRYPTO_UPGRADE)

    def aes_derive_key_and_iv(self, secrets, salt, key_length, iv_length):

        """ Create a key and an initialization vector """
        b_salt = salt

        b_digest = b_digest_i = b''
        while len(b_digest) < key_length + iv_length:
            b_text = b''.join([b_digest_i, password, b_salt])
            b_digest_i = to_bytes(md5(b_text).digest(), errors='strict')
            b_digest += b_digest_i

        b_key = b_digest[:key_length]
        b_iv = b_digest[key_length:key_length + iv_length]

        return b_key, b_iv

    def encrypt(self, data, secrets, key_length=32):

        """ Read plaintext data from in_file and write encrypted to out_file """

        raise AnsibleError("Encryption disabled for deprecated VaultAES class")

    def decrypt(self, data, secrets, key_length=32):

        """ Read encrypted data from in_file and write decrypted to out_file """

        # http://stackoverflow.com/a/14989032
        b_hex_data = data
        b_data = unhexlify(b_hex_data)

        in_file = BytesIO(b_data)
        in_file.seek(0)
        out_file = BytesIO()

        bs = AES.block_size
        b_tmpsalt = in_file.read(bs)
        b_salt = b_tmpsalt[len(b'Salted__'):]

        # TODO: default id?
        #password = secrets.get_secret()

        b_key, b_iv = self.aes_derive_key_and_iv(secrets, b_salt, key_length, bs)
        cipher = AES.new(b_key, AES.MODE_CBC, b_iv)
        b_next_chunk = b''
        finished = False

        while not finished:
            b_chunk, b_next_chunk = b_next_chunk, cipher.decrypt(in_file.read(1024 * bs))
            if len(b_next_chunk) == 0:
                if PY3:
                    padding_length = b_chunk[-1]
                else:
                    padding_length = ord(b_chunk[-1])

                b_chunk = b_chunk[:-padding_length]
                finished = True

            out_file.write(b_chunk)
            out_file.flush()

        # reset the stream pointer to the beginning
        out_file.seek(0)
        b_out_data = out_file.read()
        out_file.close()

        # split out sha and verify decryption
        b_split_data = b_out_data.split(b"\n", 1)
        b_this_sha = b_split_data[0]
        b_this_data = b_split_data[1]
        b_test_sha = to_bytes(sha256(b_this_data).hexdigest())

        if b_this_sha != b_test_sha:
            raise AnsibleError("Decryption failed")

        return b_this_data


class VaultAES256:

    """
    Vault implementation using AES-CTR with an HMAC-SHA256 authentication code.
    Keys are derived using PBKDF2
    """

    # http://www.daemonology.net/blog/2009-06-11-cryptographic-right-answers.html

    # Note: strings in this class should be byte strings by default.

    def __init__(self):

        check_prereqs()

    def create_key(self, password, salt, keylength, ivlength):
        hash_function = SHA256
        pbkdf2_prf = lambda p, s: HMAC.new(p, s, hash_function).digest()

        b_derived_key = PBKDF2(password, salt, dkLen=(2 * keylength) + ivlength,
                            count=10000, prf=pbkdf2_prf)
        return b_derived_key

    def gen_key_initctr(self, password, salt):
        # 16 for AES 128, 32 for AES256
        keylength = 32

        # match the size used for counter.new to avoid extra work
        ivlength = 16

        if HAS_PBKDF2HMAC:
            backend = default_backend()
            kdf = PBKDF2HMAC(
                algorithm=c_SHA256(),
                length=2 * keylength + ivlength,
                salt=salt,
                iterations=10000,
                backend=backend)
            b_derived_key = kdf.derive(password)
        else:
            b_derived_key = self.create_key(password, salt, keylength, ivlength)

        b_key1 = b_derived_key[:keylength]
        b_key2 = b_derived_key[keylength:(keylength * 2)]
        b_iv = b_derived_key[(keylength * 2):(keylength * 2) + ivlength]

        return b_key1, b_key2, hexlify(b_iv)

    def encrypt(self, data, secrets):
        # use b_ for bytes name scheme but don't change public method args
        b_data = data

        # random bytes
        b_salt = os.urandom(32)
        password = secrets.get_secret()
        key1, key2, iv = self.gen_key_initctr(password, b_salt)

        # PKCS#7 PAD DATA http://tools.ietf.org/html/rfc5652#section-6.3
        bs = AES.block_size
        padding_length = (bs - len(data) % bs) or bs
        b_data += to_bytes(padding_length * chr(padding_length), encoding='ascii', errors='strict')

        # COUNTER.new PARAMETERS
        # 1) nbits (integer) - Length of the counter, in bits.
        # 2) initial_value (integer) - initial value of the counter. "iv" from gen_key_initctr

        ctr = Counter.new(128, initial_value=int(iv, 16))

        # AES.new PARAMETERS
        # 1) AES key, must be either 16, 24, or 32 bytes long -- "key" from gen_key_initctr
        # 2) MODE_CTR, is the recommended mode
        # 3) counter=<CounterObject>

        cipher = AES.new(key1, AES.MODE_CTR, counter=ctr)

        # ENCRYPT PADDED DATA
        # the _data name is just to indicate this is including padding
        b_ciphertext_data = cipher.encrypt(b_data)

        # COMBINE SALT, DIGEST AND DATA
        hmac = HMAC.new(key2, b_ciphertext_data, SHA256)
        b_message = b'\n'.join([hexlify(b_salt), to_bytes(hmac.hexdigest()), hexlify(b_ciphertext_data)])
        return hexlify(b_message)


    def _verify_hmac(self, context, crypted_hmac, crypted_data):
        hmacDecrypt = HMAC.new(context.key2, crypted_data, SHA256)
        if not self.is_equal(crypted_hmac, to_bytes(hmacDecrypt.hexdigest())):
            return None


    def _decrypt(self, context, crytped_data

    def decrypt(self, data, secrets):
        b_data = data
        # SPLIT SALT, DIGEST, AND DATA
        b_data = unhexlify(b_data)
        b_salt, b_ciphertext_hmac, b_ciphertext_data = b_data.split(b"\n", 2)
        b_salt = unhexlify(b_salt)
        b_ciphertext_data = unhexlify(b_ciphertext_data)

        password = secrets.get_secret()
        b_key1, b_key2, b_iv = self.gen_key_initctr(password, b_salt)

        # TODO: move to it's own method
        # EXIT EARLY IF DIGEST DOESN'T MATCH
        hmacDecrypt = HMAC.new(b_key2, b_ciphertext_data, SHA256)
        if not self.is_equal(b_ciphertext_hmac, to_bytes(hmacDecrypt.hexdigest())):
            return None

        # SET THE COUNTER AND THE CIPHER
        ctr = Counter.new(128, initial_value=int(b_iv, 16))
        cipher = AES.new(b_key1, AES.MODE_CTR, counter=ctr)

        # DECRYPT PADDED DATA
        b_plaintext_data = cipher.decrypt(b_ciphertext_data)

        # UNPAD DATA
        try:
            padding_length = ord(b_plaintext_data[-1])
        except TypeError:
            padding_length = b_plaintext_data[-1]

        b_plaintext = b_plaintext_data[:-padding_length]
        return b_plaintext

    def is_equal(self, a, b):
        """
        Comparing 2 byte arrrays in constant time
        to avoid timing attacks.

        It would be nice if there was a library for this but
        hey.
        """
        # new names that match b_ for bytes naming scheme
        b_a = a
        b_b = b
        # http://codahale.com/a-lesson-in-timing-attacks/
        if len(b_a) != len(b_b):
            return False

        result = 0
        for b_x, b_y in zip(b_a, b_b):
            if PY3:
                result |= b_x ^ b_y
            else:
                result |= ord(b_x) ^ ord(b_y)
        return result == 0


CIPHER_MAPPING = {u'AES': VaultAES,
                  u'AES256': VaultAES256}

def cipher_factory(cipher_name):
    # Keys could be made bytes later if the code that gets the data is more
    # naturally byte-oriented
    try:
        cipher_class = CIPHER_MAPPING[cipher_name]
    except KeyError:
        raise AnsibleError(u"{0} cipher could not be found".format(cipher_name))
    return cipher_class
