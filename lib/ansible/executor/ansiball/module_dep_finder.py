import ast
import os
import imp

from ansible.errors import AnsibleError
from ansible.plugins import module_utils_loader

# ansiball.module_dep_finder is relative to module_utils, so fix the path
_PYTHON_MODULE_UTILS_PATH = os.path.join(os.path.dirname(__file__), '../..', 'module_utils')


class ModuleDepFinder(ast.NodeVisitor):
    # Caveats:
    # This code currently does not handle:
    # * relative imports from py2.6+ from . import urls
    IMPORT_PREFIX_SIZE = len('ansible.module_utils.')

    def __init__(self, *args, **kwargs):
        """
        Walk the ast tree for the python module.

        Save submodule[.submoduleN][.identifier] into self.submodules

        self.submodules will end up with tuples like:
          - ('basic',)
          - ('urls', 'fetch_url')
          - ('database', 'postgres')
          - ('database', 'postgres', 'quote')

        It's up to calling code to determine whether the final element of the
        dotted strings are module names or something else (function, class, or
        variable names)
        """
        super(ModuleDepFinder, self).__init__(*args, **kwargs)
        self.submodules = set()

    def visit_Import(self, node):
        # import ansible.module_utils.MODLIB[.MODLIBn] [as asname]
        for alias in (a for a in node.names if a.name.startswith('ansible.module_utils.')):
            py_mod = alias.name[self.IMPORT_PREFIX_SIZE:]
            py_mod = tuple(py_mod.split('.'))
            self.submodules.add(py_mod)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module.startswith('ansible.module_utils'):
            where_from = node.module[self.IMPORT_PREFIX_SIZE:]
            if where_from:
                # from ansible.module_utils.MODULE1[.MODULEn] import IDENTIFIER [as asname]
                # from ansible.module_utils.MODULE1[.MODULEn] import MODULEn+1 [as asname]
                # from ansible.module_utils.MODULE1[.MODULEn] import MODULEn+1 [,IDENTIFIER] [as asname]
                py_mod = tuple(where_from.split('.'))
                for alias in node.names:
                    self.submodules.add(py_mod + (alias.name,))
            else:
                # from ansible.module_utils import MODLIB [,MODLIB2] [as asname]
                for alias in node.names:
                    self.submodules.add((alias.name,))
        self.generic_visit(node)


def _slurp(path):
    if not os.path.exists(path):
        raise AnsibleError("imported module support code does not exist at %s" % os.path.abspath(path))
    fd = open(path, 'rb')
    data = fd.read()
    fd.close()
    return data


def _get_shebang(interpreter, task_vars, args=tuple()):
    """
    Note not stellar API:
       Returns None instead of always returning a shebang line.  Doing it this
       way allows the caller to decide to use the shebang it read from the
       file rather than trust that we reformatted what they already have
       correctly.
    """
    interpreter_config = u'ansible_%s_interpreter' % os.path.basename(interpreter).strip()

    if interpreter_config not in task_vars:
        return (None, interpreter)

    interpreter = task_vars[interpreter_config].strip()
    shebang = u'#!' + interpreter

    if args:
        shebang = shebang + u' ' + u' '.join(args)

    return (shebang, interpreter)


