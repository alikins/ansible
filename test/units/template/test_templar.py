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

from jinja2.nodes import EvalContext
from jinja2 import Environment
from jinja2.runtime import Context

from ansible.compat.tests import unittest
from ansible.compat.tests.mock import patch

from ansible import constants as C
from ansible.errors import AnsibleError, AnsibleUndefinedVariable
from ansible.plugins.strategy import SharedPluginLoaderObj
from ansible.template import Templar, AnsibleEvalContext, AnsibleContext, AnsibleEnvironment
#from ansible.vars.unsafe_proxy import AnsibleUnsafe, wrap_var, is_unsafe
from ansible.unsafe_proxy import AnsibleUnsafe, wrap_var, is_unsafe
from units.mock.loader import DictDataLoader


TEST_VARS = dict(
    foo="bar",
    bam="{{foo}}",
    num=1,
    var_true=True,
    var_false=False,
    var_dict=dict(a="b"),
    bad_dict="{a='b'",
    var_list=[1],
    recursive="{{recursive}}",
    some_var="blip",
    some_static_var="static_blip",
    some_keyword="{{ foo }}",
    some_unsafe_var=wrap_var("unsafe_blip"),
    some_unsafe_keyword=wrap_var("{{ foo }}"),
)


class BaseTemplar(object):
    def setUp(self):
        self.test_vars = dict(
            foo="bar",
            bam="{{foo}}",
            num=1,
            var_true=True,
            var_false=False,
            var_dict=dict(a="b"),
            bad_dict="{a='b'",
            var_list=[1],
            recursive="{{recursive}}",
            some_var="blip",
            some_static_var="static_blip",
            some_keyword="{{ foo }}",
            some_unsafe_var=wrap_var("unsafe_blip"),
            some_unsafe_keyword=wrap_var("{{ foo }}"),
        )
        self.fake_loader = DictDataLoader({
            "/path/to/my_file.txt": "foo\n",
        })
        self.templar = Templar(loader=self.fake_loader, variables=self.test_vars)


class TestTemplarTemplate(BaseTemplar, unittest.TestCase):

#    def test_templar_template_static_dict(self):
#        res = self.templar.template("{{var_dict}}", static_vars=['blip'])
#        print(res)
        #self.assertEqual(templar.template("{{var_dict}}"), dict(a="b"))

#    def test_lookup_jinja_dict_key_in_static_vars(self):
#        res = self.templar.template({'some_static_var': '{{ some_var }}'},
#                                   static_vars=['some_static_var'])
#        res = self.templar.template({'some_other_static_var': '{{ some_var }}'},
#                                   static_vars=['different_static_vars', 'some_other_static_var'])
#        res = self.templar.template({'some_static_var': '{{ some_var }}'},
#                                   static_vars=['different_static_vars', 'some_other_static_var'])

    #def test_lookup_jinja_dict_key_in_static_vars(self):
    #    res = self.templar.template("{'some_static_var': '{{ some_var }}'}",
    #                               static_vars=['some_static_var'])
    #    #self.assertEquals(res['{{ a_keyword }}'], "blip")
    #    print(res)
    def test_templatable(self):
        res = self.templar.templatable('foo')
        self.assertTrue(res)

    def test_templatable_none(self):
        res = self.templar.templatable(None)
        self.assertTrue(res)

    @patch('ansible.template.Templar.template', side_effect=AnsibleError)
    def test_templatable_exception(self, mock_template):
        res = self.templar.templatable('foo')
        self.assertFalse(res)

    def test_template_convert_bare_string(self):
        # Note: no bare_deprecated=False so we hit the deprecation path
        res = self.templar.template('foo', convert_bare=True)
        self.assertEquals(res, 'bar')

    def test_template_convert_bare_nested(self):
        res = self.templar.template('bam', convert_bare=True, bare_deprecated=False)
        self.assertEquals(res, 'bar')

    def test_template_convert_bare_unsafe(self):
        res = self.templar.template('some_unsafe_var', convert_bare=True, bare_deprecated=False)
        self.assertEquals(res, 'unsafe_blip')
        self.assertIsInstance(res, AnsibleUnsafe)

    def test_template_convert_bare_filter(self):
        res = self.templar.template('bam|capitalize', convert_bare=True, bare_deprecated=False)
        self.assertEquals(res, 'Bar')

    def test_template_convert_bare_filter_unsafe(self):
        res = self.templar.template('some_unsafe_var|capitalize', convert_bare=True, bare_deprecated=False)
        self.assertEquals(res, 'Unsafe_blip')
        self.assertIsInstance(res, AnsibleUnsafe)

    @patch('ansible.template.Templar._clean_data', side_effect=AnsibleError)
    def test_template_unsafe_clean_data_exception(self, mock_clean_data):
        self.assertRaises(AnsibleError,
                          self.templar.template,
                          wrap_var('blip bar'))

    # TODO: not sure what template is supposed to do it, but it currently throws attributeError
    @patch('ansible.template.Templar._clean_data', side_effect=AnsibleError)
    def test_template_unsafe_non_string_clean_data_exception(self, mock_clean_data):
        unsafe_obj = AnsibleUnsafe()
        self.templar.template(unsafe_obj)


