
import os
import pipes
import re
import select
import shlex
import subprocess
import traceback

from ansible.module_utils.pycompat24 import get_exception
from ansible.module_utils.six import (PY2, PY3, b, binary_type,
                                      text_type,)
from ansible.module_utils._text import to_native, to_bytes, to_text

PASSWD_ARG_RE = re.compile(r'^[-]{0,2}pass[-]?(word|wd)?')


class RunCommandError(Exception):
    # TODO/FIXME: subclass OSError? subprocess error?

    def __init__(self, args=None, data=None):
        super(RunCommandError, self).__init__(args)
        self.data = data or {}


def read_from_pipes(rpipes, rfds, file_descriptor):
    data = b('')
    if file_descriptor in rfds:
        data = os.read(file_descriptor.fileno(), 9000)
        if data == b(''):
            rpipes.remove(file_descriptor)

    return data


def run_command(args, check_rc=False, close_fds=True, executable=None, data=None, binary_data=False, path_prefix=None, cwd=None,
                use_unsafe_shell=False, prompt_regex=None, environ_update=None, umask=None, encoding='utf-8', errors='surrogate_or_strict', clean_args=None):
    '''
    Execute a command, returns rc, stdout, and stderr.

    :arg args: is the command to run
        * If args is a list, the command will be run with shell=False.
        * If args is a string and use_unsafe_shell=False it will split args to a list and run with shell=False
        * If args is a string and use_unsafe_shell=True it runs with shell=True.
    :kw check_rc: Whether to call fail_json in case of non zero RC.
        Default False
    :kw close_fds: See documentation for subprocess.Popen(). Default True
    :kw executable: See documentation for subprocess.Popen(). Default None
    :kw data: If given, information to write to the stdin of the command
    :kw binary_data: If False, append a newline to the data.  Default False
    :kw path_prefix: If given, additional path to find the command in.
        This adds to the PATH environment vairable so helper commands in
        the same directory can also be found
    :kw cwd: If given, working directory to run the command inside
    :kw use_unsafe_shell: See `args` parameter.  Default False
    :kw prompt_regex: Regex string (not a compiled regex) which can be
        used to detect prompts in the stdout which would otherwise cause
        the execution to hang (especially if no input data is specified)
    :kw environ_update: dictionary to *update* os.environ with
    :kw umask: Umask to be used when running the command. Default None
    :kw encoding: Since we return native strings, on python3 we need to
        know the encoding to use to transform from bytes to text.  If you
        want to always get bytes back, use encoding=None.  The default is
        "utf-8".  This does not affect transformation of strings given as
        args.
    :kw errors: Since we return native strings, on python3 we need to
        transform stdout and stderr from bytes to text.  If the bytes are
        undecodable in the ``encoding`` specified, then use this error
        handler to deal with them.  The default is ``surrogate_or_strict``
        which means that the bytes will be decoded using the
        surrogateescape error handler if available (available on all
        python3 versions we support) otherwise a UnicodeError traceback
        will be raised.  This does not affect transformations of strings
        given as args.
    :returns: A 3-tuple of return code (integer), stdout (native string),
        and stderr (native string).  On python2, stdout and stderr are both
        byte strings.  On python3, stdout and stderr are text strings converted
        according to the encoding and errors parameters.  If you want byte
        strings on python3, use encoding=None to turn decoding to text off.
    '''

    shell = False
    if isinstance(args, list):
        if use_unsafe_shell:
            args = " ".join([pipes.quote(x) for x in args])
            shell = True
    elif isinstance(args, (binary_type, text_type)) and use_unsafe_shell:
        shell = True
    elif isinstance(args, (binary_type, text_type)):
        # On python2.6 and below, shlex has problems with text type
        # On python3, shlex needs a text type.
        if PY2:
            args = to_bytes(args, errors='surrogate_or_strict')
        elif PY3:
            args = to_text(args, errors='surrogateescape')
        args = shlex.split(args)
    else:
        msg = "Argument 'args' to run_command must be list or string but args was type: %s and value: %s" % (type(args), repr(args))
        raise RunCommandError(data=dict(rc=257, cmd=args, msg=msg))

    prompt_re = None
    if prompt_regex:
        if isinstance(prompt_regex, text_type):
            if PY3:
                prompt_regex = to_bytes(prompt_regex, errors='surrogateescape')
            elif PY2:
                prompt_regex = to_bytes(prompt_regex, errors='surrogate_or_strict')
        try:
            prompt_re = re.compile(prompt_regex, re.MULTILINE)
        except re.error:
            raise RunCommandError(data={'msg': "invalid prompt regular expression given to run_command"})

    # expand things like $HOME and ~
    if not shell:
        args = [os.path.expanduser(os.path.expandvars(x)) for x in args if x is not None]

    rc = 0
    msg = None
    st_in = None

    # Manipulate the environ we'll send to the new process
    old_env_vals = {}
    if environ_update:
        for key, val in environ_update.items():
            old_env_vals[key] = os.environ.get(key, None)
            os.environ[key] = val
    if path_prefix:
        old_env_vals['PATH'] = os.environ['PATH']
        os.environ['PATH'] = "%s:%s" % (path_prefix, os.environ['PATH'])

    # If using test-module and explode, the remote lib path will resemble ...
    #   /tmp/test_module_scratch/debug_dir/ansible/module_utils/basic.py
    # If using ansible or ansible-playbook with a remote system ...
    #   /tmp/ansible_vmweLQ/ansible_modlib.zip/ansible/module_utils/basic.py

    # Clean out python paths set by ansiballz
    if 'PYTHONPATH' in os.environ:
        pypaths = os.environ['PYTHONPATH'].split(':')
        pypaths = [x for x in pypaths
                   if not x.endswith('/ansible_modlib.zip') and
                   not x.endswith('/debug_dir')]
        os.environ['PYTHONPATH'] = ':'.join(pypaths)
        if not os.environ['PYTHONPATH']:
            del os.environ['PYTHONPATH']

    # FIXME: what should the default here be ?
    clean_args = clean_args or []

    if data:
        st_in = subprocess.PIPE

    kwargs = dict(
        executable=executable,
        shell=shell,
        close_fds=close_fds,
        stdin=st_in,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # store the pwd
    prev_dir = os.getcwd()

    # make sure we're in the right working directory
    if cwd and os.path.isdir(cwd):
        cwd = os.path.abspath(os.path.expanduser(cwd))
        kwargs['cwd'] = cwd
        try:
            os.chdir(cwd)
        except (OSError, IOError):
            e = get_exception()
            raise RunCommandError(data=dict(rc=e.errno, msg="Could not open %s, %s" % (cwd, str(e))))

    old_umask = None
    if umask:
        old_umask = os.umask(umask)

    try:
        # FIXME
        # if self._debug:
        #     self.log('Executing: ' + clean_args)
        cmd = subprocess.Popen(args, **kwargs)

        # the communication logic here is essentially taken from that
        # of the _communicate() function in ssh.py

        stdout = b('')
        stderr = b('')
        rpipes = [cmd.stdout, cmd.stderr]

        if data:
            if not binary_data:
                data += '\n'
            if isinstance(data, text_type):
                data = to_bytes(data)
            cmd.stdin.write(data)
            cmd.stdin.close()

        while True:
            rfds, wfds, efds = select.select(rpipes, [], rpipes, 1)
            stdout += read_from_pipes(rpipes, rfds, cmd.stdout)
            stderr += read_from_pipes(rpipes, rfds, cmd.stderr)
            # if we're checking for prompts, do it now
            if prompt_re:
                if prompt_re.search(stdout) and not data:
                    if encoding:
                        stdout = to_native(stdout, encoding=encoding, errors=errors)
                    else:
                        stdout = stdout
                    return (257, stdout, "A prompt was encountered while running a command, but no input data was specified")
            # only break out if no pipes are left to read or
            # the pipes are completely read and
            # the process is terminated
            if (not rpipes or not rfds) and cmd.poll() is not None:
                break
            # No pipes are left to read but process is not yet terminated
            # Only then it is safe to wait for the process to be finished
            # NOTE: Actually cmd.poll() is always None here if rpipes is empty
            elif not rpipes and cmd.poll() is None:
                cmd.wait()
                # The process is terminated. Since no pipes to read from are
                # left, there is no need to call select() again.
                break

        cmd.stdout.close()
        cmd.stderr.close()

        rc = cmd.returncode
    except (OSError, IOError):
        e = get_exception()
        log_msg = "Error Executing CMD:%s Exception:%s" % (clean_args, to_native(e))
        raise RunCommandError(data=dict(rc=e.errno, msg=to_native(e),
                                        cmd=clean_args, log_msg=log_msg))
    except Exception:
        e = get_exception()
        log_msg = "Error Executing CMD:%s Exception:%s" % (clean_args, to_native(traceback.format_exc()))
        raise RunCommandError(data=dict(rc=257, msg=to_native(e),
                                        exception=traceback.format_exc(),
                                        cmd=clean_args,
                                        log_msg=log_msg))

    # Restore env settings
    for key, val in old_env_vals.items():
        if val is None:
            del os.environ[key]
        else:
            os.environ[key] = val

    if old_umask:
        os.umask(old_umask)

    if rc != 0 and check_rc:
        raise RunCommandError(data=dict(cmd=clean_args, rc=rc,
                                        stdout=stdout, stderr=stderr,
                                        msg=msg))

    # reset the pwd
    os.chdir(prev_dir)

    if encoding is not None:
        return (rc, to_native(stdout, encoding=encoding, errors=errors),
                to_native(stderr, encoding=encoding, errors=errors))
    return (rc, stdout, stderr)
