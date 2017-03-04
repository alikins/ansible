# -*- coding: utf-8 -*-
# (c) 2015, Toshio Kuratomi <tkuratomi@ansible.com>
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

from io import StringIO
import pprint

import pytest


from ansible import constants as C
from ansible.compat.selectors import SelectorKey, EVENT_READ
from ansible.compat.tests import unittest
from ansible.compat.tests.mock import patch, MagicMock, PropertyMock
from ansible.errors import AnsibleError, AnsibleConnectionFailure, AnsibleFileNotFound
from ansible.module_utils.six.moves import shlex_quote
from ansible.module_utils._text import to_bytes
from ansible.playbook.play_context import PlayContext
from ansible.plugins.connection import ssh


class TestRetry(unittest.TestCase):
    @staticmethod
    @ssh._ssh_retry
    def nothing():
        pass

    def test_no_args(self):
        try:
            self.nothing()
        except TypeError as e:
            print(e)

    def test_none(self):
        self.nothing(None)
        #self.assertRaises(TypeError, nothing())

    def test_empty(self):
        self.nothing([], {})


class TestRetryWrapsOneArgMethod(unittest.TestCase):
    @staticmethod
    @ssh._ssh_retry
    def nothing(dummy):
        print(dummy)

    def test_empty(self):
        self.nothing([], {})

    def test_none(self):
        self.nothing(None)

    def test_one_arg_empty_list(self):
        self.nothing([])


class TestRetryWrapsArgsKwargsMethod(unittest.TestCase):
    @staticmethod
    @ssh._ssh_retry
    def nothing(*args, **kwargs):
        pprint.pprint(args)
        pprint.pprint(kwargs)

    def test_empty(self):
        self.nothing([], {})

    def test_none(self):
        self.nothing(None)

    def test_one_arg_empty_list(self):
        self.nothing([])


class TestRetryFauxSshRunMethodWithBadArgs(unittest.TestCase):

    @ssh._ssh_retry
    def nothing(self, cmd, in_data, sudoable=True, checkrc=True):
        pprint.pprint(cmd)
        pprint.pprint(in_data)
        print('sudoable: %s' % sudoable)
        print('checkrc: %s' % checkrc)
        return None

    def _results(self, result):
        print('result: %s' % repr(result))

    def test_none(self):
        res = self.nothing(None)
        self._results(res)

    def test_one_arg_empty_list(self):
        res = self.nothing([])
        self._results(res)

    def test_empty(self):
        res = self.nothing([], {})
        self._results(res)

    # right number of args, but unexpected values
    def test_all_none(self):
        res = self.nothing(None, None, sudoable=None, checkrc=None)
        self._results(res)

    def test_all_none_just_kwargs(self):
        res = self.nothing(cmd=None, in_data=None, sudoable=None, checkrc=None)
        self._results(res)


class TestRetryFauxSshRunMethod(unittest.TestCase):
    _host = 'localhost'

    @ssh._ssh_retry
    def nothing(self, cmd, in_data, sudoable=True, checkrc=True, **kwargs):
        pprint.pprint(cmd)
        pprint.pprint(in_data)
        print('sudoable: %s' % sudoable)
        print('checkrc: %s' % checkrc)
        return_results = self._return(cmd, in_data, sudoable, checkrc)
        print('return_tuple: %s' % pprint.pformat(return_results))
        return return_results

    def _return(self, *args, **kwargs):
        return None

    @property
    def host(self):
        return self._host or None

    def _results(self, result):
        print('result: %s' % repr(result))

    def test_cmd_empty_list(self):
        res = self.nothing([], in_data=None, sudoable=False, checkrc=False,
                           retries=1, pause_amount=0.1, max_pause=1.0)
        self._results(res)

    def test_cmd_empty_generator(self):
        def cmd_generator():
            for i in []:
                yield i

        res = self.nothing(cmd_generator(), in_data=None, sudoable=False, checkrc=False,
                           retries=1, pause_amount=0.1, max_pause=0.2)
        self._results(res)

    def test_cmd_list_none(self):
        res = self.nothing(None, in_data=None, sudoable=False, checkrc=False,
                           retries=5, pause_amount=0.1, max_pause=0.2)
        self._results(res)

    # results in negative pause time and exception from time.sleep
