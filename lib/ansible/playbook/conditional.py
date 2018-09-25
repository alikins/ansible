# (c) 2012-2014, Michael DeHaan <michael.dehaan@gmail.com>
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
import re

from jinja2.compiler import generate
from jinja2.exceptions import UndefinedError

from ansible.errors import AnsibleError, AnsibleUndefinedVariable
from ansible.module_utils.six import text_type
from ansible.module_utils._text import to_native, to_text
from ansible.playbook.attribute import FieldAttribute

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


DEFINED_REGEX = re.compile(r'(hostvars\[.+\]|[\w_]+)\s+(not\s+is|is|is\s+not)\s+(defined|undefined)')
LOOKUP_REGEX = re.compile(r'lookup\s*\(')
VALID_VAR_REGEX = re.compile("^[_A-Za-z][_a-zA-Z0-9]*$")


class AnsibleInvalidConditional(AnsibleError):
    pass


import json


class AnsibleJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        # Handle ConditionalResult and ConditionalResults
        if hasattr(obj, '_conditional_result'):
            return obj.__getstate__()
        if hasattr(obj, '_conditional_results'):
            return obj.__getstate__()

        return super(AnsibleJSONEncoder, self).default(obj)


# First, we do some low-level jinja2 parsing involving the AST format of the
# statement to ensure we don't do anything unsafe (using the disable_lookup flag above)
class CleansingNodeVisitor(ast.NodeVisitor):
    def __init__(self, conditional, disable_lookups):
        super(CleansingNodeVisitor, self).__init__()
        self.conditional = conditional
        self.disable_lookups = disable_lookups

    def generic_visit(self, node, inside_call=False, inside_yield=False):
        if isinstance(node, ast.Call):
            inside_call = True
        elif isinstance(node, ast.Yield):
            inside_yield = True
        elif isinstance(node, ast.Str):
            if self.disable_lookups:
                if inside_call and node.s.startswith("__"):
                    # calling things with a dunder is generally bad at this point...
                    raise AnsibleError(
                        "Invalid access found in the conditional: '%s'" % self.conditional
                    )
                elif inside_yield:
                    # we're inside a yield, so recursively parse and traverse the AST
                    # of the result to catch forbidden syntax from executing
                    parsed = ast.parse(node.s, mode='exec')
                    cnv = CleansingNodeVisitor(self.conditional, self.disable_lookups)
                    cnv.visit(parsed)
        # iterate over all child nodes
        for child_node in ast.iter_child_nodes(node):
            self.generic_visit(
                child_node,
                inside_call=inside_call,
                inside_yield=inside_yield
            )


# FIXME: any ideas for a better repr?
class ConditionalResult:
    _boolable = False
    _conditional_result = True

    def __init__(self, value=None, conditional=None,
                 templated_expr=None, undefined=None,
                 jinja_exp=None, templating_error_msg=None,
                 val=None):
        self.conditional = conditional
        self.value = value or False
        self.templated_expr = templated_expr
        self.undefined = undefined
        self.jinja_exp = jinja_exp
        self.templating_error_msg = templating_error_msg
        self.val = val

    def __bool__(self):
        return self.value
    __nonzero__ = __bool__

    def __repr__(self):
        return json.dumps(self.__getstate__(), indent=4, ensure_ascii=False,
                          sort_keys=True, cls=AnsibleJSONEncoder)
        #return repr(bool(self))

    def __not_repr__(self):
        return "'%s' is %s" % (self.conditional, self.value)
        # return "ConditionalResult(value=%s, conditional='%s')" % \
        #    (self.value,
        #     self.conditional)

    def __x_repr__(self):
        return "'%s' is %s expanded_to [%s]" % (self.conditional,
                                                self.value,

                                                self.templated_expr,
                                                # self.undefined,
                                                #             self.jinja_exp
                                                )

    def __getstate__(self):
        return {'conditional': self.conditional,
                'value': self.value,
                'templated_expr': self.templated_expr,
                'templating_error_msg': self.templating_error_msg,
                'jinja_exp': self.jinja_exp,
                'val': self.val
                }


