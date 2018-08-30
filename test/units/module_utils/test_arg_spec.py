# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import logging
import pprint

import pytest

from ansible.module_utils import arg_spec

log = logging.getLogger(__name__)

pf = pprint.pformat


# FIXME: copied from test_argument_spec
@pytest.fixture
def complex_argspec():
    argspec = dict(
        foo=dict(required=True, aliases=['dup']),
        bar=dict(),
        bam=dict(),
        baz=dict(fallback=(arg_spec.env_fallback, ['BAZ'])),
        bar1=dict(type='bool'),
        zardoz=dict(choices=['one', 'two']),
        zardoz2=dict(type='list', choices=['one', 'two', 'three']),
    )
    mut_ex = (('bar', 'bam'),)
    req_to = (('bam', 'baz'),)

    kwargs = dict(
        argument_spec=argspec,
        mutually_exclusive=mut_ex,
        required_together=req_to,
        no_log=True,
        add_file_common_args=True,
        # supports_check_mode=True,
        params={'foo': 'Fu'},
    )
    return kwargs


@pytest.fixture
def arg_spec_modifiers():
    mut_ex = (('bar', 'bam'),)
    req_to = (('bam', 'baz'),)

    modifiers = {'check_invalid_arguments': None,
                 'bypass_checks': False,
                 'mutually_exclusive': mut_ex,
                 'required_together': req_to,
                 }
    return modifiers


def test_init():
    params = {}
    argument_spec = {}
    argspec = arg_spec.ArgSpec(params=params, argument_spec=argument_spec)

    log.debug('argspec: %s', argspec)
    log.debug('argspec._as_dict: %s', pf(argspec._as_dict()))


def test_complex_argspec1(complex_argspec, arg_spec_modifiers):
    log.debug('complex_argspec: %s', complex_argspec)
    log.debug('arg_spec_modifiers: %s', arg_spec_modifiers)

    argspec = arg_spec.ArgSpec(**complex_argspec)
    log.debug('argspec: %s', argspec)
    log.debug('argspec._as_dict: %s', pf(argspec._as_dict()))

    res = argspec.validate(**arg_spec_modifiers)

    log.debug('res: %s', res)


def test_complex_argspec_mutex_conflict(complex_argspec, arg_spec_modifiers):
    log.debug('complex_argspec: %s', complex_argspec)
    log.debug('arg_spec_modifiers: %s', arg_spec_modifiers)

    kwargs = {}
    kwargs.update(complex_argspec)
    params = kwargs.pop('params')
    params.update({'bar': 'Bar_value', 'bam': 'Bam_value'})
    kwargs['params'] = params
    argspec = arg_spec.ArgSpec(**kwargs)
    log.debug('argspec: %s', argspec)
    log.debug('argspec._as_dict: %s', pf(argspec._as_dict()))

    with pytest.raises(arg_spec.AnsibleArgSpecError,
                       match='parameters are mutually exclusive: bar, bam') as exc_info:
        argspec.validate(**arg_spec_modifiers)

    log.debug('exc_info: %s', exc_info)
