#!/usr/bin/env python
# (c) 2012, Jan-Piet Mens <jpmens () gmail.com>
# (c) 2012-2014, Michael DeHaan <michael@ansible.com> and others
# (c) 2017 Ansible Project
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

from __future__ import absolute_import, division, print_function
__metaclass__ = type


import datetime
import glob
import optparse
import os
import pprint
import random
import re
import sys
import warnings
from collections import defaultdict
try:
    from html import escape as html_escape
except ImportError:
    # Python-3.2 or later
    import cgi

    def html_escape(text, quote=True):
        return cgi.escape(text, quote)

import yaml
from jinja2 import Environment, FileSystemLoader
from six import iteritems, string_types

from ansible.errors import AnsibleError
from ansible.module_utils._text import to_bytes
from ansible.utils import plugin_docs


#####################################################################################
# constants and paths

# if a module is added in a version of Ansible older than this, don't print the version added information
# in the module documentation because everyone is assumed to be running something newer than this already.
TO_OLD_TO_BE_NOTABLE = 1.3

# Get parent directory of the directory this script lives in
MODULEDIR = os.path.abspath(os.path.join(
    os.path.dirname(os.path.realpath(__file__)), os.pardir, 'lib', 'ansible', 'modules'
))

# The name of the DOCUMENTATION template
EXAMPLE_YAML = os.path.abspath(os.path.join(
    os.path.dirname(os.path.realpath(__file__)), os.pardir, 'examples', 'DOCUMENTATION.yml'
))

_ITALIC = re.compile(r"I\(([^)]+)\)")
_BOLD = re.compile(r"B\(([^)]+)\)")
_MODULE = re.compile(r"M\(([^)]+)\)")
_URL = re.compile(r"U\(([^)]+)\)")
_CONST = re.compile(r"C\(([^)]+)\)")

DEPRECATED = b" (D)"


def rst_ify(text):
    ''' convert symbols like I(this is in italics) to valid restructured text '''

    try:
        t = _ITALIC.sub(r'*' + r"\1" + r"*", text)
        t = _BOLD.sub(r'**' + r"\1" + r"**", t)
        t = _MODULE.sub(r':ref:`' + r"\1 <module_\1>" + r"`", t)
        t = _URL.sub(r"\1", t)
        t = _CONST.sub(r'``' + r"\1" + r"``", t)
    except Exception as e:
        raise AnsibleError("Could not process (%s) : %s" % (str(text), str(e)))

    return t


def html_ify(text):
    ''' convert symbols like I(this is in italics) to valid HTML '''

    t = html_escape(text)
    t = _ITALIC.sub("<em>" + r"\1" + "</em>", t)
    t = _BOLD.sub("<b>" + r"\1" + "</b>", t)
    t = _MODULE.sub("<span class='module'>" + r"\1" + "</span>", t)
    t = _URL.sub("<a href='" + r"\1" + "'>" + r"\1" + "</a>", t)
    t = _CONST.sub("<code>" + r"\1" + "</code>", t)

    return t


def rst_fmt(text, fmt):
    ''' helper for Jinja2 to do format strings '''

    return fmt % (text)


def rst_xline(width, char="="):
    ''' return a restructured text line of a given length '''

    return char * width


def write_data(text, output_dir, outputname, module=None):
    ''' dumps module output to a file or the screen, as requested '''

    if output_dir is not None:
        if module:
            outputname = outputname % module

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        fname = os.path.join(output_dir, outputname)
        fname = fname.replace(".py", "")
        with open(fname, 'wb') as f:
            f.write(to_bytes(text))
    else:
        print(text)


def n_modules_per_dir(path_list, mods_per_dir=None):
    mods_per_dir = mods_per_dir or 15

    dirnames = defaultdict(list)
    for path in path_list:
        # print('path: %s' % path)
        basename = os.path.basename(path)
        dirname = os.path.dirname(path)

        dirnames[dirname].append(basename)

    filtered_list = []
    # pprint.pprint(dict(dirnames))
    for dirname, basenames in dirnames.items():
        for idx, basename in enumerate(basenames):
            if idx < mods_per_dir:
                path = os.path.join(dirname, basename)
                # print('adding %s' % path)
                filtered_list.append(path)

    print('num of mods post n_modules_per_dir(%s): %s' % (mods_per_dir, len(filtered_list)))
    return filtered_list