class ConditionalResults:
    # for the json encoder to determine we can be cast to a bool
    _boolable = False
    _conditional_results = True

    def __init__(self, conditional_results=None, when=None):
        self.conditional_results = conditional_results or []
        self.when = when or None

    def __bool__(self):
        if not all(self.conditional_results):
            return False
        return True
    __nonzero__ = __bool__

    def __iter__(self):
        return iter(self.conditional_results)

    def __repr__(self):
        return json.dumps(self.__getstate__(), indent=4, ensure_ascii=False,
                          sort_keys=True, cls=AnsibleJSONEncoder)
    # def __repr__(self):
    #    return repr(bool(self))

    def __not_repr__(self):
        buf = '%s(' % self.__class__.__name__
        buf += 'result=%s' % bool(self)
        buf += ', when=['
        for when_item in self.when:
            buf += '%s, ' % when_item

        buf += ']'
        buf += ', conditional_results=['
        for cond_result in self.conditional_results:
            buf += '%s,' % cond_result
        buf += '])'
        return buf

    @property
    def failed_conditions(self):
        return [x for x in self.conditional_results if not x]

    def append(self, conditional_result):
        return self.conditional_results.append(conditional_result)

    def __getstate__(self):
        return {'when': self.when,
                'conditional_results': self.conditional_results,
                'failed_conditions': self.failed_conditions}


