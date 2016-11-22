
import jinja2
from jinja2 import Markup, Environment
from jinja2._compat import text_type, implements_to_string

from ansible.compat.tests import unittest
from ansible.compat.tests.mock import patch, MagicMock
from units.mock.loader import DictDataLoader

from ansible import template
from ansible.plugins.filter import ipaddr


class TestIpaddr(unittest.TestCase):
    def test_ipv4(self):
        ipv4 = ipaddr.ipv4('127.0.0.1')
        self.assertEquals(ipv4, '127.0.0.1')

    def test_ipv6(self):
        ipv6 = ipaddr.ipv6('::1/128')
        self.assertTrue(ipv6)

    def test_ipsubnet(self):
        ipsubnet = ipaddr.ipsubnet('192.168.0.0/24')
        self.assertTrue(ipsubnet)

        # FIXME: whatever a ipsubnet index is
        ipsubnet2 = ipaddr.ipsubnet('192.168.0.0/24', 4)
        self.assertTrue(ipsubnet2)

    def test_nthhost(self):
        a = ipaddr.ipaddr('addr', query='192.168.0.0/24')
        ipaddr.nthhost(a, 11)


class TestIpaddrTemplate(unittest.TestCase):
    def setUp(self):
        self.fake_loader = DictDataLoader({
            "/path/to/my_file.txt": "foo\n",
        })
        self.variables = {'addr': '192.168.1.37',
                          'notaddr': 'chicane',
                          'some_subnet': '192.168.0.0/24'}
        self.templar = template.Templar(loader=self.fake_loader, variables=self.variables)

    def template(self, *args, **kwargs):
        tmpl = self.templar.template(args, kwargs)
        print('args=%s kwargs=%s tmpl=%s' % (repr(args), repr(kwargs), tmpl))
        return tmpl

    def test_net(self):
        tmpl = self.template("{{ addr | ipaddr('net')}}")
        self.assertNotEqual(tmpl[0], False)

    def test_ipaddr_ipv4(self):
        tmpl = self.template("{{ addr | ipaddr('ipv4')}}")
        self.assertNotEqual(tmpl[0], False)

    def test_ipaddr_ipv6(self):
        tmpl = self.template("{{ addr | ipaddr('ipv6')}}")
        self.assertTrue(tmpl[0])

    def test_ipaddr_ipv6_notaddr(self):
        tmpl = self.template("{{ notaddr | ipaddr('ipv6')}}")
        self.assertFalse(tmpl[0])

    def test_ipaddr_notaddr(self):
        tmpl = self.template("{{ notaddr | ipaddr }}")
        self.assertFalse(tmpl[0])

    def test_ipaddr_ipv4_notaddr(self):
        tmpl = self.template("{{ notaddr | ipaddr('ipv4')}}")
        self.assertFalse(tmpl[0])

    def test_ipaddr_address(self):
        tmpl = self.template("{{ addr | ipaddr('address')}}")
        self.assertNotEqual(tmpl[0], False)
