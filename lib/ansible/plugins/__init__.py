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

import glob
import imp
import os
import os.path
import sys
import warnings

from collections import defaultdict

from ansible import constants as C
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


def get_all_plugin_loaders():
    return [(name, obj) for (name, obj) in globals().items() if isinstance(obj, PluginLoader)]


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
        #return self.full_name(name) in self.pull_cache
        return self.find_plugin(name) is not None

    def find_plugin(self, name, mod_type=None, ignore_deprecated=False):
        find_result = self.path_cache[mod_type].get(self.full_name(name), None)
        #if find_result:
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
        #return self.full_name(name) in self.pull_cache
        return self.check_plugin(name_and_path[0], name_and_path[1]) is not None


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

        # TODO: Construct this outside of PluginLoader init, and pass it in
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


class PluginLoader:

    '''
    PluginLoader loads plugins from the configured plugin directories.

    It searches for plugins by iterating through the combined list of
    play basedirs, configured paths, and the python path.
    The first match is used.
    '''

    def __init__(self, class_name, package, config, subdir, aliases=None, required_base_class=None, namespaces=None):

        self.class_name         = class_name
        self.base_class         = required_base_class
        self.package            = package
        self.subdir             = subdir

        self.aliases = {}
        if aliases is not None:
            self.aliases = aliases

        if config and not isinstance(config, list):
            config = [config]
        elif not config:
            config = []

        self.config = config

        if class_name not in MODULE_CACHE:
            MODULE_CACHE[class_name] = {}
        if class_name not in PATH_CACHE:
            PATH_CACHE[class_name] = None
        if class_name not in PLUGIN_PATH_CACHE:
            PLUGIN_PATH_CACHE[class_name] = defaultdict(dict)

        self._module_cache      = MODULE_CACHE[class_name]
        self._paths             = PATH_CACHE[class_name]
        self._plugin_path_cache = PLUGIN_PATH_CACHE[class_name]

        self._extra_dirs = []
        self._searched_paths = set()

        self.module_finder = ModuleFinder(path_cache=self._plugin_path_cache,
                                          aliases=self.aliases)

    def __setstate__(self, data):
        '''
        Deserializer.
        '''

        class_name = data.get('class_name')
        package    = data.get('package')
        config     = data.get('config')
        subdir     = data.get('subdir')
        aliases    = data.get('aliases')
        base_class = data.get('base_class')

        PATH_CACHE[class_name] = data.get('PATH_CACHE')
        PLUGIN_PATH_CACHE[class_name] = data.get('PLUGIN_PATH_CACHE')

        self.__init__(class_name, package, config, subdir, aliases, base_class)
        self._extra_dirs = data.get('_extra_dirs', [])
        self._searched_paths = data.get('_searched_paths', set())

    def __getstate__(self):
        '''
        Serializer.
        '''

        return dict(
            class_name        = self.class_name,
            base_class        = self.base_class,
            package           = self.package,
            config            = self.config,
            subdir            = self.subdir,
            aliases           = self.aliases,
            _extra_dirs       = self._extra_dirs,
            _searched_paths   = self._searched_paths,
            PATH_CACHE        = PATH_CACHE[self.class_name],
            PLUGIN_PATH_CACHE = PLUGIN_PATH_CACHE[self.class_name],
        )

    def format_paths(self, paths):
        ''' Returns a string suitable for printing of the search path '''

        # Uses a list to get the order right
        ret = []
        for i in paths:
            if i not in ret:
                ret.append(i)
        return os.pathsep.join(ret)

    def print_paths(self):
        return self.format_paths(self._get_paths())

    def _all_directories(self, dir):
        results = []
        results.append(dir)
        for root, subdirs, files in os.walk(dir, followlinks=True):
            if '__init__.py' in files:
                for x in subdirs:
                    results.append(os.path.join(root,x))
        return results

    def _get_package_paths(self, subdirs=True):
        ''' Gets the path of a Python package '''

        if not self.package:
            return []
        if not hasattr(self, 'package_path'):
            m = __import__(self.package)
            parts = self.package.split('.')[1:]
            for parent_mod in parts:
                m = getattr(m, parent_mod)
            self.package_path = os.path.dirname(m.__file__)
        if subdirs:
            return self._all_directories(self.package_path)
        return [self.package_path]

    def _get_paths(self, subdirs=True):
        ''' Return a list of paths to search for plugins in '''

        # FIXME: This is potentially buggy if subdirs is sometimes True and
        # sometimes False.  In current usage, everything calls this with
        # subdirs=True except for module_utils_loader which always calls it
        # with subdirs=False.  So there currently isn't a problem with this
        # caching.
        if self._paths is not None:
            return self._paths

        ret = self._extra_dirs[:]

        # look in any configured plugin paths, allow one level deep for subcategories
        if self.config is not None:
            for path in self.config:
                path = os.path.realpath(os.path.expanduser(path))
                if subdirs:
                    contents = glob.glob("%s/*" % path) + glob.glob("%s/*/*" % path)
                    for c in contents:
                        if os.path.isdir(c) and c not in ret:
                            ret.append(c)
                if path not in ret:
                    ret.append(path)

        # look for any plugins installed in the package subtree
        # Note package path always gets added last so that every other type of
        # path is searched before it.
        ret.extend(self._get_package_paths(subdirs=subdirs))

        # HACK: because powershell modules are in the same directory
        # hierarchy as other modules we have to process them last.  This is
        # because powershell only works on windows but the other modules work
        # anywhere (possibly including windows if the correct language
        # interpreter is installed).  the non-powershell modules can have any
        # file extension and thus powershell modules are picked up in that.
        # The non-hack way to fix this is to have powershell modules be
        # a different PluginLoader/ModuleLoader.  But that requires changing
        # other things too (known thing to change would be PATHS_CACHE,
        # PLUGIN_PATHS_CACHE, and MODULE_CACHE.  Since those three dicts key
        # on the class_name and neither regular modules nor powershell modules
        # would have class_names, they would not work as written.
        reordered_paths = []
        win_dirs = []

        for path in ret:
            if path.endswith('windows'):
                win_dirs.append(path)
            else:
                reordered_paths.append(path)
        reordered_paths.extend(win_dirs)

        # cache and return the result
        self._paths = reordered_paths
        return reordered_paths

    def add_directory(self, directory, with_subdir=False):
        ''' Adds an additional directory to the search path '''

        directory = os.path.realpath(directory)

        if directory is not None:
            if with_subdir:
                directory = os.path.join(directory, self.subdir)
            if directory not in self._extra_dirs:
                # append the directory and invalidate the path cache
                self._extra_dirs.append(directory)
                self._paths = None

    # TODO: ignore_deprecated could be an aspect of the Namespace() object
    # TODO: rename find_ansible_module
    def find_plugin(self, name, mod_type='', ignore_deprecated=False):
        ''' Find a plugin named name '''

        if mod_type:
            suffix = mod_type
        elif self.class_name:
            # Ansible plugins that run in the controller process (most plugins)
            suffix = '.py'
        else:
            # Only Ansible Modules.  Ansible modules can be any executable so
            # they can have any suffix
            suffix = ''

        # The particular cache to look for modules within.  This matches the
        # requested mod_type
        #pull_cache = self._plugin_path_cache[suffix]

        find_result = self.module_finder.find_plugin(name, mod_type=suffix)

        # TODO: track which namespace had the name
        if find_result:
            return find_result

        #try:
        #    return pull_cache[name]
        #except KeyError:
        #   # Cache miss.  Now let's find the plugin
        #    pass

        # We didn't find the module name in any namespaces cache, so now
        # lets search plugin paths populating path caches.
        # search all the module paths populate lots of cache entries

        # TODO: Instead of using the self._paths cache (PATH_CACHE) and
        #       self._searched_paths we could use an iterator.  Before enabling that
        #       we need to make sure we don't want to add additional directories
        #       (add_directory()) once we start using the iterator.  Currently, it
        #       looks like _get_paths() never forces a cache refresh so if we expect
        #       additional directories to be added later, it is buggy.
        for path in (p for p in self._get_paths() if p not in self._searched_paths and os.path.isdir(p)):
            try:
                full_paths = (os.path.join(path, f) for f in os.listdir(path))
            except OSError as e:
                display.warning("Error accessing plugin paths: %s" % to_text(e))

            for full_path in (f for f in full_paths if os.path.isfile(f) and not f.endswith('__init__.py')):
                full_name = os.path.basename(full_path)

                # HACK: We have no way of executing python byte
                # compiled files as ansible modules so specifically exclude them
                ### FIXME: I believe this is only correct for modules and
                # module_utils.  For all other plugins we want .pyc and .pyo should
                # bew valid
                if full_path.endswith(('.pyc', '.pyo')):
                    continue

                splitname = os.path.splitext(full_name)
                base_name = splitname[0]
                try:
                    extension = splitname[1]
                except IndexError:
                    extension = ''

                # Module found, now enter it into the caches that match
                # this file
                # Add all the names we want to match
                if base_name not in self._plugin_path_cache['']:
                    self._plugin_path_cache[''][base_name] = full_path

                if full_name not in self._plugin_path_cache['']:
                    self._plugin_path_cache[''][full_name] = full_path

                if base_name not in self._plugin_path_cache[extension]:
                    self._plugin_path_cache[extension][base_name] = full_path

                if full_name not in self._plugin_path_cache[extension]:
                    self._plugin_path_cache[extension][full_name] = full_path

            self._searched_paths.add(path)

            find_result = self.module_finder.find_plugin(name, mod_type=suffix)
            if find_result:
                return find_result

        # FIXME: not sure why/when the last namespace check in the loop above wouldnt
        #        find anything but this check would
        find_result = self.module_finder.find_plugin(name, mod_type=suffix)

        # TODO: track which namespace had the name
        if find_result:
            return find_result

        return None

    def has_plugin(self, name):
        ''' Checks if a plugin named name exists '''

        return self.find_plugin(name) is not None

    __contains__ = has_plugin

    def _load_module_source(self, name, path):
        if name in sys.modules:
            # See https://github.com/ansible/ansible/issues/13110
            return sys.modules[name]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            with open(path, 'rb') as module_file:
                module = imp.load_source(name, path, module_file)
        return module

    def get(self, name, *args, **kwargs):
        ''' instantiates a plugin of the given name using arguments '''

        # print('get name=%s args=%s kwargs=%s' % (name, args, repr(kwargs)))
        found_in_cache = True
        class_only = kwargs.pop('class_only', False)
        #if name in self.aliases:
        #    name = self.aliases[name]
        path = self.find_plugin(name)
        if path is None:
            return None

        if path not in self._module_cache:
            self._module_cache[path] = self._load_module_source('.'.join([self.package, name]), path)
            found_in_cache = False

        obj = getattr(self._module_cache[path], self.class_name)
        if self.base_class:
            # The import path is hardcoded and should be the right place,
            # so we are not expecting an ImportError.
            module = __import__(self.package, fromlist=[self.base_class])
            # Check whether this obj has the required base class.
            try:
                plugin_class = getattr(module, self.base_class)
            except AttributeError:
                return None
            if not issubclass(obj, plugin_class):
                return None

        self._display_plugin_load(self.class_name, name, self._searched_paths, path,
                                  found_in_cache=found_in_cache, class_only=class_only)
        if not class_only:
            try:
                obj = obj(*args, **kwargs)
            except TypeError as e:
                if "abstract" in e.args[0]:
                    # Abstract Base Class.  The found plugin file does not
                    # fully implement the defined interface.
                    return None
                raise

        return obj

    def _display_plugin_load(self, class_name, name, searched_paths, path, found_in_cache=None, class_only=None):
        msg = 'Loading %s \'%s\' from %s' % (class_name, os.path.basename(name), path)

        if len(searched_paths) > 1:
            msg = '%s (searched paths: %s)' % (msg, self.format_paths(searched_paths))

        if found_in_cache or class_only:
            msg = '%s (found_in_cache=%s, class_only=%s)' % (msg, found_in_cache, class_only)

        display.debug(msg)

    def all(self, *args, **kwargs):
        ''' instantiates all plugins with the same arguments '''

        path_only = kwargs.pop('path_only', False)
        class_only = kwargs.pop('class_only', False)
        all_matches = []
        found_in_cache = True

        for i in self._get_paths():
            all_matches.extend(glob.glob(os.path.join(i, "*.py")))

        for path in sorted(all_matches, key=lambda match: os.path.basename(match)):
            name, _ = os.path.splitext(path)
            if '__init__' in name:
                continue

            if path_only:
                yield path
                continue

            if path not in self._module_cache:
                self._module_cache[path] = self._load_module_source(name, path)
                found_in_cache = False

            try:
                obj = getattr(self._module_cache[path], self.class_name)
            except AttributeError as e:
                display.warning("Skipping plugin (%s) as it seems to be invalid: %s" % (path, to_text(e)))
                continue

            if self.base_class:
                # The import path is hardcoded and should be the right place,
                # so we are not expecting an ImportError.
                module = __import__(self.package, fromlist=[self.base_class])
                # Check whether this obj has the required base class.
                try:
                    plugin_class = getattr(module, self.base_class)
                except AttributeError:
                    continue
                if not issubclass(obj, plugin_class):
                    continue

            self._display_plugin_load(self.class_name, name, self._searched_paths, path,
                                      found_in_cache=found_in_cache, class_only=class_only)
            if not class_only:
                try:
                    obj = obj(*args, **kwargs)
                except TypeError as e:
                    display.warning("Skipping plugin (%s) as it seems to be incomplete: %s" % (path, to_text(e)))

            # set extra info on the module, in case we want it later
            setattr(obj, '_original_path', path)
            yield obj

