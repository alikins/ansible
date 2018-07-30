# Copyright: (c) 2017, 2018, Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# Make coding more python3-ish
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import logging

from ansible.playbook.role.survey import Survey

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

