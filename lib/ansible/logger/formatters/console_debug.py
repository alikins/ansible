
import logging

from ansible import constants as C
from ansible.utils import color

from ansible.logger.formatters import debug as debug_formatter
from ansible.logger import levels

# TODO: add 'VVV' levels
level_to_ansible_color = {logging.NOTSET: None,
                          logging.DEBUG: C.COLOR_DEBUG,
                          logging.INFO: None,
                          logging.WARN: C.COLOR_WARN,
                          logging.ERROR: C.COLOR_ERROR,
                          logging.CRITICAL: C.COLOR_UNREACHABLE,
                          # the old 'vvv' levels
                          levels.V: C.COLOR_VERBOSE,
                          levels.VV: C.COLOR_VERBOSE,
                          levels.VVV: C.COLOR_VERBOSE,
                          levels.VVVV: C.COLOR_VERBOSE,
                          levels.VVVVV: C.COLOR_DEBUG,
                          }


class ConsoleDebugFormatter(debug_formatter.DebugFormatter):
    def format(self, record):
        message = super(ConsoleDebugFormatter, self).format(record)
        return self._color(message, record.levelno)

    def _color(self, message, level):
        color_code = level_to_ansible_color.get(level, None)
        if not color_code:
            return message
        return self._colorize(message, color_code)

    # more or less ansible.utils.color.stringc, except without the check if stdout is a tty, since
    # we are going to log to stderr by default and we let the handler decide if stream is a tty
    def _colorize(self, message, color_code):
        return u"\033[%sm%s\033[0m" % (color.codeCodes[color_code], message)
