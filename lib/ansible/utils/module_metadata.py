#
# (c) 2016-2017, Toshio Kuratomi <tkuratomi@ansible.com>
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

# Make coding more python3-ish
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import ast
import csv
import os
from collections import defaultdict
from distutils.version import StrictVersion

import yaml

from ansible.module_utils._text import to_text


# There's a few files that are not new-style modules.  Have to blacklist them
NONMODULE_PY_FILES = frozenset(('async_wrapper.py',))
NONMODULE_MODULE_NAMES = frozenset(os.path.splitext(p)[0] for p in NONMODULE_PY_FILES)

# Default metadata
DEFAULT_METADATA = {'metadata_version': '1.0',
                    'status': ['preview'],
                    'supported_by': 'community'}


class ParseError(Exception):
    """Thrown when parsing a file fails"""
    pass


class MissingModuleError(Exception):
    """Thrown when unable to find a plugin"""
    pass


def seek_end_of_dict(module_data, start_line, start_col, next_node_line, next_node_col):
    """Look for the end of a dict in a set of lines

    We know the starting position of the dict and we know the start of the
    next code node but in between there may be multiple newlines and comments.
    There may also be multiple python statements on the same line (separated
    by semicolons)

    Examples::
        ANSIBLE_METADATA = {[..]}
        DOCUMENTATION = [..]

        ANSIBLE_METADATA = {[..]} # Optional comments with confusing junk => {}
        # Optional comments {}
        DOCUMENTATION = [..]

        ANSIBLE_METADATA = {
            [..]
            }
        # Optional comments {}
        DOCUMENTATION = [..]

        ANSIBLE_METADATA = {[..]} ; DOCUMENTATION = [..]

        ANSIBLE_METADATA = {}EOF
    """
    if next_node_line is None:
        # The dict is the last statement in the file
        snippet = module_data.splitlines()[start_line:]
        next_node_col = 0
        # Include the last line in the file
        last_line_offset = 0
    else:
        # It's somewhere in the middle so we need to separate it from the rest
        snippet = module_data.splitlines()[start_line:next_node_line]
        # Do not include the last line because that's where the next node
        # starts
        last_line_offset = 1

    if next_node_col == 0:
        # This handles all variants where there are only comments and blank
        # lines between the dict and the next code node

        # Step backwards through all the lines in the snippet
        for line_idx, line in tuple(reversed(tuple(enumerate(snippet))))[last_line_offset:]:
            end_col = None
            # Step backwards through all the characters in the line
            for col_idx, char in reversed(tuple(enumerate(c for c in line))):
                if char == '}' and end_col is None:
                    # Potentially found the end of the dict
                    end_col = col_idx

                elif char == '#' and end_col is not None:
                    # The previous '}' was part of a comment.  Keep trying
                    end_col = None

            if end_col is not None:
                # Found the end!
                end_line = start_line + line_idx
                break
    else:
        # Harder cases involving multiple statements on one line
        # Good Ansible Module style doesn't do this so we're just going to
        # treat this as an error for now:
        raise ParseError('Multiple statements per line confuses the module metadata parser.')

    return end_line, end_col


def seek_end_of_string(module_data, start_line, start_col, next_node_line, next_node_col):
    """
    This is much trickier than finding the end of a dict.  A dict has only one
    ending character, "}".  Strings have four potential ending characters.  We
    have to parse the beginning of the string to determine what the ending
    character will be.

    Examples:
        ANSIBLE_METADATA = '''[..]''' # Optional comment with confusing chars '''
        # Optional comment with confusing chars '''
        DOCUMENTATION = [..]

        ANSIBLE_METADATA = '''
            [..]
            '''
        DOCUMENTATIONS = [..]

        ANSIBLE_METADATA = '''[..]''' ; DOCUMENTATION = [..]

        SHORT_NAME = ANSIBLE_METADATA = '''[..]''' ; DOCUMENTATION = [..]

    String marker variants:
        * '[..]'
        * "[..]"
        * '''[..]'''
        * \"\"\"[..]\"\"\"

    Each of these come in u, r, and b variants:
        * '[..]'
        * u'[..]'
        * b'[..]'
        * r'[..]'
        * ur'[..]'
        * ru'[..]'
        * br'[..]'
        * b'[..]'
        * rb'[..]'
    """
    raise NotImplementedError('Finding end of string not yet implemented')


def extract_metadata(module_data):
    """Extract the metadata from a module

    :arg module_data: Byte string containing a module's code
    :returns: a tuple of metadata (a dict), line the metadata starts on,
        column the metadata starts on, line the metadata ends on, column the
        metadata ends on, and the names the metadata is assigned to.  One of
        the names the metadata is assigned to will be ANSIBLE_METADATA If no
        metadata is found, the tuple will be (None, -1, -1, -1, -1, None)
    """
    metadata = None
    start_line = -1
    start_col = -1
    end_line = -1
    end_col = -1
    targets = None
    mod_ast_tree = ast.parse(module_data)
    for root_idx, child in enumerate(mod_ast_tree.body):
        if isinstance(child, ast.Assign):
            for target in child.targets:
                if target.id == 'ANSIBLE_METADATA':
                    if isinstance(child.value, ast.Dict):
                        metadata = ast.literal_eval(child.value)

                        try:
                            # Determine where the next node starts
                            next_node = mod_ast_tree.body[root_idx + 1]
                            next_lineno = next_node.lineno
                            next_col_offset = next_node.col_offset
                        except IndexError:
                            # Metadata is defined in the last node of the file
                            next_lineno = None
                            next_col_offset = None

                        # Determine where the current metadata ends
                        end_line, end_col = seek_end_of_dict(module_data,
                                child.lineno - 1, child.col_offset, next_lineno,
                                next_col_offset)

                    elif isinstance(child.value, ast.Str):
                        metadata = yaml.safe_load(child.value.s)
                        end_line = seek_end_of_string(module_data)
                    elif isinstance(child.value, ast.Bytes):
                        metadata = yaml.safe_load(to_text(child.value.s, errors='surrogate_or_strict'))
                        end_line = seek_end_of_string(module_data)
                    else:
                        # Example:
                        #   ANSIBLE_METADATA = 'junk'
                        #   ANSIBLE_METADATA = { [..the real metadata..] }
                        continue

                    # Do these after the if-else so we don't pollute them in
                    # case this was a false positive
                    start_line = child.lineno - 1
                    start_col = child.col_offset
                    targets = [t.id for t in child.targets]
                    break

        if metadata is not None:
            # Once we've found the metadata we're done
            break

    return metadata, start_line, start_col, end_line, end_col, targets


