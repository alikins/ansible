########################################################################
#
# (C) 2013, James Cammarata <jcammarata@ansible.com>
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
#
########################################################################

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import base64
import json
import os
import uuid

from ansible import context
from ansible.errors import AnsibleError
from ansible.module_utils.six import string_types
from ansible.module_utils.six.moves.urllib.error import HTTPError
from ansible.module_utils.six.moves.urllib.parse import quote as urlquote, urlencode
from ansible.module_utils._text import to_bytes, to_native, to_text
from ansible.module_utils.urls import open_url
from ansible.utils.display import Display
from ansible.utils.hashing import secure_hash_s

display = Display()


def g_connect(method):
    ''' wrapper to lazily initialize connection info to galaxy '''
    def wrapped(self, *args, **kwargs):
        if not self.initialized:
            display.vvvv("Initial connection to galaxy_server: %s" % self.api_server)
            server_info = self._get_server_api_info()

            if 'current_version' not in server_info:
                raise AnsibleError("Missing required 'current_version' from server API info response")

            server_version = server_info['current_version']

            if server_version not in self.SUPPORTED_VERSIONS:
                raise AnsibleError("Unsupported Galaxy server API version: %s" % server_version)

            self.baseurl = _urljoin(self.api_server, "api", server_version)

            available_api_versions = server_info.get('available_versions',
                                                     {})

            # FIXME: kluge around that prod galaxy is actually 'v2' but claims to be 'v1'
            if 'v3' not in available_api_versions:
                available_api_versions = {'v1': '/api/v1',
                                          'v2': '/api/v2'}

            self.version = server_version  # for future use
            self.available_api_versions = available_api_versions

            display.vvvv("Base API: %s" % self.baseurl)
            self.initialized = True
        return method(self, *args, **kwargs)
    return wrapped


def _urljoin(*args):
    return '/'.join(to_native(a, errors='surrogate_or_strict').rstrip('/') for a in args + ('',))