#    def test_sub_one_sec_pause(self):
#        res = self.nothing(None, in_data=None, sudoable=False, checkrc=False,
#                           retries=4, pause_amount=0.1, max_pause=1.0)
#        self._results(res)


class TestRetryFauxSshRunMethodReturnsEmptyTuple(TestRetryFauxSshRunMethod):

    def _return(self, *args, **kwargs):
        return tuple()


class TestRetryFauxSshRunMethodReturnsTupleOfNone(TestRetryFauxSshRunMethod):
    def _return(self, *args, **kwargs):
        return tuple([None, None, None])


class TestRetryFauxSshRunMethodReturnsTupleReturnCodeZero(TestRetryFauxSshRunMethod):
    def _return(self, *args, **kwargs):
        return tuple([0, None, None])


class TestRetryFauxSshRunMethodReturnsTupleReturnCodeOne(TestRetryFauxSshRunMethod):
    def _return(self, *args, **kwargs):
        return tuple([1, None, None])


class TestRetryFauxSshRunMethodReturnsTupleReturnCode255(TestRetryFauxSshRunMethod):
    def _return(self, *args, **kwargs):
        return tuple([255, None, None])


class TestRetryFauxSshRunMethodReturnsRaisesException(TestRetryFauxSshRunMethod):
    def _return(self, *args, **kwargs):
        raise Exception('this was raised from %s _return' % self.__class__.__name__)


class TestRetryFauxSshRunMethodReturnsRaisesAnsibleConnectionFailure(TestRetryFauxSshRunMethod):
    def _return(self, *args, **kwargs):
        raise AnsibleConnectionFailure('connection failure: this was raised from %s _return' % self.__class__.__name__)

    def setUp(self):
        self.patcher = patch('ansible.plugins.connection.ssh.C.ANSIBLE_SSH_RETRIES', return_value=10)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()


