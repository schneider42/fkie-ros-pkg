#!/usr/bin/env python
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

__author__ = "Alexander Tiderko (Alexander.Tiderko@fkie.fraunhofer.de)"
__copyright__ = "Copyright (c) 2012 Alexander Tiderko, Fraunhofer FKIE"
__license__ = "BSD"
__version__ = "0.1"
__date__ = "2012-02-01"


import sys

import roslib; roslib.load_manifest('master_sync_fkie')
import rospy

import master_sync

NODE_NAME = "master_sync"


def setTerminalName(name):
  '''
  Change the terminal name.
  @param name: New name of the terminal
  @type name:  C{str}
  '''
  sys.stdout.write("".join(["\x1b]2;",name,"\x07"]))

def setProcessName(name):
  '''
  Change the process name.
  @param name: New process name
  @type name:  C{str}
  '''
  try:
    from ctypes import cdll, byref, create_string_buffer
    libc = cdll.LoadLibrary('libc.so.6')
    buff = create_string_buffer(len(name)+1)
    buff.value = name
    libc.prctl(15, byref(buff), 0, 0, 0)
  except:
    pass


def main():
  '''
  Creates and runs the ROS node.
  '''
  setTerminalName(NODE_NAME)
  setProcessName(NODE_NAME)
  rospy.init_node(NODE_NAME, log_level=rospy.DEBUG)
  # time to initialize the topics to receive these in rxconsole
  rospy.sleep(1)
  discoverer = master_sync.Main()
  rospy.spin()


#if __name__ == '__main__':
#    main()
