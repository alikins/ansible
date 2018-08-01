#!/bin/bash

ANSIBLE_ROLES_PATH=../ ansible-playbook -i ../../inventory -e @../../integration_config.yml -vvv test.yml

