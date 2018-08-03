# Copyright: (c) 2018, Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import logging
import os
import pprint
import sys

from ansible import constants as C
from ansible.cli import CLI
from ansible.errors import AnsibleOptionsError, AnsibleError
from ansible.module_utils._text import to_text
from ansible.playbook import Playbook
from ansible.playbook.play import Play
from ansible.playbook.block import Block
from ansible.playbook.task import Task
from ansible.plugins.loader import get_all_plugin_loaders
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.parsing.splitter import parse_kv

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()

log = logging.getLogger(__name__)


def _play_ds(pattern, role_name, role_args_string, survey_spec, survey_answers, async_val, poll):
    # check_raw = module_name in ('command', 'win_command', 'shell', 'win_shell', 'script', 'raw')
    # role_args['name'] = role_name
    log.debug('role_name: %s', role_name)
    log.debug('role_args_string: %s', role_args_string)

    role_args = parse_kv(role_args_string, check_raw=False)
    log.debug('role_args: %s', role_args)

    log.debug('survey_spec: %s', survey_spec)
    log.debug('survey_answers: %s', survey_answers)
    module_args = {}
    _vars = {}

    #if role_name:
    #    module_args['name'] = role_name
    module_args['vars'] = role_args
    module_args.update(role_args)

    log.debug('role_args (with name): %s', role_args)

    log.debug('module_args: %s', module_args)

    log.debug('_vars: %s', _vars)

    _vars = role_args

    return {'name': "Ansible Role",
            'hosts': pattern,
            'gather_facts': 'no',
            'tasks': [
                {'action': {'module': 'validate_survey_spec',
                            'survey_spec': survey_spec,
                            'survey_answers': survey_answers},
                 # 'vars': {'survey_spec': []},
                 'async_val': async_val,
                 'poll': poll},
                {'action': {'module': 'include_role',
                            'name': role_name,
                            },
                 'vars': role_args,
                 'async_val': async_val,
                 'poll': poll}
            ]
            }


class RoleCLI(CLI):
    def parse(self):
        ''' create an options parser for bin/ansible '''

        self.parser = CLI.base_parser(
            usage="usage: %%prog [%s] [--help] [options] ..." % "|".join(self.VALID_ACTIONS),
            runas_opts=True,
            inventory_opts=True,
            async_opts=True,
            output_opts=True,
            connect_opts=True,
            check_opts=True,
            runtask_opts=True,
            vault_opts=True,
            fork_opts=True,
            module_opts=True,
            basedir_opts=True,
            epilog="\nSee '%s <command> --help' for more information on a specific command.\n\n" % os.path.basename(sys.argv[0]),
            desc="Perform various Role related operations.",
        )

        # common
        self.parser.add_option('-F', '--foobar', dest='foobar', default=None, help='Just a placeholder option. Used to bar the foo and foo the bar')
        self.parser.add_option('-a', '--args', dest='role_args_string',
                               help="role arguments", default=C.DEFAULT_ROLE_ARGS)
        self.parser.add_option('-r', '--role', dest='role_name',
                               help="role name to execute",
                               default=None)

        super(RoleCLI, self).parse()

        if not self.options.role_name:
            raise AnsibleOptionsError("-r/--role requires a role name")

        self.validate_conflicts(runas_opts=True, vault_opts=True, fork_opts=True)

    def run(self):
        super(RoleCLI, self).run()

        if self.options.foobar:
            display.display('%s%s%s' % ('foo', self.options.foobar, 'bar'))

        # only thing left should be host pattern
        pattern = to_text(self.args[0], errors='surrogate_or_strict')

        sshpass = None
        becomepass = None

        self.normalize_become_options()
        (sshpass, becomepass) = self.ask_passwords()
        passwords = {'conn_pass': sshpass, 'become_pass': becomepass}

        # dynamically load any plugins
        get_all_plugin_loaders()

        loader, inventory, variable_manager = self._play_prereqs(self.options)

        survey_spec = loader.load_from_file('survey_spec.yml')
        survey_answers = loader.load_from_file('survey_answers.yml')

        play_ds = _play_ds(pattern, self.options.role_name, self.options.role_args_string,
                           survey_spec, survey_answers, self.options.seconds, self.options.poll_interval)

        log.debug('play_ds: %s', pprint.pformat(play_ds))
        play = Play().load(play_ds, variable_manager=variable_manager, loader=loader)

        # task = Task()
        # log.debug('task: %s', task)
        log.debug('play.tasks: %s', play.tasks)

        # block = Block.load(
        # log.debug('block: %s', block)

        # play.tasks.append(task)
        log.debug('play.tasks: %s', play.tasks)

        # used in start callback
        playbook = Playbook(loader)
        playbook._entries.append(play)
        playbook._file_name = '__role_playbook__'

        cb = self.callback or C.DEFAULT_STDOUT_CALLBACK or 'minimal'

        # now create a task queue manager to execute the play
        self._tqm = None
        try:
            self._tqm = TaskQueueManager(
                inventory=inventory,
                variable_manager=variable_manager,
                loader=loader,
                options=self.options,
                passwords=passwords,
                stdout_callback=cb,
                run_additional_callbacks=C.DEFAULT_LOAD_CALLBACK_PLUGINS,
            )

            self._tqm.send_callback('v2_playbook_on_start', playbook)

            result = self._tqm.run(play)

            self._tqm.send_callback('v2_playbook_on_stats', self._tqm._stats)
        finally:
            if self._tqm:
                self._tqm.cleanup()
            if loader:
                loader.cleanup_all_tmp_files()

        return result
        # return os.EX_OK
