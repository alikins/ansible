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

import platform

from ansible.module_utils.basic import get_all_subclasses
from ansible.module_utils.six import PY3


class Facts:
    """
    This class should only attempt to populate those facts that
    are mostly generic to all systems.  This includes platform facts,
    service facts (e.g. ssh keys or selinux), and distribution facts.
    Anything that requires extensive code or may have more than one
    possible implementation to establish facts for a given topic should
    subclass Facts.
    """

    def __new__(cls, *arguments, **keyword):
        # When Hardware is created, it chooses a subclass to create instead.
        # This check prevents the subclass from then trying to find a subclass
        # and create that.
        if getattr(cls, 'impl', False):
            return super(Facts, cls).__new__(cls)

        subclass = cls
        # for sc in get_all_subclasses(Hardware):
        for sc in get_all_subclasses(cls):
            if sc.platform == platform.system():
                subclass = sc
        if PY3:
            return super(cls, subclass).__new__(subclass)
        else:
            return super(cls, subclass).__new__(subclass, *arguments, **keyword)

    def __init__(self, module, load_on_init=True):

        self.module = module

    def populate(self):
        return {}