class GalaxyAPI(object):
    ''' This class is meant to be used as a API client for an Ansible Galaxy server '''

    SUPPORTED_VERSIONS = ['v1']

    def __init__(self, galaxy, name, url, username=None, password=None, token=None):
        self.galaxy = galaxy
        self.name = name
        self.username = username
        self.password = password
        self.token = token
        self.token_type = 'Token'
        self.api_server = url
        self.validate_certs = not context.CLIARGS['ignore_certs']
        self.baseurl = None
        self.version = None
        self.initialized = False
        self.available_api_versions = {}

        display.debug('Validate TLS certificates for %s: %s' % (self.api_server, self.validate_certs))

    def _auth_header(self, required=True, token_type=None):
        '''Generate the Authorization header.

        Valid token_type values are 'Token' (galaxy v2) and 'Bearer' (galaxy v3)
        or None (default)'''
        token = self.token.get() if self.token else None

        # TODO: choose an 'auth' type
        # 'Token' for v2 api, 'Bearer' for v3
        token_type = token_type or self.token_type

        if token:
            return {'Authorization': "%s %s" % (token_type, token)}
        elif self.username:
            token = "%s:%s" % (to_text(self.username, errors='surrogate_or_strict'),
                               to_text(self.password, errors='surrogate_or_strict', nonstring='passthru') or '')
            b64_val = base64.b64encode(to_bytes(token, encoding='utf-8', errors='surrogate_or_strict'))
            return {'Authorization': "Basic %s" % to_text(b64_val)}
        elif required:
            raise AnsibleError("No access token or username set. A token can be set with --api-key, with "
                               "'ansible-galaxy login', or set in ansible.cfg.")
        else:
            return {}

    @g_connect
    def __call_galaxy(self, url, args=None, headers=None, method=None, error_context_msg=None):
        if args and not headers:
            headers = self._auth_header()
        try:
            display.vvv(url)
            resp = open_url(url, data=args, validate_certs=self.validate_certs, headers=headers, method=method,
                            timeout=20)
            data = json.loads(to_text(resp.read(), errors='surrogate_or_strict'))
        except HTTPError as http_error:
            handle_http_error(http_error, self, error_context_msg)
        return data

    def _get_server_api_info(self):
        """
        Fetches the Galaxy API current version to ensure
        the API server is up and reachable.
        """
        headers = {}
        # use any auth setup
        headers.update(self._auth_header(required=False))

        url = _urljoin(self.api_server, "api")
        try:
            return_data = open_url(url, headers=headers, validate_certs=self.validate_certs)
        except HTTPError as err:
            if err.code != 401:
                handle_http_error(err, self,
                                  "Error when finding available api info from %s (%s)" %
                                  (self.name, self.api_server))

            # assume this is v3 and auth is required.
            headers = {}
            headers.update(self._auth_header(token_type='Bearer', required=True))
            # try again with auth
            try:
                return_data = open_url(url, headers=headers, validate_certs=self.validate_certs)
            except HTTPError as authed_err:
                handle_http_error(authed_err, self,
                                  "Error when finding available api info from %s using auth (%s)" %
                                  (self.name, self.api_server))
        except Exception as e:
            raise AnsibleError("Failed to get data from the API server (%s): %s " % (url, to_native(e)))

        try:
            data = json.loads(to_text(return_data.read(), errors='surrogate_or_strict'))
        except Exception as e:
            raise AnsibleError("Could not process data from the API server (%s): %s " % (url, to_native(e)))

        return data

    @g_connect
    def authenticate(self, github_token):
        """
        Retrieve an authentication token
        """
        url = _urljoin(self.baseurl, "tokens")
        args = urlencode({"github_token": github_token})
        resp = open_url(url, data=args, validate_certs=self.validate_certs, method="POST")
        data = json.loads(to_text(resp.read(), errors='surrogate_or_strict'))
        return data

    @g_connect
    def create_import_task(self, github_user, github_repo, reference=None, role_name=None):
        """
        Post an import request
        """
        url = _urljoin(self.baseurl, "imports")
        args = {
            "github_user": github_user,
            "github_repo": github_repo,
            "github_reference": reference if reference else ""
        }
        if role_name:
            args['alternate_role_name'] = role_name
        elif github_repo.startswith('ansible-role'):
            args['alternate_role_name'] = github_repo[len('ansible-role') + 1:]
        data = self.__call_galaxy(url, args=urlencode(args), method="POST")
        if data.get('results', None):
            return data['results']
        return data

    @g_connect
    def get_import_task(self, task_id=None, github_user=None, github_repo=None):
        """
        Check the status of an import task.
        """
        url = _urljoin(self.baseurl, "imports")
        if task_id is not None:
            url = "%s?id=%d" % (url, task_id)
        elif github_user is not None and github_repo is not None:
            url = "%s?github_user=%s&github_repo=%s" % (url, github_user, github_repo)
        else:
            raise AnsibleError("Expected task_id or github_user and github_repo")

        data = self.__call_galaxy(url)
        return data['results']

    @g_connect
    def lookup_role_by_name(self, role_name, notify=True):
        """
        Find a role by name.
        """
        role_name = to_text(urlquote(to_bytes(role_name)))

        try:
            parts = role_name.split(".")
            user_name = ".".join(parts[0:-1])
            role_name = parts[-1]
            if notify:
                display.display("- downloading role '%s', owned by %s" % (role_name, user_name))
        except Exception:
            raise AnsibleError("Invalid role name (%s). Specify role as format: username.rolename" % role_name)

        url = _urljoin(self.baseurl, "roles", "?owner__username=%s&name=%s" % (user_name, role_name))[:-1]
        data = self.__call_galaxy(url)
        if len(data["results"]) != 0:
            return data["results"][0]
        return None

    @g_connect
    def fetch_role_related(self, related, role_id):
        """
        Fetch the list of related items for the given role.
        The url comes from the 'related' field of the role.
        """

        results = []
        try:
            url = _urljoin(self.baseurl, "roles", role_id, related, "?page_size=50")[:-1]
            data = self.__call_galaxy(url)
            results = data['results']
            done = (data.get('next_link', None) is None)
            while not done:
                url = _urljoin(self.api_server, data['next_link'])
                data = self.__call_galaxy(url)
                results += data['results']
                done = (data.get('next_link', None) is None)
        except Exception as e:
            display.vvvv("Unable to retrive role (id=%s) data (%s), but this is not fatal so we continue: %s" %
                         (role_id, related, to_text(e)))
        return results

    @g_connect
    def get_list(self, what):
        """
        Fetch the list of items specified.
        """
        try:
            url = _urljoin(self.baseurl, what, "?page_size")[:-1]
            data = self.__call_galaxy(url)
            if "results" in data:
                results = data['results']
            else:
                results = data
            done = True
            if "next" in data:
                done = (data.get('next_link', None) is None)
            while not done:
                url = _urljoin(self.api_server, data['next_link'])
                data = self.__call_galaxy(url)
                results += data['results']
                done = (data.get('next_link', None) is None)
            return results
        except Exception as error:
            raise AnsibleError("Failed to download the %s list: %s" % (what, to_native(error)))

    @g_connect
    def search_roles(self, search, **kwargs):

        search_url = _urljoin(self.baseurl, "search", "roles", "?")[:-1]

        if search:
            search_url += '&autocomplete=' + to_text(urlquote(to_bytes(search)))

        tags = kwargs.get('tags', None)
        platforms = kwargs.get('platforms', None)
        page_size = kwargs.get('page_size', None)
        author = kwargs.get('author', None)

        if tags and isinstance(tags, string_types):
            tags = tags.split(',')
            search_url += '&tags_autocomplete=' + '+'.join(tags)

        if platforms and isinstance(platforms, string_types):
            platforms = platforms.split(',')
            search_url += '&platforms_autocomplete=' + '+'.join(platforms)

        if page_size:
            search_url += '&page_size=%s' % page_size

        if author:
            search_url += '&username_autocomplete=%s' % author

        data = self.__call_galaxy(search_url)
        return data

    @g_connect
    def add_secret(self, source, github_user, github_repo, secret):
        url = _urljoin(self.baseurl, "notification_secrets")
        args = urlencode({
            "source": source,
            "github_user": github_user,
            "github_repo": github_repo,
            "secret": secret
        })
        data = self.__call_galaxy(url, args=args, method="POST")
        return data

    @g_connect
    def list_secrets(self):
        url = _urljoin(self.baseurl, "notification_secrets")
        data = self.__call_galaxy(url, headers=self._auth_header())
        return data

    @g_connect
    def remove_secret(self, secret_id):
        url = _urljoin(self.baseurl, "notification_secrets", secret_id)
        data = self.__call_galaxy(url, headers=self._auth_header(), method='DELETE')
        return data

    @g_connect
    def delete_role(self, github_user, github_repo):
        url = _urljoin(self.baseurl, "removerole", "?github_user=%s&github_repo=%s" % (github_user, github_repo))[:-1]
        data = self.__call_galaxy(url, headers=self._auth_header(), method='DELETE')
        return data

    @g_connect
    def publish_collection_artifact(self, b_collection_artifact_path):

        headers = {}
        headers.update(self._auth_header())

        n_url = _urljoin(self.api_server, 'api', 'v2', 'collections')
        if 'v3' in self.available_api_versions:
            n_url = _urljoin(self.api_server, 'api', 'v3', 'artifacts', 'collections')

        data, content_type = _get_mime_data(b_collection_artifact_path)
        headers.update({
            'Content-type': content_type,
            'Content-length': len(data),
        })

        error_context_msg = "Error when publishing collection to %s (%s)" % (self.name, self.api_server)
        response_data = self.__call_galaxy(n_url, args=data, headers=headers, method='POST',
                                           error_context_msg=error_context_msg)
        return response_data


