#!/usr/bin/env bash

set -euvx

ansible-playbook -i ../../inventory -v "$@" test_include_role_fails.yml
