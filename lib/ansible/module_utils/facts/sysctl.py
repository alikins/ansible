import re

# FIXME: test cases


def get_sysctl(module, prefixes):
    sysctl_cmd = module.get_bin_path('sysctl')
    cmd = [sysctl_cmd]
    cmd.extend(prefixes)

    rc, out, err = module.run_command(cmd)
    if rc != 0:
        return dict()

    sysctl = dict()
    for line in out.splitlines():
        if not line:
            continue
        (key, value) = re.split('\s?=\s?|: ', line, maxsplit=1)
        sysctl[key] = value.strip()

    return sysctl
