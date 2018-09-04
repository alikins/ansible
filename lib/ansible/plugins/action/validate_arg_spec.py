# Copyright 2018 Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import logging
import pprint

from ansible.errors import AnsibleError, AnsibleModuleError
from ansible.plugins.action import ActionBase
from ansible.module_utils import basic
from ansible.module_utils.six import iteritems, string_types

log = logging.getLogger(__name__)
pf = pprint.pformat


class AnsibleArgSpecError(AnsibleModuleError):
    def __init__(self, *args, **kwargs):
        self.argument_errors = kwargs.pop('argument_errors', [])
        super(AnsibleArgSpecError, self).__init__(*args, **kwargs)


class ArgSpecValidatingAnsibleModule(basic.AnsibleModule):
    '''AnsibleModule but with overridden _load_params so it doesnt read from stdin/ANSIBLE_ARGS'''
    def __init__(self, *args, **kwargs):
        self.params = kwargs.pop('params', {})
        self.arg_validation_errors = []
        super(ArgSpecValidatingAnsibleModule, self).__init__(*args, **kwargs)

    def _load_params(self):
        pass

    def fail_json(self, *args, **kwargs):
        msg = kwargs.pop('msg', 'Unknown arg spec validation error')
        log.debug('Arg spec validation caused fail_json() to be called')
        log.error('Arg spec validation error: %s', msg)
        self.arg_validation_errors.append(msg)

    def check_for_errors(self):
        if self.arg_validation_errors:
            raise AnsibleArgSpecError(argument_errors=self.arg_validation_errors)


class ActionModule(ActionBase):
    ''' Validate a Role survey spec and answers to it's questions '''

    TRANSFERS_FILES = False

    # WARNING: modifies argument_spec
    def build_args(self, argument_spec, task_vars):
        log.debug('argument_spec: %s', pf(argument_spec))
        log.debug('task_vars: %s', pf(task_vars))

        args = {}
        for key, attrs in iteritems(argument_spec):
            if attrs is None:
                argument_spec[key] = {'type': 'str'}
            if key in task_vars:
                if isinstance(task_vars[key], string_types):
                    value = self._templar.do_template(task_vars[key])
                    if value:
                        args[key] = value
                else:
                    args[key] = task_vars[key]
            elif attrs:
                if 'aliases' in attrs:
                    for item in attrs['aliases']:
                        if item in task_vars:
                            args[key] = self._templar.do_template(task_vars[key])
                elif 'default' in attrs and key not in args:
                    args[key] = attrs['default']
        return args

    def run(self, tmp=None, task_vars=None):
        '''
        Validate a survey spec

        :arg tmp: Deprecated. Do not use.
        :arg dict task_vars: A dict of task variables.
            Valid args include 'argument_spec', 'supplied_arguments'
        :return: An action result dict, including a 'argument_errors' key with a
            list of validation errors found.
        '''
        if task_vars is None:
            task_vars = dict()

        result = super(ActionModule, self).run(tmp, task_vars)
        del tmp  # tmp no longer has any effect

        log.debug('self._task.args: %s', pprint.pformat(self._task.args))
        if 'argument_spec' not in self._task.args:
            raise AnsibleError('"argument_spec" arg is required in args: %s' % self._task.args)

        log.debug('argument_spec: %s', pf(self._task.args['argument_spec']))

        # get the task var called argument_spec
        argument_spec_data = self._task.args.get('argument_spec')

        # then get the 'argument_spec' item from the dict in the argument_spec task var
        argument_spec = argument_spec_data.get('argument_spec', [])

        provided_arguments = self._task.args.get('provided_arguments', {})

        if not isinstance(argument_spec_data, dict):
            raise AnsibleError('Incorrect type for argument_spec, expected dict and got %s' % type(argument_spec_data))

        if not isinstance(provided_arguments, dict):
            raise AnsibleError('Incorrect type for survey_data, expected dict and got %s' % type(provided_arguments))

        module_params = provided_arguments

        # TODO: sep handling None/default values from build_args
        # TODO: drop build_args
        self.build_args(argument_spec, task_vars)

#         log.debug('built_args: %s', pf(built_args))

        module_args = {}
        module_args['argument_spec'] = argument_spec
        module_args['params'] = module_params

        log.debug('module_args: %s', pf(module_args))

        try:
            validating_module = ArgSpecValidatingAnsibleModule(**module_args)
            log.debug('validating_module: %s', validating_module)
            validating_module.check_for_errors()
        except AnsibleArgSpecError as e:
            log.exception(e)
            # log.exception(sys.exc_info)
            log.error('role arg spec validation failed')
            for error in e.argument_errors:
                log.error('role arg validation error: %s', error)

            # log.exception(e)
            result['_ansible_verbose_always'] = True
            result['failed'] = True
            result['msg'] = e.message

            # does this need to check no_log?
            result['argument_errors'] = e.argument_errors

            return result

        result['_ansible_verbose_always'] = True

        result['changed'] = False
        result['msg'] = 'The survey validation passed'
        result['valid_provided_arguments'] = provided_arguments

        return result