def shuffle_path_list(path_list):
    random.shuffle(path_list)
    return path_list


def first_n_modules(path_list, num_of_modules=None):
    num_of_modules = num_of_modules or 150
    filtered_list = path_list[0:num_of_modules]
    print('num of mods post first_n_modules(%s): %s' % (num_of_modules, len(filtered_list)))
    return filtered_list


def filter_module_list(path_list, module_dir=None):
    '''filter out modules by path

    in: path_list
    out: path_list we care about
    '''
    mods_per_dir = 1000
    if module_dir == '../../lib/ansible/modules':
        filtered_list = n_modules_per_dir(path_list, mods_per_dir=mods_per_dir)
        filtered_list = first_n_modules(filtered_list, num_of_modules=5000)

    if module_dir == '../../lib/ansible/plugins':
        filtered_list = n_modules_per_dir(path_list, mods_per_dir=1000)
        filtered_list = first_n_modules(filtered_list, num_of_modules=600)
    print('filtered all but %s paths from %s' % (len(filtered_list), module_dir))
    return filtered_list
    # return path_list


def get_module_info(module_dir, limit_to_modules=None, verbose=False):
    '''
    Returns information about modules and the categories that they belong to

    :arg module_dir: file system path to the top of the modules directory
    :kwarg limit_to_modules: If given, this is a list of module names to
        generate information for.  All other modules will be ignored.
    :returns: Tuple of two dicts containing module_info, categories, and
        aliases and a set listing deprecated modules:

        :module_info: mapping of module names to information about them.  The fields of the dict are:

            :path: filesystem path to the module
            :deprecated: boolean.  True means the module is deprecated otherwise not.
            :aliases: set of aliases to this module name
            :metadata: The modules metadata (as recorded in the module)
            :doc: The documentation structure for the module
            :examples: The module's examples
            :returndocs: The module's returndocs

        :categories: maps category names to a dict.  The dict contains at
            least one key, '_modules' which contains a list of module names in
            that category.  Any other keys in the dict are subcategories with
            the same structure.

    '''

    categories = dict()
    module_info = defaultdict(dict)
    modules_without_docs = []
    modules_without_metadata = []

    # * windows powershell modules have documentation stubs in python docstring
    #   format (they are not executed) so skip the ps1 format files
    # * One glob level for every module level that we're going to traverse
    files = (
        glob.glob("%s/*.py" % module_dir) +
        glob.glob("%s/*/*.py" % module_dir) +
        glob.glob("%s/*/*/*.py" % module_dir) +
        glob.glob("%s/*/*/*/*.py" % module_dir)
    )

    # print('module_dir: %s' % module_dir)
    # pprint.pprint(('files', files))
    path_list = []
    for module_path in files:
        # Do not list __init__.py files
        if module_path.endswith('__init__.py'):
            continue

        # Do not list blacklisted modules
        module = os.path.splitext(os.path.basename(module_path))[0]
        if module in plugin_docs.BLACKLIST['MODULE'] or module == 'base':
            continue

        # If requested, limit module documentation building only to passed-in
        # modules.
        if limit_to_modules is not None and module.lower() not in limit_to_modules:
            continue
        path_list.append(module_path)

    path_list = filter_module_list(path_list, module_dir=module_dir)

    for module_path in sorted(path_list):
        module = os.path.splitext(os.path.basename(module_path))[0]
        deprecated = False
        if module.startswith("_"):
            if os.path.islink(module_path):
                # Handle aliases
                source = os.path.splitext(os.path.basename(os.path.realpath(module_path)))[0]
                module = module.replace("_", "", 1)
                aliases = module_info[source].get('aliases', set())
                aliases.add(module)
                # In case we just created this via get()'s fallback
                module_info[source]['aliases'] = aliases
                continue
            else:
                # Handle deprecations
                module = module.replace("_", "", 1)
                deprecated = True

        #
        # Regular module to process
        #

        # print('loading info for %s' % module_path)

        category = categories

        # Start at the second directory because we don't want the "vendor"
        mod_path_only = os.path.dirname(module_path[len(module_dir):])

        module_categories = []
        # build up the categories that this module belongs to
        for new_cat in mod_path_only.split('/')[1:]:
            if new_cat not in category:
                category[new_cat] = dict()
                category[new_cat]['_modules'] = []
            module_categories.append(new_cat)
            category = category[new_cat]

        category['_modules'].append(module)

        # the category we will use in links (so list_of_all_plugins can point to plugins/action_plugins/*'
        if module_categories:
            primary_category = module_categories[0]

        # use ansible core library to parse out doc metadata YAML and plaintext examples
        try:
            doc, examples, returndocs, metadata = plugin_docs.get_docstring(module_path, verbose=verbose,
                                                                            ignore_errors=False)
        except Exception as e:
            print('error reading %s' % module_path)
            raise

        if doc is None:
            modules_without_docs.append(module_path)
        if metadata is None:
            modules_without_metadata.append(module_path)

        # save all the information
        module_info[module] = {'path': module_path,
                               'deprecated': deprecated,
                               'aliases': set(),
                               'metadata': metadata,
                               'doc': doc,
                               'examples': examples,
                               'returndocs': returndocs,
                               'categories': module_categories,
                               'primary_category': primary_category,
                               }

    # keep module tests out of becoming module docs
    if 'test' in categories:
        del categories['test']

    for module_warn in modules_without_docs:
        print('%s:no documentation found in module' % module_warn)
    for module_warn in modules_without_metadata:
        print('%s:no metadata found in module' % module_warn)

    return module_info, categories


