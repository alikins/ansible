#
# Copyright (c) 2015 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License,
# version 2 (GPLv2). There is NO WARRANTY for this software, express or
# implied, including the implied warranties of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. You should have received a copy of GPLv2
# along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.
#
# Red Hat trademarks are not licensed under GPLv2. No permission is
# granted to use or replicate Red Hat trademarks that are incorporated
# in this software or its documentation.
#

import imp
import sys

#import logging #sigh
#log = logging.getLogger(__name__)
#from ansible import module_utils as real_module_utils

class GaImporter(object):
    """Custom module importer protocol that finds and loads the 'ga' Gtk2/Gtk3 compat virtual module.

    This implements the module "Importer Protocol" as defined
    in PEP302 (https://www.python.org/dev/peps/pep-0302/). It provides
    both a module finder (find_modules) and a module loader (load_modules).

    This lets different sub classes of this module to all provide a set of
    module names in the 'ga' namespace, but to provide different implementations.

    When an instance of this class is added to sys.meta_path, all imports that
    reference modules by name (ie, normal 'import bar' statements) the names are first passed
    to this classes 'find_module' method. When this class is asked for modules in
    the 'ga' package, it returns itself (which is also a module loader).

    This classes load_module() is used to decide which implemention of the 'ga'
    package to load. GaImporter.virtual_modules is a dict mapping full module name
    to the full name of the module that is to be loaded for that name.

    The 'ga' module implementations are in the ga_impls/ module.
    The available implementations are 'ga_gtk2' and 'ga_gtk3'.

    The 'ga' module itself provides a Gtk3-like API.

    The 'ga_impls/ga_gtk3' implementation is an export of the full 'gi.repository.Gtk',
    and a few helper methods and names.

    The 'ga_impls/ga_gtk2' implementation is more complicated. It maps a subset of
    Gtk2 names and widgets to their Gtk3 equilivent. This includes an assortment
    of class enums, and helper methods. The bulk of the API compat is just mapping
    names like 'gtk.Window' to Gtk style names like 'gi.repository.Gtk.Window'.

    NOTE: Only symbols actually used in subscription-manager are provided. This
          is not a general purpose Gtk3 interface for Gtk2. Names are imported
          directly and export directly in module __all__ attributes. This is to
          make sure any Gtk3 widgets used in subman have working gtk2 equilivents
          and ga_gtk2 provides it.
    """

    #namespace = "subscription_manager.ga"
    namespace = "ansible.module_utils"
    virtual_modules = {}

    def __init__(self):
        print("ga_loader %s" % self.__class__.__name__)
        self._real_ansible = imp.find_module('ansible')
        print('real_ansible: %s' % repr(self._real_ansible))
        self._real_ansible_path = self._real_ansible[1]
        self._real_ansible_module = imp.load_module('ansible', None, self._real_ansible_path, self._real_ansible[2])
        print('self._real_ansible_module: %s' % dir(self._real_ansible_module))
        self._real_ansible_module_utils_info = imp.find_module('python_module_utils', self._real_ansible_module.__path__)
        #print('imp.get_suffices: %s' % imp.get_suffixes())
        self.module_desc = ('.py', 'U', 1)
        self.module_desc = ('.pyc', 'rb', 2)
        self._real_ansible_module_utils_module = imp.load_module('ansible.python_module_utils', None, self._real_ansible_path, self._real_ansible[2])
        sys.modules['ansible.python_module_utils'] = self._real_ansible_module_utils_module

    def is_virtual_module(self, fullname, path):
        parts = fullname.split('.')
        print('parts: %s' % parts)
        print('parg2: %s' % parts[0:2])
        if parts[0:2] == ['ansible', 'module_utils']:
            return True
        return False

    def find_module(self, fullname, path):
        print('fm: %s %s' % (fullname, path))
