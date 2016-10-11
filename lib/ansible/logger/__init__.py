# logging support for ansible using stdlib logging
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

from ansible.logger.levels import V, VV, VVV, VVVV, VVVVV

# TODO/maybe: Logger subclass with v/vv/vvv etc methods?
# TODO: add logging filter that implements no_log
#       - ideally via '__unsafe__'
#       - AnsibleError could use it in it's str/repr
# TODO: add AnsibleContextLoggingFilter
#       extra records for current_cmd, sys.argv
# TODO: add AnsiblePlaybookLoggingFilter
#       extra records for playbook/play/task/block ?
# TODO: (yaml?) config based logging setup
# TODO: Any log Formatters or Handlers that are ansible specific
# TODO: base logging setup
# TODO: NullHandler for py2.4
# TODO: for unsafe, no_log, in some ways we want the Logger to censor unsafe item, before they
#       get sent to handlers or formatters. We can do that with a custom Logger and
#       logger.setLoggerClass(). The custom logger would define a makeRecord() that would example
#       any passed in records and scrub out sensitive ones. setLoggerClass() is gloabl for entire
#       process, so any used modules that use getLogger will get it as well, so it needs to be
#       robust.
# TODO: exception logging... if we end up using custom Logger, we can add methods for low priority
#       captured exceptions and send to DEBUG instead of ERROR or CRITICAL. Or use a seperate handler
#       and filter exceptions records from main handler.
# MAYBE: custom exception formatter
# TODO: mv filters to a module?
# TODO: hook up logging for run_command argv/in/out/rc (env)?
# TODO: merge worker logging
# TODO: merge module logging
# TODO: logging plugin? plugin would need to be able to run very early
# TODO: add 'deprecated' log... method? deprecated should probably be it's own module, with log/display
#       as possibilities, but seperated from deprecation tracking logic. (so deprecated.seen_deprecation object would be
#       shared and only have one instance per process)
#       But probably just add the deprecated() to AnsibleLogger