def generate_parser():
    ''' generate an optparse parser '''

    p = optparse.OptionParser(
        version='%prog 1.0',
        usage='usage: %prog [options] arg1 arg2',
        description='Generate module documentation from metadata',
    )

    p.add_option("-A", "--ansible-version", action="store", dest="ansible_version", default="unknown", help="Ansible version number")
    p.add_option("-M", "--module-dir", action="store", dest="module_dir", default=MODULEDIR, help="Ansible library path")
    p.add_option("-P", "--plugin-type", action="store", dest="plugin_type", default='modules', help="The type of plugin (plugins, modules)")
    p.add_option("-T", "--template-dir", action="store", dest="template_dir", default="hacking/templates", help="directory containing Jinja2 templates")
    p.add_option("-t", "--type", action='store', dest='type', choices=['rst'], default='rst', help="Document type")
    p.add_option("-v", "--verbose", action='store_true', default=False, help="Verbose")
    p.add_option("-o", "--output-dir", action="store", dest="output_dir", default=None, help="Output directory for module files")
    p.add_option("-I", "--includes-file", action="store", dest="includes_file", default=None, help="Create a file containing list of processed modules")
    p.add_option("-l", "--limit-to-modules", action="store", dest="limit_to_modules", default=None,
                 help="Limit building module documentation to comma-separated list of modules. Specify non-existing module name for no modules.")
    p.add_option('-V', action='version', help='Show version number and exit')
    return p


def jinja2_environment(template_dir, typ, plugin_type):

    env = Environment(loader=FileSystemLoader(template_dir),
                      variable_start_string="@{",
                      variable_end_string="}@",
                      trim_blocks=True)
    env.globals['xline'] = rst_xline

    templates = {}
    if typ == 'rst':
        env.filters['convert_symbols_to_format'] = rst_ify
        env.filters['html_ify'] = html_ify
        env.filters['fmt'] = rst_fmt
        env.filters['xline'] = rst_xline
        templates['plugin'] = env.get_template('plugin.rst.j2')
        templates['category_list'] = env.get_template('%s_by_category.rst.j2' % plugin_type)
        templates['support_list'] = env.get_template('%s_by_support.rst.j2' % plugin_type)
        templates['list_of_CATEGORY_modules'] = env.get_template('list_of_CATEGORY_%s.rst.j2' % plugin_type)
    else:
        raise Exception("unknown module format type: %s" % typ)

    return templates


def too_old(added):
    if not added:
        return False
    try:
        added_tokens = str(added).split(".")
        readded = added_tokens[0] + "." + added_tokens[1]
        added_float = float(readded)
    except ValueError as e:
        warnings.warn("Could not parse %s: %s" % (added, str(e)))
        return False
    return added_float < TO_OLD_TO_BE_NOTABLE


