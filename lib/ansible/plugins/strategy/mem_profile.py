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

import os

from ansible.plugins.strategy.linear import StrategyModule as LinearStrategyModule

import objgraph
import memory_profiler as mem_profile
import pprint
import threading

DOCUMENTATION = '''
    strategy: mem_profile
    short_description: take some memory/objgraph info
    description:
        - Task execution is 'linear' but controlled by an interactive debug session.
    version_added: "2.5"
    author: Adrian Likins
'''

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


# from objgraph.py module Marius Gedminas, MIT lic
def show_table(stats):
    if not stats:
        return

    width = max(len(name) for name, count in stats)
    for name, count in stats:
        print('%-*s %i' % (width, name, count))


def filter_obj(obj):
    try:
        module_name = obj.__class__.__module__
        #not_these = ('AnsibleUnicode', 'AnsibleMapping')
        not_these = []
        if module_name.startswith('ansible'):
            return True
        #if not obj.__class__.__module__.startswith('ansible'):
        #    return False
    except Exception as e:
        print(e)

    type_name = obj.__class__.__name__
    if type_name not in ('__builtin__.dict', '__builtin__.list'):
        return False
    return True


def extra_info_repr(obj):
    '''Add the obj repr to extra_info for ansible.* types'''
    if not obj.__class__.__module__.startswith('ansible'):
        return None

    try:
        return repr(obj)
    except Exception as e:
        print(e)

    return None


def extra_info_id(obj):
    '''return the hex obj id as extra_info'''
    return hex(id(obj))


def extra_info_id_and_pid(obj):
    return repr((hex(id(obj)), os.getpid()))


def show_common_ansible_types(limit=None):
    print('\nmost common ansible types:')
    common = objgraph.most_common_types(shortnames=False, limit=limit)
    # ans_stats = [x for x in common if x[0].startswith('ansible') and x[1] > 1]
    ans_stats = [x for x in common if x[0].startswith('ansible') and x[1] > 10]
    show_table(ans_stats)


def show_common_types(limit=None):
    print('\nmost common types:')
    common = objgraph.most_common_types(shortnames=False, limit=limit)
    show_table(common)


# TODO/FIXME: make decorator
def track_mem(msg=None, pid=None, call_stack=None, subsystem=None, prev_mem=None):
    if pid is None:
        pid = os.getpid()

    subsystem = subsystem or 'generic'

    mem_usage = mem_profile.memory_usage(-1, timestamps=True)
    delta = 0
    new_mem = 0
    for mems in mem_usage:
        # TODO/FIXME: just print this for now
        new_mem = mems[0]
        delta = new_mem - prev_mem

        prev_mem = new_mem

    verbose = False
    if delta > 0 or verbose:
        print('\n')
        print('='*40)
        print('MEM change: %s MiB cur: %s prev: %s (pid=%s) %s -- %s' %
              (delta, new_mem, prev_mem, pid, subsystem, msg))

        growth = objgraph.growth(limit=30, shortnames=False)
        print('growth')
        pprint.pprint(growth)

        #print('new objects:')
        #objgraph.show_growth(limit=30, shortnames=False)

        #show_common_ansible_types(limit=2000)
        #show_common_types(limit=2000)
        print('\n')

    return prev_mem


def show_refs(filename=None, objs=None, max_depth=5, max_objs=None):

    filename = filename or "mem-profile-default"
    refs_full_fn = "%s-refs.png" % filename
    backrefs_full_fn = "%s-backrefs.png" % filename

    objs = objs or []
    if max_objs:
        objs = objs[:max_objs]

    def filter_obj2(obj):
        return not objgraph.is_proper_module(obj)

    # return
#    print('\nbackrefs for %s pid=%s' % (objs, os.getpid()))
    for obj in objs:
        #print(obj)
        continue
        pprint.pprint(obj.__dict__)
        res = obj.__dict__.get('_result', None)
        if res:
            pprint.pprint(res)
            for i in res:
                print('%s (%s): %s' % (i, type(res[i]), res[i]))

            #for i in res:
            #    print('%s (%s): %s' % (i, type(res[i]), res[i]))
        # pprint.pprint(obj.__dict__)
        #backrefs = objgraph.find_backref_chain(obj, filter_obj)
        #for backref in backrefs:
        #    pprint.pprint(backref)
        #print('refs')
        #refs = objgraph.find_ref_chain(obj, filter_obj)
        #for ref in refs:
        #    pprint.pprint(ref)
        #print('\n')


    #if False:
    if True:
        objgraph.show_refs(objs,
                        filename=refs_full_fn,
                        refcounts=True,
                        extra_info=extra_info_id_and_pid,
                        shortnames=False,
                        #filter=filter_obj,
                        max_depth=max_depth)
    #
        objgraph.show_backrefs(objs,
                            refcounts=True,
                            shortnames=False,
                            extra_info=extra_info_id_and_pid,
                            filename=backrefs_full_fn,
                            #filter=filter_obj,
                            max_depth=max_depth)

        # import sys
        # sys.exit()

