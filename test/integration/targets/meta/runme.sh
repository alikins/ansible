#!/usr/bin/env bash

set -eux

ANSIBLE_CACHE_PLUGIN=redis ANSIBLE_CACHE_PLUGIN_CONNECTION=./fact_cache ansible-playbook test_meta.yml -e @../../integration_config.yml -i ../../inventory -v "$@"
ANSIBLE_CACHE_PLUGIN=redis ANSIBLE_CACHE_PLUGIN_CONNECTION=./fact_cache ansible-playbook test_meta.yml -e @../../integration_config.yml -i ../../inventory -v "$@"