def process_modules(module_map, templates, outputname, output_dir, ansible_version, plugin_type):
    for module in module_map:
        # print("rendering: %s" % module)

        # pprint.pprint(('process_modules module:', module))

        fname = module_map[module]['path']

        # pprint.pprint(('process_modules module_info: ', module_map[module]))

        module_categories = module_map[module].get('categories', [])

        # crash if module is missing documentation and not explicitly hidden from docs index
        if module_map[module]['doc'] is None:
            # print("%s: ERROR: MODULE MISSING DOCUMENTATION" % (fname,))
            _doc = {'module': module,
                    'version_added': '2.4',
                    'filename': fname}
            module_map[module]['doc'] = _doc
            # continue

        # Going to reference this heavily so make a short name to reference it by
        doc = module_map[module]['doc']

        # pprint.pprint(('process_modules doc: ', doc))

        # add some defaults for plugins that dont have most of the info
        doc['module'] = doc.get('module', module)
        doc['version_added'] = doc.get('version_added', 'historical')

        doc['plugin_type'] = plugin_type
        if plugin_type == 'modules':
            doc['plugin_namespace'] = 'module'
        else:
            doc['plugin_namespace'] = '%s_plugin' % module_map[module]['primary_category']

        if module_map[module]['deprecated'] and 'deprecated' not in doc:
            print("%s:no deprecation documentation found: %s" % (fname, 'deprecated'))

        required_fields = ('short_description', 'description', 'version_added')
        for field in required_fields:
            if field not in doc:
                print("%s:required field '%s' is missing" % (fname, field))

        not_nullable_fields = ('short_description',)
        for field in not_nullable_fields:
            if field in doc and doc[field] in (None, ''):
                print("%s:documentation field '%s' is null/empty value=%s" % (fname, field, doc[field]))

        if 'version_added' not in doc:
            pprint.pprint(doc)
            print("%s:missing version_added in: %s ***\n" % (fname, module))

        #
        # The present template gets everything from doc so we spend most of this
        # function moving data into doc for the template to reference
        #

        if module_map[module]['aliases']:
            doc['aliases'] = module_map[module]['aliases']

        # don't show version added information if it's too old to be called out
        added = 0
        if doc['version_added'] == 'historical':
            del doc['version_added']
        else:
            added = doc['version_added']

        # Strip old version_added for the module
        if too_old(added):
            del doc['version_added']

        option_names = []

        if 'options' in doc and doc['options']:
            for (k, v) in iteritems(doc['options']):
                # Error out if there's no description
                if 'description' not in doc['options'][k]:
                    # raise AnsibleError("Missing required description for option %s in %s " % (k, module))
                    print("%s:missing required description for option %s in %s " % (fname, k, module))
                    continue

                # Error out if required isn't a boolean (people have been putting
                # information on when something is required in here.  Those need
                # to go in the description instead).
                required_value = doc['options'][k].get('required', False)
                if not isinstance(required_value, bool):
                    raise AnsibleError("Invalid required value '%s' for option '%s' in '%s' (must be truthy)" % (required_value, k, module))

                # Strip old version_added information for options
                if 'version_added' in doc['options'][k] and too_old(doc['options'][k]['version_added']):
                    del doc['options'][k]['version_added']

                # Make sure description is a list of lines for later formatting
                if not isinstance(doc['options'][k]['description'], list):
                    doc['options'][k]['description'] = [doc['options'][k]['description']]

                option_names.append(k)

        option_names.sort()

        doc['option_keys'] = option_names
        doc['filename'] = fname
        doc['docuri'] = doc['module'].replace('_', '-')
        doc['now_date'] = datetime.date.today().strftime('%Y-%m-%d')
        doc['ansible_version'] = ansible_version

        # check the 'deprecated' field in doc. We expect a dict potentially with 'why', 'version', and 'alternative' fields
        examples = module_map[module]['examples']
        # print('\n\n%s: type of examples: %s\n' % (module, type(examples)))
        if examples and not isinstance(examples, (str, unicode, list)):
            raise TypeError('module %s examples is wrong type (%s): %s' % (module, type(examples), examples))

        # use 'examples' for 'plainexamples' if 'examples' is a string
        if isinstance(module_map[module]['examples'], string_types):
            doc['plainexamples'] = module_map[module]['examples']  # plain text
        else:
            doc['plainexamples'] = ''

        doc['metadata'] = module_map[module]['metadata']

        # pprint.pprint(module_map[module]
        if module_map[module]['returndocs']:
            try:
                doc['returndocs'] = yaml.safe_load(module_map[module]['returndocs'])
            except Exception as e:
                print("%s:%s:yaml error:%s:returndocs=%s" % (fname, module, e, module_map[module]['returndocs']))
                doc['returndocs'] = None
        else:
            doc['returndocs'] = None

        doc['author'] = doc.get('author', ['UNKNOWN'])
        if isinstance(doc['author'], string_types):
            doc['author'] = [doc['author']]

        # print('about to template')
        # if plugin_type == 'modules':
        #    pprint.pprint(doc)
        text = templates['plugin'].render(doc)

        # plugins get namespace dirs but modules do not
        if plugin_type == 'plugins':
            for module_category in module_categories:
                category_output_dir = os.path.join(output_dir, 'plugins', '%s' % module_category)
                write_data(text, category_output_dir, outputname, module)
        else:
                write_data(text, output_dir, outputname, module)