class TestTemplarCleanData(BaseTemplar, unittest.TestCase):
    def test_clean_data(self):
        res = self.templar._clean_data(u'some string')
        self.assertEquals(res, u'some string')

    def test_clean_data_not_stringtype(self):
        res = self.templar._clean_data(None)
        # None vs NoneType
        self.assertEquals(res, None)

    def test_clean_data_jinja(self):
        res = self.templar._clean_data(u'1 2 {what} 3 4 {{foo}} 5 6 7')
        self.assertEquals(res, u'1 2 {what} 3 4 {#foo#} 5 6 7')

    def test_clean_data_block(self):
        res = self.templar._clean_data(u'1 2 {%what%} 3 4 {{foo}} 5 6 7')
        self.assertEquals(res, u'1 2 {#what#} 3 4 {#foo#} 5 6 7')

#    def test_clean_data_weird(self):
#        res = self.templar._clean_data(u'1 2 #}huh{# %}ddfg{% }}dfdfg{{  {%what%} {{#foo#}} {%{bar}%} {#%blip%#} {{asdfsd%} 3 4 {{foo}} 5 6 7')
#        print(res)

        self.assertEquals(res, u'1 2 {#what#} 3 4 {#foo#} 5 6 7')

    def test_clean_data_object(self):
        obj = {'foo': [1, 2, 3, 'bdasdf', '{what}', '{{foo}}', 5]}
        res = self.templar._clean_data(obj)
        self.assertEquals(res, obj)

    def test_clean_data_object_unsafe(self):
        rval = [1, 2, 3, wrap_var('bdasdf'), '{what}', wrap_var('{{unsafe_foo}}'), 5]
        obj = {'foo': rval}
        res = self.templar._clean_data(obj)
        self.assertEquals(res, obj)
        print(obj)
        import pprint
        pprint.pprint(obj['foo'])
        pprint.pprint(dir(obj['foo']))
        print('res is_unsafe(%s)=%s' % (res, is_unsafe(res)))
        print('obj is_unsafe(%s)=%s' % (obj, is_unsafe(obj)))
        print('res["foo"] is_unsafe(%s)=%s' % (res['foo'], is_unsafe(res['foo'])))
        print('res["foo"][3] is_unsafe(%s)=%s' % (res['foo'][3], is_unsafe(res['foo'][3])))
        self.assertTrue(hasattr(obj['foo'], '__UNSAFE__'))
        self.assertTrue(hasattr(res['foo'], '__UNSAFE__'))

    def test_clean_data_bad_dict(self):
        res = self.templar._clean_data(u'{{bad_dict}}')
        self.assertEquals(res, u'{#bad_dict#}')