def find_documentation(module_data):
    """Find the DOCUMENTATION metadata for a module file"""
    start_line = -1
    mod_ast_tree = ast.parse(module_data)
    for child in mod_ast_tree.body:
        if isinstance(child, ast.Assign):
            for target in child.targets:
                if target.id == 'DOCUMENTATION':
                    start_line = child.lineno - 1
                    break

    return start_line


def parse_assigned_metadata_initial(csvfile):
    """
    Fields:
        :0: Module name
        :1: Core (x if so)
        :2: Extras (x if so)
        :3: Category
        :4: Supported/SLA
        :5: Curated
        :6: Stable
        :7: Deprecated
        :8: Notes
        :9: Team Notes
        :10: Notes 2
        :11: final supported_by field
    """
    with open(csvfile, 'rb') as f:
        for record in csv.reader(f):
            module = record[0]

            if record[12] == 'core':
                supported_by = 'core'
            elif record[12] == 'curated':
                supported_by = 'curated'
            elif record[12] == 'community':
                supported_by = 'community'
            else:
                print('Module %s has no supported_by field.  Using community' % record[0])
                supported_by = 'community'
                supported_by = DEFAULT_METADATA['supported_by']

            status = []
            if record[6]:
                status.append('stableinterface')
            if record[7]:
                status.append('deprecated')
            if not status:
                status.extend(DEFAULT_METADATA['status'])

            yield (module, {'version': DEFAULT_METADATA['metadata_version'], 'supported_by': supported_by, 'status': status})


def return_metadata(plugins):
    """Get the metadata for all modules

    Handle duplicate module names

    :arg plugins: List of plugins to look for
    :returns: Mapping of plugin name to metadata dictionary
    """
    metadata = {}
    for name, filename in plugins:
        # There may be several files for a module (if it is written in another
        # language, for instance) but only one of them (the .py file) should
        # contain the metadata.
        if name not in metadata or metadata[name] is not None:
            with open(filename, 'rb') as f:
                module_data = f.read()
            metadata[name] = extract_metadata(module_data)[0]
    return metadata


def metadata_summary(plugins, version=None):
    """Compile information about the metadata status for a list of modules

    :arg plugins: List of plugins to look for.  Each entry in the list is
        a tuple of (module name, full path to module)
    :kwarg version: If given, make sure the modules have this version of
        metadata or higher.
    :returns: A tuple consisting of a list of modules with no metadata at the
        required version and a list of files that have metadata at the
        required version.
    """
    no_metadata = {}
    has_metadata = {}
    supported_by = defaultdict(set)
    status = defaultdict(set)
    requested_version = StrictVersion(version)

    all_mods_metadata = return_metadata(plugins)
    for name, filename in plugins:
        # Does the module have metadata?
        if name not in no_metadata and name not in has_metadata:
            metadata = all_mods_metadata[name]
            if metadata is None:
                no_metadata[name] = filename
            elif version is not None and ('metadata_version' not in metadata or StrictVersion(metadata['metadata_version']) < requested_version):
                no_metadata[name] = filename
            else:
                has_metadata[name] = filename

        # What categories does the plugin belong in?
        if all_mods_metadata[name] is None:
            # No metadata for this module.  Use the default metadata
            supported_by[DEFAULT_METADATA['supported_by']].add(filename)
            status[DEFAULT_METADATA['status'][0]].add(filename)
        else:
            supported_by[all_mods_metadata[name]['supported_by']].add(filename)
            for one_status in all_mods_metadata[name]['status']:
                status[one_status].add(filename)

    return list(no_metadata.values()), list(has_metadata.values()), supported_by, status

#
# Filters to convert between metadata versions
#


def convert_metadata_pre_1_0_to_1_0(metadata):
    """
    Convert pre-1.0 to 1.0 metadata format

    :arg metadata: The old metadata
    :returns: The new metadata

    Changes from pre-1.0 to 1.0:
    * ``version`` field renamed to ``metadata_version``
    * ``supported_by`` field value ``unmaintained`` has been removed (change to
      ``community`` and let an external list track whether a module is unmaintained)
    * ``supported_by`` field value ``committer`` has been renamed to ``curated``
    """
    new_metadata = {'metadata_version': '1.0',
                    'supported_by': metadata['supported_by'],
                    'status': metadata['status']
                    }
    if new_metadata['supported_by'] == 'unmaintained':
        new_metadata['supported_by'] = 'community'
    elif new_metadata['supported_by'] == 'committer':
        new_metadata['supported_by'] = 'curated'

    return new_metadata
