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

import os
import shlex
import subprocess
import xmlrpclib
import threading

import roslib
import rospy
import roslib.network
from ros import roslaunch
import rosgraph.masterapi


from default_cfg_fkie.msg import *
from default_cfg_fkie.srv import *
from screen_handler import ScreenHandler, ScreenHandlerException

class LoadException(Exception):
  ''' The exception throwing while searching for the given launch file. '''
  pass
class StartException(Exception):
  ''' The exception throwing while run a node containing in the loaded configuration. '''
  pass


class DefaultCfg(object):
  
  def __init__(self):
    self.nodes = [] 
    '''@var: the list with names of nodes with name spaces '''
    self.sensors = {}
    '''@ivar: Sensor description: C{dict(node name : [(sensor type, sensor name, sensor description), ...])}'''
    self.robot_descr = ('', '', '')
    '''@ivar: robot description as tupel of (type, name, text) '''
    self.package = ''
    self.file = ''
    self.__lock = threading.RLock()
    # initialize the ROS services
    rospy.Service('~load', LoadLaunch, self.rosservice_load_launch)
    rospy.Service('~description', ListDescription, self.rosservice_description)
    self.runService = None
    '''@ivar: The service will be created on each load of a launch file to
    inform the caller about a new configuration. '''
    self.listService = None
    '''@ivar: The service will be created on each load of a launch file to
    inform the caller about a new configuration. '''
    
    self.global_parameter_setted = False

  
  def load(self, package, file, argv):
    '''
    Load the launch file configuration
    @param package: the package containing the launch file, or empty string to load
    the given file
    @type package: C{str}
    @param file: the launch file or complete path, if the package is empty
    @type file: C{str}
    @param argv: the argv needed to load the launch file
    @type argv: C{str}
    '''
    try:
      self.__lock.acquire()
      # shutdown the services to inform the caller about a new configuration.
      if not self.runService is None:
        self.runService.shutdown('reload config')
      self.runService = None
      if not self.listService is None:
        self.listService.shutdown('reload config')
      self.listService = None
      self.nodes = [] # the name of nodes with namespace
      self.sensors = {} # sensor descriptions
      self.launch_file = launch_file = self.getPath(file, package)
      rospy.loginfo("loading launch file: %s", launch_file)
      self.masteruri = self._masteruri_from_ros()
      self.roscfg = roslaunch.ROSLaunchConfig()
      loader = roslaunch.XmlLoader()
      loader.load(launch_file, self.roscfg, verbose=False, argv=argv)
      # create the list with node names
      for item in self.roscfg.nodes:
        if item.machine_name:
          machine = self.roscfg.machines[item.machine_name]
          if roslib.network.is_local_address(machine.address):
            self.nodes.append(str(''.join([item.namespace, item.name])))
        else:
          self.nodes.append(str(''.join([item.namespace, item.name])))
      # get the robot description
      robot_type = ''
      robot_name = ''
      robot_descr = ''
      for param, p in self.roscfg.params.items():
        if os.path.basename(param) == 'robot_type':
          robot_type = p.value
        if os.path.basename(param) == 'robot_name':
          robot_name = p.value
        if os.path.basename(param) == 'robot_descr':
          robot_descr = p.value
      self.robot_descr = (robot_type, robot_name, robot_descr)

      # get the sensor description
      for nname in self.roscfg.resolved_node_names:
        sensor_type_name = '/'.join([nname, 'sensor_type'])
        sensor_type_value = ''
        if self.roscfg.params.has_key(sensor_type_name):
          sensor_type_value = self.roscfg.params[sensor_type_name].value
        sensor_name_name = '/'.join([nname, 'sensor_name'])
        sensor_name_value = ''
        if self.roscfg.params.has_key(sensor_name_name):
          sensor_name_value = self.roscfg.params[sensor_name_name].value
        sensor_description_name = '/'.join([nname, 'sensor_descr'])
        sensor_description_value = ''
        if self.roscfg.params.has_key(sensor_description_name):
          sensor_description_value = self.roscfg.params[sensor_description_name].value.replace("\\n ", "\n")
        # append valid value to the list
        if sensor_type_value or sensor_name_value or sensor_description_value:
          self.sensors[nname] =   [(sensor_type_value, sensor_name_value, sensor_description_value)]
      # initialize the ROS services
      #HACK to let the node_manager to update the view
      t = threading.Timer(2.0, self._timed_service_creation)
      t.start()
  #    self.timer = rospy.Timer(rospy.Duration(2), self.timed_service_creation, True)
  #    if self.nodes:
  #      self.runService = rospy.Service('~run', Task, self.rosservice_start_node)
  #    self.listService = rospy.Service('~list_nodes', ListNodes, self.rosservice_list_nodes)
    finally:
      self.__lock.release()

  def _masteruri_from_ros(self):
    '''
    Returns the master URI depending on ROS distribution API.
    @return: ROS master URI
    @rtype: C{str}
    '''
    try:
      import rospkg.distro
      distro = rospkg.distro.current_distro_codename()
      if distro in ['electric', 'diamondback', 'cturtle']:
        return roslib.rosenv.get_master_uri()
      else:
        import rosgraph
        return rosgraph.rosenv.get_master_uri()
    except:
      return roslib.rosenv.get_master_uri()

  def _timed_service_creation(self):
    try:
      self.__lock.acquire()
      if self.runService is None:
        self.runService = rospy.Service('~run', Task, self.rosservice_start_node)
      if self.listService is None:
        self.listService = rospy.Service('~list_nodes', ListNodes, self.rosservice_list_nodes)
    finally:
      self.__lock.release()

  def getPath(self, file, package=''):
    '''
    Searches for a launch file. If package is given, try first to find the launch
    file in the given package. If more then one launch file with the same name 
    found in the package, the first one will be tacked.
    @param file: the file name of the launch file
    @type file: C{str}
    @param package: the package containing the launch file or an empty string, 
    if the C{file} is an absolute path
    @type package: C{str}
    @return: the absolute path of the launch file
    @rtype: C{str}
    @raise LoadException: if the given file is not found 
    '''
    launch_file = file
    # if package is set, try to find the launch file in the given package
    if package:
      paths = roslib.packages.find_resource(package, launch_file)
      if len(paths) > 0:
        # if more then one launch file is found, take the first one
        launch_file = paths[0]
    if os.path.isfile(launch_file) and os.path.exists(launch_file):
      return launch_file
    raise LoadException(str(' '.join(['File', file, 'in package ', package, 'not found'])))

  def rosservice_list_nodes(self, req):
    '''
    Callback for the ROS service to get the list with available nodes.
    '''
    return ListNodesResponse(self.nodes)

  def rosservice_start_node(self, req):
    '''
    Callback for the ROS service to start a node.
    '''
    self.runNode(req.node)
    return []
