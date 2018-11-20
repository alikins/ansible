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

print('start of display module load')

import errno
import fcntl
import getpass
import locale
import logging
import os
import random
import subprocess
import sys
import textwrap
import time
import traceback

from struct import unpack, pack
from termios import TIOCGWINSZ

from ansible import constants as C
from ansible.errors import AnsibleError
from ansible.module_utils._text import to_bytes, to_text
from ansible.utils.color import stringc

print('just before setting display_context=None')
global display_context
display_context = None

try:
    # Python 2
    input = raw_input
except NameError:
    # Python 3, we already have raw_input
    pass


class FilterBlackList(logging.Filter):
    def __init__(self, blacklist):
        self.blacklist = [logging.Filter(name) for name in blacklist]

    def filter(self, record):
        return not any(f.filter(record) for f in self.blacklist)


logger = None
# TODO: make this a logging callback instead
if getattr(C, 'DEFAULT_LOG_PATH'):
    path = C.DEFAULT_LOG_PATH
    if path and (os.path.exists(path) and os.access(path, os.W_OK)) or os.access(os.path.dirname(path), os.W_OK):
        logging.basicConfig(filename=path, level=logging.DEBUG, format='%(asctime)s %(name)s %(message)s')
        mypid = str(os.getpid())
        user = getpass.getuser()
        logger = logging.getLogger("p=%s u=%s | " % (mypid, user))
        for handler in logging.root.handlers:
            handler.addFilter(FilterBlackList(getattr(C, 'DEFAULT_LOG_FILTER', [])))
    else:
        print("[WARNING]: log file at %s is not writeable and we cannot create it, aborting\n" % path, file=sys.stderr)

b_COW_PATHS = (
    b"/usr/bin/cowsay",
    b"/usr/games/cowsay",
    b"/usr/local/bin/cowsay",  # BSD path for cowsay
    b"/opt/local/bin/cowsay",  # MacPorts path for cowsay
)


def get_column_width():
    tty_size = 0
    if os.isatty(0):
        tty_size = unpack('HHHH', fcntl.ioctl(0, TIOCGWINSZ, pack('HHHH', 0, 0, 0, 0)))[1]
    columns = max(79, tty_size - 1)
    return columns


def get_cowsay_path():
    b_cowsay = None

    if C.ANSIBLE_NOCOWS:
        return None

    if C.ANSIBLE_COW_PATH:
        b_cowsay = C.ANSIBLE_COW_PATH
        return b_cowsay

    for b_cow_path in b_COW_PATHS:
        if os.path.exists(b_cow_path):
            return b_cow_path

    return b_cowsay


