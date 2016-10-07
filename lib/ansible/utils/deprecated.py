
from ansible import constants as C
from ansible.errors import AnsibleError

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


# FIXME: floats?
# TODO:
current_version = 2.2

FIXUP_PERMS = 'FIXUP_PERMS'
MERGE_MULTIPLE_CLI_TAGS = 'MERGE_MULTIPLE_CLI_TAGS'
MERGE_MULTIPLE_CLI_SKIP_TAGS = 'MERGE_MULTIPLE_CLI_SKIP_TAGS'
TASK_ALWAYS_RUN = 'TASK_ALWAYS_RUN'
BARE_VARIABLES = 'BARE_VARIABLES'
TAGS_IN_INCLUDE_PARAMETERS = 'TAGS_IN_INCLUDE_PARAMETERS'

# API usage
TO_BYTES = 'TO_BYTES'
TO_UNICODE = 'TO_UNICODE'
TO_STR = 'TO_STR'

# Deprecation() classes for dev/test
# TODO: remove, or better, move to unittest
ALWAYS = 'ALWAYS'
NOW = 'NOW'
FUTURE = 'FUTURE'


class Results(object):
    NOT_FOUND = 0
    MUTED = 1
    MITIGATED = 2
    REMOVED = 3
    FUTURE = 4
    VERSION = 5


class Deprecation(object):
    label = None
    version = None
    removed = None
    message = None

    def mitigated(self):
        return False


class Always(Deprecation):
    label = ALWAYS
    # a DeprecationVersion may be useful if... the evaluation semantics get weird.
    version = None
    removed = False
    message = 'This is a test deprecation that is always deprecated'


class Now(Deprecation):
    label = NOW
    version = 2.2
    removed = False
    message = 'This is a test deprecation that matches current version'


class Future(Deprecation):
    label = FUTURE
    version = 3.0
    removed = False
    message = 'This is a test deprecation that is from the future.'


class FixupPerms(Deprecation):
    label = FIXUP_PERMS
    version = 2.4
    removed = False
    message = '_fixup_perms is deprecated. Use _fixup_perms2 instead.'


class MergeMultipleCliTags(Deprecation):
    label = MERGE_MULTIPLE_CLI_TAGS
    version = 2.5
    removed = False
    message = 'Specifying --tags multiple times on the command line currently uses the last specified value. In 2.4, values will be merged instead.  Set merge_multiple_cli_tags=True in ansible.cfg to get this behavior now.'

    def mitigated(self):
        '''If user has explicitly enable MERGE_MULTIPLE_CLI_TAGS, dont warn.'''
        return C.MERGE_MULTIPLE_CLI_TAGS


class MergeMultipleCliSkipTags(Deprecation):
    label = MERGE_MULTIPLE_CLI_SKIP_TAGS
    version = 2.5
    removed = False
    message = 'Specifying --skip-tags multiple times on the command line currently uses the last specified value. In 2.4, values will be merged instead.  Set merge_multiple_cli_tags=True in ansible.cfg to get this behavior now.'

    def mitigated(self):
        '''If user has explicitly enable MERGE_MULTIPLE_CLI_TAGS, dont warn.'''
        return C.MERGE_MULTIPLE_CLI_TAGS


class TaskAlwaysRun(Deprecation):
    label = TASK_ALWAYS_RUN
    version = 2.4
    removed = False
    message = 'always_run is deprecated. Use check_mode = no instead.'


class BareVariables(Deprecation):
    label = BARE_VARIABLES
    version = None
    removed = None
    message = "Using bare variables is deprecated. Update your playbooks so that the environment value uses the full variable syntax."


class TagsInIncludeParameters(Deprecation):
    lable = TAGS_IN_INCLUDE_PARAMETERS
    version = None
    removed = None
    message = "You should not specify tags in the include parameters. All tags should be specified using the task-level option"

# TODO: it would be useful to seperate deprecations from user facing features from developer features
class ToBytes(Deprecation):
    label = TO_BYTES
    version = 2.4
    removed = None
    message = u'ansible.utils.unicode.to_bytes is deprecated.  Use ansible.module_utils._text.to_bytes instead'


class ToUnicode(Deprecation):
    label = TO_UNICODE
    version = 2.4
    removed = None
    message = 'ansible.utils.unicode.to_unicode is deprecated.  Use ansible.module_utils._text.to_text instead'


class ToStr(Deprecation):
    label = TO_STR
    version = 2.4
    removed = None
    message = 'ansible.utils.unicode.to_str is deprecated.  Use ansible.module_utils._text.to_native instead'


#TODO:
# task.py include_vars_at_top_of_File
# task_executor using_vars_for_task_params
# accelerated mode


# Default, provide a different one if needed
def display_callback(msg):
    print(msg)


