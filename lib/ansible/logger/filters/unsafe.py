

class UnsafeFilter(object):
    """Used to filter out msg args that are AnsibleUnsafe or have __UNSAFE__ attr."""
    def __init__(self, name):
        self.name = name

    def filter(self, record):
        # FIXME: filter stuff
        return True
