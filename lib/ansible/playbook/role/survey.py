# Copyright: (c) 2017, 2018, Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# Make coding more python3-ish
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.playbook.attribute import FieldAttribute
from ansible.playbook.base import Base


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

    # The list of questions in the survey
    _questions = FieldAttribute(isa='list', required=True, default=[])