#    except:
#      import traceback
#      return TaskResponse(str(traceback.format_exc().splitlines()[-1]))
#    return TaskResponse('')

  def rosservice_load_launch(self, req):
    '''
    Load the launch file
    '''
    try:
      self.__lock.acquire()
      self.load(req.package, req.file, req.argv)
    finally:
      self.__lock.release()
    return []

  def rosservice_description(self, req):
    '''
    Returns the current description.
    '''
    result = ListDescriptionResponse()
    if req.node:
      if self.sensors.has_key(req.node):
        descr_list = self.sensors[req.node]
        for type, name, descr in descr_list:
          result.items.append(Description(Description.ID_SENSOR, req.node, type, name, descr))
    else:
      (type, name, descr) = self.robot_descr
      if type or name or descr:
        result.items.append(Description(Description.ID_ROBOT, '', type, name, descr))
      for node, descr_list in self.sensors.items():
        for type, name, descr in descr_list:
          result.items.append(Description(Description.ID_SENSOR, node, type, name, descr))
    return result
    
  def runNode(self, node):
    '''
    Start the node with given name from the currently loaded configuration.
    @param node: the name of the node
    @type node: C{str}
    @raise StartException: if an error occurred while start.
    '''
    n = None
    nodename = os.path.basename(node)
    namespace = os.path.dirname(node).strip('/')
    for item in self.roscfg.nodes:
      if (item.name == nodename) and (item.namespace.strip('/') == namespace):
        n = item
        break
    if n is None:
      raise StartException(''.join(["Node '", node, "' not found!"]))
    
    env = n.env_args
    prefix = n.launch_prefix if not n.launch_prefix is None else ''
    args = [''.join(['__ns:=', n.namespace]), ''.join(['__name:=', n.name])]
    if not (n.cwd is None):
      args.append(''.join(['__cwd:=', n.cwd]))
    
    # add remaps
    for remap in n.remap_args:
      args.append(''.join([remap[0], ':=', remap[1]]))

    masteruri = self.masteruri
    
    if n.machine_name:
      machine = self.roscfg.machines[n.machine_name]
      #TODO: env-loader support?
