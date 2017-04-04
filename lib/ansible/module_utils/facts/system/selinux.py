# Collect facts related to selinux
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

from ansible.module_utils.facts.collector import BaseFactCollector

try:
    import selinux
    HAVE_SELINUX = True
except ImportError:
    HAVE_SELINUX = False

SELINUX_MODE_DICT = {1: 'enforcing',
                     0: 'permissive',
                     -1: 'disabled'}


# NOTE: the weird module deps required for this is confusing. Likely no good approach though... - akl
# NOTE: also likely a good candidate for it's own module or class, it barely uses self
class SelinuxFactCollector(BaseFactCollector):
    _fact_ids = set(['selinux'])

    def collect(self, collected_facts=None):
        facts_dict = {}
        selinux_facts = {}

        # This is weird. The value of the facts 'selinux' key can be False or a dict
        if not HAVE_SELINUX:
            selinux_facts = False
            facts_dict['selinux'] = selinux_facts
            return facts_dict

        if not selinux.is_selinux_enabled():
            selinux_facts['status'] = 'disabled'
        # NOTE: this could just return in the above clause and the rest of this is up an indent -akl
        else:
            selinux_facts['status'] = 'enabled'

            try:
                selinux_facts['policyvers'] = selinux.security_policyvers()
            except (AttributeError, OSError):
                selinux_facts['policyvers'] = 'unknown'

            try:
                (rc, configmode) = selinux.selinux_getenforcemode()
                if rc == 0:
                    selinux_facts['config_mode'] = SELINUX_MODE_DICT.get(configmode, 'unknown')
                else:
                    selinux_facts['config_mode'] = 'unknown'
            except (AttributeError, OSError):
                selinux_facts['config_mode'] = 'unknown'

            try:
                mode = selinux.security_getenforce()
                selinux_facts['mode'] = SELINUX_MODE_DICT.get(mode, 'unknown')
            except (AttributeError, OSError):
                selinux_facts['mode'] = 'unknown'

            try:
                (rc, policytype) = selinux.selinux_getpolicytype()
                if rc == 0:
                    selinux_facts['type'] = policytype
                else:
                    selinux_facts['type'] = 'unknown'
            except (AttributeError, OSError):
                selinux_facts['type'] = 'unknown'

        facts_dict['selinux'] = selinux_facts
        return facts_dict
