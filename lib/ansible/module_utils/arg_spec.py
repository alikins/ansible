import json
import logging
import os

from ansible.module_utils.six import (
    binary_type,
    integer_types,
    string_types,
    text_type,
)

from ansible.module_utils.common._collections_compat import (
    KeysView,
    Mapping,
    Sequence,
)

from ansible.module_utils._text import to_native
from ansible.module_utils.parsing.convert_bool import BOOLEANS_FALSE, BOOLEANS_TRUE

log = logging.getLogger(__name__)

# Note: When getting Sequence from collections, it matches with strings.  If
# this matters, make sure to check for strings before checking for sequencetype
SEQUENCETYPE = frozenset, KeysView, Sequence

# Python2 & 3 way to get NoneType
NoneType = type(None)

_NUMBERTYPES = tuple(list(integer_types) + [float])

# Deprecated compat.  Only kept in case another module used these names  Using
# ansible.module_utils.six is preferred

NUMBERTYPES = _NUMBERTYPES

PASS_VARS = {
    'check_mode': 'check_mode',
    'debug': '_debug',
    'diff': '_diff',
    'keep_remote_files': '_keep_remote_files',
    'module_name': '_name',
    'no_log': 'no_log',
    'remote_tmp': '_remote_tmp',
    'selinux_special_fs': '_selinux_special_fs',
    'shell_executable': '_shell',
    'socket': '_socket_path',
    'syslog_facility': '_syslog_facility',
    'tmpdir': '_tmpdir',
    'verbosity': '_verbosity',
    'version': 'ansible_version',
}

PASS_BOOLS = ('no_log', 'debug', 'diff')


def _lenient_lowercase(lst):
    """Lowercase elements of a list.

    If an element is not a string, pass it through untouched.
    """
    lowered = []
    for value in lst:
        try:
            lowered.append(value.lower())
        except AttributeError:
            lowered.append(value)
    return lowered


def return_values(obj):
    """ Return native stringified values from datastructures.

    For use with removing sensitive values pre-jsonification."""
    if isinstance(obj, (text_type, binary_type)):
        if obj:
            yield to_native(obj, errors='surrogate_or_strict')
        return
    elif isinstance(obj, SEQUENCETYPE):
        for element in obj:
            for subelement in return_values(element):
                yield subelement
    elif isinstance(obj, Mapping):
        for element in obj.items():
            for subelement in return_values(element[1]):
                yield subelement
    elif isinstance(obj, (bool, NoneType)):
        # This must come before int because bools are also ints
        return
    elif isinstance(obj, NUMBERTYPES):
        yield to_native(obj, nonstring='simplerepr')
    else:
        raise TypeError('Unknown parameter type: %s, %s' % (type(obj), obj))


# Can't remove AnsibleFallbackNotFound from basic.py since stuff
# uses it, and dont want to circular import basic<->argspec so
# add or own.
# TODO: mv AnsibleFallbackNotFound to common?
class AnsibleArgSpecFallbackNotFound(Exception):
    pass


class AnsibleArgSpecCheckModeExit(Exception):
    pass


class AnsibleArgSpecError(Exception):
    pass


def env_fallback(*args, **kwargs):
    ''' Load value from environment '''
    for arg in args:
        if arg in os.environ:
            return os.environ[arg]
    raise AnsibleArgSpecFallbackNotFound


