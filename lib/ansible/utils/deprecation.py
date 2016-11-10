
from ansible import constants as C
from ansible.errors import AnsibleError
from ansible.compat.six import with_metaclass, add_metaclass

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


# FIXME: floats?
# TODO: pull in from __version__ or equilivent so it's populated at runtime.
current_version = 2.3

# could classify... cli args, playbook params, config options
# TODO/FIXME: enum class
FIXUP_PERMS = 'FIXUP_PERMS'
MERGE_MULTIPLE_CLI_TAGS = 'MERGE_MULTIPLE_CLI_TAGS'
MERGE_MULTIPLE_CLI_SKIP_TAGS = 'MERGE_MULTIPLE_CLI_SKIP_TAGS'
TASK_ALWAYS_RUN = 'TASK_ALWAYS_RUN'
BARE_VARIABLES = 'BARE_VARIABLES'
TAGS_IN_INCLUDE_PARAMETERS = 'TAGS_IN_INCLUDE_PARAMETERS'
SUDO_USAGE = 'SUDO_USAGE'
SU_USAGE = 'SU_USAGE'
TASK_PARAM_VARIABLES = 'TASK_PARAM_VARIABLES'
ACCELERATED_MODE = 'ACCELERATED_MODE'

# API usage
TO_BYTES = 'TO_BYTES'
TO_UNICODE = 'TO_UNICODE'
TO_STR = 'TO_STR'


# TODO: other deprecations to add
# vars/ play_hosts
# vaultlib.is_encrypted[_file]
# action/unarchive 'copy'
# plugins/loader explicit set of deprecations for deprecated modules/tasks?
# galaxy text role format
# playbook/play 'use of user in Play datastructure'
# playbook/play.py 'using the short form for vars prompt'
# playbook/task.py "Specifying include variables at the top-level of the task is deprecated"
# playbook/helpers.py "since this is not explicitly marked as static..."
# playbook/helpers.py "You should not specify tags in include paramaters"
# playbook/role/requirement.py: "The comma separated role spec format, use the yaml/explicit format instead."
# playbook/base.py: deprecated attributes
# playbook/base.py: comma seperated lists, use yaml instead
#

_deprecations_registry = {}


class Results(object):
    NOT_FOUND = 0
    MUTED = 1
    MITIGATED = 2
    REMOVED = 3
    FUTURE = 4
    VERSION = 5


class Deprecation(object):
    def __init__(self, data, reaction):
        '''Define a deprecation and how to react to it.

        data is an instance of a DeprecationData or equilivent.
        reaction is an instance of a DeprecationReaction or equilivent.'''

        self.data = data
        self.reaction = reaction

    def evaluate(self):
        return self.data.evaluate()

    def react(self, result, message=None, where=None):
        return self.reaction.react(self.data, result,
                                   message=message, where=where)

    def check(self, message=None, where=None):
        res = self.evaluate()
        return self.react(res, message=message, where=where)

    def removed(self):
        res = self.evaluate()
        if res == Results.REMOVED:
            return True
        return False


class MetaDeprecationData(type):
    def __new__(meta, name, bases, class_dict):
        cls = type.__new__(meta, name, bases, class_dict)

        # we could register the labels as well to auto populate enum-ish module attrs
        # but loses the dev utility of compile time check
        # (ie, avoid runtime check('MISPELEDD_DERPICATION') errors

        # Don't include the base class in the registry
        if cls.label:
            _deprecations_registry[cls.label] = cls
        return cls

    # we do sort the class objects themselves by label. This can be
    # removed if we track instances instead in _deprecations_registry
    def __lt__(self, other):
        return self.label < other.label


@add_metaclass(MetaDeprecationData)
class DeprecationData():
    # TODO: verify if this is worth metapain

    label = None
    version = None
    removed = None
    message = None

    def mitigated(self):
        if self.label in C.DEFAULT_DEPRECATIONS_TO_IGNORE:
            return True
        return False

    def evaluate(self):
        # Yes, it is deprecated. Removed even, but stop telling me.
        if not self.removed and not C.DEPRECATION_WARNINGS:
            return Results.MUTED

        if self.mitigated():
            return Results.MITIGATED

        # We are using something that has been removed, fail loudly.
        if self.removed:
            # TODO: reasonable place to raise a DeprecationError
            return Results.REMOVED

        if self.version is not None:
            if current_version >= self.version:
                # the current version of ansible is newer than the latest depr version
                #self._warn_version(deprecation)
                return Results.VERSION

        return Results.FUTURE


