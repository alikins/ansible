#!/usr/bin/env bash

cleanup() {

    rm -fr ~/.ansible/plugins/modules/* && rm -fr ~/.ansible/plugins/module_utils/* && rm -fr ~/.ansible/roles/*
}

display() {
    printf "##### TEST: %s\n" "${@}"
}

verbosity="-vvvvv"

cleanup

display "legacy role from git+https"

ansible-galaxy content-install git+https://github.com/geerlingguy/ansible-role-ansible.git $verbosity

cleanup

display "legacy role from galaxy"

ansible-galaxy content-install geerlingguy.ansible $verbosity

cleanup

display "legacy role from galaxy with dependencies"

ansible-galaxy content-install hxpro.nginx $verbosity

cleanup

display "modules from git+https WITHOUT galaxyfile"

ansible-galaxy content-install -t module git+https://github.com/maxamillion/test-galaxy-content $verbosity

cleanup

display "module_utils from git+https WITHOUT galaxyfile"

ansible-galaxy content-install -t module git+https://github.com/maxamillion/test-galaxy-content $verbosity

cleanup

display "all content git+https WITH galaxyfile"

ansible-galaxy content-install git+https://github.com/maxamillion/test-galaxy-content-galaxyfile $verbosity

cleanup
