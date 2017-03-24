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

from ansible.module_utils.facts.facts import Facts

# FIXME: compat or remove this cond import
try:
    import json
    # Detect python-json which is incompatible and fallback to simplejson in
    # that case
    try:
        json.loads
        json.dumps
    except AttributeError:
        raise ImportError
except ImportError:
    import simplejson as json


class Facter(Facts):
    """
    This is a subclass of Facts for including information gathered from Facter.
    """
    def populate(self):
        self.run_facter()
        return self.facts

    def run_facter(self):
        facter_path = self.module.get_bin_path('facter', opt_dirs=['/opt/puppetlabs/bin'])
        cfacter_path = self.module.get_bin_path('cfacter', opt_dirs=['/opt/puppetlabs/bin'])
        # Prefer to use cfacter if available
        if cfacter_path is not None:
            facter_path = cfacter_path

        if facter_path is None:
            return

        # if facter is installed, and we can use --json because
        # ruby-json is ALSO installed, include facter data in the JSON
        rc, out, err = self.module.run_command(facter_path + " --puppet --json")
        try:
            self.facts = json.loads(out)
        except:
            pass
