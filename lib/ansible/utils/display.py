# (c) 2014, Michael DeHaan <michael.dehaan@gmail.com>
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

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import fcntl
import textwrap
import os
import random
import subprocess
import sys
import time
import locale
import logging
import getpass
import errno
from struct import unpack, pack
from termios import TIOCGWINSZ

from ansible import constants as C
from ansible.errors import AnsibleError
from ansible.utils.color import stringc
from ansible.module_utils._text import to_bytes, to_text


# TODO: mv these to a version abstration class?
#
try:
    # Python 2
    input = raw_input
except NameError:
    # Python 3, we already have raw_input
    pass

logger = None
#TODO: make this a logging callback instead
if C.DEFAULT_LOG_PATH:
    path = C.DEFAULT_LOG_PATH
    # TODO: use
    if (os.path.exists(path) and os.access(path, os.W_OK)) or os.access(os.path.dirname(path), os.W_OK):
        logging.basicConfig(filename=path, level=logging.DEBUG, format='%(asctime)s %(name)s %(message)s')
        # logging handles tracking the pid
        mypid = str(os.getpid())
        # huh, but logging doesn't have the user in log record, but something the
        # a custom Filter or Handler can do
        user = getpass.getuser()
        # FIXME: don't do this, use the module name or module.classname, or worse, specify a meaningful name
        #        like 'ansible-playbook' or 'ansible.remote.%(task_name)s'
        #        This makes it impossible to do much tweaking with log handler configuration
        #        ie, sending 'ansible.cli.ansible' errors to stderr and 'ansible.playbook.play_context' debug to ~/.ansible-playbook.log etc
        logger = logging.getLogger("p=%s u=%s | " % (mypid, user))
    else:
        # TODO: warning is fine, but just setup a NullHandler
        print("[WARNING]: log file at %s is not writeable and we cannot create it, aborting\n" % path, file=sys.stderr)

b_COW_PATHS = (b"/usr/bin/cowsay",
               b"/usr/games/cowsay",
               b"/usr/local/bin/cowsay",  # BSD path for cowsay
               b"/opt/local/bin/cowsay",  # MacPorts path for cowsay
              )
