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

import ast
import copy
import random
import uuid

from collections import MutableMapping, defaultdict
from json import dumps

from ansible import constants as C
from ansible.errors import AnsibleError, AnsibleOptionsError
from ansible.module_utils.six import iteritems, string_types
from ansible.module_utils._text import to_native, to_text
from ansible.parsing.splitter import parse_kv

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


_MAXSIZE = 2 ** 32
cur_id = 0
node_mac = ("%012x" % uuid.getnode())[:12]
random_int = ("%08x" % random.randint(0, _MAXSIZE))[:8]


def get_unique_id():
    global cur_id
    cur_id += 1
    return "-".join([
        node_mac[0:8],
        node_mac[8:12],
        random_int[0:4],
        random_int[4:8],
        ("%012x" % cur_id)[:12],
    ])


def _validate_mutable_mappings(a, b):
    """
    Internal convenience function to ensure arguments are MutableMappings

    This checks that all arguments are MutableMappings or raises an error

    :raises AnsibleError: if one of the arguments is not a MutableMapping
    """

    # If this becomes generally needed, change the signature to operate on
    # a variable number of arguments instead.

    if not (isinstance(a, MutableMapping) and isinstance(b, MutableMapping)):
        myvars = []
        for x in [a, b]:
            try:
                myvars.append(dumps(x))
            except:
                myvars.append(to_native(x))
        raise AnsibleError("failed to combine variables, expected dicts but got a '{0}' and a '{1}': \n{2}\n{3}".format(
            a.__class__.__name__, b.__class__.__name__, myvars[0], myvars[1])
        )


class DisplayDict(dict):
    def __init__(self, *args, **kw):
        super(DisplayDict, self).__init__(*args, **kw)

        print('kw: %s' % repr(kw))

        if not kw:
            import traceback
            traceback.print_stack()
        var_context = kw.pop('var_context', None)

        self.meta = defaultdict(list)
        self.meta['var_context'].append(var_context)
        self.ignore_internal = True
        self._data = {}

    def __setitem__(self, key, value):
        super(DisplayDict, self).__setitem__(key, value)

    def update(self, other, update_name=None, scope_info=None):
        for key in sorted(other):
            if key == 'update_name' or key == 'scope_info':
                continue

            orig = copy.copy(self.get(key, None))
            self[key] = other[key]

            if self._is_ignored(key):
                continue

            # msg = u'"%s" -> %s from scope=%s' % (to_text(key), to_text(repr(other[key])),
            #                                     to_text(update_name))
            msg = u'%s: %s=%s' % (
                to_text(update_name),
                to_text(key),
                to_text(repr(other[key])))

            if orig is not None:
                msg += u' (was=%s)' % (to_text(repr(orig)))

            if self.meta.get('var_context'):
                msg += u' (var_context=%s)' % to_text(repr(self.meta['var_context']))

            if display.verbosity > 5:
                msg += u' scope_info: %s' % to_text(repr(scope_info))

            display.vvvvv(msg)

    def copy(self):
        d = DisplayDict(super(DisplayDict, self).copy(), var_context=self.meta.get('var_context'))
        d.meta = self.meta.copy()
        return d

    def _is_ignored(self, key):
        ignores = ('hostvars', 'groups', 'vars', 'omit', 'inventory_hostname', 'tasks')
        if self.ignore_internal and key.startswith('ansible_') or key in ignores:
            return True
        return False

    def as_dict(self):
        data = {}
        for key in self:
            if self._is_ignored(key):
                continue
            scopes = []
            for idx, level in enumerate(self.meta[key]):
                scopes.append({'rank': idx,
                               'scope': level[0],
                               'info': level[2],
                               'value': level[1]})
            data[key] = {'scopes': scopes,
                         'final': self[key]}
        return data


