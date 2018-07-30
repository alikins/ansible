# Copyright: (c) 2017, 2018, Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# Make coding more python3-ish
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import logging

from ansible.playbook.role.survey import Survey, Question

from ansible.module_utils.six import string_types

log = logging.getLogger(__name__)


def test_survey_init_empty():
    survey = Survey()

    log.debug('survey: %s', Survey)

    assert isinstance(survey, Survey)
    import pprint
    log.debug('dir(Survey): %s', pprint.pformat(dir(survey)))

    log.debug('survey.questions: %s', survey.questions)
    log.debug('survey.description: %s', survey.description)
    log.debug('survey.name: %s', survey.name)

    assert isinstance(survey.questions, list)
    assert isinstance(survey.description, string_types)
    assert isinstance(survey.name, string_types)


def test_survey_load_data_empty():
    survey = Survey()

    survey_ = survey.load_data({})

    assert isinstance(survey_, Survey)

    assert survey == survey_


def test_survey_load_data():
    survey = Survey()

    name = 'some_survey'
    description = 'This is the survey used for unit tests'
    questions = ['foo']

    data = {'name': name,
            'description': description,
            'questions': questions}
    survey2 = survey.load_data(data)

    log.debug('survey2: %s', survey2)
    log.debug('survey2.dump_attrs: %s', survey2.dump_attrs())

    assert survey2.name == name
    assert survey2.description == description
    assert survey2.questions == questions


def test_question_init_empty():
    question = Question()

    log.debug('question: %s', question)

    assert isinstance(question, Question)

    import pprint
    log.debug('dir(Question): %s', pprint.pformat(dir(question)))

    log.debug('question.type: %s', question.type)

    assert isinstance(question.type, string_types)

    # assert isinstance(survey.questions, list)
    # assert isinstance(survey.description, string_types)


def test_question_load_data():
    question = Question()

    data = {
            'type': 'float',
            'question_name': 'some_question_name',
            'question_description': 'some_question_description',
            'variable': 'some_variable',
            'choices': '',
            'min': '',
            'max': '',
            'required': True,
            'default': 'yes'
    }

    default_data = {'min': '',
                    'max': ''
                    }
    question2 = question.load_data(data)

    log.debug('question2: %s', question2)
    log.debug('question2.dump_attrs: %s', question2.dump_attrs())

    for field_name in data:
        # verify the result matches the loaded data. For fields not specified in
        # data, verify they match the expected defaults from default_data
        assert getattr(question2, field_name) == data.get(field_name,
                                                          default_data.get(field_name))

   #     assert question2.type == data['type']
   # assert question2.question_name == data['question_name']
   # assert question2.question_description == data['question_description']

    # assert survey2.description == description
    # assert survey2.questions == questions
