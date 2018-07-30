# Copyright: (c) 2017, 2018, Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# Make coding more python3-ish
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import copy
import logging

from ansible.module_utils.six import string_types
from ansible.playbook.attribute import FieldAttribute
from ansible.playbook.base import Base

log = logging.getLogger(__name__)


# QuestionSpec? SurveyQuestion?
class Question(Base):
    '''A question as found in a Survey question list.

    Based on at https://github.com/ansible/awx/blob/devel/awx/api/templates/api/job_template_survey_spec.md

    valid types for question type include:

        'text': For survey questions expecting a textual answer
        'password': For survey questions expecting a password or other sensitive information
        'integer': For survey questions expecting a whole number answer
        'float': For survey questions expecting a decimal number
        'multiplechoice': For survey questions where one option from a list is required
        'multiselect': For survey questions where multiple items from a presented list can be selected

    Each item must contain a question_name and question_description field that
    describes the survey question itself.

    The variable elements of each survey items represents the key that
    will be given to the playbook when the Role is launched.
    It will contain the value as a result of the survey.'''

    _type = FieldAttribute(isa='string', default='text')
    _question_name = FieldAttribute(isa='string', required=True)
    _question_description = FieldAttribute(isa='string', required=True)
    _variable = FieldAttribute(isa='string')
    _choices = FieldAttribute(isa='list', default=[])

    # TODO: Looks like these can be a string, a float, or an int.
    _min = FieldAttribute(isa='string', default='')
    _max = FieldAttribute(isa='string', default='')

    # heh, the key 'required' also has attribute of being required. If not
    # specified in the yaml, the default value of the questions 'required' attribute
    # is True. ie, a question provided is required unless 'required' is specifically
    # set to False
    _required = FieldAttribute(isa='bool', default=False, required=True)

    # and the key/field 'default' defaults to True. ie, the default behavior
    # of a survey question is to be 'asked' by default
    _default = FieldAttribute(isa='string', default=True)


class Survey(Base):
    '''A set of questions to ask and info validate the answers.

    Based on awx's job template survey spec seen
    at https://github.com/ansible/awx/blob/devel/awx/api/templates/api/job_template_survey_spec.md'''

    # Base has a 'name' attribute

    # The description of the survey spec
    _description = FieldAttribute(isa='string', default='')

    # The list of question specs in the survey
    _spec = FieldAttribute(isa='list', required=True, default=[], alias='spec')

    def _load_spec(self, attr, ds):
        '''Loads a list of Questions from the 'spec' field.'''
        log.debug('attr: %s', attr)
        log.debug('ds: %s', ds)
        spec = []

        for spec_ds in ds:
            question = Question()
            question.load_data(spec_ds)
            spec.append(question)

        return spec


# FIXME: remove once 'ported' from awx
def _(the_arg):
    return the_arg


# FIXME: remove once 'ported' from awx
#        Likely will just some sort of SurveyValidationError
class ErrorResponse(object):
    def __init__(self, response_dict):
        self.response = response_dict


# FIXME: we don't have any code in ansible/ansible to do Fernat so we just dont
#        do anything at the moment. Not sure if it makes sense to encrypt as a side
#        effect of validation.
def encrypt_value(some_value):

    print('FIXME: survey validation is not actually ENCRYPTING anything')

    log.info('FIXME: survey validation is not actually ENCRYPTING anything')

    return some_value


