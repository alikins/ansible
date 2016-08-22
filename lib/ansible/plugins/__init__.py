# (c) 2012, Daniel Hokka Zakrisson <daniel@hozac.com>
# (c) 2012-2014, Michael DeHaan <michael.dehaan@gmail.com> and others
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
import inspect
import os
import os.path
import sys
import warnings

from collections import defaultdict

from ansible import constants as C
from ansible.utils.unicode import to_unicode

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()

# Global so that all instances of a PluginLoader will share the caches
MODULE_CACHE = {}
PATH_CACHE = {}
PLUGIN_PATH_CACHE = {}

import traceback
import pprint

def get_all_plugin_loaders():
    return [(name, obj) for (name, obj) in inspect.getmembers(sys.modules[__name__]) if isinstance(obj, PluginLoader)]

class PluginLoader:

    '''
    PluginLoader loads plugins from the configured plugin directories.

    It searches for plugins by iterating through the combined list of
    play basedirs, configured paths, and the python path.
    The first match is used.
    '''

    def __init__(self, class_name, package, config, subdir, aliases={}, required_base_class=None):

        self.class_name         = class_name
        self.base_class         = required_base_class
        self.package            = package
        self.subdir             = subdir
        self.aliases            = aliases

        if config and not isinstance(config, list):
            config = [config]
        elif not config:
            config = []

        self.config = config

        if not class_name in MODULE_CACHE:
            MODULE_CACHE[class_name] = {}
        if not class_name in PATH_CACHE:
            PATH_CACHE[class_name] = None
        if not class_name in PLUGIN_PATH_CACHE:
            PLUGIN_PATH_CACHE[class_name] = defaultdict(dict)

        self._module_cache      = MODULE_CACHE[class_name]
        self._paths             = PATH_CACHE[class_name]
        self._plugin_path_cache = PLUGIN_PATH_CACHE[class_name]

        self._extra_dirs = []
        self._searched_paths = set()
        #self._new_paths = self._get_initial_paths()
        self._new_paths = []

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

    def _get_package_paths(self):
        ''' Gets the path of a Python package '''

        if not self.package:
            return []
        if not hasattr(self, 'package_path'):
            m = __import__(self.package)
            parts = self.package.split('.')[1:]
            for parent_mod in parts:
                m = getattr(m, parent_mod)
            self.package_path = os.path.dirname(m.__file__)
        return self._all_directories(self.package_path)

    def _get_extra_paths(self):
        # FIXME: does this need to be a copy?
        return self._extra_dirs[:]

    def _get_config_paths(self):
        # look in any configured plugin paths, allow one level deep for subcategories
        config_paths = []
        if self.config is not None:
            for path in self.config:
                path = os.path.realpath(os.path.expanduser(path))
                contents = glob.glob("%s/*" % path) + glob.glob("%s/*/*" % path)
                for c in contents:
                    if os.path.isdir(c) and c not in config_paths:
                        config_paths.append(c)
                if path not in config_paths:
                    config_paths.append(path)
        return config_paths

    def _get_win_paths(self):
        pass

    def _get_initial_paths(self):
        ''' Return a list of paths to search for plugins in '''

        new_paths = []
        new_paths.extend(self._get_extra_paths())
        new_paths.extend(self._get_config_paths())
        new_paths.extend(self._get_package_paths())
        #new_paths.append(self._get_win_paths())
        # start with all the extra dirs, add configured dirs and sub paths
        #ret = self._extra_dirs[:]


        # look for any plugins installed in the package subtree
        #ret.extend(self._get_package_paths())

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
        for path in new_paths:
            if path.endswith('windows'):
                win_dirs.append(path)
            else:
                reordered_paths.append(path)
        reordered_paths.extend(win_dirs)

        # cache and return the result
        #self._paths = reordered_paths
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
        #        self._paths = None
                # self._plugin_path_cache = defaultdict(dict)
                self._new_paths.append(directory)

    def _get_new_paths(self):
        # We don't care if we think we searched the path before, something has claimed it is 'new'
        new_paths = []
        for path in (p for p in self._new_paths if os.path.isdir(p)):
            new_paths.append(path)

        display.vvv('new_paths=%s' % new_paths)
        return new_paths

    def _cache_full_path(self, mod_type, full_path):
        '''Populate the plugin path caches by side effect'''
        full_name = os.path.basename(full_path)

        # HACK: We have no way of executing python byte
        # compiled files as ansible modules so specifically exclude them
        if full_path.endswith(('.pyc', '.pyo')):
            return

        # _cache_path()
        splitname = os.path.splitext(full_name)
        base_name = splitname[0]
        try:
            extension = splitname[1]
        except IndexError:
            extension = ''

        display.vvv('full_path=%s' % full_path)

        # Module found, now enter it into the caches that match
        # this file
        if base_name not in self._plugin_path_cache['']:
            self._plugin_path_cache[''][base_name] = full_path

        if full_name not in self._plugin_path_cache['']:
            self._plugin_path_cache[''][full_name] = full_path

        if base_name not in self._plugin_path_cache[extension]:
            self._plugin_path_cache[extension][base_name] = full_path

        if full_name not in self._plugin_path_cache[extension]:
            self._plugin_path_cache[extension][full_name] = full_path

    def _is_valid_full_path(self, full_path):
        if not os.path.isfile(full_path):
            return False
        # make module type specific
        if full_path.endswith('__init__.py'):
            return False
        return True

    def _get_full_paths(self, dir_path):
        full_paths = []
        try:
            full_paths = (os.path.join(dir_path, f) for f in os.listdir(dir_path))
        except OSError as e:
            display.warning("Error accessing plugin paths: %s" % to_unicode(e))

        # filter out any invalid files or dirs
        return [f for f in full_paths if self._is_valid_full_path(f)]

    def update_plugin_cache(self, mod_type, name):
        display.vvv('update_plugin_cache')
        traceback.print_stack()
        # First call will be all configured paths
        for dir_path in (p for p in self._get_new_paths()):
            full_paths = self._get_full_paths(dir_path)

            # TODO: currently the module cache key is based on filename manipulations of full_path,
            #       eventually it should be decoupled
            # cache the plugins (or modules) we found
            for full_path in full_paths:
                self._cache_full_path(mod_type, full_path)

            # track the paths we've searched in for user info messages
            self._searched_paths.add(dir_path)

    def find_plugin(self, name, mod_type=None):
        ''' Find a plugin named name '''
        # mod_type can be an enum
        mod_type = mod_type or self.class_name or ''
        display.vvv('find_plugin name=%s mod_type=%s' % (name, mod_type))

        # Process 'new dirs', then check the caches

        # The particular cache to look for modules within.  This matches the
        # requested mod_type

        # Check in any new paths before trying to use the cache
        self.update_plugin_cache(mod_type, name)

        # lookup in the cached
        return self._search_cache(mod_type, name)

    def _search_cache(self, mod_type, name):
        display.vvv('mod_type=%s name=%s' % (mod_type, name))

        display.vvv('cache=%s' % pprint.pformat(self._plugin_path_cache))
        display.vvv('cache[.py] = %s' % pprint.pformat(self._plugin_path_cache['.py']))
        display.vvv('cache[%s][%s]=%s' % (mod_type, name, pprint.pformat(self._plugin_path_cache[mod_type])))

        try:
            return self._plugin_path_cache[mod_type][name]
        except KeyError:
            # Didn't find the plugin in this directory.  Load modules from
            # the next one
            pass

        return self._search_alias_in_cache(mod_type, name)

    def _search_alias_in_cache(self, mod_type, name):
        # if nothing is found, try finding alias or a deprecated version
        #
        # FIXME: magic string name
        # If the module was referenced directly with the _module name, we
        # would have found it already.
        if name.startswith('_'):
            return None

        alias_name = '_' + name

        alias_path = self._plugin_path_cache[mod_type].get(alias_name, None)
        if not alias_path:
            return None

        self._check_deprecated(name, mod_type, alias_path)

        return alias_path

    def _check_deprecated(self, name, mod_type, full_path):
        '''Detect if a plugin is deprecated.

        Currently that just means the path name is in the form of '_module_name'.

        The side_effect is displaying a deprecated warning.
        '''
        # Note: mod_type is currently not used here

        if not os.path.islink(full_path):
            display.deprecated('%s is kept for backwards compatibility '
                        'but usage is discouraged. The module '
                        'documentation details page may explain '
                        'more about this rationale.' %
                        name.lstrip('_'))

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
            with open(path, 'r') as module_file:
                module = imp.load_source(name, path, module_file)
        return module

    def get(self, name, *args, **kwargs):
        ''' instantiates a plugin of the given name using arguments '''

        found_in_cache = True
        class_only = kwargs.pop('class_only', False)
        if name in self.aliases:
            name = self.aliases[name]

        self._new_paths = self._get_initial_paths()

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
            obj = obj(*args, **kwargs)

        return obj

    def _display_plugin_load(self, class_name, name, searched_paths, path, found_in_cache=None, class_only=None):
        searched_msg = 'Searching for plugin type %s named \'%s\' in paths: %s' % (class_name, name, self.format_paths(searched_paths))
        loading_msg = 'Loading plugin type %s named \'%s\' from %s' % (class_name, name, path)

        if found_in_cache or class_only:
            extra_msg = 'found_in_cache=%s, class_only=%s' % (found_in_cache, class_only)
            display.debug('%s %s' % (searched_msg, extra_msg))
            display.debug('%s %s' % (loading_msg, extra_msg))
        else:
            display.vvvv(searched_msg)
            display.vvv(loading_msg)

    def all(self, *args, **kwargs):
        ''' instantiates all plugins with the same arguments '''

        class_only = kwargs.pop('class_only', False)
        all_matches = []
        found_in_cache = True

        for i in self._get_new_paths():
            all_matches.extend(glob.glob(os.path.join(i, "*.py")))

        for path in sorted(all_matches, key=lambda match: os.path.basename(match)):
            name, _ = os.path.splitext(path)
            if '__init__' in name:
                continue

            if path not in self._module_cache:
                self._module_cache[path] = self._load_module_source(name, path)
                found_in_cache = False

            try:
                obj = getattr(self._module_cache[path], self.class_name)
            except AttributeError as e:
                display.warning("Skipping plugin (%s) as it seems to be invalid: %s" % (path, to_unicode(e)))
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
                obj = obj(*args, **kwargs)

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
)

lookup_loader = PluginLoader(
    'LookupModule',
    'ansible.plugins.lookup',
    C.DEFAULT_LOOKUP_PLUGIN_PATH,
    'lookup_plugins',
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
