from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import signal

# timeout function to make sure some fact gathering
# steps do not exceed a time limit

GATHER_TIMEOUT = None
DEFAULT_GATHER_TIMEOUT = 10


class TimeoutError(Exception):
    pass


def timeout(seconds=None, error_message="Timer expired"):
    if seconds is None:
        seconds = globals().get('GATHER_TIMEOUT') or DEFAULT_GATHER_TIMEOUT

    def decorator(func):
        def _handle_timeout(signum, frame):
            msg = 'Timer expired after %s seconds' % globals().get('GATHER_TIMEOUT')
            raise TimeoutError(msg)

        def wrapper(*args, **kwargs):
            seconds = globals().get('GATHER_TIMEOUT') or DEFAULT_GATHER_TIMEOUT
            signal.signal(signal.SIGALRM, _handle_timeout)
            signal.alarm(seconds)

            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
            return result

        return wrapper

    # If we were called as @timeout, then the first parameter will be the
    # function we are to wrap instead of the number of seconds.  Detect this
    # and correct it by setting seconds to our default value and return the
    # inner decorator function manually wrapped around the function
    if callable(seconds):
        func = seconds
        seconds = 10
        return decorator(func)

    # If we were called as @timeout([...]) then python itself will take
    # care of wrapping the inner decorator around the function

    return decorator
