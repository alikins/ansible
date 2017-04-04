# compat module for json (builtin json, python-json, simplejson)
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

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


# 'builtin', 'simplejson'
JSON_IMPL = None

try:
    import json
    # Detect python-json which is incompatible and fallback to simplejson in
    # that case
    try:
        json.loads
        json.dumps
    except AttributeError:
        raise ImportError
    JSON_IMPL = 'builtin'
except ImportError:
    import simplejson as json
    JSON_IMPL = 'simplejson'

# facts code only seems to use loads/dumps
from json import dumps, loads

__all__ = [JSON_IMPL, json, dumps, loads]
