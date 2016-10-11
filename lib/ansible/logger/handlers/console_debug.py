
from ansible.logger.handlers import debug as console_debug_handler
from ansible.logger.formatters import console_debug as console_debug_formatter


class ConsoleDebugHandler(console_debug_handler.DebugHandler):
    """Logging handler for output to a console, with optional colors."""
    def __init__(self, *args, **kwargs):
        super(ConsoleDebugHandler, self).__init__(*args, **kwargs)
        # Default will use a DebugFormatter
        if self.isatty:
            self.setFormatter(console_debug_formatter.ConsoleDebugFormatter())

    @property
    def isatty(self):
        if hasattr(self.stream, 'isatty'):
            return self.stream.isatty()
        return False