class TestConnectionBaseClass(unittest.TestCase):

    def test_plugins_connection_ssh_basic(self):
        pc = PlayContext()
        new_stdin = StringIO()
        conn = ssh.Connection(pc, new_stdin)

        # connect just returns self, so assert that
        res = conn._connect()
        self.assertEqual(conn, res)

        ssh.SSHPASS_AVAILABLE = False
        self.assertFalse(conn._sshpass_available())

        ssh.SSHPASS_AVAILABLE = True
        self.assertTrue(conn._sshpass_available())

        with patch('subprocess.Popen') as p:
            ssh.SSHPASS_AVAILABLE = None
            p.return_value = MagicMock()
            self.assertTrue(conn._sshpass_available())

            ssh.SSHPASS_AVAILABLE = None
            p.return_value = None
            p.side_effect = OSError()
            self.assertFalse(conn._sshpass_available())

        conn.close()
        self.assertFalse(conn._connected)

    def test_plugins_connection_ssh__build_command(self):
        pc = PlayContext()
        new_stdin = StringIO()
        conn = ssh.Connection(pc, new_stdin)
        conn._build_command('ssh')

    def test_plugins_connection_ssh_exec_command(self):
        pc = PlayContext()
        new_stdin = StringIO()
        conn = ssh.Connection(pc, new_stdin)

        conn._build_command = MagicMock()
        conn._build_command.return_value = 'ssh something something'
        conn._run = MagicMock()
        conn._run.return_value = (0, 'stdout', 'stderr')

        res, stdout, stderr = conn.exec_command('ssh')
        res, stdout, stderr = conn.exec_command('ssh', 'this is some data')

    def test_plugins_connection_ssh__examine_output(self):
        pc = PlayContext()
        new_stdin = StringIO()

        conn = ssh.Connection(pc, new_stdin)

        conn.check_password_prompt = MagicMock()
        conn.check_become_success = MagicMock()
        conn.check_incorrect_password = MagicMock()
        conn.check_missing_password = MagicMock()

        def _check_password_prompt(line):
            if b'foo' in line:
                return True
            return False

        def _check_become_success(line):
            if b'BECOME-SUCCESS-abcdefghijklmnopqrstuvxyz' in line:
                return True
            return False

        def _check_incorrect_password(line):
            if b'incorrect password' in line:
                return True
            return False

        def _check_missing_password(line):
            if b'bad password' in line:
                return True
            return False

        conn.check_password_prompt.side_effect = _check_password_prompt
        conn.check_become_success.side_effect = _check_become_success
        conn.check_incorrect_password.side_effect = _check_incorrect_password
        conn.check_missing_password.side_effect = _check_missing_password

        # test examining output for prompt
        conn._flags = dict(
            become_prompt=False,
            become_success=False,
            become_error=False,
            become_nopasswd_error=False,
        )

        pc.prompt = True
        output, unprocessed = conn._examine_output(u'source', u'state', b'line 1\nline 2\nfoo\nline 3\nthis should be the remainder', False)
        self.assertEqual(output, b'line 1\nline 2\nline 3\n')
        self.assertEqual(unprocessed, b'this should be the remainder')
        self.assertTrue(conn._flags['become_prompt'])
        self.assertFalse(conn._flags['become_success'])
        self.assertFalse(conn._flags['become_error'])
        self.assertFalse(conn._flags['become_nopasswd_error'])

        # test examining output for become prompt
        conn._flags = dict(
            become_prompt=False,
            become_success=False,
            become_error=False,
            become_nopasswd_error=False,
        )

        pc.prompt = False
        pc.success_key = u'BECOME-SUCCESS-abcdefghijklmnopqrstuvxyz'
        output, unprocessed = conn._examine_output(u'source', u'state', b'line 1\nline 2\nBECOME-SUCCESS-abcdefghijklmnopqrstuvxyz\nline 3\n', False)
        self.assertEqual(output, b'line 1\nline 2\nline 3\n')
        self.assertEqual(unprocessed, b'')
        self.assertFalse(conn._flags['become_prompt'])
        self.assertTrue(conn._flags['become_success'])
        self.assertFalse(conn._flags['become_error'])
        self.assertFalse(conn._flags['become_nopasswd_error'])

        # test examining output for become failure
        conn._flags = dict(
            become_prompt=False,
            become_success=False,
            become_error=False,
            become_nopasswd_error=False,
        )

        pc.prompt = False
        pc.success_key = None
        output, unprocessed = conn._examine_output(u'source', u'state', b'line 1\nline 2\nincorrect password\n', True)
        self.assertEqual(output, b'line 1\nline 2\nincorrect password\n')
        self.assertEqual(unprocessed, b'')
        self.assertFalse(conn._flags['become_prompt'])
        self.assertFalse(conn._flags['become_success'])
        self.assertTrue(conn._flags['become_error'])
        self.assertFalse(conn._flags['become_nopasswd_error'])

        # test examining output for missing password
        conn._flags = dict(
            become_prompt=False,
            become_success=False,
            become_error=False,
            become_nopasswd_error=False,
        )

        pc.prompt = False
        pc.success_key = None
        output, unprocessed = conn._examine_output(u'source', u'state', b'line 1\nbad password\n', True)
        self.assertEqual(output, b'line 1\nbad password\n')
        self.assertEqual(unprocessed, b'')
        self.assertFalse(conn._flags['become_prompt'])
        self.assertFalse(conn._flags['become_success'])
        self.assertFalse(conn._flags['become_error'])
        self.assertTrue(conn._flags['become_nopasswd_error'])

    @patch('time.sleep')
    @patch('os.path.exists')
    def test_plugins_connection_ssh_put_file(self, mock_ospe, mock_sleep):
        pc = PlayContext()
        new_stdin = StringIO()
        conn = ssh.Connection(pc, new_stdin)
        conn._build_command = MagicMock()
        conn._run = MagicMock()

        mock_ospe.return_value = True
        conn._build_command.return_value = 'some command to run'
        conn._run.return_value = (0, '', '')
        conn.host = "some_host"

        C.ANSIBLE_SSH_RETRIES = 9

        # Test with C.DEFAULT_SCP_IF_SSH set to smart
        # Test when SFTP works
        C.DEFAULT_SCP_IF_SSH = 'smart'
        expected_in_data = b' '.join((b'put', to_bytes(shlex_quote('/path/to/in/file')), to_bytes(shlex_quote('/path/to/dest/file')))) + b'\n'
        conn.put_file('/path/to/in/file', '/path/to/dest/file')
        conn._run.assert_called_with('some command to run', expected_in_data, checkrc=False)

        # Test when SFTP doesn't work but SCP does
        conn._run.side_effect = [(1, 'stdout', 'some errors'), (0, '', '')]
        conn.put_file('/path/to/in/file', '/path/to/dest/file')
        conn._run.assert_called_with('some command to run', None, checkrc=False)
        conn._run.side_effect = None

        # test with C.DEFAULT_SCP_IF_SSH enabled
        C.DEFAULT_SCP_IF_SSH = True
        conn.put_file('/path/to/in/file', '/path/to/dest/file')
        conn._run.assert_called_with('some command to run', None, checkrc=False)

        conn.put_file(u'/path/to/in/file/with/unicode-fö〩', u'/path/to/dest/file/with/unicode-fö〩')
        conn._run.assert_called_with('some command to run', None, checkrc=False)

        # test with C.DEFAULT_SCP_IF_SSH disabled
        C.DEFAULT_SCP_IF_SSH = False
        expected_in_data = b' '.join((b'put', to_bytes(shlex_quote('/path/to/in/file')), to_bytes(shlex_quote('/path/to/dest/file')))) + b'\n'
        conn.put_file('/path/to/in/file', '/path/to/dest/file')
        conn._run.assert_called_with('some command to run', expected_in_data, checkrc=False)

        expected_in_data = b' '.join((b'put',
                                      to_bytes(shlex_quote('/path/to/in/file/with/unicode-fö〩')),
                                      to_bytes(shlex_quote('/path/to/dest/file/with/unicode-fö〩')))) + b'\n'
        conn.put_file(u'/path/to/in/file/with/unicode-fö〩', u'/path/to/dest/file/with/unicode-fö〩')
        conn._run.assert_called_with('some command to run', expected_in_data, checkrc=False)

        # test that a non-zero rc raises an error
        conn._run.return_value = (1, 'stdout', 'some errors')
        self.assertRaises(AnsibleError, conn.put_file, '/path/to/bad/file', '/remote/path/to/file')

        # test that a not-found path raises an error
        mock_ospe.return_value = False
        conn._run.return_value = (0, 'stdout', '')
        self.assertRaises(AnsibleFileNotFound, conn.put_file, '/path/to/bad/file', '/remote/path/to/file')

    @patch('time.sleep')
    def test_plugins_connection_ssh_fetch_file(self, mock_sleep):
        pc = PlayContext()
        new_stdin = StringIO()
        conn = ssh.Connection(pc, new_stdin)
        conn._build_command = MagicMock()
        conn._run = MagicMock()

        conn._build_command.return_value = 'some command to run'
        conn._run.return_value = (0, '', '')
        conn.host = "some_host"

        C.ANSIBLE_SSH_RETRIES = 9

        # Test with C.DEFAULT_SCP_IF_SSH set to smart
        # Test when SFTP works
        C.DEFAULT_SCP_IF_SSH = 'smart'
        expected_in_data = b' '.join((b'get', to_bytes(shlex_quote('/path/to/in/file')), to_bytes(shlex_quote('/path/to/dest/file')))) + b'\n'
        conn.fetch_file('/path/to/in/file', '/path/to/dest/file')
        conn._run.assert_called_with('some command to run', expected_in_data, checkrc=False)

        # Test when SFTP doesn't work but SCP does
        conn._run.side_effect = [(1, 'stdout', 'some errors'), (0, '', '')]
        conn.fetch_file('/path/to/in/file', '/path/to/dest/file')
        conn._run.assert_called_with('some command to run', None, checkrc=False)
        conn._run.side_effect = None

        # test with C.DEFAULT_SCP_IF_SSH enabled
        C.DEFAULT_SCP_IF_SSH = True
        conn.fetch_file('/path/to/in/file', '/path/to/dest/file')
        conn._run.assert_called_with('some command to run', None, checkrc=False)

        conn.fetch_file(u'/path/to/in/file/with/unicode-fö〩', u'/path/to/dest/file/with/unicode-fö〩')
        conn._run.assert_called_with('some command to run', None, checkrc=False)

        # test with C.DEFAULT_SCP_IF_SSH disabled
        C.DEFAULT_SCP_IF_SSH = False
        expected_in_data = b' '.join((b'get', to_bytes(shlex_quote('/path/to/in/file')), to_bytes(shlex_quote('/path/to/dest/file')))) + b'\n'
        conn.fetch_file('/path/to/in/file', '/path/to/dest/file')
        conn._run.assert_called_with('some command to run', expected_in_data, checkrc=False)

        expected_in_data = b' '.join((b'get',
                                      to_bytes(shlex_quote('/path/to/in/file/with/unicode-fö〩')),
                                      to_bytes(shlex_quote('/path/to/dest/file/with/unicode-fö〩')))) + b'\n'
        conn.fetch_file(u'/path/to/in/file/with/unicode-fö〩', u'/path/to/dest/file/with/unicode-fö〩')
        conn._run.assert_called_with('some command to run', expected_in_data, checkrc=False)

        # test that a non-zero rc raises an error
        conn._run.return_value = (1, 'stdout', 'some errors')
        self.assertRaises(AnsibleError, conn.fetch_file, '/path/to/bad/file', '/remote/path/to/file')


