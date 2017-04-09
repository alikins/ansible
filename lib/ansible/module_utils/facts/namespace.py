
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

def _underscore(name):
    return name.replace('-', '_')

class FactNamespace:
    def __init__(self, namespace_name):
        self.namespace_name = namespace_name

    def transform(self, name):
        '''Take a text name, and transforms it as needed (add a namespace prefix, etc)'''
        return name


class PrefixFactNamespace(FactNamespace):
    def __init__(self, namespace_name, prefix=None):
        super(PrefixFactNamespace, self).__init__(namespace_name)
        self.prefix = prefix

    def transform(self, name):
        new_name = _underscore(name)
        return '%s%s' % (self.prefix, new_name)