def process_categories(mod_info, categories, templates,
                       output_dir, output_name, plugin_type):
    # pprint.pprint(('categories', categories))
    for category in sorted(categories.keys()):
        if (plugin_type, category) == ('plugins', ''):
            print('skipping unknown cat: %s' % category)
            continue
        module_map = categories[category]
        category_filename = output_name % category

        print("*** recording category %s in %s ***" % (category, category_filename))

        # start a new category file

        category_name = category.replace("_", " ")
        category_title = category_name.title()

        # subcategories = dict((k, v) for k, v in module_map.items() if k != '_modules')
        subcategories = dict((k, v) for k, v in module_map.items() if k != '_modules')
        # add the 'other' to a subcat with same name as parent cat
        # subcategories[category] = {'_modules': module_map.pop('_modules')}
        subcategories[category] = {'_modules': module_map['_modules']}

        # add a same name subcat if there are no real subcat
        # ie, list_of_monitoring_modules gets a 'monitoring' subcat
        # so all toctree entrees are at the same level
        if not subcategories:
            subcategories[category] = {'_modules': module_map['_modules']}
        # pprint.pprint(('subcat of', category_name,  subcategories))

        template_data = {'title': category_title,
                         'category_name': category_name,
                         'category_label': category,
                         'category': module_map,
                         'categories': categories,
                         'subcategories': subcategories,
                         'module_info': mod_info,
                         'plugin_type': plugin_type
                         }

        text = templates['list_of_CATEGORY_modules'].render(template_data)
        write_data(text, output_dir, category_filename)


def process_support_levels(mod_info, templates, output_dir, plugin_type):
    supported_by = {'Ansible Core Team': {'slug': 'core_supported',
                                          'modules': [],
                                          'output': '%s_core_maintained.rst',
                                          'blurb': "These are :doc:`modules maintained by the"
                                                   " Ansible Core Team<core_maintained>` and will always ship"
                                                   " with Ansible itself."},
                    'Ansible Network Team': {'slug': 'network_supported',
                                             'modules': [],
                                             'output': '%s_network_maintained.rst',
                                             'blurb': "These are :doc:`modules maintained by the"
                                                      " Ansible Network Team<network_maintained>` in"
                                                      " a relationship similar to how the Ansible Core Team"
                                                      " maintains the Core modules."},
                    'Ansible Partners': {'slug': 'partner_supported',
                                         'modules': [],
                                         'output': '%s_partner_maintained.rst',
                                         'blurb': """
Some examples of :doc:`Certified Modules<partner_maintained>` are those submitted by other
companies. Maintainers of these types of modules must watch for any issues reported or pull requests
raised against the module.

The Ansible Core Team will review all modules becoming certified.  Core committers will review
proposed changes to existing Certified Modules once the community maintainers of the module have
approved the changes. Core committers will also ensure that any issues that arise due to Ansible
engine changes will be remediated.  Also, it is strongly recommended (but not presently required)
for these types of modules to have unit tests.

These modules are currently shipped with Ansible, but might be shipped separately in the future.
"""},
                    'Ansible Community': {'slug': 'community_supported',
                                          'modules': [],
                                          'output': '%s_community_maintained.rst',
                                          'blurb': """
These are :doc:`modules maintained by the Ansible Community<community_maintained>`.  They **are
not** supported by the Ansible Core Team or by companies/partners associated to the module.

They are still fully usable, but the response rate to issues is purely up to the community.  Best
effort support will be provided but is not covered under any support contracts.

These modules are currently shipped with Ansible, but will most likely be shipped separately in the future.
                                          """},
                    }

    # only gen support pages for modules for now, need to split and namespace templates and generated docs
    if plugin_type == 'plugins':
        return
    # Separate the modules by support_level
    for module, info in mod_info.items():
        if not info.get('metadata', None):
            print('no metadata for %s' % module)
            continue
        if info['metadata']['supported_by'] == 'core':
            supported_by['Ansible Core Team']['modules'].append(module)
        elif info['metadata']['supported_by'] == 'network':
            supported_by['Ansible Network Team']['modules'].append(module)
        elif info['metadata']['supported_by'] == 'certified':
            supported_by['Ansible Partners']['modules'].append(module)
        elif info['metadata']['supported_by'] == 'community':
            supported_by['Ansible Community']['modules'].append(module)
        else:
            raise AnsibleError('Unknown supported_by value: %s' % info['metadata']['supported_by'])

    # Render the module lists
    for maintainers, data in supported_by.items():
        template_data = {'maintainers': maintainers,
                         'modules': data['modules'],
                         'slug': data['slug'],
                         'module_info': mod_info,
                         }
        text = templates['support_list'].render(template_data)
        output_name = data['output'] % plugin_type
        write_data(text, output_dir, output_name)