class TestTemplarMisc(BaseTemplar, unittest.TestCase):
    def test_templar_simple(self):

        templar = self.templar
        # test some basic templating
        self.assertEqual(templar.template("{{foo}}"), "bar")
        self.assertEqual(templar.template("{{foo}}\n"), "bar\n")
        self.assertEqual(templar.template("{{foo}}\n", preserve_trailing_newlines=True), "bar\n")
        self.assertEqual(templar.template("{{foo}}\n", preserve_trailing_newlines=False), "bar")
        self.assertEqual(templar.template("{{bam}}"), "bar")
        self.assertEqual(templar.template("{{num}}"), 1)
        self.assertEqual(templar.template("{{var_true}}"), True)
        self.assertEqual(templar.template("{{var_false}}"), False)
        self.assertEqual(templar.template("{{var_dict}}"), dict(a="b"))
        self.assertEqual(templar.template("{{bad_dict}}"), "{a='b'")
        self.assertEqual(templar.template("{{var_list}}"), [1])
        self.assertEqual(templar.template(1, convert_bare=True), 1)

        # force errors
        self.assertRaises(AnsibleUndefinedVariable, templar.template, "{{bad_var}}")
        self.assertRaises(AnsibleUndefinedVariable, templar.template, "{{lookup('file', bad_var)}}")
        self.assertRaises(AnsibleError, templar.template, "{{lookup('bad_lookup')}}")
        self.assertRaises(AnsibleError, templar.template, "{{recursive}}")
        self.assertRaises(AnsibleUndefinedVariable, templar.template, "{{foo-bar}}")

        # test with fail_on_undefined=False
        self.assertEqual(templar.template("{{bad_var}}", fail_on_undefined=False), "{{bad_var}}")

        # test set_available_variables()
        templar.set_available_variables(variables=dict(foo="bam"))
        self.assertEqual(templar.template("{{foo}}"), "bam")
        # variables must be a dict() for set_available_variables()
        self.assertRaises(AssertionError, templar.set_available_variables, "foo=bam")

    def test_templar_escape_backslashes(self):
        # Rule of thumb: If escape backslashes is True you should end up with
        # the same number of backslashes as when you started.
        self.assertEqual(self.templar.template("\t{{foo}}", escape_backslashes=True), "\tbar")
        self.assertEqual(self.templar.template("\t{{foo}}", escape_backslashes=False), "\tbar")
        self.assertEqual(self.templar.template("\\{{foo}}", escape_backslashes=True), "\\bar")
        self.assertEqual(self.templar.template("\\{{foo}}", escape_backslashes=False), "\\bar")
        self.assertEqual(self.templar.template("\\{{foo + '\t' }}", escape_backslashes=True), "\\bar\t")
        self.assertEqual(self.templar.template("\\{{foo + '\t' }}", escape_backslashes=False), "\\bar\t")
        self.assertEqual(self.templar.template("\\{{foo + '\\t' }}", escape_backslashes=True), "\\bar\\t")
        self.assertEqual(self.templar.template("\\{{foo + '\\t' }}", escape_backslashes=False), "\\bar\t")
        self.assertEqual(self.templar.template("\\{{foo + '\\\\t' }}", escape_backslashes=True), "\\bar\\\\t")
        self.assertEqual(self.templar.template("\\{{foo + '\\\\t' }}", escape_backslashes=False), "\\bar\\t")

    def test_template_jinja2_extensions(self):
        fake_loader = DictDataLoader({})
        templar = Templar(loader=fake_loader)

        old_exts = C.DEFAULT_JINJA2_EXTENSIONS
        try:
            C.DEFAULT_JINJA2_EXTENSIONS = "foo,bar"
            self.assertEqual(templar._get_extensions(), ['foo', 'bar'])
        finally:
            C.DEFAULT_JINJA2_EXTENSIONS = old_exts


class TestTemplarLookup(BaseTemplar, unittest.TestCase):
    def test_lookup_missing_plugin(self):
        self.assertRaisesRegexp(AnsibleError,
                                'lookup plugin \(not_a_real_lookup_plugin\) not found',
                                self.templar._lookup,
                                'not_a_real_lookup_plugin',
                                'an_arg', a_keyword_arg='a_keyword_arg_value')

    def test_lookup_list(self):
        res = self.templar._lookup('list', 'an_arg', 'another_arg')
        self.assertEquals(res, 'an_arg,another_arg')

    def test_lookup_jinja_undefined(self):
        self.assertRaisesRegexp(AnsibleUndefinedVariable,
                                "'an_undefined_jinja_var' is undefined",
                                self.templar._lookup,
                                'list', '{{ an_undefined_jinja_var }}')

    def test_lookup_jinja_defined(self):
        res = self.templar._lookup('list', '{{ some_var }}')
        self.assertIsInstance(res, AnsibleUnsafe)

    def test_lookup_jinja_dict_string_passed(self):
        self.assertRaisesRegexp(AnsibleError,
                                "with_dict expects a dict",
                                self.templar._lookup,
                                'dict',
                                '{{ some_var }}')

    def test_lookup_jinja_dict_list_passed(self):
        self.assertRaisesRegexp(AnsibleError,
                                "with_dict expects a dict",
                                self.templar._lookup,
                                'dict',
                                ['foo', 'bar'])

    def test_lookup_jinja_kwargs(self):
        res = self.templar._lookup('list', 'blip', random_keyword='12345')
        self.assertIsInstance(res, AnsibleUnsafe)

    def test_lookup_jinja_list_wantlist(self):
        res = self.templar._lookup('list', '{{ some_var }}', wantlist=True)
        self.assertEquals(res, ["blip"])

    def test_lookup_jinja_list_wantlist_undefined(self):
        self.assertRaisesRegexp(AnsibleUndefinedVariable,
                                "'some_undefined_var' is undefined",
                                self.templar._lookup,
                                'list',
                                '{{ some_undefined_var }}',
                                wantlist=True)

    def test_lookup_jinja_list_wantlist_unsafe(self):
        res = self.templar._lookup('list', '{{ some_unsafe_var }}', wantlist=True)
        for lookup_result in res:
            self.assertIsInstance(lookup_result, AnsibleUnsafe)

        # Should this be an AnsibleUnsafe
        # self.assertIsInstance(res, AnsibleUnsafe)

    def test_lookup_jinja_dict(self):
        res = self.templar._lookup('list', {'{{ a_keyword }}': '{{ some_var }}'})
        self.assertEquals(res['{{ a_keyword }}'], "blip")
        # TODO: Should this be an AnsibleUnsafe
        #self.assertIsInstance(res['{{ a_keyword }}'], AnsibleUnsafe)
        #self.assertIsInstance(res, AnsibleUnsafe)

    def test_lookup_jinja_dict_unsafe(self):
        res = self.templar._lookup('list', {'{{ some_unsafe_key }}': '{{ some_unsafe_var }}'})
        self.assertIsInstance(res['{{ some_unsafe_key }}'], AnsibleUnsafe)
        # TODO: Should this be an AnsibleUnsafe
        #self.assertIsInstance(res, AnsibleUnsafe)

    def test_lookup_jinja_dict_unsafe_value(self):
        res = self.templar._lookup('list', {'{{ a_keyword }}': '{{ some_unsafe_var }}'})
        self.assertIsInstance(res['{{ a_keyword }}'], AnsibleUnsafe)
        # TODO: Should this be an AnsibleUnsafe
        #self.assertIsInstance(res, AnsibleUnsafe)

    def test_lookup_jinja_none(self):
        res = self.templar._lookup('list', None)
        self.assertIsNone(res)


