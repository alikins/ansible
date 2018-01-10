
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

__all__ = ['Version']

try:
    from packaging.version import Version
except ImportError:
    try:
        from pip._vendor.packaging.version import Version
    except ImportError:
        from distutils.version import LooseVersion as Version
