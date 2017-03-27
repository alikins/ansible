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

import os
import platform
import re

# FIXME: only Distribution uses get_uname_version()
from ansible.module_utils.facts.utils import get_file_content


# FIXME: be consitent about wrapped command (and files)
def get_uname_version(module):
    rc, out, err = module.run_command(['uname', '-v'])
    if rc == 0:
        return out
    return None


class Distribution(object):
    """
    This subclass of Facts fills the distribution, distribution_version and distribution_release variables

    To do so it checks the existence and content of typical files in /etc containing distribution information

    This is unit tested. Please extend the tests to cover all distributions if you have them available.
    """

    # every distribution name mentioned here, must have one of
    #  - allowempty == True
    #  - be listed in SEARCH_STRING
    #  - have a function get_distribution_DISTNAME implemented
    OSDIST_LIST = (
        {'path': '/etc/oracle-release', 'name': 'OracleLinux'},
        {'path': '/etc/slackware-version', 'name': 'Slackware'},
        {'path': '/etc/redhat-release', 'name': 'RedHat'},
        {'path': '/etc/vmware-release', 'name': 'VMwareESX', 'allowempty': True},
        {'path': '/etc/openwrt_release', 'name': 'OpenWrt'},
        {'path': '/etc/system-release', 'name': 'Amazon'},
        {'path': '/etc/alpine-release', 'name': 'Alpine'},
        {'path': '/etc/arch-release', 'name': 'Archlinux', 'allowempty': True},
        {'path': '/etc/os-release', 'name': 'SuSE'},
        {'path': '/etc/SuSE-release', 'name': 'SuSE'},
        {'path': '/etc/gentoo-release', 'name': 'Gentoo'},
        {'path': '/etc/os-release', 'name': 'Debian'},
        {'path': '/etc/lsb-release', 'name': 'Mandriva'},
        {'path': '/etc/altlinux-release', 'name': 'Altlinux'},
        {'path': '/etc/sourcemage-release', 'name': 'SMGL'},
        {'path': '/etc/os-release', 'name': 'NA'},
        {'path': '/etc/coreos/update.conf', 'name': 'Coreos'},
        {'path': '/usr/lib/os-release', 'name': 'ClearLinux'},
    )

    SEARCH_STRING = {
        'OracleLinux': 'Oracle Linux',
        'RedHat': 'Red Hat',
        'Altlinux': 'ALT Linux',
        'ClearLinux': 'Clear Linux Software for Intel Architecture',
        'SMGL': 'Source Mage GNU/Linux',
    }

    # A list with OS Family members
    OS_FAMILY = dict(
        RedHat='RedHat', Fedora='RedHat', CentOS='RedHat', Scientific='RedHat',
        SLC='RedHat', Ascendos='RedHat', CloudLinux='RedHat', PSBM='RedHat',
        OracleLinux='RedHat', OVS='RedHat', OEL='RedHat', Amazon='RedHat', Virtuozzo = 'RedHat',
        XenServer='RedHat', Ubuntu='Debian', Debian='Debian', Raspbian='Debian', Slackware='Slackware', SLES='Suse',
        SLED='Suse', openSUSE='Suse', openSUSE_Tumbleweed='Suse', SuSE='Suse', SLES_SAP='Suse', SUSE_LINUX='Suse', Gentoo='Gentoo',
        Funtoo='Gentoo', Archlinux='Archlinux', Manjaro='Archlinux', Mandriva='Mandrake', Mandrake='Mandrake', Altlinux='Altlinux', SMGL='SMGL',
        Solaris='Solaris', Nexenta='Solaris', OmniOS='Solaris', OpenIndiana='Solaris',
        SmartOS='Solaris', AIX='AIX', Alpine='Alpine', MacOSX='Darwin',
        FreeBSD='FreeBSD', HPUX='HP-UX', openSUSE_Leap='Suse', Neon='Debian'
    )

    def __init__(self, module):
        self.system = platform.system()
        self.facts = {}
        self.module = module

    def populate(self):
        self.get_distribution_facts()
        return self.facts

    def get_distribution_facts(self):
        # The platform module provides information about the running
        # system/distribution. Use this as a baseline and fix buggy systems
        # afterwards
        self.facts['distribution'] = self.system
        self.facts['distribution_release'] = platform.release()
        self.facts['distribution_version'] = platform.version()
        systems_implemented = ('AIX', 'HP-UX', 'Darwin', 'FreeBSD', 'OpenBSD', 'SunOS', 'DragonFly', 'NetBSD')

        self.facts['distribution'] = self.system

        if self.system in systems_implemented:
            cleanedname = self.system.replace('-', '')
            distfunc = getattr(self, 'get_distribution_' + cleanedname)
            distfunc()
        elif self.system == 'Linux':
            # try to find out which linux distribution this is
            dist = platform.dist()
            self.facts['distribution'] = dist[0].capitalize() or 'NA'
            self.facts['distribution_version'] = dist[1] or 'NA'
            self.facts['distribution_major_version'] = dist[1].split('.')[0] or 'NA'
            self.facts['distribution_release'] = dist[2] or 'NA'
            # Try to handle the exceptions now ...
            # self.facts['distribution_debug'] = []
            for ddict in self.OSDIST_LIST:
                name = ddict['name']
                path = ddict['path']

                if not os.path.exists(path):
                    continue
                # if allowempty is set, we only check for file existance but not content
                if 'allowempty' in ddict and ddict['allowempty']:
                    self.facts['distribution'] = name
                    break
                if os.path.getsize(path) == 0:
                    continue

                data = get_file_content(path)
                if name in self.SEARCH_STRING:
                    # look for the distribution string in the data and replace according to RELEASE_NAME_MAP
                    # only the distribution name is set, the version is assumed to be correct from platform.dist()
                    if self.SEARCH_STRING[name] in data:
                        # this sets distribution=RedHat if 'Red Hat' shows up in data
                        self.facts['distribution'] = name
                    else:
                        # this sets distribution to what's in the data, e.g. CentOS, Scientific, ...
                        self.facts['distribution'] = data.split()[0]
                    break
                else:
                    # call a dedicated function for parsing the file content
                    try:
                        distfunc = getattr(self, 'get_distribution_' + name)
                        parsed = distfunc(name, data, path)
                        if parsed is None or parsed:
                            # distfunc return False if parsing failed
                            # break only if parsing was succesful
                            # otherwise continue with other distributions
                            break
                    except AttributeError:
                        # this should never happen, but if it does fail quitely and not with a traceback
                        pass

                    # to debug multiple matching release files, one can use:
                    # self.facts['distribution_debug'].append({path + ' ' + name:
                    #         (parsed,
                    #          self.facts['distribution'],
                    #          self.facts['distribution_version'],
                    #          self.facts['distribution_release'],
                    #          )})

        self.facts['os_family'] = self.facts['distribution']
        distro = self.facts['distribution'].replace(' ', '_')
        if distro in self.OS_FAMILY:
            self.facts['os_family'] = self.OS_FAMILY[distro]

    def get_distribution_AIX(self):
        rc, out, err = self.module.run_command("/usr/bin/oslevel")
        data = out.split('.')
        self.facts['distribution_version'] = data[0]
        self.facts['distribution_release'] = data[1]

    def get_distribution_HPUX(self):
        rc, out, err = self.module.run_command("/usr/sbin/swlist |egrep 'HPUX.*OE.*[AB].[0-9]+\.[0-9]+'", use_unsafe_shell=True)
        data = re.search('HPUX.*OE.*([AB].[0-9]+\.[0-9]+)\.([0-9]+).*', out)
        if data:
            self.facts['distribution_version'] = data.groups()[0]
            self.facts['distribution_release'] = data.groups()[1]

    def get_distribution_Darwin(self):
        self.facts['distribution'] = 'MacOSX'
        rc, out, err = self.module.run_command("/usr/bin/sw_vers -productVersion")
        data = out.split()[-1]
        self.facts['distribution_version'] = data

    def get_distribution_FreeBSD(self):
        self.facts['distribution_release'] = platform.release()
        data = re.search('(\d+)\.(\d+)-RELEASE.*', self.facts['distribution_release'])
        if data:
            self.facts['distribution_major_version'] = data.group(1)
            self.facts['distribution_version'] = '%s.%s' % (data.group(1), data.group(2))

    def get_distribution_OpenBSD(self):
        self.facts['distribution_version'] = platform.release()
        rc, out, err = self.module.run_command("/sbin/sysctl -n kern.version")
        match = re.match('OpenBSD\s[0-9]+.[0-9]+-(\S+)\s.*', out)
        if match:
            self.facts['distribution_release'] = match.groups()[0]
        else:
            self.facts['distribution_release'] = 'release'

    def get_distribution_DragonFly(self):
        pass

    def get_distribution_NetBSD(self):
        self.facts['distribution_major_version'] = self.facts['distribution_release'].split('.')[0]

    def get_distribution_Slackware(self, name, data, path):
        if 'Slackware' not in data:
            return False  # TODO: remove
        self.facts['distribution'] = name
        version = re.findall('\w+[.]\w+', data)
        if version:
            self.facts['distribution_version'] = version[0]

    def get_distribution_Amazon(self, name, data, path):
        if 'Amazon' not in data:
            return False  # TODO: remove
        self.facts['distribution'] = 'Amazon'
        self.facts['distribution_version'] = data.split()[-1]

    def get_distribution_OpenWrt(self, name, data, path):
        if 'OpenWrt' not in data:
            return False  # TODO: remove
        self.facts['distribution'] = name
        version = re.search('DISTRIB_RELEASE="(.*)"', data)
        if version:
            self.facts['distribution_version'] = version.groups()[0]
        release = re.search('DISTRIB_CODENAME="(.*)"', data)
        if release:
            self.facts['distribution_release'] = release.groups()[0]

    def get_distribution_Alpine(self, name, data, path):
        self.facts['distribution'] = 'Alpine'
        self.facts['distribution_version'] = data

    def get_distribution_SMGL(self):
        self.facts['distribution'] = 'Source Mage GNU/Linux'

    def get_distribution_SunOS(self):
        data = get_file_content('/etc/release').splitlines()[0]
        if 'Solaris' in data:
            ora_prefix = ''
            if 'Oracle Solaris' in data:
                data = data.replace('Oracle ', '')
                ora_prefix = 'Oracle '
            self.facts['distribution'] = data.split()[0]
            self.facts['distribution_version'] = data.split()[1]
            self.facts['distribution_release'] = ora_prefix + data
            return

        uname_v = get_uname_version(self.module)
        distribution_version = None
        if 'SmartOS' in data:
            self.facts['distribution'] = 'SmartOS'
            if os.path.exists('/etc/product'):
                product_data = dict([l.split(': ', 1) for l in get_file_content('/etc/product').splitlines() if ': ' in l])
                if 'Image' in product_data:
                    distribution_version = product_data.get('Image').split()[-1]
        elif 'OpenIndiana' in data:
            self.facts['distribution'] = 'OpenIndiana'
        elif 'OmniOS' in data:
            self.facts['distribution'] = 'OmniOS'
            distribution_version = data.split()[-1]
        elif uname_v is not None and 'NexentaOS_' in uname_v:
            self.facts['distribution'] = 'Nexenta'
            distribution_version = data.split()[-1].lstrip('v')

        if self.facts['distribution'] in ('SmartOS', 'OpenIndiana', 'OmniOS', 'Nexenta'):
            self.facts['distribution_release'] = data.strip()
            if distribution_version is not None:
                self.facts['distribution_version'] = distribution_version
            elif uname_v is not None:
                self.facts['distribution_version'] = uname_v.splitlines()[0].strip()
            return

        return False  # TODO: remove if tested without this

    def get_distribution_SuSE(self, name, data, path):
        if 'suse' not in data.lower():
            return False  # TODO: remove if tested without this
        if path == '/etc/os-release':
            for line in data.splitlines():
                distribution = re.search("^NAME=(.*)", line)
                if distribution:
                    self.facts['distribution'] = distribution.group(1).strip('"')
                # example pattern are 13.04 13.0 13
                distribution_version = re.search('^VERSION_ID="?([0-9]+\.?[0-9]*)"?', line)
                if distribution_version:
                    self.facts['distribution_version'] = distribution_version.group(1)
                if 'open' in data.lower():
                    release = re.search('^VERSION_ID="?[0-9]+\.?([0-9]*)"?', line)
                    if release:
                        self.facts['distribution_release'] = release.groups()[0]
                elif 'enterprise' in data.lower() and 'VERSION_ID' in line:
                    # SLES doesn't got funny release names
                    release = re.search('^VERSION_ID="?[0-9]+\.?([0-9]*)"?', line)
                    if release.group(1):
                        release = release.group(1)
                    else:
                        release = "0"  # no minor number, so it is the first release
                    self.facts['distribution_release'] = release
        elif path == '/etc/SuSE-release':
            if 'open' in data.lower():
                data = data.splitlines()
                distdata = get_file_content(path).splitlines()[0]
                self.facts['distribution'] = distdata.split()[0]
                for line in data:
                    release = re.search('CODENAME *= *([^\n]+)', line)
                    if release:
                        self.facts['distribution_release'] = release.groups()[0].strip()
            elif 'enterprise' in data.lower():
                lines = data.splitlines()
                distribution = lines[0].split()[0]
                if "Server" in data:
                    self.facts['distribution'] = "SLES"
                elif "Desktop" in data:
                    self.facts['distribution'] = "SLED"
                for line in lines:
                    release = re.search('PATCHLEVEL = ([0-9]+)', line)  # SLES doesn't got funny release names
                    if release:
                        self.facts['distribution_release'] = release.group(1)
                        self.facts['distribution_version'] = self.facts['distribution_version'] + '.' + release.group(1)

    def get_distribution_Debian(self, name, data, path):
        if 'Debian' in data or 'Raspbian' in data:
            self.facts['distribution'] = 'Debian'
            release = re.search("PRETTY_NAME=[^(]+ \(?([^)]+?)\)", data)
            if release:
                self.facts['distribution_release'] = release.groups()[0]

            # Last resort: try to find release from tzdata as either lsb is missing or this is very old debian
            if self.facts['distribution_release'] == 'NA' and 'Debian' in data:
                dpkg_cmd = self.module.get_bin_path('dpkg')
                if dpkg_cmd:
                    cmd = "%s --status tzdata|grep Provides|cut -f2 -d'-'" % dpkg_cmd
                    rc, out, err = self.module.run_command(cmd)
                    if rc == 0:
                        self.facts['distribution_release'] = out.strip()
        elif 'Ubuntu' in data:
            self.facts['distribution'] = 'Ubuntu'
            # nothing else to do, Ubuntu gets correct info from python functions
        else:
            return False

    def get_distribution_Mandriva(self, name, data, path):
        if 'Mandriva' in data:
            self.facts['distribution'] = 'Mandriva'
            version = re.search('DISTRIB_RELEASE="(.*)"', data)
            if version:
                self.facts['distribution_version'] = version.groups()[0]
            release = re.search('DISTRIB_CODENAME="(.*)"', data)
            if release:
                self.facts['distribution_release'] = release.groups()[0]
            self.facts['distribution'] = name
        else:
            return False

    def get_distribution_NA(self, name, data, path):
        for line in data.splitlines():
            distribution = re.search("^NAME=(.*)", line)
            if distribution and self.facts['distribution'] == 'NA':
                self.facts['distribution'] = distribution.group(1).strip('"')
            version = re.search("^VERSION=(.*)", line)
            if version and self.facts['distribution_version'] == 'NA':
                self.facts['distribution_version'] = version.group(1).strip('"')

    def get_distribution_Coreos(self, name, data, path):
        if self.facts['distribution'].lower() == 'coreos':
            if not data:
                # include fix from #15230, #15228
                return
            release = re.search("^GROUP=(.*)", data)
            if release:
                self.facts['distribution_release'] = release.group(1).strip('"')
        else:
            return False  # TODO: remove if tested without this
