# (c) 2012, Daniel Hokka Zakrisson <daniel@hozac.com>
# (c) 2012-2014, Michael DeHaan <michael.dehaan@gmail.com> and others
# (c) 2017, Toshio Kuratomi <tkuratomi@ansible.com>
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

import os
import os.path

from ansible.module_utils._text import to_text

# a lib/module version of hacking/metadata-tool.py
from ansible.utils import module_metadata

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()

# Global so that all instances of a PluginLoader will share the caches
MODULE_CACHE = {}
PATH_CACHE = {}
PLUGIN_PATH_CACHE = {}


# TODO: this is becoming less of a namespace and more of a name resolver, but I
#       guess there isnt a ton of difference
class ModuleNamespace:
    _name = None

    # FIXME: pull_cache is not a very good name, but it is used elsewhere
    def __init__(self, name=None, path_cache=None):

        # name can be ''
        self.name = self._name
        if name is not None:
            self.name = name

        # print('%s __init__ name=%s' % (self.__class__.__name__, self.name))

        self.path_cache = {}
        # pull_cache could be an empty dict
        if path_cache is not None:
            self.path_cache = path_cache

    def match(self, name):
        '''if name is a full name that indicates a module is in this namespace, return True.

        ie, if self.name='old_modules' and name is 'old_modules.ping', return True.'''
        return name.startswith(self.name)

    def full_name(self, name):
        '''Augment the show base module name (copy, ec2_vip_facts, etc) with namespace.

        ie, "copy" -> "_copy", or "mynames_copy".

        Note this isnt limited to prepending a namespace. For example, a alias namespace
        can completly replace the name.'''
        if self.match(name):
            full_name = name
        else:
            full_name = self.name + name
        return full_name

    def __contains__(self, name):
        # return self.full_name(name) in self.pull_cache
        return self.find_plugin(name) is not None

    def find_plugin(self, name, mod_type=None, ignore_deprecated=False):
        find_result = self.path_cache[mod_type].get(self.full_name(name), None)
        # if find_result:
        #    print('Looking for name=%s, mod_type=%s: found %s' % (name, mod_type, find_result))
        return find_result


class DeprecatedModuleNamespace(ModuleNamespace):
    _name = '_'

    def _check_deprecated(self, name, ignore_deprecated, module_path):
        # print('ignore_deprecated: %s' % ignore_deprecated)
        if ignore_deprecated:
            return

        if module_path and os.path.islink(module_path):
            print('module is a symlink %s -> %s' % (module_path, name))
            return

        deprecated_namespace = '_'
        display.deprecated('%s is kept for backwards compatibility '
                           'but usage is discouraged. The module '
                           'documentation details page may explain '
                           'more about this rationale.' %
                           name.lstrip(deprecated_namespace))

    def find_plugin(self, name, mod_type=None, ignore_deprecated=False):
        find_result = super(DeprecatedModuleNamespace, self).find_plugin(name, mod_type,
                                                                         ignore_deprecated)

        if find_result:
            self._check_deprecated(name, ignore_deprecated=ignore_deprecated,
                                   module_path=find_result)

        return find_result


class AliasModuleNamespace(ModuleNamespace):
    '''map one module name to another'''

    name = '_alias_'

    def __init__(self, name=None, path_cache=None, alias_map=None):
        super(AliasModuleNamespace, self).__init__(name=name, path_cache=path_cache)

        # when asked for 'foo', return 'bar' found via map
        self.alias_map = {}
        if alias_map is not None:
            self.alias_map = alias_map

    def full_name(self, name):
        return self.alias_map.get(name, name)


class ModuleNamespaces:

    def __init__(self, namespaces=None):
        self.namespaces = []
        if namespaces is not None:
            self.namespaces = namespaces
        # print('%s __init__ namespaces=%s' % (self.__class__.__name__, self.namespaces))

    def find_plugin(self, name, mod_type=None, ignore_deprecated=False):
        for namespace in self.namespaces:
            plugin = namespace.find_plugin(name,
                                           mod_type=mod_type,
                                           ignore_deprecated=ignore_deprecated)

            if plugin:
                return plugin

        return None


