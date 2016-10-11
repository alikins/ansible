

# Another way to do this:
#  since we have a custom default Logger class, we can change it's makeRecord to
#  generate records with these fields populated
class DefaultAttributesFilter(object):
    """Used to make sure every LogRecord has all of our custom attributes.

    if the record doesn't populate an attribute, add it with a default value.

    This prevents log formats that reference custom log record attributes
    from causing a LogFormatter to fail when attempt to format the message."""

    def __init__(self, name):
        self.name = name
        # FIXME: should try to decouple this so it doesn't have to be kept in
        #        sync with the filters/adapters that add record attributes. Maybe not worth the effort.
        self.defaults = {'remote_addr': '',
                         'remote_user': '',
                         'user': '',
                         'cmd_name': '',
                         'cmd_line': ''}

    def filter(self, record):
        # hostname
        for attr_name, default_value in self.defaults.items():
            if not hasattr(record, attr_name):
                # Suppose this could be 'localhost' or 'local' etc
                setattr(record, attr_name, default_value)
        return True
