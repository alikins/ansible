
# -*- coding: utf-8 -*-
# Copyright: (c) 2017 Ansible Project
# License: GNU General Public License v3 or later (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt )

# Make coding more python3-ish
from __future__ import (absolute_import, division)
__metaclass__ = type

import pytest

from ansible.compat.tests.mock import mock_open
from ansible.module_utils import compat_platform


# to test fully need to mock:
# open('/etc/lsb-release')
# os.listdir('/etc')
# open('/etc/$VARIOUS_RELEASE_FILES') /etc/
# open other random locations /var/adm/inst-log/info /etc/.installed /usr/lib/setup
@pytest.fixture
def mock_lsb_release(mocker):
    mock_lsb_release_fo = mock_open(read_data=b'FooBlipLinux release 1.1 (Unblippable)\n')
    mocker.patch('ansible.module_utils.compat_platform.open', mock_lsb_release_fo, create=True)
    print('bbbbbbbbbbbbbbbb')


def test_dist(mock_lsb_release):
    dist = compat_platform.dist()
    print(dist)
    assert isinstance(dist, tuple), \
        "return of dist() is expected to be a tuple but was a %s" % type(dist)


def test_dist_all_none(mock_lsb_release):
    # this can find something, or it can throw a type error
    dist = compat_platform.dist(distname=None, version=None, id=None, supported_dists=())
    assert isinstance(dist, tuple), \
        "return of dist() is expected to be a tuple but was a %s" % type(dist)

    print(dist)


def test_dist_empty_supported_dists(mock_lsb_release):
    dist = compat_platform.dist(supported_dists=tuple())
    print(dist)
    assert dist == ('', '', ''), \
        "no supported dists were provided so dist() should have returned ('', '', '')"


# TODO: test that we dont show deprecation warnings
class TestLinuxDistribution:
    def test_linux_distribution(self, mock_lsb_release):
        linux_dist = compat_platform.linux_distribution()
        print(linux_dist)
        # This will be empty unknown for non linux
        assert isinstance(linux_dist, tuple), \
            "return of linux_distribution() is expected to be a tuple but was a %s" % type(linux_dist)

    def test_linux_distribution_all_none(self, mock_lsb_release):
        with pytest.raises(TypeError):
            compat_platform.linux_distribution(distname=None, version=None,
                                               id=None, supported_dists=None,
                                               full_distribution_name=None)

    def test_linux_distribution_empty_supported_dists(self, mock_lsb_release):
        linux_dist = compat_platform.linux_distribution(supported_dists=tuple())
        print(linux_dist)
        assert linux_dist[0] == ''
        assert linux_dist[1] == ''
        assert linux_dist[2] == ''
        assert linux_dist[0] == linux_dist[1] == linux_dist[2] == '', \
            "linux_distribtion was expected to return ('', '', '') with no supported_dists"
