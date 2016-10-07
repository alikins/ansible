
from ansible import constants as C
from ansible.errors import AnsibleError

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


# FIXME: floats?
current_version = 2.3

FIXUP_PERMS = 'FIXUP_PERMS'
MERGE_MULTIPLE_CLI_TAGS = 'MERGE_MULTIPLE_CLI_TAGS'
MERGE_MULTIPLE_CLI_SKIP_TAGS = 'MERGE_MULTIPLE_CLI_SKIP_TAGS'
TASK_ALWAYS_RUN = 'TASK_ALWAYS_RUN'


class Deprecation(object):
    label = None
    version = None
    removed = None
    message = None


class FixupPerms(Deprecation):
    label = FIXUP_PERMS
    version = 2.4
    removed = False
    message = '_fixup_perms is deprecated. Use _fixup_perms2 instead.'


class MergeMultipleCliTags(Deprecation):
    label = MERGE_MULTIPLE_CLI_TAGS
    version = 2.5
    removed = False,
    message = 'Specifying --tags multiple times on the command line currently uses the last specified value. In 2.4, values will be merged instead.  Set merge_multiple_cli_tags=True in ansible.cfg to get this behavior now.'

    def mitigated(self):
        '''If user has explicitly enable MERGE_MULTIPLE_CLI_TAGS, dont warn.'''
        return C.MERGE_MULTIPLE_CLI_TAGS


class MergeMultipleCliSkipTags(Deprecation):
    label = MERGE_MULTIPLE_CLI_SKIP_TAGS
    version = 2.5
    removed = False,
    message = 'Specifying --skip-tags multiple times on the command line currently uses the last specified value. In 2.4, values will be merged instead.  Set merge_multiple_cli_tags=True in ansible.cfg to get this behavior now.'

    def mitigated(self):
        '''If user has explicitly enable MERGE_MULTIPLE_CLI_TAGS, dont warn.'''
        return C.MERGE_MULTIPLE_CLI_TAGS


class TaskAlwaysRun(Deprecation):
    label = TASK_ALWAYS_RUN
    version = 2.4
    removed = False,
    message = 'always_run is deprecated. Use check_mode = no instead.'

#TODO:
# task.py include_vars_at_top_of_File
# task_executor using_vars_for_task_params
# accelerated mode


# Default, provide a different one if needed
def display_callback(msg):
    print(msg)


class Deprecations(object):
    future_warning = "This feature will be removed in a future release."
    version_warning = "This feature will be removed in version %s."
    warning_slug = "[DEPRECATION WARNING]: "
    quiet_msg = "Deprecation warnings can be disabled by setting deprecation_warnings=False in ansible.cfg.\n\n"

    def __init__(self):
        self._registry = {}
        self._display_callback = display_callback
        self._quiet_instructions_have_been_shown = False
        # set of all deprecation messages to prevent duplicate display
        self._deprecations_issued = set()

    def add(self, deprecation):
        self._registry[deprecation.label] = deprecation

    def _version_compare(self, a, b):
        # not sure if version is last with, or first without
        return a > b

    def _warn(self, deprecation):
        msg = "%s%s\n%s" % (self.warning_slug,
                          deprecation.message,
                          self.future_warning)
        self._display_callback(msg)

    def _warn_version(self, deprecation):
        # FIXME: implicit int->str
        msg = "%s%s\n%s" % (self.warning_slug,
                          deprecation.version,
                          self.version_warning % deprecation.version)
        self._display_callback(msg)

    def _offer_silence(self):
        # TODO: this assumes we only want to show the quiest message once
        if self._quiet_instructions_have_been_shown:
            return

        self._display_callback("Deprecation warnings can be disabled by setting deprecation_warnings=False in ansible.cfg.\n\n")

        self._quiet_instructions_have_been_shown = True

    def check(self, label):
        deprecation = self._registry.get(label, None)

        # TODO: make an assert/except/error?
        if not deprecation:
            return

        # Yes, it is deprecated. Removed even, but stop telling me.
        if not deprecation.removed and not C.DEPRECATION_WARNINGS:
            return

        if deprecation.mitigated():
            return

        # We are using something that has been removed, fail loudly.
        if not deprecation.removed:
            # TODO: reasonable place to raise a DeprecationError
            raise AnsibleError("[DEPRECATED]: %s.\nPlease update your playbooks." % deprecation.message)

        if deprecation.version:
            if current_version > deprecation.version:
                self._warn_version(deprecation)
            else:
                self._warn(deprecation)

        # Suppose we could put the full Deprecation instance in the set if we make it
        # hashable. That could potentially allow for more sophisticated matching...
        if deprecation.label not in self._deprecations_issued:
            self._deprecations_issued.add(deprecation.label)


# deprecation instance don't have to be defined and created here,
# other modules could create them and register them here.
_deprecations = Deprecations()
_deprecations.add(FixupPerms())
_deprecations.add(MergeMultipleCliTags())
_deprecations.add(MergeMultipleCliSkipTags())
_deprecations.add(TaskAlwaysRun())


def check(label):
    # side-effects include displaying of messages via display_callback
    return _deprecations.check(label)
