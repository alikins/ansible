#
# Copyright (C) 2010-2013 Vinay Sajip. See LICENSE.txt for details.
#
"""
This module contains classes which help you work with queues. A typical
application is when you want to log from performance-critical threads, but
where the handlers you want to use are slow (for example,
:class:`~logging.handlers.SMTPHandler`). In that case, you can create a queue,
pass it to a :class:`QueueHandler` instance and use that instance with your
loggers. Elsewhere, you can instantiate a :class:`QueueListener` with the same
queue and some slow handlers, and call :meth:`~QueueListener.start` on it.
This will start monitoring the queue on a separate thread and call all the
configured handlers *on that thread*, so that your logging thread is not held
up by the slow handlers.

Note that as well as in-process queues, you can use these classes with queues
from the :mod:`multiprocessing` module.

**N.B.** This is part of the standard library since Python 3.2, so the
version here is for use with earlier Python versions.
"""
import logging
try:
    import Queue as queue
except ImportError:
    import queue
import threading
import multiprocessing
import cPickle
import operator


class QueueHandler(logging.Handler):
    """
    This handler sends events to a queue. Typically, it would be used together
    with a multiprocessing Queue to centralise logging to file in one process
    (in a multi-process application), so as to avoid file write contention
    between processes.

    :param queue: The queue to send `LogRecords` to.
    """

    def __init__(self, queue):
        """
        Initialise an instance, using the passed queue.
        """
        logging.Handler.__init__(self)
        self.queue = queue

    def enqueue(self, record):
        """
        Enqueue a record.

        The base implementation uses :meth:`~queue.Queue.put_nowait`. You may
        want to override this method if you want to use blocking, timeouts or
        custom queue implementations.

        :param record: The record to enqueue.
        """
        self.queue.put_nowait(record)

    def prepare(self, record):
        """
        Prepares a record for queuing. The object returned by this method is
        enqueued.

        The base implementation formats the record to merge the message
        and arguments, and removes unpickleable items from the record
        in-place.

        You might want to override this method if you want to convert
        the record to a dict or JSON string, or send a modified copy
        of the record while leaving the original intact.

        :param record: The record to prepare.
        """
        # The format operation gets traceback text into record.exc_text
        # (if there's exception data), and also puts the message into
        # record.message. We can then use this to replace the original
        # msg + args, as these might be unpickleable. We also zap the
        # exc_info attribute, as it's no longer needed and, if not None,
        # will typically not be pickleable.

        # test to see if object is pickable. Ideally, we would try to queue it,
        # get an exception, and then try to make it pickable, but mp.Queue does not like
        # non-pickable objects at all, and a feeder thread started will just end.
        #print('record.args=%s' % str(record.args))
        #print('record.msg=%s' % str(record.msg))
        try:
            s = cPickle.dumps(record)
            cPickle.loads(s)
            # return the record as is if pickleable
            return record
        except Exception as e:
            pass
            #print(e)
            #print(record)
            #print('%s' % str(record.args))
            #record._pickle_exception = str(e)

        self.format(record)
        record.msg = record.message
        record.args = None
        record.exc_info = None
        record._serialized_by_queue_handler = True
        return record

    def emit(self, record):
        """
        Emit a record.

        Writes the LogRecord to the queue, preparing it for pickling first.

        :param record: The record to emit.
        """

        try:
            self.enqueue(self.prepare(record))
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


class QueueListener(object):
    """
    This class implements an internal threaded listener which watches for
    LogRecords being added to a queue, removes them and passes them to a
    list of handlers for processing.

    :param record: The queue to listen to.
    :param handlers: The handlers to invoke on everything received from
                     the queue.

    Note: This creates a multiprocessing.Queue that will be shared with mp
          workers, but QueueListener needs to be created in the MainProcess
          of the app before any multiprocessing workers are created.
    """
    _sentinel = None

    def __init__(self):
        """
        Initialise an instance with the specified queue and
        handlers.
        """
        # self.queue = queue
        self.queue = multiprocessing.Queue()
        # self.handlers = handlers
        self._stop = threading.Event()
        self._thread = None
        self.logger_name = 'ansible_handler'
        self.logger = logging.getLogger(self.logger_name)
        self.logger.propagate = False

        self._sorting_list = []
        self.has_task_done = hasattr(self.queue, 'task_done')

        self.start()

    def dequeue(self, block):
        """
        Dequeue a record and return it, optionally blocking.

        The base implementation uses :meth:`~queue.Queue.get`. You may want to
        override this method if you want to use timeouts or work with custom
        queue implementations.

        :param block: Whether to block if the queue is empty. If `False` and
                      the queue is empty, an :class:`~queue.Empty` exception
                      will be thrown.
        """
        return self.queue.get(block=block, timeout=1)

    def start(self):
        """
        Start the listener.

        This starts up a background thread to monitor the queue for
        LogRecords to process.
        """
        self._thread = t = threading.Thread(target=self._monitor, name='LoggingQueueListener')
        t.setDaemon(True)
        t.start()

    def prepare(self, record):
        """
        Prepare a record for handling.

        This method just returns the passed-in record. You may want to
        override this method if you need to do any custom marshalling or
        manipulation of the record before passing it to the handlers.

        :param record: The record to prepare.
        """
        return record

    def handle(self, record):
        """
        Handle a record.

        This just loops through the handlers offering them the record
        to handle.

        :param record: The record to handle.
        """
        record = self.prepare(record)
        # for handler in self.handlers:
        #    handler.handle(record)
        self.logger.handle(record)

    def flush(self):
        for record in sorted(self._sorting_list, key=operator.attrgetter('created')):
            self.handle(record)
        # race condition?
        self._sorting_list = []

    def buffer_record(self, record):
        self._sorting_list.append(record)

        if len(self._sorting_list) > 10:
            self.flush()

    def queue_is_empty(self):
        self.flush()

    def _monitor(self):
        try:
            self._monitor_queue()
        except Exception as e:
            print(e)
            print(type(e))
            raise

    def _monitor_queue(self):
        """
        Monitor the queue for records, and ask the handler
        to deal with them.

        This method runs on a separate, internal thread.
        The thread will terminate if it sees a sentinel object in the queue.
        """
        # FIXME: 'multiprocessing' and 'logging' both setup atexit hooks that end up trying to acquire logging locks
        while not self._stop.isSet():
            try:
                record = self.dequeue(False)
                if record is self._sentinel:
                    self._task_done()
                    break
                #self.handle(record)
                self.buffer_record(record)
                self._task_done()
            except queue.Empty:
                self.queue_is_empty()
                pass
        # There might still be records in the queue.
        while True:
            try:
                record = self.dequeue(False)
                if record is self._sentinel:
                    #self._task_done()
                    break
                # let these get directly handled
                self.handle(record)
                self._task_done()
            except queue.Empty:
                break
        self.flush()

    def _task_done(self):
        if self.has_task_done:
            self.queue.task_done()

    def enqueue_sentinel(self):
        """
        Writes a sentinel to the queue to tell the listener to quit. This
        implementation uses ``put_nowait()``.  You may want to override this
        method if you want to use timeouts or work with custom queue
        implementations.
        """
        #self.queue.put_nowait(self._sentinel)
        self.queue.put(self._sentinel, block=True, timeout=1)

    def stop(self):
        """
        Stop the listener.

        This asks the thread to terminate, and then waits for it to do so.
        Note that if you don't call this before your application exits, there
        may be some records still left on the queue, which won't be processed.
        """
        self._stop.set()
        self.enqueue_sentinel()
        #self._thread.join()
        self._thread = None
