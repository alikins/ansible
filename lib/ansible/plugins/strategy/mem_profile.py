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
from ansible.module_utils.six import string_types

import objgraph
import memory_profiler as mem_profile

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
        if not obj.__class__.__module__.startswith('ansible'):
            return False
    except Exception as e:
        print(e)
    return True


def filter_str(obj):
    if isinstance(obj, string_types):
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


def show_common_ansible_types(limit=None):
    print('\nmost common ansible types:')
    common = objgraph.most_common_types(shortnames=False, limit=limit)
    ans_stats = [x for x in common if x[0].startswith('ansible') and x[1] > 1]
    show_table(ans_stats)


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

        print('new objects:')
        objgraph.show_growth(limit=30, shortnames=False)

        show_common_ansible_types(limit=2000)
        print('\n')

    return prev_mem


def show_refs(filename=None, objs=None, max_depth=5, max_objs=None):

    filename = filename or "mem-profile-default"
    refs_full_fn = "%s-refs.png" % filename
    backrefs_full_fn = "%s-backrefs.png" % filename

    objs = objs or []
    if max_objs:
        objs = objs[:max_objs]

    objgraph.show_refs(objs,
                       filename=refs_full_fn,
                       refcounts=True,
                       extra_info=extra_info_id,
                       shortnames=False,
                       #filter=filter_str,
                       too_many=4,
                       max_depth=max_depth)

    objgraph.show_backrefs(objs,
                           refcounts=True,
                           shortnames=False,
                           extra_info=extra_info_id,
                           filename=backrefs_full_fn,
                           too_many=4,
                           #filter=filter_str,
                           max_depth=max_depth)


class StrategyModule(LinearStrategyModule):
    def __init__(self, tqm):
        super(StrategyModule, self).__init__(tqm)
        self.prev_mem = 0
        self.track_mem(msg='in __init__')

    def track_mem(self, msg=None, pid=None, call_stack=None, subsystem=None):
        subsystem = subsystem or 'strategy'
        self.prev_mem = track_mem(msg=msg, pid=pid, call_stack=call_stack, subsystem=subsystem,
                                  prev_mem=self.prev_mem)
        return self.prev_mem

    # FIXME: base Strategy.run has a result kwarg, but lineary does not
    def run(self, iterator, play_context, result=0):
        self.track_mem(msg='before run')
        res = super(StrategyModule, self).run(iterator, play_context)
        self.track_mem(msg='after run')

        show_common_ansible_types()


        return res


        # example of dumping graphviz dot/pngs for ref graph of some objs
#        tis = objgraph.by_type('ansible.playbook.task_include.TaskInclude')
        #import pprint
        #for i in tis:
        #    pprint.pprint(i.__dict__)
#        show_refs(filename='task_include_refs', objs=tis, max_depth=6, max_objs=1)

#        things = objgraph.by_type('ansible.playbook.attribute.FieldAttribute')
#        show_refs(filename='things_refs', objs=things, max_depth=6, max_objs=2)

#        things2 = objgraph.by_type('ansible.playbook.block.Block')
#        show_refs(filename='things2_refs', objs=things2, max_depth=6, max_objs=2)

#        return res

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
        res = super(StrategyModule, self)._process_pending_results(iterator, one_pass, max_passes)
        self.track_mem(msg='after _process_pending_results')
        return res
