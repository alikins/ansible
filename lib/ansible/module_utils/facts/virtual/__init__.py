from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.module_utils.facts.virtual import base
from ansible.module_utils.facts.virtual import sysctl

from ansible.module_utils.facts.virtual import dragonfly
from ansible.module_utils.facts.virtual import freebsd
from ansible.module_utils.facts.virtual import hpux
from ansible.module_utils.facts.virtual import linux
from ansible.module_utils.facts.virtual import netbsd
from ansible.module_utils.facts.virtual import openbsd
from ansible.module_utils.facts.virtual import sunos

__all__ = [base, dragonfly, freebsd, hpux, linux, netbsd, openbsd, sunos, sysctl]
