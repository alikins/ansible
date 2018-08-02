# Copyright 2018 Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import logging
log = logging.getLogger(__name__)

from ansible.errors import AnsibleError
from ansible.plugins.action import ActionBase
from ansible.playbook.role import survey


class ActionModule(ActionBase):
    ''' Validate a Role survey spec and answers to it's questions '''

    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        '''
        Validate a survey spec

        :arg tmp: Deprecated. Do not use.
        :arg dict task_vars: A dict of task variables.
            Valid args include 'survey_spec', 'survey_answers'
        :return: An action result dict, including a 'survey_errors' key with a
            list of validation errors found.
        '''
        if task_vars is None:
            task_vars = dict()

        result = super(ActionModule, self).run(tmp, task_vars)
        del tmp  # tmp no longer has any effect

        if 'survey_spec' not in self._task.args:
            raise AnsibleError('"survey_spec" arg is required in args')

        survey_spec = self._task.args.get('survey_spec')
        log.debug('survey_spec: %s', survey_spec)

        survey_spec_elements = survey_spec.get('spec', [])
        log.debug('survey_spec_elements: %s', survey_spec_elements)

        survey_answers = self._task.args.get('survey_answers', {})

        log.debug('survey_answers: %s', survey_answers)

        if not isinstance(survey_spec, dict):
            raise AnsibleError('Incorrect type for survey_spec, expected dict and got %s' % type(survey_spec))

        if not isinstance(survey_answers, dict):
            raise AnsibleError('Incorrect type for survey_data, expected dict and got %s' % type(survey_answers))

        survey_errors = []
        for survey_item in survey_spec_elements:
            res = survey._survey_element_validation(survey_item, survey_answers, validate_required=True)
            survey_errors.extend(res)

        result['_ansible_verbose_always'] = True
        if survey_errors:
            result['failed'] = True
            result['survey_errors'] = survey_errors

            result['msg'] = 'There were validation errors in the survey'
            return result

        result['changed'] = False
        result['msg'] = 'The survey validation passed'
        result['valid_survey_answers'] = survey_answers
        return result
