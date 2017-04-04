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

from ansible.module_utils.facts import _json
from ansible.module_utils.facts.facts import Facts


class Ohai(Facts):
    """
    This is a subclass of Facts for including information gathered from Ohai.
    """

    def populate(self):
        self.run_ohai()
        return self.facts

    def run_ohai(self):
        ohai_path = self.module.get_bin_path('ohai')
        if ohai_path is None:
            return
        rc, out, err = self.module.run_command(ohai_path)
        try:
            self.facts.update(_json.loads(out))
        except:
            pass
