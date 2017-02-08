#!/usr/bin/python
# -*- coding: utf-8 -*-

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

ANSIBLE_METADATA = {'status': ['stableinterface'],
                    'supported_by': 'community',
                    'version': '1.0'}

DOCUMENTATION = '''
---
module: postgresql_db
short_description: Add or remove PostgreSQL databases from a remote host.
description:
   - Add or remove PostgreSQL databases from a remote host.
version_added: "0.6"
options:
  name:
    description:
      - name of the database to add or remove
    required: true
    default: null
  owner:
    description:
      - Name of the role to set as owner of the database
    required: false
    default: null
  template:
    description:
      - Template used to create the database
    required: false
    default: null
  encoding:
    description:
      - Encoding of the database
    required: false
    default: null
  lc_collate:
    description:
      - Collation order (LC_COLLATE) to use in the database. Must match collation order of template database unless C(template0) is used as template.
    required: false
    default: null
  lc_ctype:
    description:
      - Character classification (LC_CTYPE) to use in the database (e.g. lower, upper, ...) Must match LC_CTYPE of template database unless C(template0) is used as template.
    required: false
    default: null
  state:
    description:
      - The database state
    required: false
    default: present
    choices: [ "present", "absent" ]
requirements: [ psycopg2 ]
author: "Ansible Core Team"
extends_documentation_fragment:
- postgres
'''

EXAMPLES = '''
# Create a new database with name "acme"
- postgresql_db:
    name: acme

# Create a new database with name "acme" and specific encoding and locale
# settings. If a template different from "template0" is specified, encoding
# and locale settings must match those of the template.
- postgresql_db:
    name: acme
    encoding: UTF-8
    lc_collate: de_DE.UTF-8
    lc_ctype: de_DE.UTF-8
    template: template0
'''

# pg imports
try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    postgresqldb_found = False
else:
    postgresqldb_found = True


# ===========================================
# PostgreSQL module specific support methods.
#

def set_owner(cursor, db, owner):
    query = "ALTER DATABASE %s OWNER TO %s" % (
            pg_quote_identifier(db, 'database'),
            pg_quote_identifier(owner, 'role'))
    cursor.execute(query)
    return True

def get_encoding_id(cursor, encoding):
    query = "SELECT pg_char_to_encoding(%(encoding)s) AS encoding_id;"
    cursor.execute(query, {'encoding': encoding})
    return cursor.fetchone()['encoding_id']

def get_db_info(cursor, db):
    query = """
    SELECT rolname AS owner,
    pg_encoding_to_char(encoding) AS encoding, encoding AS encoding_id,
    datcollate AS lc_collate, datctype AS lc_ctype
    FROM pg_database JOIN pg_roles ON pg_roles.oid = pg_database.datdba
    WHERE datname = %(db)s
    """
    cursor.execute(query, {'db': db})
    return cursor.fetchone()

def db_exists(cursor, db):
    query = "SELECT * FROM pg_database WHERE datname=%(db)s"
    cursor.execute(query, {'db': db})
    return cursor.rowcount == 1

def db_delete(cursor, db):
    if db_exists(cursor, db):
        query = "DROP DATABASE %s" % pg_quote_identifier(db, 'database')
        cursor.execute(query)
        return True
    else:
        return False

