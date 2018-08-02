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

import re
import textwrap
import types

from ansible.compat.tests import unittest
from ansible.compat.tests.mock import patch, mock_open, MagicMock


from ansible.plugins.callback import CallbackBase
from ansible.plugins.callback.default import CallbackModule as DefaultCallbackModule
from . test_callback import TestCallback, TestCallbackOnMethods


class TestDefaultCallbackOnMethods(TestCallbackOnMethods):
    callback_class = DefaultCallbackModule


class TestDefaultCallback(TestCallback):
    callback_class = DefaultCallbackModule
