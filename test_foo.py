import sys
import imp
import logging

log = logging.getLogger('ansible_module_loader')
logging.basicConfig(level=logging.DEBUG)

class ImportThing(object):
    def __init__(self):
        # one to one for now to bootstrap
        self.virtual_modules = {'vansible': None,
                                'vansible.module_utils':['ansible.module_utils', []],
                                'vansible.module_utils.basic': ['ansible.module_utils.basic', []],
                                'vansible.module_utils.facts': ['ansible.module_utils.facts', []]}
        self.virtual_packages = {'vansible': True,
                                 'vansible.module_utils': True}

        self.namespace = 'vansible'

    def find_module(self, fullname, path=None):
        #log.debug('find_module fullname=%s path=%s', fullname, path)
        if fullname in self.virtual_modules:
            return self
        return None

    def load_module(self, fullname):
        log.debug('load_module: %s', fullname)
        if fullname in sys.modules:
            return sys.modules[fullname]

        if fullname not in self.virtual_modules:
            raise ImportError(fullname)

        # The base namespace
        if fullname == self.namespace:
            return self._namespace_module()

        real_module_name = real_module_from = None
        mod_info = self.virtual_modules[fullname]
        if mod_info:
            real_module_name, real_module_from = mod_info

        #if not real_module_from:
        #    raise ImportError(fullname)

        # looks like a real_module alias
        log.debug('loading real module')
        return self._import_real_module(fullname, real_module_name, real_module_from)

    def _is_package(self, fullname):
        log.debug('is_package fullname=%s', fullname)
        if fullname in self.virtual_packages:
            log.debug('is_package fullname=%s True', fullname)
            return True
        return False

    def get_filename(self, fullname):
        log.debug('get_filename fullname=%s', fullname)
        if fullname not in self.virtual_modules:
            raise ImportError(fullname)
        return 'this_is_not_a_real_filename'

    def _import_real_module(self, fullname, real_module_name, real_module_from):
        log.debug('fullname=%s module_name=%s module_from=%s', fullname, real_module_name, real_module_from)
        #ret = __import__(module_name, globals(), locals(), [module_from])
        parts = fullname.split('.')
        from_list = []
        ret = sys.modules.setdefault(fullname, __import__(real_module_name))

        #ret = __import__(fullname, globals(), dir(ret), from_list)
        show_module(ret)
        #sys.modules.setdefault(ret
        #ret = imp.load_module(fullname, None, '', ('', '', imp.PY_SOURCE))

        log.debug('import_real_module ret=%s', ret)
        log.debug('dir(ret)=%s', dir(ret))

        if hasattr(ret, '__file__'):
            orig_filename = ret.__file__
            log.debug('orig_filename: %s' % orig_filename)

        ret.__file__ = '<ansible faux module based on %s>' % orig_filename
        ret.__orig_file__ = orig_filename
        ret.__name__ = fullname
        ret.__loader__ = self
        ret.__package__ = True
        #ret.__file__ = fullname
        sys.modules[fullname] = ret
        return ret

    # This creates a new module from scratch, but it could be one loaded by imp
    # from file
    def _new_module(self, fullname):
        """Create a an empty module, we can populate with impl specific."""
        ret = sys.modules.setdefault(fullname, imp.new_module(fullname))
        ret.__name__ = fullname
        ret.__loader__ = self
        ret.__file__ = fullname
        ret.__path__ = [fullname]
        #ret.__package__ = '.'.join(fullname.split('.')[:-1])
        log.debug('packagepath? %s', '.'.join(fullname.split('.')[:-1]))
        ret.__package__ = False
        return ret

    def _new_package(self, fullname):
        ret = self._new_module(fullname)
        ret.__package__ = True
        return ret

    def _namespace_module(self):
        #return self._import_real_module(self.namespace,
        #                                self.namespace,
        #                                None)
        return self._new_module(self.namespace)

sys.meta_path.append(ImportThing())

def show_module(module):
    log.debug('module: %s', module)
    log.debug('__file__: %s', getattr(module, '__file__', 'N/A'))
    log.debug('__orig_ file__: %s', getattr(module, '__orig_file__', 'N/A'))
    log.debug('dir %s', dir(module))
    log.debug('__package__ %s', module.__package__)

import vansible
import vansible.module_utils
print vansible, vansible.module_utils
show_module(vansible)
show_module(vansible.module_utils)

from vansible.module_utils import basic
show_module(basic)
