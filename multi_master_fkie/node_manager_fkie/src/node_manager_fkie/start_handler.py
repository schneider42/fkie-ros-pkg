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
import os, shlex, subprocess

import roslib
import rospy
import node_manager_fkie as nm
try:
  from launch_config import LaunchConfig
except:
  pass


class StartException(Exception):
  pass

class StartHandler(object):
  '''
  This class contains the methods to run the nodes on local and remote machines
  in a screen terminal.
  '''
  def __init__(self):
    self._lock = threading.RLock()
  
  @classmethod
  def runNode(cls, node, launch_config):
    '''
    Start the node with given name from the given configuration.
    @param node: the name of the node (with name space)
    @type node: C{str}
    @param launch_config: the configuration containing the node
    @type launch_config: L{LaunchConfig} 
    @raise StartException: if the screen is not available on host.
    @raise Exception: on errors while resolving host
    @see: L{node_manager_fkie.is_local()}
    '''
    n = launch_config.getNode(node)
    if n is None:
      raise StartException(''.join(["Node '", node, "' not found!"]))
    
    env = list(n.env_args)
    prefix = n.launch_prefix if not n.launch_prefix is None else ''
    # thus the parameters while the transfer are not separated
    if prefix:
      prefix = ''.join(['"', prefix, '"'])
    args = [''.join(['__ns:=', n.namespace]), ''.join(['__name:=', n.name])]
    if not (n.cwd is None):
      args.append(''.join(['__cwd:=', n.cwd]))
    
    # add remaps
    for remap in n.remap_args:
      args.append(''.join([remap[0], ':=', remap[1]]))

    # get host of the node
    host = launch_config.hostname
    env_loader = ''
    if n.machine_name:
      machine = launch_config.Roscfg.machines[n.machine_name]
      host = machine.address
      #TODO: env-loader support?
