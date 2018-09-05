#!/bin/bash

ANSIBLE_ROLE=${ANSIBLE_ROLE:-"ansible-role"}
$ANSIBLE_ROLE localhost -r test1

$ANSIBLE_ROLE localhost -r test1 -e @test1_extra_vars.yml

$ANSIBLE_ROLE localhost -vvv -r test1 -a 'test1_var1=TowelFear test1_var2=arg_from_cli' -e @test1_extra_vars.yml
