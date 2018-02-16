#!/bin/bash

ansible-playbook -i ../../../../inventory -vvvvv --vault-password-file ../../vault-password --vault-password-file ../../vault-hunter42-password test.yml