action_loader = PluginLoader(
    'ActionModule',
    'ansible.plugins.action',
    C.DEFAULT_ACTION_PLUGIN_PATH,
    'action_plugins',
    required_base_class='ActionBase',
)

cache_loader = PluginLoader(
    'CacheModule',
    'ansible.plugins.cache',
    C.DEFAULT_CACHE_PLUGIN_PATH,
    'cache_plugins',
)

callback_loader = PluginLoader(
    'CallbackModule',
    'ansible.plugins.callback',
    C.DEFAULT_CALLBACK_PLUGIN_PATH,
    'callback_plugins',
)

connection_loader = PluginLoader(
    'Connection',
    'ansible.plugins.connection',
    C.DEFAULT_CONNECTION_PLUGIN_PATH,
    'connection_plugins',
    aliases={'paramiko': 'paramiko_ssh'},
    required_base_class='ConnectionBase',
)

shell_loader = PluginLoader(
    'ShellModule',
    'ansible.plugins.shell',
    'shell_plugins',
    'shell_plugins',
)

module_loader = PluginLoader(
    '',
    'ansible.modules',
    C.DEFAULT_MODULE_PATH,
    'library',
    # for testing atm
    aliases={'bedug': 'debug'},
)

module_utils_loader = PluginLoader(
    '',
    'ansible.module_utils',
    C.DEFAULT_MODULE_UTILS_PATH,
    'module_utils',
)

