#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright 2018 Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['stableinterface'],
                    'supported_by': 'core'}


DOCUMENTATION = '''
---
module: validate_arg_spec
short_description: Validate Arg Specs
description:
     - This module validate args specs
version_added: "2.7"
options:
  argument_spec:
    required: true
  provided_arguments:
author:
    - "Ansible Core Team"
    - "Adrian Likins"
'''

EXAMPLES = '''
'''
