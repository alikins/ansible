import os


def get_file_content(path, default=None, strip=True):
    data = default
    if os.path.exists(path) and os.access(path, os.R_OK):
        try:
            try:
                datafile = open(path)
                data = datafile.read()
                if strip:
                    data = data.strip()
                if len(data) == 0:
                    data = default
            finally:
                datafile.close()
        except:
            # ignore errors as some jails/containers might have readable permissions but not allow reads to proc
            # done in 2 blocks for 2.4 compat
            pass
    return data


# FIXME: be consitent about wrapped command (and files)
# FIXME: move somewhere better
def get_uname_version(module):
    rc, out, err = module.run_command(['uname', '-v'])
    if rc == 0:
        return out
    return None