class Conditional:

    '''
    This is a mix-in class, to be used with Base to allow the object
    to be run conditionally when a condition is met or skipped.
    '''

    _when = FieldAttribute(isa='list', default=[], extend=True, prepend=True)

    def __init__(self, loader=None):
        # when used directly, this class needs a loader, but we want to
        # make sure we don't trample on the existing one if this class
        # is used as a mix-in with a playbook base class
        if not hasattr(self, '_loader'):
            if loader is None:
                raise AnsibleError("a loader must be specified when using Conditional() directly")
            else:
                self._loader = loader
        super(Conditional, self).__init__()

    def _validate_when(self, attr, name, value):
        if not isinstance(value, list):
            setattr(self, name, [value])

    def extract_defined_undefined(self, conditional):
        results = []

        cond = conditional
        m = DEFINED_REGEX.search(cond)
        while m:
            results.append(m.groups())
            cond = cond[m.end():]
            m = DEFINED_REGEX.search(cond)

        return results

    def evaluate_conditional(self, templar, all_vars):
        '''
        Loops through the conditionals set on this object, returning
        False if any of them evaluate as such.
        '''

        # since this is a mix-in, it may not have an underlying datastructure
        # associated with it, so we pull it out now in case we need it for
        # error reporting below
        ds = None
        if hasattr(self, '_ds'):
            ds = getattr(self, '_ds')

        conditional_results = ConditionalResults(when=self.when)

        # this allows for direct boolean assignments to conditionals "when: False"
        if isinstance(self.when, bool):
            conditional_results.append(ConditionalResult(self.when, self.when))
        else:
            # undefined_errors = []
            for conditional in self.when:

                # FIXME:
                # NOTE: this does not short circuit on first fail, but tries all the 'when' items
                #       It probably should short circuit (ideally by just raising an excep), but that might break compat
                try:
                    result = self._check_conditional(conditional, templar, all_vars)
                    conditional_results.append(result)
                except AnsibleUndefinedVariable as e:
                    # FIXME:  I think we could rm this check now
                    # FIXME: really need a ConditionalError
                    raise AnsibleError("The conditional check '%s' failed. The error was: %s" %
                                       (to_native(conditional), to_native(e)), obj=ds)

                # if we short circuit then we wont need to track true/false and undefined separately
                #if result.undefined:
                    # could add a ConditionalResult(false) here to trigger short circuit on first undefined
                #    undefined_errors.append(result)
                    #return conditional_results

                # return the falsey results when we hit the first false
                # if not result:
                if conditional_results is False:
                    return conditional_results

            #if any(undefined_errors):
            #    raise AnsibleError("The conditional undefined check '%s' failed. The error was: %s" %
            #                    (to_native(undefined_errors), [x.undefined for x in undefined_errors]), obj=ds)

        return conditional_results

    def _check_conditional(self, conditional, templar, all_vars):
        '''
        This method does the low-level evaluation of each conditional
        set on this object, using jinja2 to wrap the conditionals for
        evaluation.
        '''

        original = conditional
        if conditional is None or conditional == '':
            return ConditionalResult(True, conditional=conditional)

        if templar.is_template(conditional):
            display.warning('when statements should not include jinja2 '
                            'templating delimiters such as {{ }} or {%% %%}. '
                            'Found: %s' % conditional)

        # pull the "bare" var out, which allows for nested conditionals
        # and things like:
        # - assert:
        #     that:
        #     - item
        #   with_items:
        #   - 1 == 1
        if conditional in all_vars and VALID_VAR_REGEX.match(conditional):
            conditional = all_vars[conditional]

        # make sure the templar is using the variables specified with this method
        templar.set_available_variables(variables=all_vars)

        try:
            disable_lookups = hasattr(conditional, '__UNSAFE__')

            # FIXME: extract to method args: disable_lookups, conditional
            # bleah, wtf... clobbering conditional?
            conditional = templar.template(conditional, disable_lookups=disable_lookups)
            if not isinstance(conditional, text_type) or conditional == "":
                return ConditionalResult(True, conditional=conditional)

            # update the lookups flag, as the string returned above may now be unsafe
            # and we don't want future templating calls to do unsafe things
            disable_lookups |= hasattr(conditional, '__UNSAFE__')

            try:
                # FIXME: extract to method
                # ffs, 'e' in a try block as var name?
                env = templar.environment.overlay()
                env.filters.update(templar._get_filters())
                env.tests.update(templar._get_tests())

                res = env._parse(conditional, None, None)
                res2 = generate(res, env, None, None)
                parsed = ast.parse(res2, mode='exec')

                cnv = CleansingNodeVisitor(conditional, disable_lookups)
                cnv.visit(parsed)
            except Exception as e:
                raise AnsibleInvalidConditional("Invalid conditional detected: %s" % to_native(e))

            # TODO: verify that conditional can be templated
            #       then verify the presented conditional fixture can be templated
            #       then if they dont fail, then

            # test the conditional first
            # FIXME: are there cases where conditional alone would not be templateable but the whole exp is?
            try:
                conditional_val = templar.template(conditional, disable_lookups=disable_lookups).strip()
            except (AnsibleUndefinedVariable, UndefinedError) as e:
                raise
            except Exception as e:
                # return a falsey result, but because it failed to template not because of how it eval'ed
                return ConditionalResult(False, conditional=conditional,
                                         templating_error_msg=to_text(e))

            presented = "{%% if %s %%} True {%% else %%} False {%% endif %%}" % conditional

            # not template the presented predicate
            try:
                val = templar.template(presented, disable_lookups=disable_lookups).strip()
            except (AnsibleUndefinedVariable, UndefinedError) as e:
                raise
            except Exception as e:
                return ConditionalResult(False, conditional=conditional,
                                         templated_expr=conditional_val,
                                         templating_error_msg=to_text(e))

            if val == "True":
                return ConditionalResult(True, conditional=conditional,
                                         templated_expr=conditional_val,
                                         jinja_exp=presented,
                                         val=val)
            elif val == "False":
                return ConditionalResult(False, conditional=original,
                                         templated_expr=conditional_val,
                                         jinja_exp=presented,
                                         val=val)
            else:
                raise AnsibleError("unable to evaluate conditional: %s" % original)
        except (AnsibleUndefinedVariable, UndefinedError) as e:
            # FIXME: extract to method
            # the templating failed, meaning most likely a variable was undefined. If we happened
            # to be looking for an undefined variable, return True, otherwise fail
            try:
                # first we extract the variable name from the error message

                undef_re = re.compile(r"'(hostvars\[.+\]|[\w_]+)' is undefined").search(str(e))
                if undef_re is None:
                    # could return result here with explain
                    raise

                re_groups = undef_re.groups()
                var_name = re_groups[0]

                # next we extract all defined/undefined tests from the conditional string
                def_undef = self.extract_defined_undefined(conditional)
                # then we loop through these, comparing the error variable name against
                # each def/undef test we found above. If there is a match, we determine
                # whether the logic/state mean the variable should exist or not and return
                # the corresponding True/False
                for (du_var, logic, state) in def_undef:
                    # when we compare the var names, normalize quotes because something
                    # like hostvars['foo'] may be tested against hostvars["foo"]
                    if var_name.replace("'", '"') == du_var.replace("'", '"'):
                        # the should exist is a xor test between a negation in the logic portion
                        # against the state (defined or undefined)
                        should_exist = ('not' in logic) != (state == 'defined')
                        if should_exist:
                            return ConditionalResult(False, conditional=conditional)
                        else:
                            return ConditionalResult(True, conditional=conditional, undefined='xxxx')

                # undefined
                # return ConditionalResult(False, conditional=conditional, undefined='ccccc')
                # as nothing above matched the failed var name, re-raise here to
                # trigger the AnsibleUndefinedVariable exception again below
                raise
            # we dont except as e to avoid clobbering existing e exception
            except Exception as new_e:
                # to get here, a conditional has cause an Undefined error and then in the except
                # block above we've verif'ed that the statement isn't checking for 'is undefined'
                # so we return a failed conditional results with some info about the undefined
                raise
                return ConditionalResult(False, conditional=conditional,
                                         undefined=to_text(new_e),
                                         templating_error_msg=to_text(new_e))
