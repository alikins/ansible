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

from collections import defaultdict
import glob
import imp
import os
import sys
import warnings

from ansible.module_utils._text import to_text

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class PluginInfo:
    '''The various info related to a plugin path.'''
    def __init__(self, full_path=None, base_name=None, split_name=None, full_name=None, extension=None):
        self.full_path = full_path
        self.base_name = base_name
        self.split_name = split_name
        self.full_name = full_name
        self.extension = extension
        # module/plugin type (ie, python or powershell etc?)

    @classmethod
    def from_full_path(cls, full_path):

        full_name = os.path.basename(full_path)
        split_name = os.path.splitext(full_name)
        base_name = split_name[0]
        try:
            extension = split_name[1]
        except IndexError:
            extension = ''
        return cls(full_path=full_path,
                   base_name=base_name,
                   split_name=split_name,
                   full_name=full_name,
                   extension=extension)

    def __repr__(self):
        return "%s(full_path=%s, base_name=%s, split_name=%s, full_name=%s, extension=%s)" % \
            (self.__class__.__name__, self.full_path, self.base_name, self.split_name, self.full_name, self.extension)


class PluginPath:
    def __init__(self):
        self.name = None

    def glob(self, pattern):
        return []


# - search for something in the paths
# - enumerate everything found in the paths
# - add a path
# - maintain and respect an ordering or paths
# - get a container of python 'ids' (ie, the python import path ansible.plugins.foo.bar')
#
# a stack of PluginPaths for ordering? potentially with a cache on top of the stack?
#  (chain of responsibity?)
# each plugin type would have differnt PluginPaths instances
# different impl for powershell modules?
class PluginPaths:
    '''A container of plugin paths.'''
    def __init__(self):
        self._paths = []


class CachedPluginPaths(PluginPaths):
    pass


class ChainedPluginPaths:
    '''chain of resp of PluginPaths objects.

    one could be a cache and a finder for ex.'''
    pass


class PluginLoader:
    '''
    PluginLoader loads plugins from the configured plugin directories.

    It searches for plugins by iterating through the combined list of
    play basedirs, configured paths, and the python path.
    The first match is used.
    '''
    class_name = None
    package = None
    default_config = None
    required_base_class = None
    subdir = None
    aliases = None

    def __init__(self, class_name=None, package=None, config=None,
                 subdir=None, aliases=None, required_base_class=None):
        # FIXME: get rid of this once we have classes for each loader, possibly add a
        # classmethod constuctor if we need it
        self.class_name = class_name or self.class_name
        self.package = package or self.package
        self.base_class = required_base_class or self.required_base_class
        self.subdir = subdir or self.subdir
        self.aliases = aliases or self.aliases or {}

        self.config = self.default_config
        config = config or []
        if not isinstance(config, list):
            config = [config]
        if config:
            self.config = config

        self._plugin_path_cache = defaultdict(dict)
        self._module_cache = {}
        self._path_cache = None

        self._extra_dirs = []
        self._searched_paths = set()

        self._plugin_paths = PluginPaths()

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

        self._path_cache = data.get('path_cache')
        self._plugin_path_cache = data.get('plugin_path_cache')

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
            # FIXME: strategy tests call getstate before path_cache has the LookupModule
            # added to the cache and key look fails. Using default and defaulting to None
            # for now. May need instances of lookup loader shared more. or possibly less global
            # caches
            path_cache=self._path_cache,
            plugin_path_cache=self._plugin_path_cache,
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
                    results.append(os.path.join(root, x))
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

    def _get_paths(self):
        ''' Return a list of paths to search for plugins in '''

        if self._path_cache is not None:
            return self._path_cache

        ret = self._extra_dirs[:]

        # look in any configured plugin paths, allow one level deep for subcategories
        if self.config is not None:
            for path in self.config:
                path = os.path.realpath(os.path.expanduser(path))
                contents = glob.glob("%s/*" % path) + glob.glob("%s/*/*" % path)
                for c in contents:
                    if os.path.isdir(c) and c not in ret:
                        ret.append(c)
                if path not in ret:
                    ret.append(path)

        # look for any plugins installed in the package subtree
        ret.extend(self._get_package_paths())

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
        self._path_cache = reordered_paths
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
                self._path_cache = None

    def find_plugin(self, name, mod_type=''):
        ''' Find a plugin named name '''

        display.debug('Looking for %s plugin name=%s and mod_type=%s' % (self.__class__.__name__, name, mod_type))
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
        pull_cache = self._plugin_path_cache[suffix]
        try:
            ret = pull_cache[name]
            display.debug('Found plugin %s for name=%s in the plugin_path_cache' % (ret, name))
            return ret
        except KeyError:
            # Cache miss.  Now let's find the plugin
            pass

        # TODO: Instead of using the self._path_cache (PATH_CACHE) and
        #       self._searched_paths we could use an iterator.  Before enabling that
        #       we need to make sure we don't want to add additional directories
        #       (add_directory()) once we start using the iterator.  Currently, it
        #       looks like _get_paths() never forces a cache refresh so if we expect
        #       additional directories to be added later, it is buggy.
        for path in (p for p in self._get_paths() if p not in self._searched_paths and os.path.isdir(p)):
            display.debug('%s path=%s' % (self.__class__.__name__, path))
            try:
                full_paths = (os.path.join(path, f) for f in os.listdir(path))
            except OSError as e:
                display.warning("Error accessing plugin paths: %s" % to_text(e))

            for full_path in (f for f in full_paths if os.path.isfile(f) and not f.endswith('__init__.py')):
                full_name = os.path.basename(full_path)

                display.debug('%s full_path=%s' % (self.__class__.__name__, full_path))
                # HACK: We have no way of executing python byte
                # compiled files as ansible modules so specifically exclude them
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
                if base_name not in self._plugin_path_cache['']:
                    self._plugin_path_cache[''][base_name] = full_path

                if full_name not in self._plugin_path_cache['']:
                    self._plugin_path_cache[''][full_name] = full_path

                if base_name not in self._plugin_path_cache[extension]:
                    self._plugin_path_cache[extension][base_name] = full_path

                if full_name not in self._plugin_path_cache[extension]:
                    self._plugin_path_cache[extension][full_name] = full_path

            self._searched_paths.add(path)
            try:
                return pull_cache[name]
            except KeyError:
                # Didn't find the plugin in this directory.  Load modules from
                # the next one
                pass

        # if nothing is found, try finding alias/deprecated
        if not name.startswith('_'):
            alias_name = '_' + name
            # We've already cached all the paths at this point
            if alias_name in pull_cache:
                if not os.path.islink(pull_cache[alias_name]):
                    display.deprecated('%s is kept for backwards compatibility '
                              'but usage is discouraged. The module '
                              'documentation details page may explain '
                              'more about this rationale.' %
                              name.lstrip('_'))
                return pull_cache[alias_name]

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

        # print('get name=%s self=%sbeing created with args=%s kwargs=%s' % (name, self, repr(args), repr(kwargs)))
        found_in_cache = True
        class_only = kwargs.pop('class_only', False)
        if name in self.aliases:
            name = self.aliases[name]
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
                try:
                    self._module_cache[path] = self._load_module_source(name, path)
                except ImportError as e:
                    print('Error loading %s: %s' % (path, e))
                    continue

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
                obj = obj(*args, **kwargs)

            # set extra info on the module, in case we want it later
            setattr(obj, '_original_path', path)
            yield obj