# from https://github.com/ansible/awx/blob/devel/awx/main/models/mixins.py#L185-L265
# master, 1ba6073569358e81e69a3e2f8406d3f96c21663c
def _survey_element_validation(survey_element, data, validate_required=True):
    # Don't apply validation to the `$encrypted$` placeholder; the decrypted
    # default (if any) will be validated against instead
    errors = []

    if (survey_element['type'] == "password"):
        password_value = data.get(survey_element['variable'])
        if (
            isinstance(password_value, string_types) and
            password_value == '$encrypted$'
        ):
            if survey_element.get('default') is None and survey_element['required']:
                if validate_required:
                    errors.append("'%s' value missing" % survey_element['variable'])
            return errors

    if survey_element['variable'] not in data and survey_element['required']:
        if validate_required:
            errors.append("'%s' value missing" % survey_element['variable'])
    elif survey_element['type'] in ["textarea", "text", "password"]:
        if survey_element['variable'] in data:
            if not isinstance(data[survey_element['variable']], string_types):
                errors.append("Value %s for '%s' expected to be a string." % (data[survey_element['variable']],
                                                                              survey_element['variable']))
                return errors

            if 'min' in survey_element and survey_element['min'] not in ["", None] and len(data[survey_element['variable']]) < int(survey_element['min']):
                errors.append("'%s' value %s is too small (length is %s must be at least %s)." %
                              (survey_element['variable'], data[survey_element['variable']], len(data[survey_element['variable']]), survey_element['min']))
            if 'max' in survey_element and survey_element['max'] not in ["", None] and len(data[survey_element['variable']]) > int(survey_element['max']):
                errors.append("'%s' value %s is too large (must be no more than %s)." %
                              (survey_element['variable'], data[survey_element['variable']], survey_element['max']))

    elif survey_element['type'] == 'integer':
        if survey_element['variable'] in data:
            if type(data[survey_element['variable']]) != int:
                errors.append("Value %s for '%s' expected to be an integer." % (data[survey_element['variable']],
                                                                                survey_element['variable']))
                return errors
            if 'min' in survey_element and survey_element['min'] not in ["", None] and survey_element['variable'] in data and \
                    data[survey_element['variable']] < int(survey_element['min']):
                errors.append("'%s' value %s is too small (must be at least %s)." %
                              (survey_element['variable'], data[survey_element['variable']], survey_element['min']))
                if 'max' in survey_element and survey_element['max'] not in ["", None] and survey_element['variable'] in data and \
                        data[survey_element['variable']] > int(survey_element['max']):
                    errors.append("'%s' value %s is too large (must be no more than %s)." %
                                  (survey_element['variable'], data[survey_element['variable']], survey_element['max']))
    elif survey_element['type'] == 'float':
        if survey_element['variable'] in data:
            if type(data[survey_element['variable']]) not in (float, int):
                errors.append("Value %s for '%s' expected to be a numeric type." % (data[survey_element['variable']],
                                                                                    survey_element['variable']))
                return errors
            if 'min' in survey_element and survey_element['min'] not in ["", None] and data[survey_element['variable']] < float(survey_element['min']):
                errors.append("'%s' value %s is too small (must be at least %s)." %
                              (survey_element['variable'], data[survey_element['variable']], survey_element['min']))
            if 'max' in survey_element and survey_element['max'] not in ["", None] and data[survey_element['variable']] > float(survey_element['max']):
                errors.append("'%s' value %s is too large (must be no more than %s)." %
                              (survey_element['variable'], data[survey_element['variable']], survey_element['max']))
    elif survey_element['type'] == 'multiselect':
        if survey_element['variable'] in data:
            if type(data[survey_element['variable']]) != list:
                errors.append("'%s' value is expected to be a list." % survey_element['variable'])
            else:
                choice_list = copy.copy(survey_element['choices'])
                if isinstance(choice_list, string_types):
                    choice_list = choice_list.split('\n')
                for val in data[survey_element['variable']]:
                    if val not in choice_list:
                        errors.append("Value %s for '%s' expected to be one of %s." % (val, survey_element['variable'],
                                                                                       choice_list))
    elif survey_element['type'] == 'multiplechoice':
        choice_list = copy.copy(survey_element['choices'])
        if isinstance(choice_list, string_types):
            choice_list = choice_list.split('\n')
        if survey_element['variable'] in data:
            if data[survey_element['variable']] not in choice_list:
                errors.append("Value %s for '%s' expected to be one of %s." % (data[survey_element['variable']],
                                                                               survey_element['variable'],
                                                                               choice_list))
    return errors