class TestTemplarLookupTemplate(BaseTemplar, unittest.TestCase):
    def test_unknown_lookup(self):
        self.assertRaisesRegexp(AnsibleError,
                                'lookup plugin \(sdfsdf\) not found',
                                self.templar.template,
                                u"{{ lookup('sdfsdf','sdfsdf') }}")

#    def test_file(self):
#        res = self.templar.template(u"{{ lookup('file', '/tmp/lookup_test') }}")
#        print(res)

    def test_env(self):
        res = self.templar.template(u"{{ lookup('env', 'TEST_VAR') }}")
        print(res)

    def test_nested_env(self):
        res = self.templar.template(u"{{ lookup('env', lookup('env', 'TEST_VAR_VAR')) }}")
        print(res)

#    def test_lines(self):
#        res = self.templar.template(u"{{ lookup('lines', '/tmp/lookup_test') }}")
#        print(res)

    def test_fileglob(self):
        res = self.templar.template(u"{{ lookup('fileglob', '/usr/share/man/man4/*') }}")
        print(res)


class TestAnsibleContext(unittest.TestCase):
    def _context(self, variables=None):
        variables = variables or {}

        env = AnsibleEnvironment()
        context = AnsibleContext(env, parent={}, name='some_context',
                                 blocks={})

        for key, value in variables.items():
            context.vars[key] = value

        return context

    def test(self):
        context = self._context()
        self.assertIsInstance(context, AnsibleContext)
        self.assertIsInstance(context, Context)

    def test_resolve_unsafe(self):
        context = self._context(variables={'some_unsafe_key': wrap_var('some_unsafe_string')})
        res = context.resolve('some_unsafe_key')
        self.assertIsInstance(res, AnsibleUnsafe)

    def test_resolve_unsafe_list(self):
        context = self._context(variables={'some_unsafe_key': [wrap_var('some unsafe string 1')]})
        res = context.resolve('some_unsafe_key')
        self.assertIsInstance(res[0], AnsibleUnsafe)

    def test_resolve_unsafe_dict(self):
        context = self._context(variables={'some_unsafe_key':
                                           {'an_unsafe_dict': wrap_var('some unsafe string 1')}
                                           })
        res = context.resolve('some_unsafe_key')
        self.assertIsInstance(res['an_unsafe_dict'], AnsibleUnsafe)

    def test_resolve(self):
        context = self._context(variables={'some_key': 'some_string'})
        res = context.resolve('some_key')
        self.assertEquals(res, 'some_string')
        self.assertNotIsInstance(res, AnsibleUnsafe)

    def test_resolve_none(self):
        context = self._context(variables={'some_key': None})
        res = context.resolve('some_key')
        self.assertEquals(res, None)
        self.assertNotIsInstance(res, AnsibleUnsafe)
