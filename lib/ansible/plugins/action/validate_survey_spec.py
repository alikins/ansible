# Copyright 2018 Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import logging
import pprint

from ansible.errors import AnsibleError
from ansible.plugins.action import ActionBase
from ansible.playbook.role import survey

log = logging.getLogger(__name__)
pf = pprint.pformat


class ActionModule(ActionBase):
    ''' Validate a Role survey spec and answers to it's questions '''

    TRANSFERS_FILES = False

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

        if 'argument_spec' not in self._task.args:
            raise AnsibleError('"argument_spec" arg is required in args')

        argument_spec = self._task.args.get('argument_spec')
        log.debug('argument_spec: %s', argument_spec)

        argument_spec_elements = argument_spec.get('spec', [])
        log.debug('argument_spec_elements: %s', argument_spec_elements)

        log.debug('self._task.args: %s', pf(self._task.args))
        survey_answers = self._task.args.get('survey_answers', {})
        provided_arguments = self._task.args.get('provided_arguments', {})

        log.debug('provided_arguments: %s', provided_arguments)
        log.debug('survey_answers: %s', survey_answers)

        if not isinstance(argument_spec, dict):
            raise AnsibleError('Incorrect type for argument_spec, expected dict and got %s' % type(argument_spec))

        if not isinstance(provided_arguments, dict):
            raise AnsibleError('Incorrect type for survey_data, expected dict and got %s' % type(provided_arguments))

        argument_errors = []
        for argument_spec_item in argument_spec_elements:
            res = survey._survey_element_validation(argument_spec_item,
                                                    provided_arguments,
                                                    validate_required=True)
            argument_errors.extend(res)

        result['_ansible_verbose_always'] = True
        if argument_errors:
            result['failed'] = True
            result['argument_errors'] = argument_errors

            result['msg'] = 'There were validation errors in the survey'
            return result

        result['changed'] = False
        result['msg'] = 'The survey validation passed'
        result['valid_supplied_arguments'] = provided_arguments
        return result

    def validate_args(self, spec_elements, answers):
        '''Validate the role arg spec and raise AnsibleModuleError if it fails

        Return: void?
        '''
        # build arg spec
        # dump it as ansiballz/AnsibleModuleish arg format
        # monkeypath module_utils.basic _ANSIBLE_ARGS, AnsibleModule.fail_json (???)
        # build faux-ish AnsibleModule
        # monkeypath AnsibleModule
        #  call AnsibleModule(**spec) to do it's arg validation and fail_json
        # raise from fail_json if called
        pass