def db_create(cursor, db, owner, template, encoding, lc_collate, lc_ctype):
    params = dict(enc=encoding, collate=lc_collate, ctype=lc_ctype)
    if not db_exists(cursor, db):
        query_fragments = ['CREATE DATABASE %s' % pg_quote_identifier(db, 'database')]
        if owner:
            query_fragments.append('OWNER %s' % pg_quote_identifier(owner, 'role'))
        if template:
            query_fragments.append('TEMPLATE %s' % pg_quote_identifier(template, 'database'))
        if encoding:
            query_fragments.append('ENCODING %(enc)s')
        if lc_collate:
            query_fragments.append('LC_COLLATE %(collate)s')
        if lc_ctype:
            query_fragments.append('LC_CTYPE %(ctype)s')
        query = ' '.join(query_fragments)
        cursor.execute(query, params)
        return True
    else:
        db_info = get_db_info(cursor, db)
        if (encoding and
            get_encoding_id(cursor, encoding) != db_info['encoding_id']):
            raise NotSupportedError(
                'Changing database encoding is not supported. '
                'Current encoding: %s' % db_info['encoding']
            )
        elif lc_collate and lc_collate != db_info['lc_collate']:
            raise NotSupportedError(
                'Changing LC_COLLATE is not supported. '
                'Current LC_COLLATE: %s' % db_info['lc_collate']
            )
        elif lc_ctype and lc_ctype != db_info['lc_ctype']:
            raise NotSupportedError(
                'Changing LC_CTYPE is not supported.'
                'Current LC_CTYPE: %s' % db_info['lc_ctype']
            )
        elif owner and owner != db_info['owner']:
            return set_owner(cursor, db, owner)
        else:
            return False

def db_matches(cursor, db, owner, template, encoding, lc_collate, lc_ctype):
    if not db_exists(cursor, db):
        return False
    else:
        db_info = get_db_info(cursor, db)
        if (encoding and
            get_encoding_id(cursor, encoding) != db_info['encoding_id']):
            return False
        elif lc_collate and lc_collate != db_info['lc_collate']:
            return False
        elif lc_ctype and lc_ctype != db_info['lc_ctype']:
            return False
        elif owner and owner != db_info['owner']:
            return False
        else:
            return True

# ===========================================
# Module execution.
#

def main():
    argument_spec = pgutils.postgres_common_argument_spec()
    argument_spec.update(dict(
        db=dict(required=True, aliases=['name']),
        owner=dict(default=""),
        template=dict(default=""),
        encoding=dict(default=""),
        lc_collate=dict(default=""),
        lc_ctype=dict(default=""),
        state=dict(default="present", choices=["absent", "present"]),
        ssl_rootcert=dict(default=None),
    ))

    module = AnsibleModule(
        argument_spec = argument_spec,
        supports_check_mode = True
    )

    if not postgresqldb_found:
        module.fail_json(msg="the python psycopg2 module is required")

    db = module.params["db"]
    port = module.params["port"]
    owner = module.params["owner"]
    template = module.params["template"]
    encoding = module.params["encoding"]
    lc_collate = module.params["lc_collate"]
    lc_ctype = module.params["lc_ctype"]
    state = module.params["state"]
    changed = False

    kw = pgutils.params_to_kwmap(module)

    db_connection = pgutils.postgres_conn(module, database="postgres", kw=kw, enable_autocommit=True)
    cursor = db_connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        if module.check_mode:
            if state == "absent":
                changed = db_exists(cursor, db)
            elif state == "present":
                changed = not db_matches(cursor, db, owner, template, encoding, lc_collate, lc_ctype)
            module.exit_json(changed=changed, db=db)

        if state == "absent":
            try:
                changed = db_delete(cursor, db)
            except SQLParseError:
                e = get_exception()
                module.fail_json(msg=str(e))

        elif state == "present":
            try:
                changed = db_create(cursor, db, owner, template, encoding, lc_collate, lc_ctype)
            except SQLParseError:
                e = get_exception()
                module.fail_json(msg=str(e))
    except NotSupportedError:
        e = get_exception()
        module.fail_json(msg=str(e))
    except SystemExit:
        # Avoid catching this on Python 2.4
        raise
    except Exception:
        e = get_exception()
        module.fail_json(msg="Database query failed: %s" % e)

    module.exit_json(changed=changed, db=db)

# import module snippets
from ansible.module_utils.basic import AnsibleModule,get_exception
from ansible.module_utils.database import pg_quote_identifier,SQLParseError
import ansible.module_utils.postgres as pgutils
if __name__ == '__main__':
    main()
