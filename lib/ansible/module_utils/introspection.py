# This code is part of Ansible, but is an independent component.
# This particular file snippet, and this file snippet only, is BSD licensed.
# Modules you write using this snippet, which is embedded dynamically by Ansible
# still belong to the author of the module, and may assign their own license
# to the complete work.
#
# Copyright (c), Adrian Likins <alikins@redhat.com>, 2016-2017
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
# USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

import locale
import os
import sys

import __main__ as module_main


def _module_meta_info():
    meta_info = {}

    meta_info['documentation'] = getattr(module_main, 'DOCUMENTATION', None)
    meta_info['metadata'] = getattr(module_main, 'ANSIBLE_METADATA', None)
    meta_info['return'] = getattr(module_main, 'RETURN', None)
    meta_info['examples'] = getattr(module_main, 'EXAMPLES', None)

    return meta_info


def process_info():
    process_info = {}

    process_info['pid'] = os.getpid()
    process_info['uid'] = os.getuid()
    process_info['euid'] = os.geteuid()
    process_info['gid'] = os.getgid()
    process_info['cwd'] = os.getcwdu()
    process_info['ppid'] = os.getppid()

    process_info['sys_argv'] = sys.argv

    times_result = os.times()
    process_times = {'user': times_result[0],
                     'system': times_result[1],
                     'children_user': times_result[2],
                     'children_system': times_result[3],
                     'elapsed': times_result[4]}
    process_info['times'] = process_times

    return process_info


def python_site_info():
    import site

    python_info = {}

    # These only exist for python 2.6+
    try:
        python_info['PREFIXES'] = site.PREFIXES
        python_info['USER_SITE'] = site.USER_SITE
        python_info['USER_BASE'] = site.USER_BASE
    except AttributeError:
        pass

    # only exists in python 2.7+
    try:
        python_info['getsitepackages'] = site.getsitepackages()
    except AttributeError:
        pass

    return python_info


def python_version_info():
    version_info = {}

    # Note: sys.version and other info is already collected in get_python_facts
    #       during fact collection. This info could be collected there as well.
    versions = {'major': sys.version_info[0],
                'minor': sys.version_info[1],
                'micro': sys.version_info[2],
                'releaselevel': sys.version_info[3],
                'serial': sys.version_info[4]}

    version_info['version'] = versions
    version_info['version_list'] = list(sys.version_info)

    return version_info


def python_paths_info():
    path_info = {}

    path_info['path'] = sys.path
    path_info['prefix'] = sys.prefix
    path_info['exec_prefix'] = sys.exec_prefix
    path_info['meta_path'] = sys.meta_path

    # items in path hooks can be custom types, namely zipimporter
    path_info['path_hooks'] = [repr(x) for x in sys.path_hooks]
    return path_info


def python_sys_modules_info():
    sys_modules_info = {}
    for name, py_module in sys.modules.items():
        module_repr = None
        if py_module:
            module_repr = repr(py_module)
        sys_modules_info[name] = module_repr

    return sys_modules_info
    python_info['sys_modules'] = sys_modules_info


def python_info():
    info = {}
    info['executable'] = sys.executable

    python_type = None
    try:
        python_type = sys.subversion[0]
    except AttributeError:
        try:
            python_type = sys.implementation.name
        except AttributeError:
            pass
    info['type'] = python_type

    versions = python_version_info()
    info.update(versions)

    return info


def env_info():
    return os.environ.copy()


def module_invocation():
    # info about the env and runtime of the module as it was invoked
    data = {}
    data['locale'] = locale.getlocale()

    py_info = python_info()

    py_info['site'] = python_site_info()
    py_info['sys_paths'] = python_paths_info()
    py_info['sys_modules'] = python_sys_modules_info()

    data['python'] = py_info

    # facts collects env info as well, but the goal here is to collect the
    # env this particular module invocation is using.
    data['environment'] = env_info()

    # collect process info last so process cumulative times are useful
    data['process'] = process_info()

    return data
