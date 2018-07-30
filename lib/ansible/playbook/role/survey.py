# Copyright: (c) 2017, 2018, Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# Make coding more python3-ish
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.playbook.attribute import FieldAttribute
from ansible.playbook.base import Base


class Survey(Base):
    '''A set of questions to ask and info validate the answers.

    Based on awx's job template survey spec seen
    at https://github.com/ansible/awx/blob/devel/awx/api/templates/api/job_template_survey_spec.md'''

    # Base has a 'name' attribute

    # The description of the survey spec
    _description = FieldAttribute(isa='str', default='')

    # The list of questions in the survey
    _questions = FieldAttribute(isa='list', required=True, default=[])
