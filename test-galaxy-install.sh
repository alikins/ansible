#!/usr/bin/env bash

cleanup() {

    rm -fr ~/.ansible/plugins/modules/* && rm -fr ~/.ansible/plugins/module_utils/* && rm -fr ~/.ansible/roles/*
}

display() {
    printf "##### TEST: %s\n" "${@}"
}

ANSIBLE_CONFIG=/home/adrian/src/ansible/ansible_empty.cfg
ANSIBLE_ROLES_PATH="/tmp/test-galaxy-install/roles"
export ANSIBLE_CONFIG
export ANSIBLE_ROLES_PATH
mkdir -p "${ANSIBLE_ROLES_PATH}"

verbosity="-vvvvv"

cleanup

display "legacy role from git+https"

ansible-galaxy content-install git+https://github.com/geerlingguy/ansible-role-ansible.git $verbosity

ansible-galaxy list

cleanup

display "legacy role from galaxy"

ansible-galaxy content-install geerlingguy.ansible $verbosity
ansible-galaxy list
cleanup

display "legacy role from galaxy with dependencies"

ansible-galaxy content-install hxpro.nginx $verbosity
ansible-galaxy list
cleanup

display "modules from git+https WITHOUT galaxyfile"

ansible-galaxy content-install -t module git+https://github.com/maxamillion/test-galaxy-content $verbosity
ansible-galaxy list

#ansible-doc my_sample_module
ansible "${verbosity}" localhost -m my_sample_module -a 'name=foooo1'

cleanup

display "module_utils from git+https WITHOUT galaxyfile"

ansible-galaxy content-install -t module git+https://github.com/maxamillion/test-galaxy-content $verbosity

cleanup

display "all content git+https WITH galaxyfile"

ansible-galaxy content-install git+https://github.com/maxamillion/test-galaxy-content-galaxyfile $verbosity
ansible-galaxy list
# ansible-doc galaxyfile_sample_module
# ansible-doc module_c

ansible "${verbosity}" localhost -m galaxyfile_sample_module -a 'name=bar1'

cleanup
