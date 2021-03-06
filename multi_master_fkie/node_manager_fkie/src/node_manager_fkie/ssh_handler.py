# Software License Agreement (BSD License)
#
# Copyright (c) 2012, Fraunhofer FKIE/US, Alexander Tiderko
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#  * Neither the name of I Heart Engineering nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import sys
import shlex
import subprocess
from threading import RLock

try:
  import paramiko
except Exception, e:
  print  >> sys.stderr, e
  sys.exit(1)

import rospy
import node_manager_fkie as nm

class SSHhandler(object):
  '''
  The class to handle the SSH sessions to the remote hosts.
  '''
  USER_DEFAULT = 'robot'
  SSH_SESSIONS = {}
  SSH_AUTH = {}


  def __init__(self):
    self.mutex = RLock()

  def close(self):
    '''
    Closes all open SSH sessions. Used on the closing the node manager.
    '''
    # close all ssh sessions
    for ssh in SSHhandler.SSH_SESSIONS.keys():
      s = SSHhandler.SSH_SESSIONS.pop(ssh)
      if not s._transport is None:
        s.close()
      del s

  def ssh_exec(self, host, cmd, user=None, pw=None):
    '''
    Executes a command on remote host. Returns the output channels with 
    execution result or None. The connection will be established using paramiko 
    SSH library.
    @param host: the host
    @type host: C{str}
    @param cmd: the list with command and arguments
    @type cmd: C{[str,...]}
    @param user: user name
    @param pw: the password
    @return: the (stdin, stdout, stderr) and boolean of the executing command
    @rtype: C{tuple(ChannelFile, ChannelFile, ChannelFile), boolean}
    @see: U{http://www.lag.net/paramiko/docs/paramiko.SSHClient-class.html#exec_command}
    '''
    try:
      self.mutex.acquire()
      ssh = self._getSSH(host, self.USER_DEFAULT if user is None else user, pw)
      if not ssh is None:
        rospy.loginfo("REMOTE execute: %s",' '.join(cmd))
        return ssh.exec_command(' '.join(cmd)), True
      else:
        return (None, None, None), False
    finally:
      self.mutex.release()

    
  def ssh_x11_exec(self, host, cmd, title=None, user=None):
    '''
    Executes a command on remote host using a terminal with X11 forwarding. 
    @todo: establish connection using paramiko SSH library.
    @param host: the host
    @type host: C{str}
    @param cmd: the list with command and arguments
    @type cmd: C{[str,...]}
    @param title: the title of the new opened terminal, if it is None, no new terminal will be created
    @type title: C{str} or C{None}
    @param user: user name
    @return: the result of C{subprocess.Popen(command)} 
    @see: U{http://docs.python.org/library/subprocess.html?highlight=subproces#subprocess}
    '''
    try:
      self.mutex.acquire()
      # workaround: use ssh in a terminal with X11 forward
      user = self.USER_DEFAULT if user is None else user
      if self.SSH_AUTH.has_key(host):
        user = self.SSH_AUTH[host]
      # generate string for SSH command
      ssh_str = ' '.join(['/usr/bin/ssh',
                          '-aqtx',
                          '-oClearAllForwardings=yes',
                          '-oStrictHostKeyChecking=no',
                          '-oVerifyHostKeyDNS=no',
                          '-oCheckHostIP=no',
                          ''.join([user, '@', host])])
      if not title is None:
        cmd_str = nm.terminal_cmd([ssh_str, ' '.join(cmd)], title)
      else:
        cmd_str = ' '.join([ssh_str, ' '.join(cmd)])
      rospy.loginfo("REMOTE x11 execute: %s",cmd_str)
      return subprocess.Popen(shlex.split(str(cmd_str)))
    finally:
      self.mutex.release()
    
  def _getSSH(self, host, user, pw=None, do_connect=True):
    '''
    @return: the paramiko ssh client
    @rtype: L{paramiko.SSHClient} 
    @raise BadHostKeyException: - if the server's host key could not be verified
    @raise AuthenticationException: - if authentication failed
    @raise SSHException: - if there was any other error connecting or establishing an SSH session
    @raise socket.error: - if a socket error occurred while connecting
    '''
    session = SSHhandler.SSH_SESSIONS.get(host, paramiko.SSHClient())
    if session is None:
      t = SSHhandler.SSH_SESSIONS.pop(host)
      del t
      session = SSHhandler.SSH_SESSIONS.get(host, paramiko.SSHClient())
    if session._transport is None:
      session.set_missing_host_key_policy(paramiko.AutoAddPolicy())
      while (session.get_transport() is None or not session.get_transport().authenticated) and do_connect:
        try:
          session.connect(host, username=user, password=pw, timeout=3)
        except Exception, e:
#          import traceback
#          print traceback.format_exc()
          if str(e) in ['Authentication failed.', 'No authentication methods available']:
            res, user, pw = self._requestPW(user, host)
            if not res:
              return None
            self.SSH_AUTH[host] = user
          else:
            rospy.logwarn("ssh connection to %s failed: %s", host, str(e))
            return None
        else:
          SSHhandler.SSH_SESSIONS[host] = session
      if not session.get_transport() is None:
        session.get_transport().set_keepalive(10)
    return session

  def _requestPW(self, user, host):
    '''
    Open the dialog to input the user name and password to open an SSH connection. 
    '''
    from PySide import QtCore
    from PySide import QtUiTools
    result = False
    pw = None
    loader = QtUiTools.QUiLoader()
    pwInput = loader.load(":/forms/PasswordInput.ui")
    pwInput.setWindowTitle(''.join(['Enter the password for user ', user, ' on ', host]))
    pwInput.userLine.setText(str(user))
    pwInput.pwLine.setText("")
    pwInput.pwLine.setFocus(QtCore.Qt.OtherFocusReason)
    if pwInput.exec_():
      result = True
      user = pwInput.userLine.text()
      pw = pwInput.pwLine.text()
    return result, user, pw