def handle_http_error(http_error, api, context_error_message):
    try:
        err_info = json.load(http_error)
    except (AttributeError, ValueError):
        err_info = {}

    if 'v3' in api.available_api_versions:
        message_lines = []
        errors = err_info.get('errors', None)

        if not errors:
            errors = [{'detail': 'Unknown error returned by Galaxy server.',
                       'code': 'Unknown'}]

        for error in errors:
            error_msg = error.get('detail') or error.get('title') or 'Unknown error returned by Galaxy server.'
            error_code = error.get('code') or 'Unknown'
            message_line = "(HTTP Code: %d, Message: %s Code: %s)" % (http_error.code, error_msg, error_code)
            message_lines.append(message_line)

        full_error_msg = "%s %s" % (context_error_message, ', '.join(message_lines))
        raise AnsibleError(full_error_msg)

    if 'v2' in api.available_api_versions:
        code = to_native(err_info.get('code', 'Unknown'))
        message = to_native(err_info.get('message', 'Unknown error returned by Galaxy server.'))
        full_error_msg = "%s (HTTP Code: %d, Message: %s Code: %s)" \
            % (context_error_message, http_error.code, message, code)
        raise AnsibleError(full_error_msg)

    # v1 style errors
    # res = json.loads(to_text(http_error.fp.read(), errors='surrogate_or_strict'))
    raise AnsibleError(err_info.get('detail', 'Unknown error'))


def _get_mime_data(b_collection_path):
    with open(b_collection_path, 'rb') as collection_tar:
        data = collection_tar.read()

    boundary = '--------------------------%s' % uuid.uuid4().hex
    b_file_name = os.path.basename(b_collection_path)
    part_boundary = b"--" + to_bytes(boundary, errors='surrogate_or_strict')

    form = [
        part_boundary,
        b"Content-Disposition: form-data; name=\"sha256\"",
        to_bytes(secure_hash_s(data), errors='surrogate_or_strict'),
        part_boundary,
        b"Content-Disposition: file; name=\"file\"; filename=\"%s\"" % b_file_name,
        b"Content-Type: application/octet-stream",
        b"",
        data,
        b"%s--" % part_boundary,
    ]

    content_type = 'multipart/form-data; boundary=%s' % boundary

    return b"\r\n".join(form), content_type