class OutputHandler(object):
    future_warning = "This feature will be removed in a future release."
    version_warning = "This feature will be removed in version %s."
    warning_slug = "[DEPRECATION WARNING]: "
    quiet_msg = "Deprecation warnings can be disabled by setting deprecation_warnings=False in ansible.cfg.\n\n"

    def __init__(self, output_callbacks=None):
        self._quiet_instructions_have_been_shown = False

        # set of all deprecation messages to prevent duplicate display
        self._deprecations_issued = set()

        self.output_callbacks = output_callbacks or []

    # FIXME: ugly name
    def process(self, deprecation, result, message=None):
        # Suppose we could put the full Deprecation instance in the set if we make it
        # hashable. That could potentially allow for more sophisticated matching...
        if deprecation.label not in self._deprecations_issued:
            self._deprecations_issued.add(deprecation.label)

        # A message passed in from a check() will be used instead of Deprecation default.
        msg = message or deprecation.message
        if result == Results.FUTURE:
            self.warn(msg,
                      postscript=self.future_warning)
        elif result == Results.VERSION:
            self.warn(msg,
                      postscript=self.version_warning % deprecation.version)

    def _display(self, msg):
        for output_callback in self.output_callbacks:
            output_callback(msg)

    def warn(self, message, postscript=None):
        lines = ["%s%s" % (self.warning_slug, message)]
        lines.append(postscript or '')
        msg = '\n'.join(lines)

        self._display(msg)
        self._offer_silence()

    def _offer_silence(self):
        'Expain how to turn off deprecation warnings _once_'

        # TODO: this assumes we only want to show the quiest message once
        if self._quiet_instructions_have_been_shown:
            return

        self._display("Deprecation warnings can be disabled by setting deprecation_warnings=False in ansible.cfg.\n\n")

        self._quiet_instructions_have_been_shown = True


# what are the potential actions after checking a dep?
# - throw an exception
#     - attempting to use removed feature
# - warn that a feature used will be removed in 'the future'
# - warn that a feature used will be removed in version X.Y
#  all just output aside from exception


# TODO: make Deprecations more container/dict like (getitem/setitem/__contains__/len, etc)
#       so deprecated.Deprecations[SOME_LABEL] = MyDeprecation() would work
#       and check:
#       deprecated.Deprecations[SOME_LABEL].check() and deprecated.Deprecations.check() for all
# TODO: split container/iteratable parts from evaluation.
class Deprecations(object):

    def __init__(self):
        self._registry = {}
        self._results = Results()
        self.output_handler = None

    def add(self, deprecation):
        self._registry[deprecation.label] = deprecation

    def process_result(self, deprecation, result, message=None):
        if self.output_handler:
            self.output_handler.process(deprecation, result, message=message)

    def check(self, label, message=None):
        deprecation = self._registry.get(label, None)

        result = self.evaluate(deprecation)
        # handle results/print it

        # FIXME: ugh, terrible name
        self.process_result(deprecation, result, message=message)

        if result == Results.REMOVED:
            raise AnsibleError("[DEPRECATED]: %s.\nPlease update your playbooks." % deprecation.message)

        return result

    # TODO: could be static or module level method
    #       if module method, Deprecation class could implement self.evaluate() with it
    #       Deprecation.check() could use module ver of process_result/handler. Per Deprecation
    #       .check() would also allow a Deprecation() to raise a particular exception on REMOVE
    #       - would also make Deprecations() more of a pure container
    def evaluate(self, deprecation):

        # TODO: make an assert/except/error?
        if not deprecation:
            print('deprecation is None/False?')
            return Results.NOT_FOUND

        # Yes, it is deprecated. Removed even, but stop telling me.
        if not deprecation.removed and not C.DEPRECATION_WARNINGS:
            print('not deprecation.removed %s' % C.DEPRECATION_WARNINGS)
            return Results.MUTED

        if deprecation.mitigated():
            print('deprecation/mitigated()')
            return Results.MITIGATED

        # We are using something that has been removed, fail loudly.
        if deprecation.removed:
            print('d.removed=%s' % deprecation.removed)
            print('deprecaton removed and we are using it, raise')
            # TODO: reasonable place to raise a DeprecationError
            return Results.REMOVED

        if deprecation.version is not None:
            print('d.version=%s' % deprecation.version)
            if current_version < deprecation.version:
                # the current version of ansible is newer than the latest depr version
                #self._warn_version(deprecation)
                return Results.VERSION

        return Results.FUTURE


# deprecation instance don't have to be defined and created here,
# other modules could create them and register them here.

# TODO: worth trying to be clever about registering these
#       auto-magically (ie, a metaclass that keeps track?)
_deprecations = Deprecations()
_deprecations.add(FixupPerms())
_deprecations.add(MergeMultipleCliTags())
_deprecations.add(MergeMultipleCliSkipTags())
_deprecations.add(TaskAlwaysRun())
_deprecations.add(Always())
_deprecations.add(Now())
_deprecations.add(Future())


def check(label, message=None):
    # side-effects include displaying of messages via display_callback
    return _deprecations.check(label, message=message)


def add_output_handler(output_handler):
    _deprecations.output_handler = output_handler