def get_cows_available(b_cowsay):
    try:
        cmd = subprocess.Popen([b_cowsay, "-l"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out, err) = cmd.communicate()
        cows_available = set([to_text(c) for c in out.split()])
        if C.ANSIBLE_COW_WHITELIST:
            cows_available = set(C.ANSIBLE_COW_WHITELIST).intersection(cows_available)
        return cows_available
    except:
        # cowsay exec failed
        return None


class DisplayContext:
    def __init__(self, verbosity=0):
        self.verbosity = verbosity

        self.deprecations = {}
        self.warns = {}
        self.errors = {}

        self.b_cowsay = get_cowsay_path()
        self.cows_available = get_cows_available(self.b_cowsay)
        self.cow_selected = C.ANSIBLE_COW_SELECTION

        self.columns = get_column_width()


# import traceback
print('just before checking if display_context is None')
# traceback.print_stack()
if display_context is None:
    print('display_context is None, initing display_context %r' % display_context)
    display_context = DisplayContext()
    print('inited display_context %r' % display_context)


class Display:
    def __init__(self, context=None, verbosity=0):
        # defualt to the global display_context
        print('Display init: %r verbosity: %s' % (self, verbosity))
        self.context = context or display_context
        # traceback.print_stack()
        print('Display init context: %r' % (self.context))

    @property
    def verbosity(self):
        return self.context.verbosity

    @verbosity.setter
    def verbosity(self, value):
        print('setting context.verbosity = %s' % value)
        traceback.print_stack()
        self.context.verbosity = value

    def display(self, msg, color=None, stderr=False, screen_only=False, log_only=False):
        """ Display a message to the user

        Note: msg *must* be a unicode string to prevent UnicodeError tracebacks.
        """

        msg = '(d_c: %r pid: %s) ' % (self.context, os.getpid()) + msg
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

            # Note: After Display() class is refactored need to update the log capture
            # code in 'bin/ansible-connection' (and other relevant places).
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

            if color == C.COLOR_ERROR:
                logger.error(msg2)
            else:
                logger.info(msg2)

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

    def debug(self, msg, host=None):
        if C.DEFAULT_DEBUG:
            if host is None:
                self.display("%6d %0.5f: %s" % (os.getpid(), time.time(), msg), color=C.COLOR_DEBUG)
            else:
                self.display("%6d %0.5f [%s]: %s" % (os.getpid(), time.time(), host, msg), color=C.COLOR_DEBUG)

    def verbose(self, msg, host=None, caplevel=2):
        if self.context.verbosity > caplevel:
            if host is None:
                self.display(msg, color=C.COLOR_VERBOSE)
            else:
                self.display("<%s> %s" % (host, msg), color=C.COLOR_VERBOSE, screen_only=True)

    def deprecated(self, msg, version=None, removed=False):
        ''' used to print out a deprecation message.'''

        if not removed and not C.DEPRECATION_WARNINGS:
            return

        if not removed:
            if version:
                new_msg = "[DEPRECATION WARNING]: %s. This feature will be removed in version %s." % (msg, version)
            else:
                new_msg = "[DEPRECATION WARNING]: %s. This feature will be removed in a future release." % (msg)
            new_msg = new_msg + " Deprecation warnings can be disabled by setting deprecation_warnings=False in ansible.cfg.\n\n"
        else:
            raise AnsibleError("[DEPRECATED]: %s.\nPlease update your playbooks." % msg)

        wrapped = textwrap.wrap(new_msg, self.context.columns, drop_whitespace=False)
        new_msg = "\n".join(wrapped) + "\n"

        if new_msg not in self.context.deprecations:
            self.display(new_msg.strip(), color=C.COLOR_DEPRECATE, stderr=True)
            self.context.deprecations[new_msg] = 1

    def warning(self, msg, formatted=False):

        if not formatted:
            new_msg = "\n[WARNING]: %s" % msg
            wrapped = textwrap.wrap(new_msg, self.context.columns)
            new_msg = "\n".join(wrapped) + "\n"
        else:
            new_msg = "\n[WARNING]: \n%s" % msg

        if new_msg not in self.context.warns:
            self.display(new_msg, color=C.COLOR_WARN, stderr=True)
            self.context.warns[new_msg] = 1

    def system_warning(self, msg):
        if C.SYSTEM_WARNINGS:
            self.warning(msg)

    def banner(self, msg, color=None, cows=True):
        '''
        Prints a header-looking line with cowsay or stars wit hlength depending on terminal width (3 minimum)
        '''
        if self.context.b_cowsay and cows:
            try:
                self.banner_cowsay(msg)
                return
            except OSError:
                self.warning("somebody cleverly deleted cowsay or something during the PB run.  heh.")

        msg = msg.strip()
        star_len = self.context.columns - len(msg)
        if star_len <= 3:
            star_len = 3
        stars = u"*" * star_len
        self.display(u"\n%s %s" % (msg, stars), color=color)

    # TODO: most this doesn't need to be method of Display, just
    # needs a DisplayContext passed in and to return the text
    def banner_cowsay(self, msg, color=None):
        if u": [" in msg:
            msg = msg.replace(u"[", u"")
            if msg.endswith(u"]"):
                msg = msg[:-1]
        runcmd = [self.context.b_cowsay, b"-W", b"60"]
        # TODO: could be a DisplayContext.cow_selected property?
        if self.context.cow_selected:
            thecow = self.context.cow_selected
            if thecow == 'random':
                thecow = random.choice(list(self.context.cows_available))
            runcmd.append(b'-f')
            runcmd.append(to_bytes(thecow))
        runcmd.append(to_bytes(msg))
        cmd = subprocess.Popen(runcmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out, err) = cmd.communicate()
        self.display(u"%s\n" % to_text(out), color=color)

    def error(self, msg, wrap_text=True):
        if wrap_text:
            new_msg = u"\n[ERROR]: %s" % msg
            wrapped = textwrap.wrap(new_msg, self.context.columns)
            new_msg = u"\n".join(wrapped) + u"\n"
        else:
            new_msg = u"ERROR! %s" % msg
        if new_msg not in self.context.errors:
            self.display(new_msg, color=C.COLOR_ERROR, stderr=True)
            self.context.errors[new_msg] = 1

    @staticmethod
    def prompt(msg, private=False):
        prompt_string = to_bytes(msg, encoding=Display._output_encoding())
        if sys.version_info >= (3,):
            # Convert back into text on python3.  We do this double conversion
            # to get rid of characters that are illegal in the user's locale
            prompt_string = to_text(prompt_string)

        if private:
            return getpass.getpass(prompt_string)
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

    @staticmethod
    def _output_encoding(stderr=False):
        encoding = locale.getpreferredencoding()
        # https://bugs.python.org/issue6202
        # Python2 hardcodes an obsolete value on Mac.  Use MacOSX defaults
        # instead.
        if encoding in ('mac-roman',):
            encoding = 'utf-8'
        return encoding


# import traceback
# print('just before checking if display_ is None')
# traceback.print_stack()
# if display_ is None:
#    print('display_ is None, initing display_ %r' % display_)
#    display_ = Display()
#    print('inited display_ %r' % display_)
print('end of display module load')
