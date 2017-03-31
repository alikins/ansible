from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import signal

# timeout function to make sure some fact gathering
# steps do not exceed a time limit

GATHER_TIMEOUT = None


class TimeoutError(Exception):
    pass

def foo():
    print('fooo')
    print('foo GT: %s' % globals().get('GATHER_TIMEOUT'))


def timeout(seconds=None, error_message="Timer expired"):

    print('timeout seconds: %s' % seconds)
    if seconds is None:
        seconds = globals().get('GATHER_TIMEOUT') or 10

    def decorator(func):
        print('\ndecorator.locals(): %s' % locals())
        print('globals() GATHER_TIMEOUT: %s' % globals().get('GATHER_TIMEOUT'))
        print('decorator seconds: %s' % seconds)

        def _handle_timeout(signum, frame):
            raise TimeoutError(error_message)

        def wrapper(*args, **kwargs):
            #print('wrapper wrapped_function: %s' % wrapped_function)
            #print('wrapper seconds: %s' % seconds)
            print('func: %s' % func)
            print('wrapper args: %s' % repr(args))
            print('wrapper kwargs: %s' % repr(kwargs))
            #print('wrapper seconds: %s' % seconds)
            seconds = globals().get('GATHER_TIMEOUT')
            print('wrapper globals seconds: %s' % seconds)
            signal.signal(signal.SIGALRM, _handle_timeout)
            signal.alarm(seconds)

            try:
                result = func(*args,  **kwargs)
            finally:
                signal.alarm(0)
            return result

        return wrapper

    print('out callable: %s' % seconds)
    # If we were called as @timeout, then the first parameter will be the
    # function we are to wrap instead of the number of seconds.  Detect this
    # and correct it by setting seconds to our default value and return the
    # inner decorator function manually wrapped around the function
    if callable(seconds):
        print('callable: seconds: %s' % seconds)
        print('callable globals() GATHER_TIMEOUT: %s' % globals().get('GATHER_TIMEOUT'))
        func = seconds
        seconds = 10
        return decorator(func)

    # If we were called as @timeout([...]) then python itself will take
    # care of wrapping the inner decorator around the function

    return decorator