def recursive_finder(name, data, py_module_names, py_module_cache, zf):
    """
    Using ModuleDepFinder, make sure we have all of the module_utils files that
    the module its module_utils files needs.
    """
    # Parse the module and find the imports of ansible.module_utils
    tree = ast.parse(data)
    finder = ModuleDepFinder()
    finder.visit(tree)

    #
    # Determine what imports that we've found are modules (vs class, function.
    # variable names) for packages
    #

    normalized_modules = set()
    # Loop through the imports that we've found to normalize them
    # Exclude paths that match with paths we've already processed
    # (Have to exclude them a second time once the paths are processed)

    module_utils_paths = [p for p in module_utils_loader._get_paths(subdirs=False) if os.path.isdir(p)]
    module_utils_paths.append(_PYTHON_MODULE_UTILS_PATH)
    for py_module_name in finder.submodules.difference(py_module_names):
        module_info = None

        if py_module_name[0] == 'six':
            # Special case the python six library because it messes up the
            # import process in an incompatible way
            module_info = imp.find_module('six', module_utils_paths)
            py_module_name = ('six',)
            idx = 0
        else:
            # Check whether either the last or the second to last identifier is
            # a module name
            for idx in (1, 2):
                if len(py_module_name) < idx:
                    break
                try:
                    module_info = imp.find_module(py_module_name[-idx],
                            [os.path.join(p, *py_module_name[:-idx]) for p in module_utils_paths])
                    break
                except ImportError:
                    continue

        # Could not find the module.  Construct a helpful error message.
        if module_info is None:
            msg = ['Could not find imported module support code for %s.  Looked for' % name]
            if idx == 2:
                msg.append('either %s.py or %s.py' % (py_module_name[-1], py_module_name[-2]))
            else:
                msg.append(py_module_name[-1])
            raise AnsibleError(' '.join(msg))

        # Found a byte compiled file rather than source.  We cannot send byte
        # compiled over the wire as the python version might be different.
        # imp.find_module seems to prefer to return source packages so we just
        # error out if imp.find_module returns byte compiled files (This is
        # fragile as it depends on undocumented imp.find_module behaviour)
        if module_info[2][2] not in (imp.PY_SOURCE, imp.PKG_DIRECTORY):
            msg = ['Could not find python source for imported module support code for %s.  Looked for' % name]
            if idx == 2:
                msg.append('either %s.py or %s.py' % (py_module_name[-1], py_module_name[-2]))
            else:
                msg.append(py_module_name[-1])
            raise AnsibleError(' '.join(msg))

        if idx == 2:
            # We've determined that the last portion was an identifier and
            # thus, not part of the module name
            py_module_name = py_module_name[:-1]

        # If not already processed then we've got work to do
        if py_module_name not in py_module_names:
            # If not in the cache, then read the file into the cache
            # We already have a file handle for the module open so it makes
            # sense to read it now
            if py_module_name not in py_module_cache:
                if module_info[2][2] == imp.PKG_DIRECTORY:
                    # Read the __init__.py instead of the module file as this is
                    # a python package
                    py_module_cache[py_module_name + ('__init__',)] = _slurp(os.path.join(os.path.join(module_info[1], '__init__.py')))
                    normalized_modules.add(py_module_name + ('__init__',))
                else:
                    py_module_cache[py_module_name] = module_info[0].read()
                    module_info[0].close()
                    normalized_modules.add(py_module_name)

            # Make sure that all the packages that this module is a part of
            # are also added
            for i in range(1, len(py_module_name)):
                py_pkg_name = py_module_name[:-i] + ('__init__',)
                if py_pkg_name not in py_module_names:
                    pkg_dir_info = imp.find_module(py_pkg_name[-1],
                            [os.path.join(p, *py_pkg_name[:-1]) for p in module_utils_paths])
                    normalized_modules.add(py_pkg_name)
                    py_module_cache[py_pkg_name] = _slurp(pkg_dir_info[1])

    #
    # iterate through all of the ansible.module_utils* imports that we haven't
    # already checked for new imports
    #

    # set of modules that we haven't added to the zipfile
    unprocessed_py_module_names = normalized_modules.difference(py_module_names)

    for py_module_name in unprocessed_py_module_names:
        py_module_path = os.path.join(*py_module_name)
        py_module_file_name = '%s.py' % py_module_path

        zf.writestr(os.path.join("ansible/module_utils",
                py_module_file_name), py_module_cache[py_module_name])

    # Add the names of the files we're scheduling to examine in the loop to
    # py_module_names so that we don't re-examine them in the next pass
    # through recursive_finder()
    py_module_names.update(unprocessed_py_module_names)

    for py_module_file in unprocessed_py_module_names:
        recursive_finder(py_module_file, py_module_cache[py_module_file], py_module_names, py_module_cache, zf)
        # Save memory; the file won't have to be read again for this ansible module.
        del py_module_cache[py_module_file]