class AnsibleDeprecation(AnsibleError):
    pass


class Reaction(object):
    '''If a deprecation applies, we need to have some reaction.

    ie, print a warning, raise an exception, etc.'''
    def react(self, depr, result, message=None, where=None):
        if result == Results.REMOVED:
            raise AnsibleDeprecation("[DEPRECATED]: %s.\nPlease update your playbooks." % depr.message)
        return result

# For more useful output, set deprecation.reaction to something like DefaultReaction
default_reaction = Reaction()


class OutputHandler(object):
    future_warning = "This feature will be removed in a future release."
    version_warning = "This feature will be removed in version %s."
    warning_slug = "[DEPRECATION WARNING]: "
    quiet_msg = "Deprecation warnings can be disabled by setting deprecation_warnings=False in ansible.cfg.\n\n"

    def __init__(self, output_callbacks=None):
        self._quiet_instructions_have_been_shown = False

        # set of all deprecation messages to prevent duplicate display
        self._deprecations_issued = set()
        self._test_depr_set = set()

        self.output_callbacks = output_callbacks or []

    # FIXME: ugly name
    def process(self, depr, result, message=None, where=None):
        # Suppose we could put the full Deprecation instance in the set if we make it
        # hashable. That could potentially allow for more sophisticated matching...
        if depr.label not in self._deprecations_issued:
            self._deprecations_issued.add(depr.label)
            #self._test_depr_set.add(depr.data)

        # TODO: include where info here
        # A message passed in from a check() will be used instead of Deprecation default.
        msg = message or depr.message
        if result == Results.FUTURE:
            self.warn(msg,
                      postscript=self.future_warning)
        elif result == Results.VERSION:
            self.warn(msg,
                      postscript=self.version_warning % depr.version)

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


class DefaultReaction(Reaction):
    def __init__(self, output_callback):
        super(DefaultReaction, self).__init__()
        self.output_handler = OutputHandler(output_callbacks=[output_callback])

    def react(self, depr, result, message=None, where=None):
        self.process_result(depr, result, message=message)

        if result == Results.REMOVED:
            raise AnsibleDeprecation("[DEPRECATED]: %s.\nPlease update your playbooks." % depr.message)

        return result

    def process_result(self, depr, result, message=None, where=None):
            self.output_handler.process(depr, result, message=message, where=where)


# NOTE: Deprecation classes don't have to be defined here, they could be defined where used, but
#       need to be defined in a scope that gets interpreted (ie, module scope) so they show up
#       in list_deprecations()

# NOTE: The bulk of these classes could be defined in data/config. The classes that need to extend
#       mitigated() need a class defination though. The utility of being able to define these
#       when/where the deprecated code is changed would be lost however.
class FixupPerms(DeprecationData):
    label = FIXUP_PERMS
    version = 2.4
    removed = False
    message = '_fixup_perms is deprecated. Use _fixup_perms2 instead.'


class MergeMultipleCliTags(DeprecationData):
    label = MERGE_MULTIPLE_CLI_TAGS
    version = 2.5
    removed = False
    message = 'Specifying --tags multiple times on the command line currently uses the last specified value. In 2.4, values will be merged instead.  Set merge_multiple_cli_tags=True in ansible.cfg to get this behavior now.'

    def mitigated(self):
        '''If user has explicitly enable MERGE_MULTIPLE_CLI_TAGS, dont warn.

        Also checks if deprecation is in DEFAULT_DEPRECATIONS_TO_IGNORE.'''
        return C.MERGE_MULTIPLE_CLI_TAGS or super(MergeMultipleCliTags, self).mitigated()


class MergeMultipleCliSkipTags(DeprecationData):
    label = MERGE_MULTIPLE_CLI_SKIP_TAGS
    version = 2.5
    removed = False
    message = 'Specifying --skip-tags multiple times on the command line currently uses the last specified value. In 2.4, values will be merged instead.  Set merge_multiple_cli_tags=True in ansible.cfg to get this behavior now.'

    def mitigated(self):
        '''If user has explicitly enable MERGE_MULTIPLE_CLI_TAGS, dont warn.

        Also checks if deprecation is in DEFAULT_DEPRECATIONS_TO_IGNORE.'''
        return C.MERGE_MULTIPLE_CLI_TAGS or super(MergeMultipleCliSkipTags, self).mitigated()


