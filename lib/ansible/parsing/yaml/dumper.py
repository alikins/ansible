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
from ansible.playbook import Playbook
from ansible.playbook.play import Play
from ansible.playbook.block import Block
from ansible.playbook.handler import Handler
from ansible.playbook.task import Task
from ansible.playbook.role import Role
from ansible.playbook.attribute import FieldAttribute
from ansible.playbook.playbook_include import PlaybookInclude


class AnsibleDumper(yaml.SafeDumper):
    '''
    A simple stub class that allows us to add representers
    for our overridden object types.
    '''
    def represent_undefined(self, data):
        print('undefined data=%s, type=%s' % (data, type(data)))
        return yaml.Dumper.represent_undefined(self, data)


class AnsibleUnsafeDumper(yaml.Dumper):
    # for debugging
    def represent_undefined(self, data):
        print('undefined data=%s, type=%s' % (data, type(data)))
        return yaml.Dumper.represent_undefined(self, data)

    def ignore_aliases(self, data):
        if data == {} or data == []:
            return True

        if isinstance(data, (list, dict, FieldAttribute, Playbook, Play, Role, Task)):
            return True

        default = super(AnsibleUnsafeDumper, self).ignore_aliases(data)

        if default is None:
            print('type: %s ig_data: %s default ignore: %s' % (type(data), data, default))
        return default


def represent_hostvars(self, data):
    return self.represent_dict(dict(data))


def represent_playbook(self, data):
    # return self.represent_list(data)
    return self.represent_dict(data.__getstate__())


def represent_play(self, data):
    return self.represent_dict(data.serialize())


def represent_attribute(self, data):
    # print('repr_attribute %s' % data)
    # print('repr_attrubte.serialize: %s' % data.serialize())
    return self.represent_dict(data.serialize())


def represent_block(self, data):
    return self.represent_dict(data.serialize(serialize_parent=False))


def represent_playbook_include(self, data):
    return self.represent_dict(data.serialize())


def represent_bloc2k(self, data):
    new_data = {}
    block_data = data.serialize(serialize_parent=False)
    for internal in ('dep_chain',):
        del block_data[internal]
    # new_data['block'] = block_data
    # for d in block_data:
    #    print('%s t=%s %s' % (d, type(d), repr(d)))
    new_data.update(block_data)
    return self.represent_dict(new_data)


def represent_task(self, data):
    new_data = {}
    task_data = data.serialize(serialize_parent=False)

#    for internal in ('uuid', 'squashed', 'finalized'):
#        del task_data[internal]
    new_data['task'] = task_data

    return self.represent_dict(new_data)


def represent_handler(self, data):
    handler_data = data.serialize()
    return self.represent_dict(handler_data)


def represent_role(self, data):
    role_data = data.serialize()
    return self.represent_dict(role_data)


# Note: only want to represent the encrypted data
def represent_vault_encrypted_unicode(self, data):
    return self.represent_scalar(u'!vault', data._ciphertext.decode(), style='|')

if PY3:
    represent_unicode = yaml.representer.SafeRepresenter.represent_str
else:
    represent_unicode = yaml.representer.SafeRepresenter.represent_unicode

if PY3:
    unsafe_represent_unicode = yaml.representer.SafeRepresenter.represent_str
else:
    unsafe_represent_unicode = yaml.representer.SafeRepresenter.represent_unicode

AnsibleUnsafeDumper.add_representer(
    Playbook,
#    yaml.representer.SafeRepresenter.represent_list,
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
    Handler,
    represent_handler
)


AnsibleUnsafeDumper.add_representer(
    Role,
    represent_role
)


AnsibleUnsafeDumper.add_representer(
    FieldAttribute,
    represent_attribute
)

# playbook includes dont really show up in the Playbook
# object (the analog would be C/cpp 'include' files, sort of)
AnsibleUnsafeDumper.add_representer(
    PlaybookInclude,
    represent_playbook_include
)


AnsibleUnsafeDumper.add_representer(
    AnsibleUnicode,
    represent_unicode,
)

AnsibleUnsafeDumper.add_representer(
    unicode,
    represent_unicode,
)


AnsibleUnsafeDumper.add_representer(
    HostVars,
    represent_hostvars,
)


AnsibleUnsafeDumper.add_representer(
    AnsibleSequence,
    # yaml.representer.SafeRepresenter.represent_list,
    yaml.representer.Representer.represent_list,
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
    Handler,
    represent_handler
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
