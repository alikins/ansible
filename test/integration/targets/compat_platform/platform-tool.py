#!/usr/bin/env python

import sys

import platform

from ansible.module_utils import compat_platform

# compare the output of platform.linux_distribution and compat.linux_distribution


def main(args):
    py_linux_distribution = None
    linux_distribution = None

    linux_distribution = compat_platform.linux_distribution()

    if linux_distribution:
        print('compat_platform.linux_distribution: %s' % repr(linux_distribution))

    try:
        py_linux_distribution = platform.linux_distribution()
    except AttributeError as e:
        sys.stderr.write('No platform.linux_distribution found. Is this python 3.8?\n')
        sys.stderr.write('If so, thats okay, we will just use compat_platform.\n')
        sys.stderr.write('%s\n' % e)
        return 0

    if py_linux_distribution:
        print('upstream python platform.linux_distribution: %s' % repr(py_linux_distribution))

    if py_linux_distribution or linux_distribution:
        if py_linux_distribution != linux_distribution:
            print('FAIL: py_linux_distribution != linux_distribution  %s != %s' %
                  (repr(py_linux_distribution), repr(linux_distribution)))
            return 1
        return 0

    print('FAIL: Neither py_linux_distribution (%s) or linux_distribution (%s) were valid' %
          (repr(py_linux_distribution), repr(linux_distribution)))
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[:]))
