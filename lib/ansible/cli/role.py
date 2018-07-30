# Copyright: (c) 2018, Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os
import sys

from ansible.cli import CLI
# from ansible.playbook import Playbook
# from ansible.playbook.play import Play
# from ansible.plugins.loader import get_all_plugin_loaders

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class RoleCLI(CLI):
    def parse(self):
        ''' create an options parser for bin/ansible '''

        self.parser = CLI.base_parser(
            usage="usage: %%prog [%s] [--help] [options] ..." % "|".join(self.VALID_ACTIONS),
            epilog="\nSee '%s <command> --help' for more information on a specific command.\n\n" % os.path.basename(sys.argv[0]),
            desc="Perform various Role related operations.",
        )

        # common
        self.parser.add_option('-F', '--foobar', dest='foobar', default=None, help='Just a placeholder option. Used to bar the foo and foo the bar')

        super(RoleCLI, self).parse()

    def run(self):
        super(RoleCLI, self).run()

        if self.options.foobar:
            display.display('%s%s%s' % ('foo', self.options.foobar, 'bar'))

        return os.EX_OK
