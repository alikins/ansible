
#from ansible.module_utils.facts.virtual import aix
#from ansible.module_utils.facts.virtual import darwin
from ansible.module_utils.facts.virtual import dragonfly
from ansible.module_utils.facts.virtual import freebsd
from ansible.module_utils.facts.virtual import hpux
#from ansible.module_utils.facts.virtual import hurd
from ansible.module_utils.facts.virtual import linux
#from ansible.module_utils.facts.virtual import netbsd
#from ansible.module_utils.facts.virtual import openbsd
from ansible.module_utils.facts.virtual import sunos

__all__ = [dragonfly, freebsd, hpux, linux, sunos]
