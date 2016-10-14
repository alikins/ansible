
import jinja2
from jinja2 import Markup, Environment
from jinja2._compat import text_type, implements_to_string

from ansible.compat.tests import unittest
from ansible.compat.tests.mock import patch, MagicMock
from units.mock.loader import DictDataLoader

from ansible import template
from ansible.plugins.filter import ipaddr


class TestIpaddr(unittest.TestCase):


    def test_ipaddr(self):
        a = ipaddr.ipaddr('addr', query='192.168.0.0/24')
        print(a)
        a = ipaddr.ipaddr('host', query='192.168.0.0')
        print(a)

    def test_ipv4(self):
        ipv4 = ipaddr.ipv4('127.0.0.1')
        print(ipv4)

    def test_ipv6(self):
        ipv6 = ipaddr.ipv6('::1/128')
        print(ipv6)

    def test_ipsubnet(self):
        ipsubnet = ipaddr.ipsubnet('192.168.0.0/24')
        print(ipsubnet)

        # FIXME: whatever a ipsubnet index is
        ipsubnet2 = ipaddr.ipsubnet('192.168.0.0/24', 4)
        print(ipsubnet2)

    def test_nthhost(self):
        a = ipaddr.ipaddr('addr', query='192.168.0.0/24')
        b = ipaddr.nthhost(a, 11)
        print(a)
        print(b)

    def test_filter(self):
        fake_loader = DictDataLoader({
            "/path/to/my_file.txt": "foo\n",
        })
        variables = {'addr': '192.168.1.37',
                     'notaddr': 'chicane',
                     'some_subnet': '192.168.0.0/24'}
        templar = template.Templar(loader=fake_loader, variables=variables)
        tmpl = templar.template("{{ addr | ipaddr('net')}}")
        self.assertNotEqual(tmpl, False)

        tmpl = templar.template("{{ addr | ipaddr('ipv4')}}")
        self.assertNotEqual(tmpl, False)

        tmpl = templar.template("{{ addr | ipaddr('ipv6')}}")
        print(tmpl)

        tmpl = templar.template("{{ notaddr | ipaddr('ipv6')}}")
        print(tmpl)
        self.assertFalse(tmpl)

        tmpl = templar.template("{{ notaddr | ipaddr }}")
        self.assertFalse(tmpl)

        tmpl = templar.template("{{ notaddr | ipaddr('ipv4')}}")
        self.assertFalse(tmpl)

        tmpl = templar.template("{{ addr | ipaddr('address')}}")
        print(tmpl)
        self.assertNotEqual(tmpl, False)