#      if hasattr(machine, "env_loader") and machine.env_loader:
#        env_loader = machine.env_loader

    masteruri = nm.nameres().getUri(host=host)
    # set the ROS_MASTER_URI
    if masteruri is None:
      env.append(('ROS_MASTER_URI', nm.masteruri_from_ros()))

    # set the global parameter
    if not masteruri is None and not masteruri in launch_config.global_param_done:
      global_node_names = cls.getGlobalParams(launch_config.Roscfg)
      rospy.loginfo("Register global parameter:\n%s", '\n'.join(global_node_names))
      cls._load_parameters(masteruri, global_node_names, [])
      launch_config.global_param_done.append(masteruri)

    # add params
    if not masteruri is None:
      nodens = ''.join([n.namespace, n.name, '/'])
      params = dict()
      for param, value in launch_config.Roscfg.params.items():
        if param.startswith(nodens):
          params[param] = value
      clear_params = []
      for cparam in launch_config.Roscfg.clear_params:
        if cparam.startswith(nodens):
          clear_params.append(param)
      rospy.loginfo("Register parameter:\n%s", '\n'.join(params))
      cls._load_parameters(masteruri, params, clear_params)
    if nm.is_local(host): 
      nm.screen().testScreen()
      try:
        cmd = roslib.packages.find_node(n.package, n.type)
      except (Exception, roslib.packages.ROSPkgException) as e:
        # multiple nodes, invalid package
        raise StartException(''.join(["Can't find resource: ", str(e)]))
      # handle diferent result types str or array of string
      import types
      if isinstance(cmd, types.StringTypes):
        cmd = [cmd]
      cmd_type = ''
      if cmd is None or len(cmd) == 0:
        raise nm.StartException(' '.join([n.type, 'in package [', n.package, '] not found!\n\nThe package was created?\nIs the binary executable?\n']))
      if len(cmd) > 1:
        # Open selection for executables
        try:
          from PySide import QtGui
          item, result = QtGui.QInputDialog.getItem(None, ' '.join(['Multiple executables', n.type, 'in', n.package]),
                                            'Select an executable',
                                            cmd, 0, False)
          if result:
            #open the selected screen
            cmd_type = item
          else:
            return
        except:
          raise nm.StartException('Multiple executables with same name in package found!')
      else:
        cmd_type = cmd[0]
      node_cmd = [prefix, cmd_type]
      cmd_args = [nm.screen().getSceenCmd(node)]
      cmd_args[len(cmd_args):] = node_cmd
      cmd_args.append(n.args)
      cmd_args[len(cmd_args):] = args
      rospy.loginfo("RUN: %s", ' '.join(cmd_args))
      subprocess.Popen(shlex.split(str(' '.join(cmd_args))))
    else:
      # start remote
      if launch_config.PackageName is None:
        raise StartException(''.join(["Can't run remote without a valid package name!"]))
      # setup environment
      env_command = ''
      if env_loader:
        rospy.logwarn("env_loader in machine tag currently not supported")
        raise nm.StartException("env_loader in machine tag currently not supported")
      if env:
        env_command = "env "+' '.join(["%s=%s"%(k,v) for (k, v) in env])
      
      startcmd = [env_command, nm.STARTER_SCRIPT, 
                  '--package', str(n.package),
                  '--node_type', str(n.type),
                  '--node_name', str(node)]
      if prefix:
        startcmd[len(startcmd):] = ['--prefix', prefix]

      startcmd[len(startcmd):] = n.args
      startcmd[len(startcmd):] = args
      rospy.loginfo("Run remote: %s", ' '.join(startcmd))
      (stdin, stdout, stderr), ok = nm.ssh().ssh_exec(host, startcmd)

      if ok:
        stdin.close()
  #      stderr.close()
  #      stdout.close()
        error = stderr.read()
        if error:
          rospy.logwarn("ERROR while start '%s': %s", node, error)
          raise nm.StartException(str(''.join(['The host "', host, '" reports:\n', error])))
        output = stdout.read()
        if output:
          rospy.logdebug("STDOUT while start '%s': %s", node, output)
  #      if error:
  #        raise StartException(''.join(['Error while run a node ', node, ':\n', error]))
  #        content = stdout.read()
  
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
        param_server_multi.setParam(rospy.get_name(), p.key, p.value)
      r  = param_server_multi()
      for code, msg, _ in r:
        if code != 1:
          raise StartException("Failed to set parameter: %s"%(msg))
    except roslaunch.core.RLException, e:
      raise StartException(e)
    except Exception as e:
      raise #re-raise as this is fatal

  
  @classmethod
  def runNodeWithoutConfig(cls, host, package, type, name, args=[]):
    '''
    Start a node with using a launch configuration.
    @param host: the host or ip to run the node
    @type host: C{str} 
    @param package: the ROS package containing the binary
    @type package: C{str} 
    @param type: the binary of the node to execute
    @type type: C{str} 
    @param name: the ROS name of the node (with name space)
    @type name: C{str} 
    @param args: the list with arguments passed to the binary
    @type args: C{[str, ...]} 
    @raise Exception: on errors while resolving host
    @see: L{node_manager_fkie.is_local()}
    '''
    # create the name with namespace
    fullname = ''.join(['/', name])
    for a in args:
      if a.startswith('__ns:='):
        fullname = ''.join(['/', a.replace('__ns:=', '').strip('/ '), fullname])
    fullname = fullname.replace('//', '/')
    args2 = list(args)
    args2.append(''.join(['__name:=', name]))
    # run on local host
    if nm.is_local(host):
      try:
        cmd = roslib.packages.find_node(package, type)
      except roslib.packages.ROSPkgException as e:
        # multiple nodes, invalid package
        raise StartException(str(e))
      # handle diferent result types str or array of string
      import types
      if isinstance(cmd, types.StringTypes):
        cmd = [cmd]
      cmd_type = ''
      if cmd is None or len(cmd) == 0:
        raise nm.StartException(' '.join([type, 'in package [', package, '] not found!']))
      if len(cmd) > 1:
        # Open selection for executables
        try:
          from PySide import QtGui
          item, result = QtGui.QInputDialog.getItem(None, ' '.join(['Multiple executables', type, 'in', package]),
                                            'Select an executable',
                                            cmd, 0, False)
          if result:
            #open the selected screen
            cmd_type = item
          else:
            return
        except:
          raise nm.StartException('Multiple executables with same name in package found!')
      else:
        cmd_type = cmd[0]
      cmd_str = str(' '.join([nm.screen().getSceenCmd(fullname), cmd_type, ' '.join(args2)]))
      rospy.loginfo("Run without config: %s", cmd_str)
      subprocess.Popen(shlex.split(cmd_str))
    else:
      # run on a remote machine
      startcmd = [nm.STARTER_SCRIPT, 
                  '--package', str(package),
                  '--node_type', str(type),
                  '--node_name', str(fullname)]
      startcmd[len(startcmd):] = args2
      rospy.loginfo("Run remote: %s", ' '.join(startcmd))
      (stdin, stdout, stderr), ok = nm.ssh().ssh_exec(host, startcmd)
      if ok:
        stdin.close()
        error = stderr.read()
        if error:
          rospy.logwarn("ERROR while start '%s': %s", name, error)
          from PySide import QtGui
          QtGui.QMessageBox.warning(None, 'Error while remote start %s'%str(name),
                                      str(''.join(['The host "', host, '" reports:\n', error])),
                                      QtGui.QMessageBox.Ok)
        output = stdout.read()
        if output:
          rospy.logdebug("STDOUT while start '%s': %s", name, output)

  def callService(self, service_uri, service, type, *args, **kwds):
    '''
    Calls the service and return the response.
    To call the service the ServiceProxy can't be used, because it uses 
    environment variables to determine the URI of the running service. In our 
    case this service can be running using another ROS master. The changes on the
    environment variables is not thread safe.
    So the source code of the rospy.SerivceProxy (tcpros_service.py) was modified.
    
    @param service_uri: the URI of the service
    @type service_uri: C{str}
    @param service: full service name (with name space)
    @type service: C{str}
    @param type: service class
    @type type: ServiceDefinition: service class
    @param args: arguments to remote service
    @param kwds: message keyword arguments
    @return: the tuple of request and response.
    @rtype: C{(request object, response object)}
    @raise StartException: on error

    @see: L{rospy.SerivceProxy}

    '''
    from rospy.core import parse_rosrpc_uri, is_shutdown
    from rospy.msg import args_kwds_to_message
    from rospy.exceptions import TransportInitError, TransportException
    from rospy.impl.tcpros_base import TCPROSTransport, TCPROSTransportProtocol, DEFAULT_BUFF_SIZE
    from rospy.impl.tcpros_service import TCPROSServiceClient
    from rospy.service import ServiceException
    request = args_kwds_to_message(type._request_class, args, kwds) 
    transport = None
    protocol = TCPROSServiceClient(service, type, headers={})
    transport = TCPROSTransport(protocol, service)
    # initialize transport
    dest_addr, dest_port = parse_rosrpc_uri(service_uri)

    # connect to service            
    transport.buff_size = DEFAULT_BUFF_SIZE
    try:
      transport.connect(dest_addr, dest_port, service_uri)
    except TransportInitError as e:
      # can be a connection or md5sum mismatch
      raise StartException("unable to connect to service: %s"%e)
    transport.send_message(request, 0)
    try:
      responses = transport.receive_once()
      if len(responses) == 0:
        raise StartException("service [%s] returned no response"%service)
      elif len(responses) > 1:
        raise StartException("service [%s] returned multiple responses: %s"%(service, len(responses)))
    except TransportException as e:
      # convert lower-level exception to exposed type
      if is_shutdown():
        raise StartException("node shutdown interrupted service call")
      else:
        raise StartException("transport error completing service call: %s"%(str(e)))
    except ServiceException, e:
      raise StartException("Service error: %s"%(str(e)))
    finally:
      transport.close()
      transport = None
    return request, responses[0] if len(responses) > 0 else None


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
  def openLog(cls, nodename, host):
    '''
    Opens the log file associated with the given node in a new terminal.
    @param nodename: the name of the node (with name space)
    @type nodename: C{str}
    @param host: the host name or ip where the log file are
    @type host: C{str}
    @return: C{True}, if a log file was found
    @rtype: C{bool}
    @raise Exception: on errors while resolving host
    @see: L{node_manager_fkie.is_local()}
    '''
    title_opt = ' '.join(['"LOG', nodename, 'on', host, '"'])
    if nm.is_local(host):
      found = False
      screenLog = nm.screen().getScreenLogFile(node=nodename)
      if os.path.isfile(screenLog):
        cmd = nm.terminal_cmd([nm.LESS, screenLog], title_opt)
        rospy.loginfo("open log: %s", cmd)
        subprocess.Popen(shlex.split(cmd))
        found = True
      #open roslog file
      roslog = nm.screen().getROSLogFile(nodename)
      if os.path.isfile(roslog):
        title_opt = title_opt.replace('LOG', 'ROSLOG')
        cmd = nm.terminal_cmd([nm.LESS, roslog], title_opt)
        rospy.loginfo("open ROS log: %s", cmd)
        subprocess.Popen(shlex.split(cmd))
        found = True
      return found
    else:
      nm.ssh().ssh_x11_exec(host, [nm.STARTER_SCRIPT, '--show_screen_log', nodename], title_opt)
      nm.ssh().ssh_x11_exec(host, [nm.STARTER_SCRIPT, '--show_ros_log', nodename], title_opt.replace('LOG', 'ROSLOG'))
    return False


  @classmethod
  def deleteLog(cls, nodename, host):
    '''
    Deletes the log file associated with the given node.
    @param nodename: the name of the node (with name space)
    @type nodename: C{str}
    @param host: the host name or ip where the log file are to delete
    @type host: C{str}
    @raise Exception: on errors while resolving host
    @see: L{node_manager_fkie.is_local()}
    '''
    if nm.is_local(host):
      screenLog = nm.screen().getScreenLogFile(node=nodename)
      pidFile = nm.screen().getScreenPidFile(node=nodename)
      roslog = nm.screen().getROSLogFile(nodename)
      if os.path.isfile(screenLog):
        os.remove(screenLog)
      if os.path.isfile(pidFile):
        os.remove(pidFile)
      if os.path.isfile(roslog):
        os.remove(roslog)
    else:
      (stdin, stdout, stderr), ok = nm.ssh().ssh_exec(host, [nm.STARTER_SCRIPT, '--delete_logs', nodename])
      if ok:
        stdin.close()

  def kill(self, host, pid):
    '''
    Kills the process with given process id on given host.
    @param host: the name or address of the host, where the process must be killed.
    @type host: C{str}
    @param pid: the process id
    @type pid: C{int}
    @raise StartException: on error
    @raise Exception: on errors while resolving host
    @see: L{node_manager_fkie.is_local()}
    '''
    if nm.is_local(host): 
      import signal
      os.kill(pid, signal.SIGKILL)
      rospy.loginfo("kill: %s", str(pid))
    else:
      # kill on a remote machine
      cmd = ['kill -9', str(pid)]
      rospy.loginfo("kill remote: %s", ' '.join(cmd))
      (stdin, stdout, stderr), ok = nm.ssh().ssh_exec(host, cmd)
      if ok:
        stdin.close()
        error = stderr.read()
        if error:
          rospy.logwarn("ERROR while kill %s: %s", str(pid), error)
          raise nm.StartException(str(''.join(['The host "', host, '" reports:\n', error])))
        output = stdout.read()
        if output:
          rospy.logdebug("STDOUT while kill %s: %s", str(pid), output)