class Display:

    def __init__(self, verbosity=0):

        self.columns = None
        self.verbosity = verbosity

        # list of all deprecation messages to prevent duplicate display
        self._deprecations = {}
        self._warns        = {}
        self._errors       = {}

        self.b_cowsay = None
        self.noncow = C.ANSIBLE_COW_SELECTION

        self.set_cowsay_info()

        if self.b_cowsay:
            try:
                cmd = subprocess.Popen([self.b_cowsay, "-l"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                (out, err) = cmd.communicate()
                self.cows_available = [ to_bytes(c) for c in set(C.ANSIBLE_COW_WHITELIST).intersection(out.split())]
            except:
                # could not execute cowsay for some reason
                self.b_cowsay = False

        self._set_column_width()

    def set_cowsay_info(self):
        if not C.ANSIBLE_NOCOWS:
            for b_cow_path in b_COW_PATHS:
                if os.path.exists(b_cow_path):
                    self.b_cowsay = b_cow_path

    def display(self, msg, color=None, stderr=False, screen_only=False, log_only=False):
        """ Display a message to the user

        Note: msg *must* be a unicode string to prevent UnicodeError tracebacks.
        """

        nocolor = msg
        if color:
            msg = stringc(msg, color)

        if not log_only:
            if not msg.endswith(u'\n'):
                msg2 = msg + u'\n'
            else:
                msg2 = msg

            msg2 = to_bytes(msg2, encoding=self._output_encoding(stderr=stderr))
            if sys.version_info >= (3,):
                # Convert back to text string on python3
                # We first convert to a byte string so that we get rid of
                # characters that are invalid in the user's locale
                msg2 = to_text(msg2, self._output_encoding(stderr=stderr), errors='replace')

            if not stderr:
                fileobj = sys.stdout
            else:
                fileobj = sys.stderr

            fileobj.write(msg2)

            try:
                fileobj.flush()
            except IOError as e:
                # Ignore EPIPE in case fileobj has been prematurely closed, eg.
                # when piping to "head -n1"
                if e.errno != errno.EPIPE:
                    raise

        if logger and not screen_only:
            msg2 = nocolor.lstrip(u'\n')

            msg2 = to_bytes(msg2)
            if sys.version_info >= (3,):
                # Convert back to text string on python3
                # We first convert to a byte string so that we get rid of
                # characters that are invalid in the user's locale
                msg2 = to_text(msg2, self._output_encoding(stderr=stderr))

            # could potentially use logger 'extras' dict to set any per message colors that
            # dont map to logger/level
            if color == C.COLOR_ERROR:
                logger.error(msg2)
            else:
                logger.info(msg2)

    # caplevel/verbosity could be mapped to standard logging levels (DEBUG, etc) and/or values in between
    # ie, OURLOG_V=18 (between INFO and DEBUG) ,OURLOG_VVV=12, OURLOG_VVVV=9 (higher than DEBUG) etc
    # could add a logger subclass with .v() methods that call logger.log(OURLOG_V,msg, *args, *kkwargs)
    # or just use:
    # from ourlog import V,VV,VVV,VVVV,VVVVV,VVVVVV
    # log = logging.getLogger(__name__)
    # log.log(VV, 'the blah foo=%s', foo)
    #
    def v(self, msg, host=None):
        return self.verbose(msg, host=host, caplevel=0)

    def vv(self, msg, host=None):
        return self.verbose(msg, host=host, caplevel=1)

    def vvv(self, msg, host=None):
        return self.verbose(msg, host=host, caplevel=2)

    def vvvv(self, msg, host=None):
        return self.verbose(msg, host=host, caplevel=3)

    def vvvvv(self, msg, host=None):
        return self.verbose(msg, host=host, caplevel=4)

    def vvvvvv(self, msg, host=None):
        return self.verbose(msg, host=host, caplevel=5)

    # The locking here seems prone to deadlocking with ANSIBLE_DEBUG=1
    def debug(self, msg):
        if C.DEFAULT_DEBUG:
            self.display("%6d %0.5f: %s" % (os.getpid(), time.time(), msg), color=C.COLOR_DEBUG)

    def verbose(self, msg, host=None, caplevel=2):
        # FIXME: this needs to be implemented
        # could be custom logging.Filter()
        # The advantage of doing that with logging is we that we would get a object to log,
        # and dont str/repr it until we are emitting the log message, so have more info to
        # base sanitizing on
        #  unsafe or tainted object could also provide a 'public_statement' method that is
        #  the str/repr for public consumption, that could sanitize/censor. Or potentially, encrypt,
        #  or send to a different log handler
        #msg = utils.sanitize_output(msg)
        if self.verbosity > caplevel:
            # host is a little tricker to get into the log record, but a custom logging.Filter with
            # a reference to the context info with host can do it.
            if host is None:
                self.display(msg, color=C.COLOR_VERBOSE)
            else:
                self.display("<%s> %s" % (host, msg), color=C.COLOR_VERBOSE, screen_only=True)

    # could be WARNING level logging or potentially using python warnings module which
    # already has 'show once' support
    def deprecated(self, msg, version=None, removed=False):
        ''' used to print out a deprecation message.'''

        if not removed and not C.DEPRECATION_WARNINGS:
            return

        if not removed:
            if version:
                new_msg = "[DEPRECATION WARNING]: %s.\nThis feature will be removed in version %s." % (msg, version)
            else:
                new_msg = "[DEPRECATION WARNING]: %s.\nThis feature will be removed in a future release." % (msg)
            new_msg = new_msg + " Deprecation warnings can be disabled by setting deprecation_warnings=False in ansible.cfg.\n\n"
        else:
            raise AnsibleError("[DEPRECATED]: %s.\nPlease update your playbooks." % msg)

        # could be up to Formatter
        wrapped = textwrap.wrap(new_msg, self.columns, replace_whitespace=False, drop_whitespace=False)
        new_msg = "\n".join(wrapped) + "\n"

        if new_msg not in self._deprecations:
            self.display(new_msg.strip(), color=C.COLOR_DEPRECATE, stderr=True)
            self._deprecations[new_msg] = 1

    def warning(self, msg, formatted=False):
        # TODO: verify 'formatted' is actually used somewhere, I don't see any where obvious
        #       It's more or less in module api though...
        if not formatted:
            new_msg = "\n[WARNING]: %s" % msg
            wrapped = textwrap.wrap(new_msg, self.columns)
            new_msg = "\n".join(wrapped) + "\n"
        else:
            new_msg = "\n[WARNING]: \n%s" % msg

        if new_msg not in self._warns:
            self.display(new_msg, color=C.COLOR_WARN, stderr=True)
            self._warns[new_msg] = 1

    # TODO: remove? there seems to be one usage of this
    def system_warning(self, msg):
        if C.SYSTEM_WARNINGS:
            self.warning(msg)

    def banner(self, msg, color=None, cows=True):
        '''
        Prints a header-looking line with stars taking up to 80 columns
        of width (3 columns, minimum)
        '''
        if self.b_cowsay and cows:
        # cowsay could be a custom log handler... we would just not set it up if
        #  cowsay is disabled by default. Or you know, just remove it...

            try:
                self.banner_cowsay(msg)
                return
            except OSError:
                self.warning("somebody cleverly deleted cowsay or something during the PB run.  heh.")

        msg = msg.strip()
        star_len = self.columns - len(msg)
        if star_len <= 3:
            star_len = 3
        stars = u"*" * star_len
        self.display(u"\n%s %s" % (msg, stars), color=color)

    # could be Formatter or Filter
    def banner_cowsay(self, msg, color=None):
        if u": [" in msg:
            msg = msg.replace(u"[", u"")
            if msg.endswith(u"]"):
                msg = msg[:-1]
        runcmd = [self.b_cowsay, b"-W", b"60"]
        if self.noncow:
            thecow = self.noncow
            if thecow == b'random':
                thecow = random.choice(self.cows_available)
            runcmd.append(b'-f')
            runcmd.append(thecow)
        runcmd.append(to_bytes(msg))
        cmd = subprocess.Popen(runcmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out, err) = cmd.communicate()
        self.display(u"%s\n" % to_text(out), color=color)

    def error(self, msg, wrap_text=True):
        # wrap_text is used in only 5 places, 4 of which are the top level cli wrappers
        if wrap_text:
            new_msg = u"\n[ERROR]: %s" % msg
            # TODO: see if this works with non-ascii, it's been buggy in the past
            #       and prone to wrapping multibyte chars between bytes
            wrapped = textwrap.wrap(new_msg, self.columns)
            new_msg = u"\n".join(wrapped) + u"\n"
        else:
            new_msg = u"ERROR! %s" % msg
        if new_msg not in self._errors:
            self.display(new_msg, color=C.COLOR_ERROR, stderr=True)
            self._errors[new_msg] = 1

    @staticmethod
    def prompt(msg, private=False):
        # TODO: decouple 'prompt' from the display code
        #       otherwise this causes the same kind of problems as all
        #       weird ways ssh/sshpass/sftp do when reading stdout
        prompt_string = to_bytes(msg, encoding=Display._output_encoding())
        if sys.version_info >= (3,):
            # Convert back into text on python3.  We do this double conversion
            # to get rid of characters that are illegal in the user's locale
            prompt_string = to_text(prompt_string)

        if private:
            return getpass.getpass(msg)
        else:
            return input(prompt_string)

    def do_var_prompt(self, varname, private=True, prompt=None, encrypt=None, confirm=False, salt_size=None, salt=None, default=None):

        result = None
        if sys.__stdin__.isatty():

            do_prompt = self.prompt

            if prompt and default is not None:
                msg = "%s [%s]: " % (prompt, default)
            elif prompt:
                msg = "%s: " % prompt
            else:
                msg = 'input for %s: ' % varname

            if confirm:
                while True:
                    result = do_prompt(msg, private)
                    second = do_prompt("confirm " + msg, private)
                    if result == second:
                        break
                    self.display("***** VALUES ENTERED DO NOT MATCH ****")
            else:
                result = do_prompt(msg, private)
        else:
            # TODO: there could be a non-interactive callback registered for handling this
            result = None
            self.warning("Not prompting as we are not in interactive mode")

        # if result is false and default is not None
        if not result and default is not None:
            result = default

        if encrypt:
            # Circular import because encrypt needs a display class
            from ansible.utils.encrypt import do_encrypt
            result = do_encrypt(result, encrypt, salt_size, salt)

        # handle utf-8 chars
        result = to_text(result, errors='surrogate_or_strict')
        return result

    # What is stderr used for?
    @staticmethod
    def _output_encoding(stderr=False):
        encoding = locale.getpreferredencoding()
        # https://bugs.python.org/issue6202
        # Python2 hardcodes an obsolete value on Mac.  Use MacOSX defaults
        # instead.
        if encoding in ('mac-roman',):
            encoding = 'utf-8'
        return encoding

    def _set_column_width(self):
        if os.isatty(0):
            tty_size = unpack('HHHH', fcntl.ioctl(0, TIOCGWINSZ, pack('HHHH', 0, 0, 0, 0)))[1]
        else:
            tty_size = 0
        self.columns = max(79, tty_size - 1)
