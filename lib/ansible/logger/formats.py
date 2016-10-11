# Various log format strings
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

EVERYTHING_VLOG_FORMAT = "%(asctime)s user=%(user)s cmd_name=%(cmd_name)s argv='%(cmd_line)s' %(processName)s <%(remote_user)s@%(remote_addr)s> [%(name)s %(levelname)s] (pid=%(process)d) tid=%(thread)d:%(threadName)s %(funcName)s:%(lineno)d - %(message)s"

THREAD_DEBUG_LOG_FORMAT = "%(asctime)s user=%(user)s cmd_name=%(cmd_name)s <%(remote_user)s@%(remote_addr)s> [%(name)s %(levelname)s] (pid=%(process)d) tid=%(thread)d:%(threadName)s %(funcName)s:%(lineno)d - %(message)s"

REMOTE_DEBUG_LOG_FORMAT = "%(asctime)s [%(name)s %(levelname)s] (pid=%(process)d,tname=%(threadName)s) %(funcName)s:%(lineno)d - %(message)s"

# aka, splunk or elk
LOG_INDEXER_FRIENDLY_FORMAT = "%(asctime)s logger_name=%(name)s logger_level=%(levelname)s user=%(user)s cmd_name=%(cmd_name)s argv='%(cmd_line)s' process_name=%(processName)s pid=%(process)d tid=%(thread)d thread_name=%(threadName)s remote_user=%(remote_user)s remote_addr=%(remote_addr)s module=%(module)s function=%(funcName)s line_number=%(lineno)d message=%(message)s"