class MockSelector(object):
    def __init__(self):
        self.files_watched = 0
        self.register = MagicMock(side_effect=self._register)
        self.unregister = MagicMock(side_effect=self._unregister)
        self.close = MagicMock()
        self.get_map = MagicMock(side_effect=self._get_map)
        self.select = MagicMock()

    def _register(self, *args, **kwargs):
        self.files_watched += 1

    def _unregister(self, *args, **kwargs):
        self.files_watched -= 1

    def _get_map(self, *args, **kwargs):
        return self.files_watched


@pytest.fixture
def mock_run_env(request, mocker):
    pc = PlayContext()
    new_stdin = StringIO()

    conn = ssh.Connection(pc, new_stdin)
    conn._send_initial_data = MagicMock()
    conn._examine_output = MagicMock()
    conn._terminate_process = MagicMock()
    conn.sshpass_pipe = [MagicMock(), MagicMock()]

    request.cls.pc = pc
    request.cls.conn = conn

    mock_popen_res = MagicMock()
    mock_popen_res.poll = MagicMock()
    mock_popen_res.wait = MagicMock()
    mock_popen_res.stdin = MagicMock()
    mock_popen_res.stdin.fileno.return_value = 1000
    mock_popen_res.stdout = MagicMock()
    mock_popen_res.stdout.fileno.return_value = 1001
    mock_popen_res.stderr = MagicMock()
    mock_popen_res.stderr.fileno.return_value = 1002
    mock_popen_res.returncode = 0
    request.cls.mock_popen_res = mock_popen_res

    mock_popen = mocker.patch('subprocess.Popen', return_value=mock_popen_res)
    request.cls.mock_popen = mock_popen

    request.cls.mock_selector = MockSelector()
    mocker.patch('ansible.compat.selectors.DefaultSelector', lambda: request.cls.mock_selector)

    request.cls.mock_openpty = mocker.patch('pty.openpty')

    mocker.patch('fcntl.fcntl')
    mocker.patch('os.write')
    mocker.patch('os.close')


