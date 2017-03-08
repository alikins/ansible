#!/bin/bash

VAULT_PASSWORD_FILE=${VAULT_PASSWORD_FILE:-"pass_latin1"}

for example1 in files/example1-pass*;
do
    ansible-vault decrypt -v -v -v --vault-password-file="${VAULT_PASSWORD_FILE}" "${example1}" --output=-
done
