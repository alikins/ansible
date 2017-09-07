#!/usr/bin/env python

import optparse
import os
import re
import sys
import yaml

from jinja2 import Environment, FileSystemLoader

DEFAULT_TEMPLATE_FILE = 'config.rst.j2'


def generate_parser():
    p = optparse.OptionParser(
        version='%prog 1.0',
        usage='usage: %prog [options]',
        description='Generate module documentation from metadata',
    )
    p.add_option("-t", "--template-file", action="store", dest="template_file", default=DEFAULT_TEMPLATE_FILE, help="directory containing Jinja2 templates")
    p.add_option("-o", "--output-dir", action="store", dest="output_dir", default='/tmp/', help="Output directory for rst files")
    p.add_option("-d", "--docs-source", action="store", dest="docs", default=None, help="Source for attribute docs")

    (options, args) = p.parse_args()

    return p


def fix_description(config_options, config_key):
    '''some descriptions are strings, some are lists. workaround it...'''

    description = config_options[config_key].get('description', [])
    if isinstance(description, list):
        desc_list = description
    else:
        desc_list = [description]
    # pprint.pprint(('desc_list', desc_list))
    config_options[config_key]['description'] = desc_list
    return config_options


def sluggify(text):
    # extend to know punct or better, use someone elses debugged sluggify
    return '%s' % (re.sub(r'[^\w-]', '_', text).lower().lstrip('_'))


def add_sluggified_option_names(config_options, config_key):

    # TODO:
    # if we have a label or id, use that
    # if we have ini or yaml key, try that? section.key?
    # if we have a name, try a sluggified version of the name
    name = config_options[config_key].get('name', None)
    if name is None:
        # todo: update name? maybe
        name = config_key
        slug_label = config_key
    else:
        slug_label = sluggify(name)

    config_options[config_key]['slug_label'] = slug_label
    return config_options


def fix_name(config_options, config_key):
    '''modifies config_options'''
    name = config_options[config_key].get('name', config_key)
    config_options[config_key]['name'] = name
    return config_options


def fix_ups(config_options):
    '''fix any options without a name to use the ID as the name'''
    for config_key in config_options:
        config_options = fix_description(config_options, config_key)
        config_options = fix_name(config_options, config_key)
        config_options = add_sluggified_option_names(config_options, config_key)
    return config_options


def main(args):

    parser = generate_parser()
    (options, args) = parser.parse_args()

    output_dir = os.path.abspath(options.output_dir)
    template_file_full_path = os.path.abspath(options.template_file)
    template_file = os.path.basename(template_file_full_path)
    template_dir = os.path.dirname(os.path.abspath(template_file_full_path))

    if options.docs:
        with open(options.docs) as f:
            docs = yaml.safe_load(f)
    else:
        docs = {}

    # some value validation
    fields = ['name', 'default', 'description', 'type', 'version_added', 'env', 'ini', 'yaml']
    type_names = ['boolean', 'integer', 'pathlist', 'list', 'path', 'float', 'string']
    fields_dict = {'name': (str,),
                   'default': None,
                   'description': (str, list),
                   'type': (str,),
                   'version_added': (str,),
                   'env': (list,),
                   'ini': (list,),
                   'yaml': (dict,)}
    for thing in sorted(docs):
    # for field in sorted(fields_dict):
        # for thing in sorted(docs):
        for field in sorted(fields_dict):
            field_types = fields_dict[field]
            data = docs[thing]

            if field in data:
                # print('default of "%s" is type: %s value: %s cfg type: %s' %
                #       (thing, type(data[field]),
                #        data[field], data.get('type', 'UNKNOWN')))
                if field_types is None:
                    continue
                if not isinstance(data[field], field_types):
                    print('wrong data type for field "%s" %s != %s' %
                          (field, type(data[field]), repr(field_types)))
                # if field == 'type':
                #    if data[field] not in type_names:
                #        print('the "type" field for "%s" is bogus: %s' %
                #              (thing, data[field]))
                continue

            if 'deprecated' not in data:
                print('%s: missing field "%s"' % (thing, field))
            else:
                print('%s: missing field "%s" (deprecated)' % (thing, field))
        print('')

    config_options = docs
    #config_options = fix_description(config_options)
    config_options = fix_ups(config_options)

    # FIXME: remove when format solidifies
    for thing in config_options:
        blip = config_options[thing]
        desc = blip.get('description', None)
        if not desc:
            print('No description found for %s: %s' % (thing, blip))
        if not isinstance(desc, list):
            raise Exception('Description for %s: %s was not a list' % (thing, blip))

    env = Environment(loader=FileSystemLoader(template_dir), trim_blocks=True,)
    template = env.get_template(template_file)
    output_name = os.path.join(output_dir, template_file.replace('.j2', ''))
    temp_vars = {'config_options': config_options}

    with open(output_name, 'w') as f:
        f.write(template.render(temp_vars).encode('utf-8'))

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[:]))