lookup_loader = PluginLoader(
    'LookupModule',
    'ansible.plugins.lookup',
    C.DEFAULT_LOOKUP_PLUGIN_PATH,
    'lookup_plugins',
    # FIXME: just for testing, remove
    aliases={'xfilex': 'file'},
    required_base_class='LookupBase',
)

vars_loader = PluginLoader(
    'VarsModule',
    'ansible.plugins.vars',
    C.DEFAULT_VARS_PLUGIN_PATH,
    'vars_plugins',
)

filter_loader = PluginLoader(
    'FilterModule',
    'ansible.plugins.filter',
    C.DEFAULT_FILTER_PLUGIN_PATH,
    'filter_plugins',
)

test_loader = PluginLoader(
    'TestModule',
    'ansible.plugins.test',
    C.DEFAULT_TEST_PLUGIN_PATH,
    'test_plugins'
)

fragment_loader = PluginLoader(
    'ModuleDocFragment',
    'ansible.utils.module_docs_fragments',
    os.path.join(os.path.dirname(__file__), 'module_docs_fragments'),
    '',
)

strategy_loader = PluginLoader(
    'StrategyModule',
    'ansible.plugins.strategy',
    C.DEFAULT_STRATEGY_PLUGIN_PATH,
    'strategy_plugins',
    required_base_class='StrategyBase',
)

terminal_loader = PluginLoader(
    'TerminalModule',
    'ansible.plugins.terminal',
    'terminal_plugins',
    'terminal_plugins'
)