#        print('self.vm: %s' % self.virtual_modules)

        if not self.is_virtual_module(fullname, path):
            return None
        print('searching for virtual module: %s %s' % (fullname, path))
        return self

        # just the namespace
        parts = fullname.split('.')
        print('partssdsd: %s' % parts)
        if parts == ['ansible', 'module_utils']:
            return self

        ret = self.find_virtual_modules(fullname)
        print('ret: %s' % ret)
        if ret:
            return self
        return None

    def find_virtual_modules(self, fullname):
        print('fullname: %s' % fullname)

        real_fullname = fullname.replace('.module_utils.', '.python_module_utils.')
        print('real_fullname: %s' % real_fullname)
        print('real_ansible: %s' % repr(self._real_ansible))

        path_parts = real_fullname.split('.')
        module_name_trunk = path_parts[:-1]
        module_name_leaf = path_parts[-1]

        print('module_filename: %s' % module_name_leaf)
        print('self.self._real_ansible_module_utils_module: %s' % self._real_ansible_module_utils_module)
        print('find module path: %s' % self._real_ansible_module_utils_module.__path__)
        real_module_name = '.'.join(module_name_trunk)
        return [real_module_name, None]

        #real_module_info = imp.find_module(module_filename, self._real_ansible_module_utils_module.__path__)
        print('self._real_ansible_module_utils_info: %s' % repr(self._real_ansible_module_utils_info))

        print('module_name_leaf: %s' % module_name_leaf)
        print('imp.find_module(%s, %s)' % (module_name_leaf, [self._real_ansible_module_utils_info[1]]))
        import pprint
        print('sys.modules:')
        pprint.pprint([(x[0], x[1]) for x in sys.modules.items() if x[0].startswith('ansible')])

        real_parent_name = '.'.join(module_name_trunk)
        print('real_parent_name: %s' % real_parent_name)
        #parent_module = imp.load_module(real_parent_name, None, self._real_ansible_module_utils_module.__path__, self._real_ansible_module_utils_module)
        real_parent_module = sys.modules.get(real_parent_name, None)
        print('real_parent_module: %s' % real_parent_module)

        real_parent_path = real_parent_module.__path__
        #real_module_info = imp.find_module(module_name_leaf, [self._real_ansible_module_utils_info[1]])
        try:
            real_module_info = imp.find_module(module_name_leaf, real_parent_path)
            print('real_module_info: %s' % repr(real_module_info))
        except ImportError as e:
            print('imp.find_module raised an ImportError while trying imp.find_module(%s, %s) cccccccccccccc %s' % (module_name_leaf, [real_parent_path], e))
            return None

        mod_type = real_module_info[2][2]
        print('mod_type: %s' % mod_type)

        from_name = None
        if mod_type in [imp.PY_SOURCE, imp.PY_COMPILED]:
            from_name = module_name_leaf
        else:
            print('unknown mod type: %s' % mod_type)
        #return [real_fullname, from_name]
        virtual_module_info = ['.'.join(module_name_trunk), from_name]
        print('vmi: %s' % virtual_module_info)
        return virtual_module_info
        #return [real_fullname, from_name]
        #return self.virtual_modules[real_fullname]

    def load_module(self, fullname):
        print('LOAD_MODULE: %s' % fullname)
        if fullname in sys.modules:
            return sys.modules[fullname]

        #if fullname not in self.virtual_modules:
        #    raise ImportError('fullname: %s not found in virtual_modules' % fullname)

        # The base namespace
        if fullname == self.namespace:
            return self._namespace_module()

        real_module_name = real_module_from = None
        #mod_info = self.virtual_modules[fullname]
        mod_info = self.find_virtual_modules(fullname)
        if mod_info:
            real_module_name, real_module_from = mod_info