# filter out modules by their metadata. ie, 'only supported' or 'ignore community' etc
class MetadataModuleFilter:
    '''Can filter modules based on the modules ANSIBLE_METADATA.

    At least for python modules.
    '''
    _DEFAULT_FILTER_RULES = {'whitelists': {'supported_by_whitelist': [],
                                            'status_whitelist': []},
                             'blacklists': {'supported_by_blacklist': [],
                                            'status_blacklist': []}}

    def __init__(self, name=None, path_cache=None, filter_rules=None):
        self.path_cache = path_cache
        self.filter_rules = filter_rules or self._DEFAULT_FILTER_RULES

    def check_metadata(self, name, path, metadata):
        # default to allow
        allowed = True
        status_allowed = True
        supported_by_allowed = True
        deniers = set([])

        mod_metadata = metadata.get(name, None)

        # print('mod_metadata: %s' % mod_metadata)

        # FIXME: if a module doesnt have metadata, do we always exclude it? vice versa
        #  if no mod_metadata, assume it 'passes' for now so non-module plugins work
        if not mod_metadata:
            return True, deniers

        status = mod_metadata.get('status', [])
        # print('status: %si type():%s ' % (status, type(status)))

        supported_by = mod_metadata.get('supported_by', [])
        # print('supported_by: %s type: %s' % (supported_by, type(supported_by)))

        # TODO: generalize  set()s?
        # print('self.filter_rules: %s' % self.filter_rules)

        # FIXME: filter_rules need an operator (ie, 'is', '==') or a callable to apply  or compare by type
        #        so we dont special each type
        # FIXME/TODO: 'blacklists']['status_blacklists'] is redundant
        # FIXME/TODO: precedence (is 'status' more important than 'supported_by')
        for disallowed_status in self.filter_rules['blacklists']['status_blacklist']:
            for module_status in status:
                if module_status == disallowed_status:
                    allowed = False
                    status_allowed = False
                    deniers.add(('status_blacklist', disallowed_status, module_status))

        for disallowed_supported_by in self.filter_rules['blacklists']['supported_by_blacklist']:
            if disallowed_supported_by == supported_by:
                allowed = False
                supported_by_allowed = False
                deniers.add(('supported_by_blacklist', disallowed_supported_by, supported_by))

        # FIXME/TODO: mechanism for resolving conflicts of the filter rules
        for allowed_supported_by in self.filter_rules['whitelists']['supported_by_whitelist']:
            if allowed_supported_by == supported_by:
                allowed = True
                supported_by_allowed = True

        for allowed_status in self.filter_rules['whitelists']['status_whitelist']:
            if allowed_status in status:
                allowed = True
                status_allowed = True

        # print('\nname: %s' % name)
        # print('supported_by_allowed: %s' % supported_by_allowed)
        # print('status_allowed: %s' % status_allowed)

        # require both supported_by and status to be valid
        allowed = supported_by_allowed and status_allowed

        return allowed, deniers

    # FIXME: rename to something more filtery
    def check_plugin(self, name, path):

        metadata = None
        # FIXME: this doesnt 'cache' module metadata
        metadata = module_metadata.return_metadata([(name, path)])

        # pprint.pprint(metadata)

        metadata_result = self.check_metadata(name, path, metadata)
        # print('mr: %s' % repr(metadata_result))

        # FIXME FIXME FIXME: add a Result obj instead of this tuple nonsense
        # (is_allowed_bool, deniers, name, path)
        if metadata_result is None:
            return (False, [], None, None)

        if metadata_result[0]:
            return (True, metadata_result[1], name, path)

        return (False, metadata_result[1], name, path)

    def __contains__(self, name_and_path):
        # return self.full_name(name) in self.pull_cache
        return self.check_plugin(name_and_path[0], name_and_path[1]) is not None


# other potential subclass
# a finder that adds filter rules from a config or playbook (sort of task firewall ish)
class BaseModuleFinder:
    def __init__(self, path_cache=None, module_namespaces=None, filter_rules=None):

        self.namespaces = ModuleNamespaces(namespaces=module_namespaces)

        self.metadata_filter = MetadataModuleFilter(filter_rules=filter_rules)

    def find_plugin(self, name, mod_type=None, ignore_deprecated=False):
        namespace_find_result = self.namespaces.find_plugin(name, mod_type, ignore_deprecated)

        if namespace_find_result is None:
            return None

        # filter_result with be either a return of the passed in data, or None
        filter_result = self.metadata_filter.check_plugin(name, namespace_find_result)

        # print('filter_result: %s' % repr(filter_result))
        if filter_result[0]:
            # just the module path
            return filter_result[3]

        # TODO: track which filter denied a module
        display.warning("The module '%s' was found, but was disabled by the metadata filter rules: %s" % (to_text(name), filter_result[1]))
        # this module was disabled by the filter finder
        return None


# The module finder with our defaults
class ModuleFinder(BaseModuleFinder):
    # TODO: could be passed to an alt constructor, or just called directly
    def __init__(self, path_cache=None, module_namespaces=None, aliases=None):
        # alias -> real name

        # TODO: Construct this outside of ModuleFinder init, and pass it in
        #       as namespaces option. Most instances with use the same setup, but
        #       it would be useful to use different impls at times (for example,
        #       a windows/winrm specific pluginload would want a window specific module
        #       namespace object). The tricky part there is the many many caches and
        #       getting their scopes and lifetimes sorted out.

        # Now check other namespaces as well, include the default '' namespacei
        module_namespaces = [ModuleNamespace(name='',                 # the normal namespace
                                             path_cache=path_cache),

                             # potentially runtime mapping of module names
                             AliasModuleNamespace(alias_map=aliases,
                                                  path_cache=path_cache),

                             # deprecated modules with _modulename
                             DeprecatedModuleNamespace(path_cache=path_cache)]

        filter_rules = {'whitelists': {'supported_by_whitelist': ['core',
                                                                  'community',
                                                                  'curated'],
                                       'status_whitelist': []},
                        'blacklists': {'supported_by_blacklist': ['community'],
                                       'status_blacklist': ['preview', 'removed']}}
        super(ModuleFinder, self).__init__(path_cache=path_cache,
                                           module_namespaces=module_namespaces,
                                           filter_rules=filter_rules)
