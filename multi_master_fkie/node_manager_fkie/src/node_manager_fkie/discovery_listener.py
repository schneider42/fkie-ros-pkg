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

import threading
import time

from PySide import QtCore

import roslib; roslib.load_manifest('node_manager_fkie')
import rospy

try:
  from master_discovery_fkie.msg import *
  from master_discovery_fkie.srv import *
except ImportError, e:
  import sys
  print >> sys.stderr, "Can't import massages and services of master_discovery_fkie. Is master_discovery_fkie package compiled?"
  raise ImportError(str(e))

import master_discovery_fkie.interface_finder as interface_finder
from master_discovery_fkie.master_monitor import MasterMonitor, MasterConnectionException


class MasterListService(QtCore.QObject):
  '''
  A class to retrieve the ROS master list from a ROS service. The service
  will be determine using L{master_discovery_fkie.interface_finder.get_listmaster_service()}

  '''
  masterlist_signal = QtCore.Signal(list)
  '''@ivar: a signal with a list of the masters retrieved from the master_discovery service 'list_masters'.
  ParameterB{:} C{[L{master_discovery_fkie.ROSMaster}, ...]}'''
  masterlist_err_signal = QtCore.Signal(str)
  '''@ivar: this signal is emitted if an error while calling #list_masters' 
  service of master_discovery is failed.
  ParameterB{:} C{str}'''
  
  def retrieveMasterList(self, masteruri, wait=True):
    '''
    This method use the service 'list_masters' of the master_discovery to get 
    the list of discovered ROS master. The retrieved list will be emitted as 
    masterlist_signal.
    @param masteruri: the ROS master URI
    @type masteruri: C{str}
    @param wait: wait for the service
    @type wait: C{boolean}
    '''
    found = False
    service_names = interface_finder.get_listmaster_service(masteruri, wait)
    for service_name in service_names:
      rospy.loginfo("service 'list_masters' found on %s as %s", masteruri, service_name)
      rospy.wait_for_service(service_name)
      discoverMasters = rospy.ServiceProxy(service_name, DiscoverMasters)
      try:
        resp = discoverMasters()
      except rospy.ServiceException, e:
        rospy.logwarn("ERROR Service call 'list_masters' failed: %s", str(e))
        self.masterlist_err_signal.emit("ERROR Service call 'list_masters' failed: %s", str(e))
      else:
        self.masterlist_signal.emit(resp.masters)
        found = True
    return found



class MasterStateTopic(QtCore.QObject):
  '''
  A class to receive the ROS master state updates from a ROS topic. The topic
  will be determine using L{master_discovery_fkie.interface_finder.get_changes_topic()}.
  '''
  state_signal = QtCore.Signal(master_discovery_fkie.msg.MasterState)
  '''@ivar: a signal to inform the receiver about new master state. 
  Parameter: L{master_discovery_fkie.msg.MasterState}'''

  def registerByROS(self, masteruri, wait=True):
    '''
    This method creates a ROS subscriber to received the notifications of ROS 
    master updates. The retrieved messages will be emitted as state_signal.
    @param masteruri: the ROS master URI
    @type masteruri: C{str}
    @param wait: wait for the topic
    @type wait: C{boolean}
    '''
    found = False
    topic_names = interface_finder.get_changes_topic(masteruri, wait)
    self.stop()
    self.sub_changes = []
    for topic_name in topic_names:
      rospy.loginfo("listen for updates on %s", topic_name)
      sub_changes = rospy.Subscriber(topic_name, master_discovery_fkie.msg.MasterState, self.handlerMasterStateMsg)
      self.sub_changes.append(sub_changes)
      found = True
    return found

  def stop(self):
    '''
    Unregister the subscribed topics
    '''
    if hasattr(self, 'sub_changes'):
      for s in self.sub_changes:
        s.unregister()
      del self.sub_changes

  def handlerMasterStateMsg(self, msg):
    '''
    The method to handle the received MasterState messages. The received message
    will be emitted as state_signal.
    @param msg: the received message
    @type msg: L{master_discovery_fkie.MasterState}
    '''
    self.state_signal.emit(msg)