#        if not real_module_from:
#            raise ImportError('fullname: %s from load_module real_module_from' % fullname)
        #self._real_ansible_module = imp.load_module('ansible', None, self._real_ansible_path, self._real_ansible[2])
        #self._real_ansible_module_utils_module = imp.load_module('ansible.python_module_utils', None, self._real_ansible_path, self._real_ansible[2])
        #real_module_info = imp.find_module(module_name_leaf, real_parent_path)
        #return imp.load_module(real_module_name, None,
        # looks like a real_module alias
        #return self._import_real_module(fullname, real_module_name, real_module_from)
        if real_module_name == 'ansible.python_module_utils':
            real_module_from = None
        else:
            parts = real_module_name.split('.')
            real_module_from = [parts[-1]]

        return self._import_real_module(real_module_name, real_module_name, real_module_from)

    def _import_real_module(self, fullname, module_name, module_from):
        print('IMPORT_REAL_MODULE module_name=%s' % module_name)
        import pprint
        #pprint.pprint(sys.modules)
        print('module_name: %s' % module_name)
        print('fullname: %s' % fullname)
        print('module_from: %s' % module_from)
        #return real_module_utils
        #if fullname == self.namespace:
        #    return real_module_utils

        parts = module_name.split('.')
        if len(parts) > 2:
            module_name = '.'.join(parts[0:2])


        print('module_from2: %s' % module_from)
        try:
            ret = __import__(module_name, globals(), locals(), module_from)
        except ImportError as e:
            print('Got an ImportError on the __import__ module_name=%s %s: %s' % (module_name, module_from, e))
            raise
        print('ret: %s' % ret)
        print('dir(ret): %s' % pprint.pformat(dir(ret)))
        print('module_from: %s' % module_from)
        print('type(module_from): %s' % type(module_from))
        if module_from:
            inner_ret = getattr(ret, module_from[0], None)
            if inner_ret:
                ret = inner_ret
                ret.__package__ = True
        ret.__name__ = fullname
        ret.__loader__ = self
        #ret.__package__ = True
        print('RET: %s' % ret)
        sys.modules[fullname] = ret
        return ret

    def _new_module(self, fullname):
        """Create a an empty module, we can populate with impl specific."""
        print('_new_module(%s)' % fullname)
        ret = sys.modules.setdefault(fullname, imp.new_module(fullname))
        ret.__name__ = fullname
        ret.__loader__ = self
        ret.__filename__ = fullname
        ret.__path__ = [fullname]
        ret.__package__ = '.'.join(fullname.split('.')[:-1])
        return ret

    def _namespace_module(self):
        """Create and return a 'ga' package module.

        Since the 'ga' module has to work for Gtk2/Gtk3, but can't import
        either, we create a new module instance and add it to the system
        path.

        Imports like 'from ga import Gtk3' first have to import 'ga'. When
        they do, the module instance is the one we create here.
        """
        #return real_module_utils
        return self._new_module(self.namespace)


class ModuleUtilsImporter(GaImporter):
    virtual_modules = {'ansible.module_utils': None,
                       'ansible.module_utils.facts': ['ansible.python_module_utils.facts', 'facts'],
                       #'ansible.module_utils.facts.Facts': ['python_module_utils.facts.Facts', 'facts'],
                       'ansible.module_utils._text': ['ansible.python_module_utils._text', '_text'],
                       'ansible.module_utils.basic': ['ansible.python_module_utils.basic', 'basic'],
                       'ansible.module_utils.six': ['ansible.python_module_utils.six', None],
                       }


def init_ga(module_utils_paths=None):
    """Decide which GaImporter implementation to load.

    Applications should import this module and call this method before
    importing anything from the 'ga' namespace.

    After calling this method, a GaImporter implementation is added to sys.meta_path.
    This sets up a module finder and loader that will return 'virtual' modules
    when asked for 'ga.Gtk' for example. Depending on the GaImporter, 'ga.Gtk'
    may be implemented with Gtk3 or gtk2.

    The default implementation is the gtk2 based one (DEFAULT_GTK_VERSION).

    The acceptable values of 'gtk_version' are '2' and '3', for gtk2 and
    gtk3.

    It can be overridden by, in order:

        Hardcoded DEFAULT_GTK_VERSION.
        (default is '2')

        The value of subscription_manager.version.gtk_version if it exists
        and is not None.
        (As set at build time)

        The 'gtk_version' argument to this method if not None.
        (The default is None)

        The value of the environment variable 'SUBMAN_GTK_VERSION' if set
        to '2' or '3'.
        (default is unset)
    """

    sys.meta_path.append(ModuleUtilsImporter())
    # if module_utils_paths is whatever:
    #     sys.meta_path.append(one instance of GaImporter)

    #if GTK_VERSION == "3":
    #    sys.meta_path.append(GaImporterGtk3())
    #if GTK_VERSION == "2":
    #    sys.meta_path.append(GaImporterGtk2())
