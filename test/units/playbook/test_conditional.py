
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
        #self.templar = Templar(loader=fake_loader, variables=variables)

    def test(self):
        print(self.cond)

    def test_false(self):
        exp = u"False"
        templar = Templar(loader=self.loader, variables={})
        self.cond.when = [exp]
        ret = self.cond.evaluate_conditional(templar, {})
        self.assertFalse(ret)

    def test_true(self):
        exp = u"True"
        templar = Templar(loader=self.loader, variables={})
        self.cond.when = [exp]
        ret = self.cond.evaluate_conditional(templar, {})
        self.assertTrue(ret)

    def test_undefined(self):
        exp = u"{{ some_undefined_thing }}"
        templar = Templar(loader=self.loader, variables={})
        self.cond.when = [exp]
        try:
            ret = self.cond.evaluate_conditional(templar, {})
        except Exception as e:
            print(e.__class__.__name__)
            print(dir(e))
            raise
        print(ret)

    def test_defined(self):
        exp = u"{{ some_defined_thing }}"
        variables = {'some_defined_thing': 'foobar'}
        templar = Templar(loader=self.loader, variables=variables)
        self.cond.when = [exp]
        ret = self.cond.evaluate_conditional(templar, variables)
        print(ret)
