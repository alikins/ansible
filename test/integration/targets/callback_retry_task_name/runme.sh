#!/usr/bin/env bash

set -eux

# we are looking to verify the callback for v2_retry_runner gets a correct task name, include
# if the value needs templating based on results of previous tasks
ansible-playbook -i ../../inventory test.yml | grep -e "^TASK.*18236 callback task template fix OUTPUT 2"