class TrackingDict(dict):
    def __init__(self, *args, **kw):
        super(TrackingDict, self).__init__(*args, **kw)

        self.meta = defaultdict(list)
        self.ignore_internal = True

    def __setitem__(self, key, value):
        super(TrackingDict, self).__setitem__(key, value)

    def update(self, other, update_name=None, scope_info=None):
        # If we are updating where other is a TrackingDict, try to merge its meta
        # info into ours so we preserve the origin update_name/scope_info
        other_meta = getattr(other, 'meta', None)
        if other_meta:
            # import pprint
            # pprint.pprint(('other_meta', dict(other_meta)))
            # pprint.pprint(('update_name', update_name))
            # print('other_meta: %s update_name=%s' % (other_meta, update_name))
            self.meta.update(other_meta)

        for key in other:
            if key == 'update_name' or key == 'scope_info':
                continue
            self.meta[key].append((update_name, other[key], scope_info))
            self[key] = other[key]

    def copy(self):
        d = TrackingDict(super(TrackingDict, self).copy())
        d.meta = self.meta.copy()
        return d

    def _is_ignored(self, key):
        if self.ignore_internal and key.startswith('ansible_') or key in ['hostvars', 'groups', 'vars', 'omit', 'inventory_hostname']:
            return True
        return False

    def __repr__(self):
        lines = []
        for key in self:
            if self._is_ignored(key):
                continue
            lines.append('var: %s' % key)
            lines.append('    scopes:')
            for idx, level in enumerate(reversed(self.meta[key])):
                # lines.append('  level %s: %s' % (idx, repr(level)))
                scope_info_blurb = ''
                scope_info = level[2]
                if scope_info is not None:
                    scope_info_blurb = scope_info
                lines.append('        %s:' % idx)
                lines.append('            source: %s' % level[0])
                lines.append('              info: %s' % scope_info_blurb)
                lines.append('             value: %s' % level[1])
            lines.append('    final:')
            lines.append('           %s' % self[key])
        return to_text('\n'.join(lines))

    def as_dict(self):
        data = {}
        for key in self:
            if self._is_ignored(key):
                continue
            data[key] = self[key]
        return data


def combine_vars(a, b, scope_name=None, scope_info=None):
    """
    Return a copy of dictionaries of variables based on configured hash behavior
    """

    if C.DEFAULT_HASH_BEHAVIOUR == "merge":
        return merge_hash(a, b)
    else:
        # HASH_BEHAVIOUR == 'replace'
        _validate_mutable_mappings(a, b)
        result = a.copy()

        # TODO: need to only add the extra args for update if we are using a TrackingDict
        #       but would like avoid doing an isinstance or duck type check for the normal
        #       path. (to avoid non tracking dicts getting bogus keys from the kwargs to update())
        # maybe switch out combine_vars based on verbosity?  (means import display here)
        # pass verbosity to combine_vars
        result.update(b, update_name=scope_name, scope_info=scope_info)
        return result


def merge_hash(a, b):
    """
    Recursively merges hash b into a so that keys from b take precedence over keys from a
    """

    _validate_mutable_mappings(a, b)

    # if a is empty or equal to b, return b
    if a == {} or a == b:
        return b.copy()

    # if b is empty the below unfolds quickly
    result = a.copy()

    # next, iterate over b keys and values
    for k, v in iteritems(b):
        # if there's already such key in a
        # and that key contains a MutableMapping
        if k in result and isinstance(result[k], MutableMapping) and isinstance(v, MutableMapping):
            # merge those dicts recursively
            result[k] = merge_hash(result[k], v)
        else:
            # otherwise, just copy the value from b to a
            result[k] = v

    return result


def load_extra_vars(loader, options):
    extra_vars = {}
    if hasattr(options, 'extra_vars'):
        for extra_vars_opt in options.extra_vars:
            data = None
            extra_vars_opt = to_text(extra_vars_opt, errors='surrogate_or_strict')
            if extra_vars_opt.startswith(u"@"):
                # Argument is a YAML file (JSON is a subset of YAML)
                data = loader.load_from_file(extra_vars_opt[1:])
            elif extra_vars_opt and extra_vars_opt[0] in u'[{':
                # Arguments as YAML
                data = loader.load(extra_vars_opt)
            else:
                # Arguments as Key-value
                data = parse_kv(extra_vars_opt)

            if isinstance(data, MutableMapping):
                extra_vars = combine_vars(extra_vars, data, scope_name='_load_extra_vars')
            else:
                raise AnsibleOptionsError("Invalid extra vars data supplied. '%s' could not be made into a dictionary" % extra_vars_opt)

    return extra_vars


def load_options_vars(options, version):

    options_vars = {'ansible_version': version}
    aliases = {'check': 'check_mode',
               'diff': 'diff_mode',
               'inventory': 'inventory_sources',
               'subset': 'limit',
               'tags': 'run_tags'}

    for attr in ('check', 'diff', 'forks', 'inventory', 'skip_tags', 'subset', 'tags'):
        opt = getattr(options, attr, None)
        if opt is not None:
            options_vars['ansible_%s' % aliases.get(attr, attr)] = opt

    return options_vars


def isidentifier(ident):
    """
    Determines, if string is valid Python identifier using the ast module.
    Originally posted at: http://stackoverflow.com/a/29586366
    """

    if not isinstance(ident, string_types):
        return False

    try:
        root = ast.parse(ident)
    except SyntaxError:
        return False

    if not isinstance(root, ast.Module):
        return False

    if len(root.body) != 1:
        return False

    if not isinstance(root.body[0], ast.Expr):
        return False

    if not isinstance(root.body[0].value, ast.Name):
        return False

    if root.body[0].value.id != ident:
        return False

    return True
