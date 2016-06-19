
__all__ = ['urllib_request', 'urllib_error', 'AbstractHTTPHandler', 'urlparse', 'urlunparse', 'HAS_URLPARSE']

import ansible.compat.six.moves.urllib.request as urllib_request
import ansible.compat.six.moves.urllib.error as urllib_error

try:
    # python3
    import urllib.request as urllib_request
    from urllib.request import AbstractHTTPHandler
except ImportError:
    # python2
    import urllib2 as urllib_request
    from urllib2 import AbstractHTTPHandler

try:
    from ansible.compat.six.moves.urllib.parse import urlparse, urlunparse
    HAS_URLPARSE = True
except:
    HAS_URLPARSE = False