#      if machine.env_args:
#        env[len(env):] = machine.env_args

    # set the global parameter
    if not self.global_parameter_setted:
      global_node_names = self.getGlobalParams(self.roscfg)
      self._load_parameters(masteruri, global_node_names, [])
      self.global_parameter_setted = True

    # add params
    nodens = ''.join([n.namespace, n.name, '/'])
    params = dict()
    for param, value in self.roscfg.params.items():
      if param.startswith(nodens):
        params[param] = value
    clear_params = []
    for cparam in self.roscfg.clear_params:
      if cparam.startswith(nodens):
        clear_params.append(param)
      rospy.loginfo("register PARAMS:\n%s", '\n'.join(params))
    self._load_parameters(masteruri, params, clear_params)


#    nm.screen().testScreen()
    try:
      cmd = roslib.packages.find_node(n.package, n.type)
    except roslib.packages.ROSPkgException as e:
      # multiple nodes, invalid package
      raise StartException(str(e))
    # handle diferent result types str or array of string
    import types
    if isinstance(cmd, types.StringTypes):
      cmd = [cmd]
    if cmd is None or len(cmd) == 0:
      raise StartException(' '.join([n.type, 'in package [', n.package, '] not found!']))
    node_cmd = [prefix, cmd[0]]
    cmd_args = [ScreenHandler.getSceenCmd(node)]
    cmd_args[len(cmd_args):] = node_cmd
    cmd_args.append(n.args)
    cmd_args[len(cmd_args):] = args
#    print 'runNode: ', cmd_args
    popen_cmd = shlex.split(str(' '.join(cmd_args)))
    rospy.loginfo("run node '%s as': %s", node, str(' '.join(popen_cmd)))
    subprocess.Popen(popen_cmd)

  @classmethod
  def getGlobalParams(cls, roscfg):
    '''
    Return the parameter of the configuration file, which are not associated with 
    any nodes in the configuration.
    @param roscfg: the launch configuration
    @type roscfg: L{roslaunch.ROSLaunchConfig}
    @return: the list with names of the global parameter
    @rtype: C{dict(param:value, ...)}
    '''
    result = dict()
    nodes = []
    for item in roscfg.resolved_node_names:
      nodes.append(item)
    for param, value in roscfg.params.items():
      nodesparam = False
      for n in nodes:
        if param.startswith(n):
          nodesparam = True
          break
      if not nodesparam:
        result[param] = value
    return result

  @classmethod
  def _load_parameters(cls, masteruri, params, clear_params):
    """
    Load parameters onto the parameter server
    """
    import roslaunch
    import roslaunch.launch
    import xmlrpclib
    param_server = xmlrpclib.ServerProxy(masteruri)
    p = None
    try:
      # multi-call style xmlrpc
      param_server_multi = xmlrpclib.MultiCall(param_server)

      # clear specified parameter namespaces
      # #2468 unify clear params to prevent error
      for p in clear_params:
        param_server_multi.deleteParam(rospy.get_name(), p)
      r = param_server_multi()
#      for code, msg, _ in r:
#        if code != 1:
#          raise StartException("Failed to clear parameter: %s"%(msg))

      # multi-call objects are not reusable
      param_server_multi = xmlrpclib.MultiCall(param_server)
      for p in params.itervalues():
        # suppressing this as it causes too much spam
        #printlog("setting parameter [%s]"%p.key)
        param_server_multi.setParam(rospy.get_name(), p.key, p.value)
      r  = param_server_multi()
      for code, msg, _ in r:
        if code != 1:
          raise StartException("Failed to set parameter: %s"%(msg))
    except roslaunch.core.RLException, e:
      raise StartException(e)
    except Exception as e:
      raise #re-raise as this is fatal
