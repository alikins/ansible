# (c) 2012-2014, Michael DeHaan <michael.dehaan@gmail.com>
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

import multiprocessing
import os
import sys
import traceback

from jinja2.exceptions import TemplateNotFound

HAS_PYCRYPTO_ATFORK = False
try:
    from Crypto.Random import atfork
    HAS_PYCRYPTO_ATFORK = True
except:
    # We only need to call atfork if pycrypto is used because it will need to
    # reinitialize its RNG.  Since old paramiko could be using pycrypto, we
    # need to take charge of calling it.
    pass

from ansible.errors import AnsibleConnectionFailure
from ansible.executor.task_executor import TaskExecutor
from ansible.executor.task_result import TaskResult
from ansible.module_utils._text import to_text

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()

__all__ = ['WorkerProcess']

import persistqueue
import time
import pickle


class Sentinel(object):
    pass


class WorkerProcess(multiprocessing.Process):
    '''
    The worker thread class, which uses TaskExecutor to run tasks
    read from a job queue and pushes results into a results queue
    for reading later.
    '''

    def __init__(self, rslt_q, loader, variable_manager, shared_loader_obj, queue_filename=None):

        super(WorkerProcess, self).__init__()
        # takes a task queue manager as the sole param:
        self._rslt_q = rslt_q
        self.queue_filename = queue_filename
        # self._task_vars = task_vars
        # self._host = host
        # self._task = task
        # self._play_context = play_context
        self._loader = loader
        self._variable_manager = variable_manager
        self._shared_loader_obj = shared_loader_obj
        self._task_queue = persistqueue.Queue(self.queue_filename, tempdir='/home/adrian/.ansible/tmp/')

        if sys.stdin.isatty():
            # dupe stdin, if we have one
            self._new_stdin = sys.stdin
            try:
                fileno = sys.stdin.fileno()
                if fileno is not None:
                    try:
                        self._new_stdin = os.fdopen(os.dup(fileno))
                    except OSError:
                        # couldn't dupe stdin, most likely because it's
                        # not a valid file descriptor, so we just rely on
                        # using the one that was passed in
                        pass
            except (AttributeError, ValueError):
                # couldn't get stdin's fileno, so we just carry on
                pass
        else:
            # set to /dev/null
            self._new_stdin = os.devnull

    def terminate(self):
        print('TERMINATE')
        self.running = False
        return super(WorkerProcess, self).terminate()

    def stop(self):
        self._task_queue.put(Sentinel)

    def run(self):
        '''
        Called when the process is started.  Pushes the result onto the
        results queue. We also remove the host from the blocked hosts list, to
        signify that they are ready for their next task.
        '''

        # import cProfile, pstats, StringIO
        # pr = cProfile.Profile()
        # pr.enable()

        if HAS_PYCRYPTO_ATFORK:
            atfork()

        pqueue = self._task_queue
        #pqueue = persistqueue.Queue(self.queue_filename, tempdir='/home/adrian/.ansible/tmp/')
        display.v('pqueue worker(%s): %s' % (os.getpid(), pqueue))

        self.running = True

        sleep = 1
        while self.running:
            task_obj = None
            try:
                task_obj = pqueue.get(block=True, timeout=10)
            except pickle.PickleError as e:
                display.v('Exception: %s' % to_text(e))
                display.v('Traceback: %s' % to_text(traceback.format_exc()))
                display.v('sleeping for %s' % sleep)
                #pqueue.task_done()
                #time.sleep(sleep)
                raise
            except persistqueue.Empty as e:
                display.v('pqueue empty')
                display.v('sleeping for %s' % sleep)
                time.sleep(sleep)
                continue
            except Exception as e:
                display.v('Exception: %s' % to_text(e))
                display.v('Traceback: %s' % to_text(traceback.format_exc()))
                display.v('sleeping for %s' % sleep)
                #pqueue.task_done()
                time.sleep(sleep)
                continue

            pqueue.task_done()

            if task_obj is Sentinel:
                self.terminate()

            display.v('task_obj: %s' % repr(dir(task_obj)))
            display.v('type(task_obj): %s' % type(task_obj))
            display.v('task_obj2: %s' % repr(task_obj[0]))
            task_obj[0]._loader = self._loader

            task, task_vars, host, play_context = task_obj

            display.v('CCCCCCCCC')
            try:
                # execute the task and build a TaskResult from the result
                # display.debug("running TaskExecutor() for %s/%s" % (self._host, self._task))
                display.debug("running TaskExecutor() for %s/%s" % (host, task))
                executor_result = TaskExecutor(
                    host,
                    task,
                    task_vars,
                    play_context,
                    self._new_stdin,
                    self._loader,
                    self._shared_loader_obj,
                    self._rslt_q
                ).run()

                display.debug("done running TaskExecutor() for %s/%s" % (host, task))
                host.vars = dict()
                host.groups = []
                task_result = TaskResult(
                    host.name,
                    task._uuid,
                    executor_result,
                    task_fields=task.dump_attrs(),
                )

                # put the result on the result queue
                display.debug("sending task result")
                self._rslt_q.put(task_result)
                display.debug("done sending task result")

            except AnsibleConnectionFailure:
                host.vars = dict()
                host.groups = []
                task_result = TaskResult(
                    host.name,
                    task._uuid,
                    dict(unreachable=True),
                    task_fields=task.dump_attrs(),
                )
                self._rslt_q.put(task_result, block=False)

            except Exception as e:
                if not isinstance(e, (IOError, EOFError, KeyboardInterrupt, SystemExit)) or isinstance(e, TemplateNotFound):
                    try:
                        host.vars = dict()
                        host.groups = []
                        task_result = TaskResult(
                            host.name,
                            task._uuid,
                            dict(failed=True, exception=to_text(traceback.format_exc()), stdout=''),
                            task_fields=task.dump_attrs(),
                        )
                        self._rslt_q.put(task_result, block=False)
                    except:
                        display.debug(u"WORKER EXCEPTION: %s" % to_text(e))
                        display.debug(u"WORKER TRACEBACK: %s" % to_text(traceback.format_exc()))


        display.debug("WORKER PROCESS EXITING")

        # pr.disable()
        # s = StringIO.StringIO()
        # sortby = 'time'
        # ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
        # ps.print_stats()
        # with open('worker_%06d.stats' % os.getpid(), 'w') as f:
        #     f.write(s.getvalue())
