
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


class FactNamespace:
    def __init__(self, namespace_name):
        self.namespace_name = namespace_name

    def transform(self, name):
        '''Take a text name, and transforms it as needed (add a namespace prefix, etc)'''
        return name

    def underscore(self, name):
        return name.replace('-', '_')


class PrefixFactNamespace(FactNamespace):
    def __init__(self, namespace_name, prefix=None):
        super(PrefixFactNamespace, self).__init__(namespace_name)
        self.prefix = prefix

    def transform(self, name):
        new_name = self.underscore(name)
        return '%s%s' % (self.prefix, new_name)
