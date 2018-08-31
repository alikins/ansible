#!/bin/bash

# ANSIBLE_ROLES_PATH=../ ansible-playbook -i ../../inventory -e @../../integration_config.yml -vvv test.yml
ansible-playbook -i ../../inventory -e @../../integration_config.yml -e@validate_extra_vars.yml -vvvv run_role.yml
