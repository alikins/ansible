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


class FacterFactCollector(BaseFactCollector):
    _fact_ids = set(['facter'])

    def __init__(self, module, collectors=None, namespace=None):
        namespace = PrefixFactNamespace(namespace_name='facter',
                                        prefix='facter_')
        super(FacterFactCollector, self).__init__(module,
                                                  collectors=collectors,
                                                  namespace=namespace)

    def collect(self, collected_facts=None):
        # Note that this mirrors previous facter behavior, where there isnt
        # a 'ansible_facter' key in the main fact dict, but instead, 'facter_whatever'
        # items are added to the main dict.
        facter_dict = {}

        facter_output = self.get_facter_output()

        # TODO: if we fail, should we add a empty facter key or nothing?
        if facter_output is None:
            return facter_dict

        try:
            facter_dict = _json.loads(facter_output)
        except Exception:
            # FIXME: maybe raise a FactCollectorError with some info attrs?
            pass

        return facter_dict

    def get_facter_output(self):
        facter_path = self.find_facter()
        if not facter_path:
            return None

        rc, out, err = self.run_facter(facter_path)

        if rc != 0:
            return None

        return out

    def find_facter(self):
        facter_path = self.module.get_bin_path('facter', opt_dirs=['/opt/puppetlabs/bin'])
        cfacter_path = self.module.get_bin_path('cfacter', opt_dirs=['/opt/puppetlabs/bin'])

        # Prefer to use cfacter if available
        if cfacter_path is not None:
            facter_path = cfacter_path

        if facter_path is None:
            return

        return facter_path

    def run_facter(self, facter_path):
        # if facter is installed, and we can use --json because
        # ruby-json is ALSO installed, include facter data in the JSON
        rc, out, err = self.module.run_command(facter_path + " --puppet --json")
        return rc, out, err
