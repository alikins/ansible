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

from ansible.module_utils.facts import _json

from ansible.module_utils.facts.namespace import PrefixFactNamespace

from ansible.module_utils.facts.collector import BaseFactCollector


class OhaiFactCollector(BaseFactCollector):
    '''This is a subclass of Facts for including information gathered from Ohai.'''

    _fact_ids = set(['ohai'])

    def __init__(self, module, collectors=None, namespace=None):
        namespace = PrefixFactNamespace(namespace_name='ohai',
                                        prefix='ohai_')
        super(OhaiFactCollector, self).__init__(module,
                                                collectors=collectors,
                                                namespace=namespace)

    def find_ohai(self):
        ohai_path = self.module.get_bin_path('ohai')
        return ohai_path

    def run_ohai(self, ohai_path):
        rc, out, err = self.module.run_command(ohai_path)
        return rc, out, err

    def get_ohai_output(self):
        ohai_path = self.find_ohai()
        if not ohai_path:
            return None

        rc, out, err = self.run_ohai(ohai_path)
        if rc != 0:
            return None

        return out

    def collect(self, collected_facts=None):
        ohai_facts = {}

        ohai_output = self.get_ohai_output()

        if ohai_output is None:
            return ohai_facts

        try:
            ohai_facts = _json.loads(ohai_output)
        except Exception:
            # FIXME: useful error, logging, something...
            pass

        return ohai_facts