# all of the argspec logic from module_utils.py:AnsibleModule
class ArgSpec(object):
    def __init__(self,
                 params,
                 argument_spec,
                 no_log=False,
                 bypass_checks=False,
                 mutually_exclusive=None,
                 required_together=None,
                 required_one_of=None,
                 add_file_common_args=False,
                 required_if=None):
        # in lieue of AM._load_params
        # self.params is a dict, key is name of spec
        # value is the value AnsibleModule is called with,
        #  though it is mutated to include various defaults eventually
        self.params = params

        # If file args like owner/group/perms are added
        self.add_file_common_args = add_file_common_args

        # from AnsibleModule __init__ argument_spec param
        # It too gets mutated on init to add things like add_file_common_args
        self.argument_spec = argument_spec

        # ?? something to do with when/where/how self._check_* are applied
        self.bypass_checks = bypass_checks

        self.no_log = no_log
        self.no_log_values = set()

        self.mutually_exclusive = mutually_exclusive
        self.required_together = required_together
        self.required_one_of = required_one_of
        self.required_if = required_if

        self.aliases = {}
        self._legal_inputs = []
        self._options_context = []
        # fallbacks?

        self._CHECK_ARGUMENT_TYPES_DISPATCHER = {
            'str': self._check_type_str,
            'list': self._check_type_list,
            'dict': self._check_type_dict,
            'bool': self._check_type_bool,
            'int': self._check_type_int,
            'float': self._check_type_float,
            'path': self._check_type_path,
            'raw': self._check_type_raw,
            'jsonarg': self._check_type_jsonarg,
            'json': self._check_type_jsonarg,
            'bytes': self._check_type_bytes,
            'bits': self._check_type_bits,
        }

        # ???
        # check_invalid_arguments - deprecated already... shrug

    def do_stuff(self,
                 check_invalid_arguments=None,
                 bypass_checks=False,
                 mutually_exclusive=None,
                 required_together=None,
                 required_one_of=None,
                 required_if=None,
                 ):
        self._set_fallbacks()

        # FIXME: mutate self
        self.aliases = self._handle_aliases()

        # FIXME: _handle_no_log_values() can return a set instead of modifying
        #        self.no_log_values
        self._handle_no_log_values()

        self._check_arguments(check_invalid_arguments)

        # check exclusive early
        if not bypass_checks:
            self._check_mutually_exclusive(mutually_exclusive)

        # FIXME: return param updates
        self._set_defaults(pre=True)

        if not bypass_checks:
            self._check_required_arguments()
            self._check_argument_types()
            self._check_argument_values()
            self._check_required_together(required_together)
            self._check_required_one_of(required_one_of)
            self._check_required_if(required_if)

        self._set_defaults(pre=False)

        # deal with options sub-spec
        self._handle_options()

    def _as_dict(self):
        data = {'argument_spec': self.argument_spec,
                'params': self.params,
                'bypass_checks': self.bypass_checks,
                'no_log': self.no_log,
                # 'check_invalid_arguments': self.check_invalid_arguments,
                'mutually_exclusive': self.mutually_exclusive,
                'required_together': self.required_together,
                'required_one_of': self.required_one_of,
                'required_if': self.required_if,
                'aliases': self.aliases,
                '_legal_inputs': self._legal_inputs,
                'no_log_values': self.no_log_values,
                }
        return data

    def __repr__(self):
        kvs = ', '.join(['%s=%s' % (item[0], item[1]) for item in self._as_dict().items()])
        buf = '%s(%s)' % (self.__class__.__name__,
                          kvs)
        return buf

    def _handle_aliases(self, spec=None, param=None):
        '''handle aliases

        modifies self._legal_inputs
        '''
        # this uses exceptions as it happens before we can safely call fail_json
        aliases_results = {}  # alias:canon
        if param is None:
            param = self.params

        if spec is None:
            spec = self.argument_spec
        for (k, v) in spec.items():
            self._legal_inputs.append(k)
            aliases = v.get('aliases', None)
            default = v.get('default', None)
            required = v.get('required', False)
            if default is not None and required:
                # not alias specific but this is a good place to check this
                raise Exception("internal error: required and default are mutually exclusive for %s" % k)
            if aliases is None:
                continue
            if not isinstance(aliases, SEQUENCETYPE) or isinstance(aliases, (binary_type, text_type)):
                raise Exception('internal error: aliases must be a list or tuple')
            for alias in aliases:
                self._legal_inputs.append(alias)
                aliases_results[alias] = k
                if alias in param:
                    param[k] = param[alias]

        return aliases_results

    def _handle_no_log_values(self, spec=None, param=None):
        '''_handle_no_log_values

        side effect: self.no_log_values is updated
        '''
        if spec is None:
            spec = self.argument_spec
        if param is None:
            param = self.params

        # Use the argspec to determine which args are no_log
        for arg_name, arg_opts in spec.items():
            if arg_opts.get('no_log', False):
                # Find the value for the no_log'd param
                no_log_object = param.get(arg_name, None)
                if no_log_object:
                    self.no_log_values.update(return_values(no_log_object))

            if arg_opts.get('removed_in_version') is not None and arg_name in param:
                self._deprecations.append({
                    'msg': "Param '%s' is deprecated. See the module docs for more information" % arg_name,
                    'version': arg_opts.get('removed_in_version')
                })

    def _check_arguments(self, check_invalid_arguments, spec=None, param=None, legal_inputs=None):
        unsupported_parameters = set()
        if spec is None:
            spec = self.argument_spec
        if param is None:
            param = self.params
        if legal_inputs is None:
            legal_inputs = self._legal_inputs

        for (k, v) in list(param.items()):

            if check_invalid_arguments and k not in legal_inputs:
                unsupported_parameters.add(k)
            elif k.startswith('_ansible_'):
                # handle setting internal properties from internal ansible vars
                key = k.replace('_ansible_', '')
                if key in PASS_BOOLS:
                    setattr(self, PASS_VARS[key], self.boolean(v))
                else:
                    setattr(self, PASS_VARS[key], v)

                # clean up internal params:
                del self.params[k]

        if unsupported_parameters:
            msg = "Unsupported parameters for (%s) module: %s" % (self._name, ', '.join(sorted(list(unsupported_parameters))))
            if self._options_context:
                msg += " found in %s." % " -> ".join(self._options_context)
            msg += " Supported parameters include: %s" % (', '.join(sorted(spec.keys())))
            # self.fail_json(msg=msg)
            raise AnsibleArgSpecError(msg)

        # if self.check_mode and not self.supports_check_mode:
        #    msg = "remote module (%s) does not support check mode" % self._name
        #    raise AnsibleArgSpecCheckModeExit(msg)

        return True
        # self.exit_json(skipped=True, msg="remote module (%s) does not support check mode" % self._name)

    def _count_terms(self, check, param=None):
        count = 0
        if param is None:
            param = self.params
        for term in check:
            if term in param:
                count += 1
        return count

    # FIXME: pass in options_context
    def _check_mutually_exclusive(self, spec, param=None):
        if spec is None:
            return
        for check in spec:
            count = self._count_terms(check, param)
            if count > 1:
                msg = "parameters are mutually exclusive: %s" % ', '.join(check)
                if self._options_context:
                    msg += " found in %s" % " -> ".join(self._options_context)
                raise AnsibleArgSpecError(msg)

    def _check_required_one_of(self, spec, param=None):
        if spec is None:
            return
        for check in spec:
            count = self._count_terms(check, param)
            if count == 0:
                msg = "one of the following is required: %s" % ', '.join(check)
                if self._options_context:
                    msg += " found in %s" % " -> ".join(self._options_context)
                raise AnsibleArgSpecError(msg)

    def _check_required_together(self, spec, param=None):
        if spec is None:
            return
        for check in spec:
            counts = [self._count_terms([field], param) for field in check]
            non_zero = [c for c in counts if c > 0]
            if len(non_zero) > 0:
                if 0 in counts:
                    msg = "parameters are required together: %s" % ', '.join(check)
                    if self._options_context:
                        msg += " found in %s" % " -> ".join(self._options_context)
                    raise AnsibleArgSpecError(msg)
                    # self.fail_json(msg=msg)

    def _check_required_arguments(self, spec=None, param=None):
        ''' ensure all required arguments are present '''
        missing = []
        if spec is None:
            spec = self.argument_spec
        if param is None:
            param = self.params
        for (k, v) in spec.items():
            required = v.get('required', False)
            if required and k not in param:
                missing.append(k)
        if len(missing) > 0:
            msg = "missing required arguments: %s" % ", ".join(missing)
            if self._options_context:
                msg += " found in %s" % " -> ".join(self._options_context)
            raise AnsibleArgSpecError(msg)
            # self.fail_json(msg=msg)

    def _check_required_if(self, spec, param=None):
        ''' ensure that parameters which conditionally required are present '''
        if spec is None:
            return
        if param is None:
            param = self.params
        for sp in spec:
            missing = []
            max_missing_count = 0
            is_one_of = False
            if len(sp) == 4:
                key, val, requirements, is_one_of = sp
            else:
                key, val, requirements = sp

            # is_one_of is True at least one requirement should be
            # present, else all requirements should be present.
            if is_one_of:
                max_missing_count = len(requirements)
                term = 'any'
            else:
                term = 'all'

            if key in param and param[key] == val:
                for check in requirements:
                    count = self._count_terms((check,), param)
                    if count == 0:
                        missing.append(check)
            if len(missing) and len(missing) >= max_missing_count:
                msg = "%s is %s but %s of the following are missing: %s" % (key, val, term, ', '.join(missing))
                if self._options_context:
                    msg += " found in %s" % " -> ".join(self._options_context)
                raise AnsibleArgSpecError(msg)
                # self.fail_json(msg=msg)

    def _check_argument_values(self, spec=None, param=None):
        ''' ensure all arguments have the requested values, and there are no stray arguments '''
        if spec is None:
            spec = self.argument_spec
        if param is None:
            param = self.params
        for (k, v) in spec.items():
            choices = v.get('choices', None)
            if choices is None:
                continue
            if isinstance(choices, SEQUENCETYPE) and not isinstance(choices, (binary_type, text_type)):
                if k in param:
                    # Allow one or more when type='list' param with choices
                    if isinstance(param[k], list):
                        diff_list = ", ".join([item for item in param[k] if item not in choices])
                        if diff_list:
                            choices_str = ", ".join([to_native(c) for c in choices])
                            msg = "value of %s must be one or more of: %s. Got no match for: %s" % (k, choices_str, diff_list)
                            if self._options_context:
                                msg += " found in %s" % " -> ".join(self._options_context)
                            raise AnsibleArgSpecError(msg)
                            # self.fail_json(msg=msg)
                    elif param[k] not in choices:
                        # PyYaml converts certain strings to bools.  If we can unambiguously convert back, do so before checking
                        # the value.  If we can't figure this out, module author is responsible.
                        lowered_choices = None
                        if param[k] == 'False':
                            lowered_choices = _lenient_lowercase(choices)
                            overlap = BOOLEANS_FALSE.intersection(choices)
                            if len(overlap) == 1:
                                # Extract from a set
                                (param[k],) = overlap

                        if param[k] == 'True':
                            if lowered_choices is None:
                                lowered_choices = _lenient_lowercase(choices)
                            overlap = BOOLEANS_TRUE.intersection(choices)
                            if len(overlap) == 1:
                                (param[k],) = overlap

                        if param[k] not in choices:
                            choices_str = ", ".join([to_native(c) for c in choices])
                            msg = "value of %s must be one of: %s, got: %s" % (k, choices_str, param[k])
                            if self._options_context:
                                msg += " found in %s" % " -> ".join(self._options_context)
                            raise AnsibleArgSpecError(msg)
                            # self.fail_json(msg=msg)
            else:
                msg = "internal error: choices for argument %s are not iterable: %s" % (k, choices)
                if self._options_context:
                    msg += " found in %s" % " -> ".join(self._options_context)
                raise AnsibleArgSpecError(msg)
                # self.fail_json(msg=msg)

    def _check_type_str(self, value):
        if isinstance(value, string_types):
            return value
        # Note: This could throw a unicode error if value's __str__() method
        # returns non-ascii.  Have to port utils.to_bytes() if that happens
        return str(value)

    def _check_type_list(self, value):
        if isinstance(value, list):
            return value

        if isinstance(value, string_types):
            return value.split(",")
        elif isinstance(value, int) or isinstance(value, float):
            return [str(value)]

        raise TypeError('%s cannot be converted to a list' % type(value))

    def _check_type_dict(self, value):
        if isinstance(value, dict):
            return value

        if isinstance(value, string_types):
            if value.startswith("{"):
                try:
                    return json.loads(value)
                except:
                    (result, exc) = self.safe_eval(value, dict(), include_exceptions=True)
                    if exc is not None:
                        raise TypeError('unable to evaluate string as dictionary')
                    return result
            elif '=' in value:
                fields = []
                field_buffer = []
                in_quote = False
                in_escape = False
                for c in value.strip():
                    if in_escape:
                        field_buffer.append(c)
                        in_escape = False
                    elif c == '\\':
                        in_escape = True
                    elif not in_quote and c in ('\'', '"'):
                        in_quote = c
                    elif in_quote and in_quote == c:
                        in_quote = False
                    elif not in_quote and c in (',', ' '):
                        field = ''.join(field_buffer)
                        if field:
                            fields.append(field)
                        field_buffer = []
                    else:
                        field_buffer.append(c)

                field = ''.join(field_buffer)
                if field:
                    fields.append(field)
                return dict(x.split("=", 1) for x in fields)
            else:
                raise TypeError("dictionary requested, could not parse JSON or key=value")

        raise TypeError('%s cannot be converted to a dict' % type(value))

    def _check_type_bool(self, value):
        if isinstance(value, bool):
            return value

        if isinstance(value, string_types) or isinstance(value, int):
            return self.boolean(value)

        raise TypeError('%s cannot be converted to a bool' % type(value))

    def _check_type_int(self, value):
        if isinstance(value, int):
            return value

        if isinstance(value, string_types):
            return int(value)

        raise TypeError('%s cannot be converted to an int' % type(value))

    def _check_type_float(self, value):
        if isinstance(value, float):
            return value

        if isinstance(value, (binary_type, text_type, int)):
            return float(value)

        raise TypeError('%s cannot be converted to a float' % type(value))

    def _check_type_path(self, value):
        value = self._check_type_str(value)
        return os.path.expanduser(os.path.expandvars(value))

    def _check_type_jsonarg(self, value):
        # Return a jsonified string.  Sometimes the controller turns a json
        # string into a dict/list so transform it back into json here
        if isinstance(value, (text_type, binary_type)):
            return value.strip()
        else:
            if isinstance(value, (list, tuple, dict)):
                return self.jsonify(value)
        raise TypeError('%s cannot be converted to a json string' % type(value))

    def _check_type_raw(self, value):
        return value

    def _check_type_bytes(self, value):
        try:
            self.human_to_bytes(value)
        except ValueError:
            raise TypeError('%s cannot be converted to a Byte value' % type(value))

    def _check_type_bits(self, value):
        try:
            self.human_to_bytes(value, isbits=True)
        except ValueError:
            raise TypeError('%s cannot be converted to a Bit value' % type(value))

    def _handle_options(self, argument_spec=None, params=None):
        ''' deal with options to create sub spec '''
        if argument_spec is None:
            argument_spec = self.argument_spec
        if params is None:
            params = self.params

        for (k, v) in argument_spec.items():
            wanted = v.get('type', None)
            if wanted == 'dict' or (wanted == 'list' and v.get('elements', '') == 'dict'):
                spec = v.get('options', None)
                if v.get('apply_defaults', False):
                    if spec is not None:
                        if params.get(k) is None:
                            params[k] = {}
                    else:
                        continue
                elif spec is None or k not in params or params[k] is None:
                    continue

                self._options_context.append(k)

                if isinstance(params[k], dict):
                    elements = [params[k]]
                else:
                    elements = params[k]

                for param in elements:
                    if not isinstance(param, dict):
                        self.fail_json(msg="value of %s must be of type dict or list of dict" % k)

                    self._set_fallbacks(spec, param)
                    options_aliases = self._handle_aliases(spec, param)

                    self._handle_no_log_values(spec, param)
                    options_legal_inputs = list(spec.keys()) + list(options_aliases.keys())

                    self._check_arguments(self.check_invalid_arguments, spec, param, options_legal_inputs)

                    # check exclusive early
                    if not self.bypass_checks:
                        self._check_mutually_exclusive(v.get('mutually_exclusive', None), param)

                    self._set_defaults(pre=True, spec=spec, param=param)

                    if not self.bypass_checks:
                        self._check_required_arguments(spec, param)
                        self._check_argument_types(spec, param)
                        self._check_argument_values(spec, param)

                        self._check_required_together(v.get('required_together', None), param)
                        self._check_required_one_of(v.get('required_one_of', None), param)
                        self._check_required_if(v.get('required_if', None), param)

                    self._set_defaults(pre=False, spec=spec, param=param)

                    # handle multi level options (sub argspec)
                    self._handle_options(spec, param)
                self._options_context.pop()

    def _check_argument_types(self, spec=None, param=None):
        ''' ensure all arguments have the requested type '''

        if spec is None:
            spec = self.argument_spec
        if param is None:
            param = self.params

        for (k, v) in spec.items():
            wanted = v.get('type', None)
            if k not in param:
                continue

            value = param[k]
            if value is None:
                continue

            if not callable(wanted):
                if wanted is None:
                    # Mostly we want to default to str.
                    # For values set to None explicitly, return None instead as
                    # that allows a user to unset a parameter
                    if param[k] is None:
                        continue
                    wanted = 'str'
                try:
                    type_checker = self._CHECK_ARGUMENT_TYPES_DISPATCHER[wanted]
                except KeyError:
                    msg = "implementation error: unknown type %s requested for %s" % (wanted, k)
                    raise AnsibleArgSpecError(msg)
                    # self.fail_json(msg="implementation error: unknown type %s requested for %s" % (wanted, k))
            else:
                # set the type_checker to the callable, and reset wanted to the callable's name (or type if it doesn't have one, ala MagicMock)
                type_checker = wanted
                wanted = getattr(wanted, '__name__', to_native(type(wanted)))

            try:
                param[k] = type_checker(value)
            except (TypeError, ValueError) as e:
                msg = "argument %s is of type %s and we were unable to convert to %s: %s" % \
                    (k, type(value), wanted, to_native(e))
                raise AnsibleArgSpecError(msg)

    def _set_defaults(self, pre=True, spec=None, param=None):
        if spec is None:
            spec = self.argument_spec
        if param is None:
            param = self.params
        for (k, v) in spec.items():
            default = v.get('default', None)
            if pre is True:
                # this prevents setting defaults on required items
                if default is not None and k not in param:
                    param[k] = default
            else:
                # make sure things without a default still get set None
                if k not in param:
                    param[k] = default

    def _set_fallbacks(self, spec=None, param=None):
        if spec is None:
            spec = self.argument_spec
        if param is None:
            param = self.params

        for (k, v) in spec.items():
            fallback = v.get('fallback', (None,))
            fallback_strategy = fallback[0]
            fallback_args = []
            fallback_kwargs = {}
            if k not in param and fallback_strategy is not None:
                for item in fallback[1:]:
                    if isinstance(item, dict):
                        fallback_kwargs = item
                    else:
                        fallback_args = item
                try:
                    param[k] = fallback_strategy(*fallback_args, **fallback_kwargs)
                except AnsibleArgSpecFallbackNotFound:
                    continue
