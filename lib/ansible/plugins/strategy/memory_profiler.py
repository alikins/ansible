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

DOCUMENTATION = '''
    strategy: memory_profiler
    short_description: take some memory/objgraph info
    description:
        - Task execution is 'linear' but controlled by an interactive debug session.
    version_added: "2.5"
    author: Adrian Likins
'''

import cmd
import datetime
import os
import pprint
import sys

from ansible.module_utils.six.moves import reduce
from ansible.plugins.strategy.linear import StrategyModule as LinearStrategyModule

import objgraph
import memory_profiler as mem_profile

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class NextAction(object):
    """ The next action after an interpreter's exit. """
    REDO = 1
    CONTINUE = 2
    EXIT = 3

    def __init__(self, result=EXIT):
        self.result = result


# from objgraph.py module Marius Gedminas, MIT lic
def show_table(stats):
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

def extra_info(obj):
    if not obj.__class__.__module__.startswith('ansible'):
        return None
    try:
        return repr(obj)
    except Exception as e:
        print(e)
    return None

# TODO/FIXME: make decorator
def track_mem(msg=None, pid=None, call_stack=None, subsystem=None, prev_mem=None):
    if pid is None:
        pid = os.getpid()

    subsystem = subsystem or 'generic'
    print('\n')
    print('='*40)
    print('track_mem (%s) pid=%s' % (subsystem, pid))
    if msg:
        print('%s' % msg)

    #print('new objects:')
    #objgraph.show_growth(limit=30, shortnames=False)

    #print('leaking objects:')
    #roots = objgraph.get_leaking_objects()
    #objgraph.show_most_common_types(objects=roots, shortnames=False)
    # pprint.pprint(res)
    # print('\n')
    # print('type stats:')
    #pprint.pprint(objgraph.typestats(shortnames=False))
    #print('\n')
    #mem_usage = mem_profile.memory_usage(-1, interval=.2, timeout=1, timestamps=True)
    mem_usage = mem_profile.memory_usage(-1, timestamps=True)
    delta = 0
    for mems in mem_usage:
        # TODO/FIXME: just print this for now
        dt = datetime.datetime.fromtimestamp(mems[1])
        new_mem = mems[0]
        delta = new_mem - prev_mem
        print('mem_usage change: %s cur: %s prev: %s (pid=%s)' %
              (delta, new_mem, prev_mem, pid))
        # print('mem_usage delta: + %s MiB prev: %s' % (new_mem - prev_mem, prev_mem))

        prev_mem = new_mem

    if delta > 0:
        print('new objects:')
        objgraph.show_growth(limit=30, shortnames=False)

        print('\nmost common ansible types:')
        common = objgraph.most_common_types(shortnames=False, limit=200)
        ans_stats = [x for x in common if x[0].startswith('ansible')]
        show_table(ans_stats)
        #for info in common:
        #    if info[0].startswith('ansible'):
        #        print('%s\t%s' % (info[0], info[1]))
        print('\n')

    return prev_mem


def show_refs(filename=None, objs=None, max_depth=5, max_objs=None):
    SKIP = False
    if SKIP:
        return
    filename = filename or "playbook_iterator-object-graph"
    refs_full_fn = "%s-refs.png" % filename
    backrefs_full_fn = "%s-backrefs.png" % filename
    print('refs: filename=%s' % (filename))
    objs = objs or []
    if max_objs:
        objs = objs[:max_objs]
    print('SHOW BACK REFS')
    # print('SHOW REFS: show the chain for objs=%s' % objs)
    #pprint.pprint(objgraph.show_chain(objgraph.find_backref_chain(objs, objgraph.is_proper_module)))
    print('\n')
    print('SHOW REFS')
    # print('SHOW REFS: show the chain for objs=%s' % objs)
    #pprint.pprint(objgraph.show_chain(objgraph.find_ref_chain(objs, objgraph.is_proper_module)))
    objgraph.show_refs(objs,
                       filename=refs_full_fn,
                       refcounts=True,
                       # filter=filter_obj,
                       extra_info=extra_info,
                       shortnames=False,
                       max_depth=max_depth)
    #objgraph.show_refs(objs,
    #                   filename=refs_full_fn,
    #                   refcounts=True,
    #                   shortnames=False,
    #                   max_depth=max_depth)
    objgraph.show_backrefs(objs,
                           refcounts=True,
                           shortnames=False,
                           #filter=filter_obj,
                           extra_info=extra_info,
                           filename=backrefs_full_fn,
                           max_depth=max_depth)


class StrategyModule(LinearStrategyModule):
    def __init__(self, tqm):
        print('Using MEMORY_PROFILER STRATEGY')
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

        tis = objgraph.by_type('ansible.playbook.task_include.TaskInclude')
        show_refs(filename='task_include_refs', objs=tis, max_depth=6, max_objs=1)
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
        res = super(StrategyModule, self)._process_pending_results(iterator, one_pass, max_passes)
        self.track_mem(msg='after _process_pending_results')
        return res


class Debugger(cmd.Cmd):
    prompt = '(debug) '  # debugger
    prompt_continuous = '> '  # multiple lines

    def __init__(self, strategy_module, results, next_action):
        # cmd.Cmd is old-style class
        cmd.Cmd.__init__(self)

        self.intro = "Debugger invoked"
        self.scope = {}
        self.scope['task'] = strategy_module.curr_task
        self.scope['vars'] = strategy_module.curr_task_vars
        self.scope['host'] = strategy_module.curr_host
        self.scope['result'] = results[0]._result
        self.scope['results'] = results  # for debug of this debugger
        self.next_action = next_action

    def cmdloop(self):
        try:
            cmd.Cmd.cmdloop(self)
        except KeyboardInterrupt:
            pass

    def do_EOF(self, args):
        return self.do_quit(args)

    def do_quit(self, args):
        display.display('aborted')
        self.next_action.result = NextAction.EXIT
        return True

    do_q = do_quit

    def do_continue(self, args):
        self.next_action.result = NextAction.CONTINUE
        return True

    do_c = do_continue

    def do_redo(self, args):
        self.next_action.result = NextAction.REDO
        return True

    do_r = do_redo

    def evaluate(self, args):
        try:
            return eval(args, globals(), self.scope)
        except:
            t, v = sys.exc_info()[:2]
            if isinstance(t, str):
                exc_type_name = t
            else:
                exc_type_name = t.__name__
            display.display('***%s:%s' % (exc_type_name, repr(v)))
            raise

    def do_p(self, args):
        try:
            result = self.evaluate(args)
            display.display(pprint.pformat(result))
        except:
            pass

    def execute(self, args):
        try:
            code = compile(args + '\n', '<stdin>', 'single')
            exec(code, globals(), self.scope)
        except:
            t, v = sys.exc_info()[:2]
            if isinstance(t, str):
                exc_type_name = t
            else:
                exc_type_name = t.__name__
            display.display('***%s:%s' % (exc_type_name, repr(v)))
            raise

    def default(self, line):
        try:
            self.execute(line)
        except:
            pass