def validate_options(options):
    ''' validate option parser options '''

    if not options.module_dir:
        sys.exit("--module-dir is required", file=sys.stderr)
    if not os.path.exists(options.module_dir):
        sys.exit("--module-dir does not exist: %s" % options.module_dir, file=sys.stderr)
    if not options.template_dir:
        sys.exit("--template-dir must be specified")


def main():

    p = generate_parser()

    (options, args) = p.parse_args()
    validate_options(options)

    plugin_type = options.plugin_type

    if plugin_type == 'modules':
        templates = jinja2_environment(options.template_dir, options.type, plugin_type)
        output_dir = options.output_dir
        # trim trailing s off of plugin_type for plugin_type=='modules'. ie 'copy_module.rst'
        outputname = '%s_' + '%s.rst' % plugin_type[:-1]
    else:
        templates = jinja2_environment(options.template_dir, options.type, 'plugins')
        # for plugins, just use 'ssh.rst' vs 'ssh_module.rst'
        outputname = '%s.rst'
        output_dir = '%s/plugins/%s' % (options.output_dir, plugin_type)

    # Convert passed-in limit_to_modules to None or list of modules.
    if options.limit_to_modules is not None:
        options.limit_to_modules = [s.lower() for s in options.limit_to_modules.split(",")]

    mod_info, categories = get_module_info(options.module_dir, limit_to_modules=options.limit_to_modules, verbose=options.verbose)

    categories['all'] = {'_modules': mod_info.keys()}

    # pprint.pprint(categories)
    # pprint.pprint(mod_info)
    # pprint.pprint(dict(mod_info))
    # Transform the data
    if options.type == 'rst':
        for key, record in mod_info.items():
            # pprint.pprint(('record', record))
            if record.get('doc', None):
                short_desc = record['doc']['short_description']
                if short_desc is None:
                    print('WARNING: short_description for %s is None' % key)
                    short_desc = ''
                record['doc']['short_description'] = rst_ify(short_desc)

    if plugin_type == 'modules':
        # Write master category list
        category_list_text = templates['category_list'].render(categories=sorted(categories.keys()))
        category_index_name = '%s_by_category.rst' % plugin_type
        write_data(category_list_text, output_dir, category_index_name)

    # Render all the individual module pages
    process_modules(mod_info, templates, outputname, output_dir, options.ansible_version, plugin_type)

    # Render all the categories for modules
    if plugin_type == 'modules':
        category_list_name_template = 'list_of_%s_' + '%s.rst' % plugin_type
        process_categories(mod_info, categories, templates, output_dir, category_list_name_template, plugin_type)

        # Render all the categories for modules
        process_support_levels(mod_info, templates, output_dir, plugin_type)


if __name__ == '__main__':
    main()
