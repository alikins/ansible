
from ansible.compat.tests import unittest
from ansible.compat.tests.mock import patch, MagicMock
from units.mock.loader import DictDataLoader
from units.mock.path import mock_unfrackpath_noop

from ansible.plugins.strategy import SharedPluginLoaderObj
from ansible.playbook import conditional
from ansible.template import Templar


class TestConditional(unittest.TestCase):
    def setUp(self):
        self.loader = DictDataLoader({})
        self.cond = conditional.Conditional(loader=self.loader)
        self.shared_loader = SharedPluginLoaderObj()
        self.templar = Templar(loader=self.loader, variables={})

    def test(self):
        print(self.cond)

    def test_false(self):
        exp = u"False"
        self.cond.when = [exp]
        ret = self.cond.evaluate_conditional(self.templar, {})
        self.assertFalse(ret)

    def test_true(self):
        exp = u"True"
        self.cond.when = [exp]
        ret = self.cond.evaluate_conditional(self.templar, {})
        self.assertTrue(ret)

    def test_undefined(self):
        exp = u"{{ some_undefined_thing }}"
        self.cond.when = [exp]
        try:
            ret = self.cond.evaluate_conditional(self.templar, {})
        except Exception as e:
            print(e.__class__.__name__)
            print(dir(e))
            raise
        print(ret)
        self.assertFalse(ret)

    def test_defined(self):
        exp = u"{{ some_defined_thing }}"
        variables = {'some_defined_thing': True}
        self.cond.when = [exp]
        ret = self.cond.evaluate_conditional(self.templar, variables)
        print('defined ret=%s' % ret)
        self.assertTrue(ret)

    def test_dict_defined_values(self):
        exp = u"{{ some_defined_dict }}"
        variables = {'dict_value': 1,
                     'some_defined_dict': {'key1': 'value1',
                                           'key2': '{{ dict_value }}'}}

        self.cond.when = [exp]
        ret = self.cond.evaluate_conditional(self.templar, variables)
        print('dict_defined ret=%s' % ret)
        self.assertTrue(ret)

    def test_dict_defined_values_is_defined(self):
        exp = u"{{ some_defined_dict['key1'] is defined }}"
        variables = {'dict_value': 1,
                     'some_defined_dict': {'key1': 'value1',
                                           'key2': '{{ dict_value }}'}}

        self.cond.when = [exp]
        ret = self.cond.evaluate_conditional(self.templar, variables)
        print('dict_defined ret=%s' % ret)
        self.assertTrue(ret)

    def test_dict_defined_multiple_values_is_defined(self):
        variables = {'dict_value': 1,
                     'some_defined_dict': {'key1': 'value1',
                                           'key2': '{{ dict_value }}'}}

        self.cond.when = [u"{{ some_defined_dict['key1'] is defined }}",
                          u"{{ some_defined_dict['key2'] is defined }}"]
        ret = self.cond.evaluate_conditional(self.templar, variables)
        print('dict_defined ret=%s' % ret)
        self.assertTrue(ret)

    def test_dict_undefined_values(self):
        exp = u"{{ some_defined_dict_with_undefined_values }}"
        variables = {'dict_value': 1,
                     'some_defined_dict_with_undefined_values': {'key1': 'value1',
                                                                 'key2': '{{ dict_value }}',
                                                                 'key3': '{{ undefined_dict_value }}'
                                                                 }}

        self.cond.when = [exp]
        ret = self.cond.evaluate_conditional(self.templar, variables)
        print('dict_define_with_undefined_values ret=%s' % ret)
        # FIXME/TODO: Is this correct? should this be false
        self.assertFalse(ret)

    def test_is_defined(self):
        exp = u"{{ some_defined_thing is defined}}"
        variables = {'some_defined_thing': True}
        self.cond.when = [exp]
        ret = self.cond.evaluate_conditional(self.templar, variables)
        print('defined ret=%s' % ret)
        self.assertTrue(ret)

    def test_is_undefined(self):
        exp = u"{{ some_defined_thing is undefined}}"
        variables = {'some_defined_thing': True}
        self.cond.when = [exp]
        ret = self.cond.evaluate_conditional(self.templar, variables)
        print('defined ret=%s' % ret)
        self.assertFalse(ret)

    def test_is_undefined_and_defined(self):
        variables = {'some_defined_thing': True}
        self.cond.when = [u"{{ some_defined_thing is undefined}}", u"{{ some_defined_thing is defined }}"]
        ret = self.cond.evaluate_conditional(self.templar, variables)
        print('defined ret=%s' % ret)
        self.assertFalse(ret)

    def test_is_undefined_and_defined_reversed(self):
        variables = {'some_defined_thing': True}
        self.cond.when = [u"{{ some_defined_thing is defined}}", u"{{ some_defined_thing is undefined }}"]
        ret = self.cond.evaluate_conditional(self.templar, variables)
        print('defined ret=%s' % ret)
        self.assertFalse(ret)

    def test_is_not_undefined(self):
        variables = {'some_defined_thing': True}
        self.cond.when = [u"{{ some_defined_thing is not undefined}}"]
        ret = self.cond.evaluate_conditional(self.templar, variables)
        print('defined ret=%s' % ret)
        self.assertFalse(ret)

    def test_is_not_defined(self):
        variables = {'some_defined_thing': True}
        self.cond.when = [u"{{ some_undefined_thing is not defined}}"]
        ret = self.cond.evaluate_conditional(self.templar, variables)
        print('defined ret=%s' % ret)
        self.assertTrue(ret)

