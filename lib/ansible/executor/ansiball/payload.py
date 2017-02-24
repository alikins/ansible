
import base64
import datetime
import io
import json
import os
import zipfile

from ansible import constants as C
from ansible.errors import AnsibleError
from ansible.executor.ansiball.templates.python_template import ACTIVE_ANSIBALLZ_TEMPLATE
from ansible.module_utils._text import to_bytes, to_text
from ansible.release import __version__, __author__

# Must import strategy and use write_locks from there
# If we import write_locks directly then we end up binding a
# variable to the object and then it never gets updated.
from ansible.executor import action_write_locks

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()

# FIXME: afaict, we could just hardcode this in ANZIBALLS_TEMPLATE unless it confuses something
# We could end up writing out parameters with unicode characters so we need to
# specify an encoding for the python source file
ENCODING_STRING = u'# -*- coding: utf-8 -*-'


def build_payload(module_name, b_module_data, module_path,
                  module_args, task_vars, module_compression,
                  shebang=None, interpreter=None):

    shebang = shebang or u'/usr/bin/python'
    output = io.BytesIO()

    py_module_names = set()

    params = dict(ANSIBLE_MODULE_ARGS=module_args,)
    python_repred_params = repr(json.dumps(params))

    try:
        compression_method = getattr(zipfile, module_compression)
    except AttributeError:
        display.warning(u'Bad module compression string specified: %s.  Using ZIP_STORED (no compression)' % module_compression)
        compression_method = zipfile.ZIP_STORED

    lookup_path = os.path.join(C.DEFAULT_LOCAL_TMP, 'ansiballz_cache')
    cached_module_filename = os.path.join(lookup_path, "%s-%s" % (module_name, module_compression))

    zipdata = None
    # Optimization -- don't lock if the module has already been cached
    if os.path.exists(cached_module_filename):
        display.debug('ANSIBALLZ: using cached module: %s' % cached_module_filename)
        zipdata = open(cached_module_filename, 'rb').read()
    else:
        if module_name in action_write_locks.action_write_locks:
            display.debug('ANSIBALLZ: Using lock for %s' % module_name)
            lock = action_write_locks.action_write_locks[module_name]
        else:
            # If the action plugin directly invokes the module (instead of
            # going through a strategy) then we don't have a cross-process
            # Lock specifically for this module.  Use the "unexpected
            # module" lock instead
            display.debug('ANSIBALLZ: Using generic lock for %s' % module_name)
            lock = action_write_locks.action_write_locks[None]

        display.debug('ANSIBALLZ: Acquiring lock')
        with lock:
            display.debug('ANSIBALLZ: Lock acquired: %s' % id(lock))
            # Check that no other process has created this while we were
            # waiting for the lock
            if not os.path.exists(cached_module_filename):
                display.debug('ANSIBALLZ: Creating module')
                # Create the module zip data
                zipoutput = io.BytesIO()
                zf = zipfile.ZipFile(zipoutput, mode='w', compression=compression_method)
                # Note: If we need to import from release.py first,
                # remember to catch all exceptions: https://github.com/ansible/ansible/issues/16523
                zf.writestr('ansible/__init__.py',
                        b'from pkgutil import extend_path\n__path__=extend_path(__path__,__name__)\n__version__="' +
                        to_bytes(__version__) + b'"\n__author__="' +
                        to_bytes(__author__) + b'"\n')
                zf.writestr('ansible/module_utils/__init__.py', b'from pkgutil import extend_path\n__path__=extend_path(__path__,__name__)\n')

                zf.writestr('ansible_module_%s.py' % module_name, b_module_data)

                py_module_cache = { ('__init__',): b'' }
                recursive_finder(module_name, b_module_data, py_module_names, py_module_cache, zf)
                zf.close()
                zipdata = base64.b64encode(zipoutput.getvalue())

                # Write the assembled module to a temp file (write to temp
                # so that no one looking for the file reads a partially
                # written file)
                if not os.path.exists(lookup_path):
                    # Note -- if we have a global function to setup, that would
                    # be a better place to run this
                    os.makedirs(lookup_path)
                display.debug('ANSIBALLZ: Writing module')
                with open(cached_module_filename + '-part', 'wb') as f:
                    f.write(zipdata)

                # Rename the file into its final position in the cache so
                # future users of this module can read it off the
                # filesystem instead of constructing from scratch.
                display.debug('ANSIBALLZ: Renaming module')
                os.rename(cached_module_filename + '-part', cached_module_filename)
                display.debug('ANSIBALLZ: Done creating module')

        if zipdata is None:
            display.debug('ANSIBALLZ: Reading module after lock')
            # Another process wrote the file while we were waiting for
            # the write lock.  Go ahead and read the data from disk
            # instead of re-creating it.
            try:
                zipdata = open(cached_module_filename, 'rb').read()
            except IOError:
                raise AnsibleError('A different worker process failed to create module file.'
                ' Look at traceback for that process for debugging information.')
    zipdata = to_text(zipdata, errors='surrogate_or_strict')

    # TODO: add as parameter
    now = datetime.datetime.utcnow()

    output.write(to_bytes(ACTIVE_ANSIBALLZ_TEMPLATE % dict(
        zipdata=zipdata,
        ansible_module=module_name,
        params=python_repred_params,
        shebang=shebang,
        interpreter=interpreter,
        coding=ENCODING_STRING,
        year=now.year,
        month=now.month,
        day=now.day,
        hour=now.hour,
        minute=now.minute,
        second=now.second,
    )))
    b_module_data = output.getvalue()