import gc

class StrategyModule(LinearStrategyModule):
    def __init__(self, tqm):
        super(StrategyModule, self).__init__(tqm)
        self.prev_mem = 0
        self.track_mem(msg='in __init__')

        # gc.set_debug(gc.DEBUG_LEAK|gc.DEBUG_STATS)

    def show_backrefs(self):
        # funcs = objgraph.by_type('__builtin__.dict')
        # funcs = objgraph.by_type('ansible.parsing.yaml.objects.AnsibleUnicode')
        #funcs = objgraph.by_type('ansible.executor.task_result.TaskResult')

        funcs = []
        #funcs = objgraph.by_type('ansible.playbook.task.Task')
        #funcs = objgraph.by_type('ansible.vars.manager.VariableManager')
        funcs = objgraph.by_type('ansible.vars.hostvars.HostVars')
        #funcs.extend(objgraph.by_type('ansible.playbook.block.Block'))
        #funcs.extend(objgraph.by_type('TaskResult'))
        #funcs.extend(objgraph.by_type('ansible.playbook.role_include.RoleInclude'))
        #funcs.extend(objgraph.by_type('ansible.playbook.included_file.IncludedFile'))
        #funcs.extend(objgraph.by_type('ansible.playbook.base.Base'))
        #funcs.extend(objgraph.by_type('ansible.playbook.handler.Handler'))
        #funcs.extend(objgraph.by_type('ansible.inventory.host.Host'))
        #funcs.extend(objgraph.by_type('ansible.inventory.group.Group'))
        if len(funcs) > 0:

#        show_refs(filename='task_include_refs', objs=tis, max_depth=6, max_objs=1)
            show_refs(filename='task_include_refs', objs=funcs, max_depth=6)


    def track_mem(self, msg=None, pid=None, call_stack=None, subsystem=None):
        subsystem = subsystem or 'strategy'
#        show_common_ansible_types()

#        show_refs(filename='task_include_refs', objs=tis, max_depth=6, max_objs=1)
        # show_refs(filename='task_include_refs', objs=funcs, max_depth=6, max_objs=1)
        self.prev_mem = track_mem(msg=msg, pid=pid, call_stack=call_stack, subsystem=subsystem,
                                  prev_mem=self.prev_mem)
        return self.prev_mem

    # FIXME: base Strategy.run has a result kwarg, but lineary does not
    def run(self, iterator, play_context, result=0):
        # self.track_mem(msg='before run')
        res = super(StrategyModule, self).run(iterator, play_context)
        # self.track_mem(msg='after run')
        print('after strat.run')
        self.show_backrefs()

        # self.show_backrefs()
        #show_common_ansible_types()

##        # example of dumping graphviz dot/pngs for ref graph of some objs
        # funcs = objgraph.by_type('ansible.playbook.task_include.TaskInclude')
        #funcs = objgraph.by_type('__builtin__.dict')
        #funcs = objgraph.by_type('ansible.parsing.yaml.objects.AnsibleUnicode')

#        show_refs(filename='task_include_refs', objs=tis, max_depth=6, max_objs=1)
        #show_refs(filename='task_include_refs', objs=funcs, max_depth=6, max_objs=1)

        return res

    def add_tqm_variables(self, vars, play):
        self.track_mem(msg='before add_tqm_variables')
        res = super(StrategyModule, self).add_tqm_variables(vars, play)
        self.track_mem(msg='after tqm_variables')
        return res

    def _queue_task(self, host, task, task_vars, play_context):
        self.track_mem(msg='before queue_task')
        res = super(StrategyModule, self)._queue_task(host, task, task_vars, play_context)
        self.track_mem(msg='after queue_task')
        return res

    def _load_included_file(self, included_file, iterator, is_handler=False):
        self.track_mem(msg='before _load_included_file')
        res = super(StrategyModule, self)._load_included_file(included_file, iterator, is_handler=is_handler)
        self.track_mem(msg='after _load_included_file')
        return res

    def _process_pending_results(self, iterator, one_pass=False, max_passes=None):
        self.track_mem(msg='before _process_pending_results')
        self.show_backrefs()
        res = super(StrategyModule, self)._process_pending_results(iterator, one_pass, max_passes)
        self.track_mem(msg='after _process_pending_results')
        return res