class MasterStatisticTopic(QtCore.QObject):
  '''
  A class to receive the connections statistics from a ROS topic. The topic
  will be determine using L{master_discovery_fkie.interface_finder.get_stats_topic()}
  '''
  stats_signal = QtCore.Signal(master_discovery_fkie.msg.LinkStatesStamped)
  '''@ivar: a signal with a list of link states to discovered ROS masters.
  Paramter: L{master_discovery_fkie.msg.LinkStatesStamped}'''

  def registerByROS(self, masteruri, wait=True):
    '''
    This method creates a ROS subscriber to received the notifications of 
    connection updates. The retrieved messages will be emitted as stats_signal.
    @param masteruri: the ROS master URI
    @type masteruri: str
    @param wait: wait for the topic
    @type wait: boolean
    '''
    found = False
    self.stop()
    self.sub_stats = []
    topic_names = interface_finder.get_stats_topic(masteruri, wait)
    for topic_name in topic_names:
      pass
      rospy.loginfo("listen for connection statistics on %s", topic_name)
      sub_stats = rospy.Subscriber(topic_name, master_discovery_fkie.msg.LinkStatesStamped, self.handlerMasterStatsMsg)
      self.sub_stats.append(sub_stats)
      found = True
    return found

  def stop(self):
    '''
    Unregister the subscribed topics.
    '''
    if hasattr(self, 'sub_stats'):
      for s in self.sub_stats:
        s.unregister()
      del self.sub_stats

  def handlerMasterStatsMsg(self, msg):
    '''
    The method to handle the received LinkStatesStamped messages. The received 
    message will be emitted as stats_signal.
    @param msg: the received message
    @type msg: L{master_discovery_fkie.LinkStatesStamped}
    '''
    self.stats_signal.emit(msg.links)


class OwnMasterMonitoring(QtCore.QObject):
  '''
  A class to monitor the state of the master. Will be used, if no master 
  discovering is available. On changes the 'state_signal' of type 
  L{master_discovery_fkie.msg.MasterState} will be emitted.
  '''
  state_signal = QtCore.Signal(master_discovery_fkie.msg.MasterState)
  '''@ivar: a signal to inform the receiver about new master state. 
  Parameter: L{master_discovery_fkie.msg.MasterState}'''
  
  ROSMASTER_HZ = 1
  '''@ivar: the rate to test ROS master for changes.'''
  
  def init(self, monitor_port):
    '''
    Creates the local monitoring. Call start() to run the local monitoring.
    @param monitor_port: the port of the XML-RPC Server created by monitoring class.
    @type monitor_port: C{int}
    '''
    self._master_monitor = MasterMonitor(monitor_port)
    self._do_pause = True
#    self._local_addr = roslib.network.get_local_address()
#    self._masteruri = roslib.rosenv.get_master_uri()
    self._masteruri = self._master_monitor.getMasteruri()
    self._local_addr = self._master_monitor.getMastername()
    self._masterMonitorThread = threading.Thread(target = self.mastermonitor_loop)
    self._masterMonitorThread.setDaemon(True)
    self._masterMonitorThread.start()

  def mastermonitor_loop(self):
    '''
    The method test periodically the state of the ROS master. The new state will
    be published as 'state_signal'.
    '''
    import os
    current_check_hz = OwnMasterMonitoring.ROSMASTER_HZ
    while (not rospy.is_shutdown()):
      try:
        if not self._do_pause:
          cputimes = os.times()
          cputime_init = cputimes[0] + cputimes[1]
          if self._master_monitor.checkState():
            mon_state = self._master_monitor.getState()
            # publish the new state
            state = MasterState(MasterState.STATE_CHANGED, 
                                ROSMaster(str(self._local_addr), 
                                          str(self._masteruri), 
                                          mon_state.timestamp, 
                                          True, 
                                          rospy.get_name(), 
                                          ''.join(['http://', str(self._local_addr),':',str(self._master_monitor.rpcport)])))
            self.state_signal.emit(state)
          # adapt the check rate to the CPU usage time
          cputimes = os.times()
          cputime = cputimes[0] + cputimes[1] - cputime_init
          if current_check_hz*cputime > 0.4:
            current_check_hz = float(current_check_hz)/2.0
          elif current_check_hz*cputime < 0.20 and current_check_hz < OwnMasterMonitoring.ROSMASTER_HZ:
            current_check_hz = float(current_check_hz)*2.0
      except MasterConnectionException, e:
        rospy.logwarn("Error while master check loop: %s", str(e))
      except RuntimeError, e:
        # will thrown on exit of the app while try to emit the signal
        rospy.logwarn("Error while master check loop: %s", str(e))
      time.sleep(1.0/current_check_hz)
  
  def pause(self, state):
    '''
    Sets the local monitoring to pause.
    @param state: On/Off pause
    @type state: C{boolean}
    '''
    if not state and self._do_pause != state:
      self._master_monitor.reset()
    self._do_pause = state

  def isPaused(self):
    '''
    @return: True if the local monitoring of the Master state is paused.
    @rtype: C{boolean}
    '''
    return self._do_pause

