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

import sys
from collections import defaultdict

from ansible.compat.tests import unittest
from ansible.compat.tests.mock import patch, MagicMock

from ansible.template.safe_eval import safe_eval


class TestSafeEval(unittest.TestCase):

    def setUp(self):
        self._locals = {}

    def tearDown(self):
        pass

    def _eval(self, code, expected, expected_type,
              locals=None, expected_exc_type=None, expected_exc_message=None):
        _locals = locals or self._locals
        # adding the include_exceptions=True changes the type returned...
        res = safe_eval(code, locals=_locals)
        print('code: %s' % code)
        print('expected: %s' % expected)
        print('res: %s' % res)
        print('expected_type: %s' % expected_type)
        print('type: %s' % type(res))
        print('_locals: %s' % locals)
        self.assertEquals(res, expected)
        self.assertIsInstance(res, expected_type)
        return res

    def test_empty_string(self):
        self._eval('', '', str, self._locals)

    def test_quoted_string(self):
        code = '''"foo"'''
        self._eval(code, code, str, self._locals)

    def test_escaped_quoted_string(self):
        code = '''\"foo\"'''
        self._eval(code, code, str, self._locals)

    def test_double_escaped_quoted_string(self):
        code = '''\\"foo\\"'''
        self._eval(code, code, str, self._locals)

    def test_int_literal(self):
        self._eval('1', 1, int, self._locals)

    def test_float_literal(self):
        self._eval('37.1', 37.1, float, self._locals)

    def test_bool_true(self):
        self._eval('True', True, bool, self._locals)

    def test_bool_false(self):
        self._eval('False', False, bool, self._locals)

    def test_list_empty(self):
        self._eval('[]', [], list, self._locals)

    def test_dict_empty(self):
        self._eval('{}', {}, dict, self._locals)

    def test_dict_keyword_empty(self):
        self._eval('dict()', 'dict()', str, self._locals, Exception,
                   expected_exc_message='invalid function: dict')

    def test_dict_string(self):
        code = '''{"key_string": "value_string"}'''
        self._eval(code, {'key_string': 'value_string'}, dict, self._locals)

    def test_lambda(self):
        code = '''lambda a, b: a+b'''
        self._eval(code, code, str, self._locals, Exception,
                   expected_exc_message='invalid expression (lambda a, b: a+b)')

    def test_if(self):
        code = '''if True: pass'''
        self._eval(code, code, str, self._locals)

    def test_eval(self):
        code = '''eval()'''
        self._eval(code, code, str, self._locals, Exception,
                   expected_exc_message='invalid function: eval')

    def test_filter_asdfasdf(self):
        code = '''asdfasdf'''
        self._eval(code, code, str, self._locals, NameError,
                   expected_exc_message="name 'asdfasdf' is not defined")

    def test_non_string(self):
        code = ['whatever']
        self._eval(code, code, list, self._locals)

    def test_builtin_method_zip(self):
        code = '''zip()'''
        self._eval(code, code, str, self._locals, Exception,
                   expected_exc_message='invalid function: zip')

    def test_builtin_method_type(self):
        code = '''type(type)'''
        self._eval(code, code, str, self._locals, TypeError)

    def test_builtin_method_type_some_obj(self):
        code = '''type(some_obj)'''
        _locals = {'some_obj': set(['foo'])}
        self._eval(code, code, str, _locals, TypeError)

    def test_safe_eval_usage(self):
        # test safe eval calls with different possible types for the
        # locals dictionary, to ensure we don't run into problems like
        # ansible/ansible/issues/12206 again
        for locals_vars in (dict(), defaultdict(dict)):
            self.assertEqual(safe_eval('True', locals=locals_vars), True)
            self.assertEqual(safe_eval('False', locals=locals_vars), False)
            self.assertEqual(safe_eval('0', locals=locals_vars), 0)
            self.assertEqual(safe_eval('[]', locals=locals_vars), [])
            self.assertEqual(safe_eval('{}', locals=locals_vars), {})

    @unittest.skipUnless(sys.version_info[:2] >= (2, 7), "Python 2.6 has no set literals")
    def test_set_literals(self):
        self.assertEqual(safe_eval('{0}'), set([0]))


class TestSafeEvalIncludeExceptions(TestSafeEval):
    def _eval(self, code, expected, expected_type,
              locals=None, expected_exc_type=None, expected_exc_message=None):
        _locals = locals or self._locals

        # adding the include_exceptions=True changes the type returned...
        res, exc = safe_eval(code, locals=_locals, include_exceptions=True)

        #b = res()
        #print('b: %s' % b)
        print('code: %s' % code)
        print('expected: %s' % expected)
        print('res: %s' % res)
        print('expected_type: %s' % expected_type)
        print('type: %s' % type(res))
        print('expected_exc_type: %s' % expected_exc_type)
        print('exception: %s' % exc)
        print('exception_type: %s' % type(exc))
        print('expected_exc_message: %s' % expected_exc_message)
        if exc:
            print('exc.message: %s' % exc.message)
        print('_locals: %s' % locals)

        self.assertEquals(res, expected)
        self.assertIsInstance(res, expected_type)
        if expected_exc_type:
            self.assertIsInstance(exc, expected_exc_type)
        if expected_exc_message:
            self.assertEquals(exc.message, expected_exc_message)
        return res

    # TODO: add a test subclass for this case
    def test_non_string_inclue_exceptions(self):
        code = ['whatever']
        self._eval(code, code, list, self._locals)