class TaskAlwaysRun(DeprecationData):
    label = TASK_ALWAYS_RUN
    version = 2.4
    removed = False
    message = 'always_run is deprecated. Use check_mode = no instead.'


class BareVariables(DeprecationData):
    label = BARE_VARIABLES
    version = None
    removed = None
    message = "Using bare variables is deprecated. Update your playbooks so that the environment value uses the full variable syntax."


class TagsInIncludeParameters(DeprecationData):
    label = TAGS_IN_INCLUDE_PARAMETERS
    version = 2.2
    removed = None
    message = "You should not specify tags in the include parameters. All tags should be specified using the task-level option"


class SudoUsage(DeprecationData):
    label = SUDO_USAGE
    version = 2.0
    removed = None
    message = "Instead of sudo/sudo_user, use become/become_user and set become_method to 'sudo' (default is sudo)"


class SuUsage(DeprecationData):
    label = SU_USAGE
    version = 2.0
    removed = None
    message = "Instead of su/su_user, use become/become_user and set become_method to 'su' (default is sudo)"


class TaskParamVariables(DeprecationData):
    label = TASK_PARAM_VARIABLES
    version = None
    removed = None
    message = "Using variables for task params is unsafe, especially if the variables come from an external source like facts"


class AcceleratedMode(DeprecationData):
    label = ACCELERATED_MODE
    version = 2.1
    removed = None
    message = "Accelerated mode is deprecated. Consider using SSH with ControlPersist and pipelining enabled instead"


# API stuff
# TODO: it would be useful to seperate deprecations from user facing features from developer features
class ToBytes(DeprecationData):
    label = TO_BYTES
    version = 2.4
    removed = None
    message = u'ansible.utils.unicode.to_bytes is deprecated.  Use ansible.module_utils._text.to_bytes instead'


class ToUnicode(DeprecationData):
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


# Track deprecations seen, at least for the lifetime of a
# Deprecations() obj, which isn't super useful atm since it's not
# shared across WorkerProcesses...
class SeenDeprecation(object):
    def __init__(self, depr, result, where=None):
        self.depr = depr
        self.result = result
        self.where = where


class Deprecations(object):
    def __init__(self):
        # map of DeprecationData.label to a Deprecation()
        self._registry = {}
        self.output_handler = None
        self.seen_deprs = []

    def add(self, label, depr):
        self._registry[label] = depr

    def add_depr_data_class(self, depr_data_class, reaction):
        depr_data = depr_data_class()
        depr = Deprecation(depr_data, reaction)
        self.add(depr_data.label, depr)
        return depr

    def __iter__(self):
        return iter(self._registry)

    # This is to catch deprecations added at run time
    def _find(self, label):
        # we dont have a full Deprecation() object
        depr = self._registry.get(label, None)
        if depr:
            return depr

        # see if the label has a class registered
        depr_data_class = _deprecations_registry.get(label)
        if not depr_data_class:
            return None

        # There was a DeprecationData class registered, but it didn't get added to Deprecations()
        # so add with default reaction
        return self.add_depr_data_class(depr_data_class, default_reaction)

    def check(self, label, message=None, where=None):
        # default to a DeprecationNotFound?
        depr = self._find(label)

        if not depr:
            return Results.NOT_FOUND

        check_result = depr.check(message=message,
                                  where=where)

        self.seen_deprs.append(SeenDeprecation(depr, check_result, where=where))

        return check_result

    def removed(self, label):
        depr = self._find(label)
        return depr.removed()


# deprecation instance don't have to be defined and created here,
# other modules could create them and register them here.

# TODO: worth trying to be clever about registering these
#       auto-magically (ie, a metaclass that keeps track?)
# REVISIT: remove metaclass if too annoying

_deprecations = Deprecations()


def check(label, message=None, where=None):
    '''where is an 'ansible_pos' style tuple of ('filename', line_number, column_number)'''
    # side-effects include displaying of messages via display_callback
    return _deprecations.check(label, message=message, where=where)


def removed(label):
    return _deprecations.removed(label)


# FIXME: only the list of deprecations seen in the current process so far
#        DeprecationData() instances added at runtime from worker process will be missed...
#        Make need to track multiple isntances and accumulate once/if the per process/play info
#        is shared.
def list_deprecations():
    return sorted(_deprecations_registry.values())
