# Copyright: (c) 2017, 2018, Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# Make coding more python3-ish
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import logging

import pytest
from ansible.playbook.role.survey import Survey, Question, _validate_spec_data, _survey_element_validation

from ansible.module_utils.six import string_types

log = logging.getLogger(__name__)


def test_survey_init_empty():
    survey = Survey()

    log.debug('survey: %s', Survey)

    assert isinstance(survey, Survey)
    import pprint
    log.debug('dir(Survey): %s', pprint.pformat(dir(survey)))

    log.debug('survey.spec: %s', survey.spec)
    log.debug('survey.description: %s', survey.description)
    log.debug('survey.name: %s', survey.name)

    assert isinstance(survey.spec, list)
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
    questions = [{'type': 'text',
                  'question_name': 'some_question_name',
                  'question_description': 'some_question_description',
                  'required': True}]

    data = {'name': name,
            'description': description,
            'spec': questions}
    survey2 = survey.load_data(data)

    log.debug('survey2: %s', survey2)
    log.debug('survey2.dump_attrs: %s', survey2.dump_attrs())

    assert survey2.name == name
    assert survey2.description == description

    assert isinstance(survey2.spec[0], Question)
    assert survey2.spec[0].type == questions[0]['type']
    assert survey2.spec[0].question_name == questions[0]['question_name']
    assert survey2.spec[0].question_description == questions[0]['question_description']


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


@pytest.mark.parametrize("data,default_data", [
    ({
        "type": "float",
        "question_name": "some_question_name",
        "question_description": "some_question_description",
        "variable": "some_variable",
        "choices": "",
        "min": "",
        "max": "",
        "required": True,
        "default": "yes"
    }, {}),
    ({
        "type": "text",
        "question_name": "cantbeshort",
        "question_description": "What is a long answer",
        "variable": "long_answer",
        "choices": "",
        "min": 5,
        "max": "",
        "required": False,
        "default": "yes"
    }, {}),
    ({
        "type": "text",
        "question_name": "cantbelong",
        "question_description": "What is a short answer",
        "variable": "short_answer",
        "choices": "",
        "min": "",
        "max": 5,
        "required": False,
        "default": "yes"
    }, {}),
    ({
        "type": "text",
        "question_name": "reqd",
        "question_description": "I should be required",
        "variable": "reqd_answer",
        "choices": "",
        "min": "",
        "max": "",
        "required": False,
        "default": "yes"
    }, {}),
    ({
        "type": "multiplechoice",
        "question_name": "achoice",
        "question_description": "Need one of these",
        "variable": "single_choice",
        "choices": ["one", "two"],
        "min": "",
        "max": "",
        "required": False,
        "default": "yes"
    }, {}),
    ({
        "type": "multiselect",
        "question_name": "mchoice",
        "question_description": "Can have multiples of these",
        "variable": "multi_choice",
        "choices": ["one", "two", "three"],
        "min": "",
        "max": "",
        "required": False,
        "default": "yes"
    }, {}),
    ({
        "type": "integer",
        "question_name": "integerchoice",
        "question_description": "I need an int here",
        "variable": "int_answer",
        "choices": "",
        "min": 1,
        "max": 5,
        "required": False,
        "default": ""
    }, {}),
    ({
        "type": "float",
        "question_name": "float",
        "question_description": "I need a float here",
        "variable": "float_answer",
        "choices": "",
        "min": 2,
        "max": 5,
        "required": False,
        "default": ""
    }, {})
])
def test_question_load_data(data, default_data):
    question = Question()

    question2 = question.load_data(data)

    log.debug('question2: %s', question2)
    log.debug('question2.dump_attrs: %s', question2.dump_attrs())

    for field_name in data:
        # verify the result matches the loaded data. For fields not specified in
        # data, verify they match the expected defaults from default_data
        assert getattr(question2, field_name) == data.get(field_name,
                                                          default_data.get(field_name))


def test_question_serialize():
    question_data = {"type": "text",
                     "question_name": "cantbelong",
                     "question_description": "What is a short answer",
                     "variable": "short_answer",
                     "choices": "",
                     "min": "",
                     "max": 5,
                     "required": False,
                     "default": "yes"
                     }

    question = Question()
    question2 = question.load_data(question_data)

    log.debug('question2: %s', question2)
    log.debug('question2.dump_attrs: %s', question2.dump_attrs())

    res = question2.serialize()
    log.debug('question2.serialize res: %s', res)

    assert isinstance(res, dict)


