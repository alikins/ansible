# (c) 2012-2014, Michael DeHaan <michael.dehaan@gmail.com>
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

import yaml

from ansible.module_utils.six import PY3
from ansible.parsing.yaml.objects import AnsibleUnicode, AnsibleSequence, AnsibleMapping, AnsibleVaultEncryptedUnicode
from ansible.utils.unsafe_proxy import AnsibleUnsafeText
from ansible.vars.hostvars import HostVars
from ansible.vars.unsafe_proxy import AnsibleUnsafeText
from ansible.playbook import Playbook
from ansible.playbook.play import Play
from ansible.playbook.block import Block
from ansible.playbook.task import Task


class AnsibleDumper(yaml.SafeDumper):
    '''
    A simple stub class that allows us to add representers
    for our overridden object types.
    '''
    pass



class AnsibleUnsafeDumper(yaml.Dumper):
    # for debugging
    def represent_undefined(self, data):
        print('undefined data=%s' % data)
        return yaml.Dumper.represent_undefined(self, data)


        return yaml.Dumper.represent_undefined(self, data)

def represent_hostvars(self, data):
    return self.represent_dict(dict(data))



def represent_playbook(self, data):
    return self.represent_list(data)
    # return self.represent_dict(data.__getstate__())


def represent_play(self, data):
    return self.represent_dict(data.serialize())


def represent_block(self, data):
    new_data = {}
    block_data = data.serialize(serialize_parent=False)
    for internal in ('dep_chain',):
        del block_data[internal]
    #new_data['block'] = block_data
    #for d in block_data:
    #    print('%s t=%s %s' % (d, type(d), repr(d)))
    new_data.update(block_data)
    return self.represent_dict(new_data)


def represent_task(self, data):
    new_data = {}
    task_data = data.serialize(serialize_parent=False)

    for internal in ('uuid', 'squashed', 'finalized'):
        del task_data[internal]
    new_data['task'] = task_data

    return self.represent_dict(new_data)


# Note: only want to represent the encrypted data
def represent_vault_encrypted_unicode(self, data):
    return self.represent_scalar(u'!vault', data._ciphertext.decode(), style='|')

if PY3:
    represent_unicode = yaml.representer.SafeRepresenter.represent_str
else:
    represent_unicode = yaml.representer.SafeRepresenter.represent_unicode

AnsibleUnsafeDumper.add_representer(
    Playbook,
    #yaml.representer.SafeRepresenter.represent_list,
    represent_playbook
)

AnsibleUnsafeDumper.add_representer(
    Play,
    represent_play
)

AnsibleUnsafeDumper.add_representer(
    Block,
    represent_block
)

AnsibleUnsafeDumper.add_representer(
    Task,
    represent_task
)


AnsibleUnsafeDumper.add_representer(
    AnsibleUnicode,
    represent_unicode,
)

AnsibleUnsafeDumper.add_representer(
    HostVars,
    represent_hostvars,
)


AnsibleUnsafeDumper.add_representer(
    AnsibleSequence,
    yaml.representer.SafeRepresenter.represent_list,
)

AnsibleUnsafeDumper.add_representer(
    AnsibleMapping,
    yaml.representer.SafeRepresenter.represent_dict,
)

AnsibleUnsafeDumper.add_representer(
    AnsibleVaultEncryptedUnicode,
    represent_vault_encrypted_unicode,
)


AnsibleDumper.add_representer(
    AnsibleUnicode,
    represent_unicode,
)

AnsibleDumper.add_representer(
    AnsibleUnsafeText,
    represent_unicode,
)

AnsibleDumper.add_representer(
    HostVars,
    represent_hostvars,
)

AnsibleDumper.add_representer(
    Playbook,
    #yaml.representer.SafeRepresenter.represent_list,
    represent_playbook
)

AnsibleDumper.add_representer(
    Play,
    represent_play
)

AnsibleDumper.add_representer(
    Block,
    represent_block
)

AnsibleDumper.add_representer(
    Task,
    represent_task
)


AnsibleDumper.add_representer(
    AnsibleSequence,
    yaml.representer.SafeRepresenter.represent_list,
)

AnsibleDumper.add_representer(
    AnsibleMapping,
    yaml.representer.SafeRepresenter.represent_dict,
)

AnsibleDumper.add_representer(
    AnsibleVaultEncryptedUnicode,
    represent_vault_encrypted_unicode,
)