# TODO: hook this up to Survey.load_data
# NOTE: all the ErrorResponse objects returned here indicate errors (replace with exception)
def _validate_spec_data(new_spec):
    schema_errors = {}
    for field, expect_type, type_label in [
            ('name', string_types, 'string'),
            ('description', string_types, 'string'),
            ('spec', list, 'list of items')]:
        if field not in new_spec:
            schema_errors['error'] = _("Field '{}' is missing from survey spec.").format(field)
        elif not isinstance(new_spec[field], expect_type):
            schema_errors['error'] = _("Expected {} for field '{}', received {} type.").format(
                type_label, field, type(new_spec[field]).__name__)

    if isinstance(new_spec.get('spec', None), list) and len(new_spec["spec"]) < 1:
        schema_errors['error'] = _("'spec' doesn't contain any items.")

    if schema_errors:
        return ErrorResponse(schema_errors)

    variable_set = set()

    # client will not have the old survey spec, so can't do any of the logic that needs it.
    # Assume the old_spec_dict is empty for now.
    # old_spec_dict = JobTemplate.pivot_spec(old_spec)
    old_spec_dict = {}

    # NOTE: changing the survey_item while iterating over the list of question specs (for the encryption cases)
    for idx, survey_item in enumerate(new_spec['spec']):
        if not isinstance(survey_item, dict):
            return ErrorResponse(dict(error=_("Survey question %s is not a json object.") % str(idx)))

        # For these cases, we should get an error when we try Survey.load_data().
        # TODO: decide if we need to support these checks for Survey() created without a load_data() or any
        #       post_validate() step
        if "type" not in survey_item:
            return ErrorResponse(dict(error=_("'type' missing from survey question %s.") % str(idx)))
        if "question_name" not in survey_item:
            return ErrorResponse(dict(error=_("'question_name' missing from survey question %s.") % str(idx)))
        if "variable" not in survey_item:
            return ErrorResponse(dict(error=_("'variable' missing from survey question %s.") % str(idx)))
        if survey_item['variable'] in variable_set:
            return ErrorResponse(dict(error=_("'variable' '%(item)s' duplicated in survey question %(survey)s.") % {
                'item': survey_item['variable'], 'survey': str(idx)}))
        else:
            variable_set.add(survey_item['variable'])
        if "required" not in survey_item:
            return ErrorResponse(dict(error=_("'required' missing from survey question %s.") % str(idx)))

        if survey_item["type"] == "password" and "default" in survey_item:
            if not isinstance(survey_item['default'], string_types):
                return ErrorResponse(dict(error=_(
                    "Value {question_default} for '{variable_name}' expected to be a string."
                ).format(
                    question_default=survey_item["default"], variable_name=survey_item["variable"])
                ))

        if ("default" in survey_item and isinstance(survey_item['default'], string_types) and
                survey_item['default'].startswith('$encrypted$')):
            # Submission expects the existence of encrypted DB value to replace given default
            if survey_item["type"] != "password":
                return ErrorResponse(dict(error=_(
                    "$encrypted$ is a reserved keyword for password question defaults, "
                    "survey question {question_position} is type {question_type}."
                ).format(
                    question_position=str(idx), question_type=survey_item["type"])
                ))
            old_element = old_spec_dict.get(survey_item['variable'], {})
            encryptedish_default_exists = False
            if 'default' in old_element:
                old_default = old_element['default']
                if isinstance(old_default, string_types):
                    if old_default.startswith('$encrypted$'):
                        encryptedish_default_exists = True
                    elif old_default == "":  # unencrypted blank string is allowed as DB value as special case
                        encryptedish_default_exists = True
            if not encryptedish_default_exists:
                return ErrorResponse(dict(error=_(
                    "$encrypted$ is a reserved keyword, may not be used for new default in position {question_position}."
                ).format(question_position=str(idx))))
            survey_item['default'] = old_element['default']
        elif survey_item["type"] == "password" and 'default' in survey_item:
            # Submission provides new encrypted default
            survey_item['default'] = encrypt_value(survey_item['default'])