def test_survey_load_with_questions():
    questions = [{
        "type": "float",
        "question_name": "float",
        "question_description": "I need a float here",
        "variable": "float_answer",
        "choices": "",
        "min": 2,
        "max": 5,
        "required": False,
        "default": ""
    }]
    data = {'name': 'some_survey_with_questions',
            'description': 'A survey spec that includes questions',
            # The list of survey questions is found in the 'spec' value
            'spec': questions}

    survey = Survey()
    survey2 = survey.load_data(data)

    log.debug('survey2: %s', survey2)
    log.debug('survey2.dump_attrs: %s', survey2.dump_attrs())

    assert survey2.name == data['name']
    assert survey2.description == data['description']
    spec_data = []
    for spec_obj in survey2.spec:
        log.debug('spec_obj: %s', spec_obj)
        log.debug('spec_obj.dump_attrs: %s', spec_obj.dump_attrs())

        # the starting expected data
        qdata = {}

        # the data after loading a survey with questions and gettings its attrs dict
        sdata = spec_obj.dump_attrs()

        # use the first question to find the fields/keys we care about (and not all
        # the assorted playbook base object stuff)
        for dkey in questions[0]:
            qdata[dkey] = sdata[dkey]

        spec_data.append(qdata)
    assert spec_data == data['spec']


def test_survey_validate_data():
    questions = [{
        "type": "float",
        "question_name": "float",
        "question_description": "I need a float here",
        "variable": "float_answer",
        "choices": "",
        "min": 2,
        "max": 5,
        "required": False,
        "default": ""
    }]
    data = {'name': 'some_survey_with_questions',
            'description': 'A survey spec that includes questions',
            # The list of survey questions is found in the 'spec' value
            'spec': questions}

    res = _validate_spec_data(data)

    log.debug('res: %s', res)


def test_survey_validate_data_no_question_name():
    questions = [{
        "type": "float",
        # "question_name": "float",
        "question_description": "I need a float here",
        "variable": "float_answer",
        "choices": "",
        "min": 2,
        "max": 5,
        "required": False,
        "default": ""
    }]
    data = {'name': 'some_survey_with_questions',
            'description': 'A survey spec that includes questions',
            # The list of survey questions is found in the 'spec' value
            'spec': questions}

    res = _validate_spec_data(data)

    log.debug('res: %s', res)
    log.debug('res.response: %s', res.response)


@pytest.mark.parametrize("survey_element,answer,expected", [
    (
        {
            "type": "float",
            "question_name": "some_question_name",
            "question_description": "some_question_description",
            "variable": "some_float",
            "choices": "",
            "min": 2,
            "max": 5,
            "required": True,
            "default": "yes"
        },
        {'some_float': 1.0},
        ["'some_float' value 1.0 is too small (must be at least 2)."]
    ),
    (
        {
            "type": "multiplechoice",
            "question_name": "achoice",
            "question_description": "Need one of these",
            "variable": "single_choice",
            "choices": ["one", "two"],
            "min": "",
            "max": "",
            "required": False,
            "default": "yes"
        },
        {'single_choice': 'three'},
        ["Value three for 'single_choice' expected to be one of ['one', 'two']."],
    ),
    (
        {
            "type": "text",
            "question_name": "not_provided_not_required",
            "question_description": "Not provided and not required",
            "variable": "not_provided_not_required_answer",
            "choices": "",
            "min": "",
            "max": 5,
            "required": False,
            "default": "yes"
        },
        {},
        []
    ),
    (
        {
            "type": "text",
            "question_name": "not_provided_required",
            "question_description": "Not provided but is required",
            "variable": "not_provided_required_answer",
            "choices": "",
            "min": "",
            "max": 5,
            "required": True,
            "default": "yes"
        },
        {},
        ["'not_provided_required_answer' value missing"]
    ),
    # NOTE: for type text, min/max is the min/max length of the string, not the min/max values
    (
        {
            "type": "text",
            "question_name": "provided_not_required",
            "question_description": "Provided and not required",
            "variable": "provided_not_required_answer",
            "choices": "",
            "min": "",
            "max": 255,
            "required": False,
            "default": "yes"
        },
        {"provided_not_required_answer": "some answer"},
        []
    ),
])
def test_survey_element_validation(survey_element, answer, expected):
    res = _survey_element_validation(survey_element, answer, validate_required=True)

    log.debug('res: %s', res)
    assert res == expected
