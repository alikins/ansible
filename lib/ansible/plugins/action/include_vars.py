# (c) 2013-2014, Benno Joy <benno@ansible.com>
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

import os

from ansible.errors import AnsibleError
from ansible.plugins.action import ActionBase


class ActionModule(ActionBase):

    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = dict()

        result = super(ActionModule, self).run(tmp, task_vars)

        source, info  = self._find_needle('vars', self._task.args.get('_raw_params'))

        if source is not None and os.path.exists(source):
            (data, show_content) = self._loader._get_file_contents(source)
            data = self._loader.load(data, show_content)
            if data is None:
                data = {}
            if not isinstance(data, dict):
                raise AnsibleError("%s must be stored as a dictionary/hash" % source)
            result['ansible_facts'] = data
            result['_ansible_no_log'] = not show_content
        else:
            result['file'] = source
            result.update(info)

        return result