@pytest.mark.usefixtures('mock_run_env')
class TestSSHConnectionRun(object):
    # FIXME:
    # These tests are little more than a smoketest.  Need to enhance them
    # a bit to check that they're calling the relevant functions and making
    # complete coverage of the code paths
    def test_no_escalation(self):
        self.mock_popen_res.stdout.read.side_effect = [b"my_stdout\n", b"second_line"]
        self.mock_popen_res.stderr.read.side_effect = [b"my_stderr"]
        self.mock_selector.select.side_effect = [
            [(SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            [(SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            [(SelectorKey(self.mock_popen_res.stderr, 1002, [EVENT_READ], None), EVENT_READ)],
            []]
        self.mock_selector.get_map.side_effect = lambda: True

        return_code, b_stdout, b_stderr = self.conn._run("ssh", "this is input data")
        assert return_code == 0
        assert b_stdout == b'my_stdout\nsecond_line'
        assert b_stderr == b'my_stderr'
        assert self.mock_selector.register.called is True
        assert self.mock_selector.register.call_count == 2
        assert self.conn._send_initial_data.called is True
        assert self.conn._send_initial_data.call_count == 1
        assert self.conn._send_initial_data.call_args[0][1] == 'this is input data'

    def test_with_password(self):
        # test with a password set to trigger the sshpass write
        self.pc.password = '12345'
        self.mock_popen_res.stdout.read.side_effect = [b"some data", b"", b""]
        self.mock_popen_res.stderr.read.side_effect = [b""]
        self.mock_selector.select.side_effect = [
            [(SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            [(SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            [(SelectorKey(self.mock_popen_res.stderr, 1002, [EVENT_READ], None), EVENT_READ)],
            [(SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            []]
        self.mock_selector.get_map.side_effect = lambda: True

        return_code, b_stdout, b_stderr = self.conn._run(["ssh", "is", "a", "cmd"], "this is more data")
        assert return_code == 0
        assert b_stdout == b'some data'
        assert b_stderr == b''
        assert self.mock_selector.register.called is True
        assert self.mock_selector.register.call_count == 2
        assert self.conn._send_initial_data.called is True
        assert self.conn._send_initial_data.call_count == 1
        assert self.conn._send_initial_data.call_args[0][1] == 'this is more data'

    def _password_with_prompt_examine_output(self, sourice, state, b_chunk, sudoable):
        if state == 'awaiting_prompt':
            self.conn._flags['become_prompt'] = True
        elif state == 'awaiting_escalation':
            self.conn._flags['become_success'] = True
        return (b'', b'')

    def test_password_with_prompt(self):
        # test with password prompting enabled
        self.pc.password = None
        self.pc.prompt = b'Password:'
        self.conn._examine_output.side_effect = self._password_with_prompt_examine_output
        self.mock_popen_res.stdout.read.side_effect = [b"Password:", b"Success", b""]
        self.mock_popen_res.stderr.read.side_effect = [b""]
        self.mock_selector.select.side_effect = [
            [(SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            [(SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            [(SelectorKey(self.mock_popen_res.stderr, 1002, [EVENT_READ], None), EVENT_READ),
             (SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            []]
        self.mock_selector.get_map.side_effect = lambda: True

        return_code, b_stdout, b_stderr = self.conn._run("ssh", "this is input data")
        assert return_code == 0
        assert b_stdout == b''
        assert b_stderr == b''
        assert self.mock_selector.register.called is True
        assert self.mock_selector.register.call_count == 2
        assert self.conn._send_initial_data.called is True
        assert self.conn._send_initial_data.call_count == 1
        assert self.conn._send_initial_data.call_args[0][1] == 'this is input data'

    def test_password_with_become(self):
        # test with some become settings
        self.pc.prompt = b'Password:'
        self.pc.become = True
        self.pc.success_key = 'BECOME-SUCCESS-abcdefg'
        self.conn._examine_output.side_effect = self._password_with_prompt_examine_output
        self.mock_popen_res.stdout.read.side_effect = [b"Password:", b"BECOME-SUCCESS-abcdefg", b"abc"]
        self.mock_popen_res.stderr.read.side_effect = [b"123"]
        self.mock_selector.select.side_effect = [
            [(SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            [(SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            [(SelectorKey(self.mock_popen_res.stderr, 1002, [EVENT_READ], None), EVENT_READ)],
            [(SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            []]
        self.mock_selector.get_map.side_effect = lambda: True

        return_code, b_stdout, b_stderr = self.conn._run("ssh", "this is input data")
        assert return_code == 0
        assert b_stdout == b'abc'
        assert b_stderr == b'123'
        assert self.mock_selector.register.called is True
        assert self.mock_selector.register.call_count == 2
        assert self.conn._send_initial_data.called is True
        assert self.conn._send_initial_data.call_count == 1
        assert self.conn._send_initial_data.call_args[0][1] == 'this is input data'

    def test_pasword_without_data(self):
        # simulate no data input
        self.mock_openpty.return_value = (98, 99)
        self.mock_popen_res.stdout.read.side_effect = [b"some data", b"", b""]
        self.mock_popen_res.stderr.read.side_effect = [b""]
        self.mock_selector.select.side_effect = [
            [(SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            [(SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            [(SelectorKey(self.mock_popen_res.stderr, 1002, [EVENT_READ], None), EVENT_READ)],
            [(SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            []]
        self.mock_selector.get_map.side_effect = lambda: True

        return_code, b_stdout, b_stderr = self.conn._run("ssh", "")
        assert return_code == 0
        assert b_stdout == b'some data'
        assert b_stderr == b''
        assert self.mock_selector.register.called is True
        assert self.mock_selector.register.call_count == 2
        assert self.conn._send_initial_data.called is False

    def test_pasword_without_data(self):
        # simulate no data input but Popen using new pty's fails
        self.mock_popen.return_value = None
        self.mock_popen.side_effect = [OSError(), self.mock_popen_res]

        # simulate no data input
        self.mock_openpty.return_value = (98, 99)
        self.mock_popen_res.stdout.read.side_effect = [b"some data", b"", b""]
        self.mock_popen_res.stderr.read.side_effect = [b""]
        self.mock_selector.select.side_effect = [
            [(SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            [(SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            [(SelectorKey(self.mock_popen_res.stderr, 1002, [EVENT_READ], None), EVENT_READ)],
            [(SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            []]
        self.mock_selector.get_map.side_effect = lambda: True

        return_code, b_stdout, b_stderr = self.conn._run("ssh", "")
        assert return_code == 0
        assert b_stdout == b'some data'
        assert b_stderr == b''
        assert self.mock_selector.register.called is True
        assert self.mock_selector.register.call_count == 2
        assert self.conn._send_initial_data.called is False


@pytest.mark.usefixtures('mock_run_env')
class TestSSHConnectionRetries(object):
    def test_retry_then_success(self, monkeypatch):
        monkeypatch.setattr(C, 'HOST_KEY_CHECKING', False)
        monkeypatch.setattr(C, 'ANSIBLE_SSH_RETRIES', 3)

        monkeypatch.setattr('time.sleep', lambda x: None)

        self.mock_popen_res.stdout.read.side_effect = [b"", b"my_stdout\n", b"second_line"]
        self.mock_popen_res.stderr.read.side_effect = [b"", b"my_stderr"]
        type(self.mock_popen_res).returncode = PropertyMock(side_effect=[255] * 3 + [0] * 4)

        self.mock_selector.select.side_effect = [
            [(SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            [(SelectorKey(self.mock_popen_res.stderr, 1002, [EVENT_READ], None), EVENT_READ)],
            [],
            [(SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            [(SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            [(SelectorKey(self.mock_popen_res.stderr, 1002, [EVENT_READ], None), EVENT_READ)],
            []
        ]
        self.mock_selector.get_map.side_effect = lambda: True

        self.conn._build_command = MagicMock()
        self.conn._build_command.return_value = 'ssh'

        return_code, b_stdout, b_stderr = self.conn.exec_command('ssh', 'some data')
        assert return_code == 0
        assert b_stdout == b'my_stdout\nsecond_line'
        assert b_stderr == b'my_stderr'

    def test_multiple_failures(self, monkeypatch):
        monkeypatch.setattr(C, 'HOST_KEY_CHECKING', False)
        monkeypatch.setattr(C, 'ANSIBLE_SSH_RETRIES', 9)

        monkeypatch.setattr('time.sleep', lambda x: None)

        self.mock_popen_res.stdout.read.side_effect = [b""] * 10
        self.mock_popen_res.stderr.read.side_effect = [b""] * 10
        type(self.mock_popen_res).returncode = PropertyMock(side_effect=[255] * 30)

        self.mock_selector.select.side_effect = [
            [(SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            [(SelectorKey(self.mock_popen_res.stderr, 1002, [EVENT_READ], None), EVENT_READ)],
            [],
        ] * 10
        self.mock_selector.get_map.side_effect = lambda: True

        self.conn._build_command = MagicMock()
        self.conn._build_command.return_value = 'ssh'

        pytest.raises(AnsibleConnectionFailure, self.conn.exec_command, 'ssh', 'some data')
        assert self.mock_popen.call_count == 10

    def test_abitrary_exceptions(self, monkeypatch):
        monkeypatch.setattr(C, 'HOST_KEY_CHECKING', False)
        monkeypatch.setattr(C, 'ANSIBLE_SSH_RETRIES', 9)

        monkeypatch.setattr('time.sleep', lambda x: None)

        self.conn._build_command = MagicMock()
        self.conn._build_command.return_value = 'ssh'

        self.mock_popen.side_effect = [Exception('bad')] * 10
        pytest.raises(Exception, self.conn.exec_command, 'ssh', 'some data')
        assert self.mock_popen.call_count == 10

    def test_put_file_retries(self, monkeypatch):
        monkeypatch.setattr(C, 'HOST_KEY_CHECKING', False)
        monkeypatch.setattr(C, 'ANSIBLE_SSH_RETRIES', 3)

        monkeypatch.setattr('time.sleep', lambda x: None)
        monkeypatch.setattr('ansible.plugins.connection.ssh.os.path.exists', lambda x: True)

        self.mock_popen_res.stdout.read.side_effect = [b"", b"my_stdout\n", b"second_line"]
        self.mock_popen_res.stderr.read.side_effect = [b"", b"my_stderr"]
        type(self.mock_popen_res).returncode = PropertyMock(side_effect=[255] * 4 + [0] * 4)

        self.mock_selector.select.side_effect = [
            [(SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            [(SelectorKey(self.mock_popen_res.stderr, 1002, [EVENT_READ], None), EVENT_READ)],
            [],
            [(SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            [(SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            [(SelectorKey(self.mock_popen_res.stderr, 1002, [EVENT_READ], None), EVENT_READ)],
            []
        ]
        self.mock_selector.get_map.side_effect = lambda: True

        self.conn._build_command = MagicMock()
        self.conn._build_command.return_value = 'sftp'

        return_code, b_stdout, b_stderr = self.conn.put_file('/path/to/in/file', '/path/to/dest/file')
        assert return_code == 0
        assert b_stdout == b"my_stdout\nsecond_line"
        assert b_stderr == b"my_stderr"
        assert self.mock_popen.call_count == 2

    def test_fetch_file_retries(self, monkeypatch):
        monkeypatch.setattr(C, 'HOST_KEY_CHECKING', False)
        monkeypatch.setattr(C, 'ANSIBLE_SSH_RETRIES', 3)

        monkeypatch.setattr('time.sleep', lambda x: None)
        monkeypatch.setattr('ansible.plugins.connection.ssh.os.path.exists', lambda x: True)

        self.mock_popen_res.stdout.read.side_effect = [b"", b"my_stdout\n", b"second_line"]
        self.mock_popen_res.stderr.read.side_effect = [b"", b"my_stderr"]
        type(self.mock_popen_res).returncode = PropertyMock(side_effect=[255] * 4 + [0] * 4)

        self.mock_selector.select.side_effect = [
            [(SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            [(SelectorKey(self.mock_popen_res.stderr, 1002, [EVENT_READ], None), EVENT_READ)],
            [],
            [(SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            [(SelectorKey(self.mock_popen_res.stdout, 1001, [EVENT_READ], None), EVENT_READ)],
            [(SelectorKey(self.mock_popen_res.stderr, 1002, [EVENT_READ], None), EVENT_READ)],
            []
        ]
        self.mock_selector.get_map.side_effect = lambda: True

        self.conn._build_command = MagicMock()
        self.conn._build_command.return_value = 'sftp'

        return_code, b_stdout, b_stderr = self.conn.fetch_file('/path/to/in/file', '/path/to/dest/file')
        assert return_code == 0
        assert b_stdout == b"my_stdout\nsecond_line"
        assert b_stderr == b"my_stderr"
        assert self.mock_popen.call_count == 2
