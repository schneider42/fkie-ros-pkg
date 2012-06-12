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

from PySide import QtCore
from PySide import QtGui

import roslib

class ServiceItem(QtGui.QStandardItem):
  '''
  The service item stored in the service model. This class stores the service as
  L{master_discovery_fkie.ServiceInfo}. The name of the service is represented in HTML.
  '''

  ITEM_TYPE = QtGui.QStandardItem.UserType + 37

  def __init__(self, service, parent=None):
    '''
    Initialize the service item.
    @param service: the service object to view
    @type service: L{master_discovery_fkie.ServiceInfo}
    '''
    QtGui.QStandardItem.__init__(self, self.toHTML(service.name))
    self.service = service
    '''@ivar: service info as L{master_discovery_fkie.ServiceInfo}.'''

  def updateServiceView(self, parent):
    '''
    Updates the view of the service on changes.
    @param parent: the item containing this item
    @type parent: L{PySide.QtGui.QStandardItem}
    '''
    if not parent is None:
      # update type view
      child = parent.child(self.row(), 1)
      if not child is None:
        self.updateTypeView(self.service, child)

  def type(self):
    return TopicItem.ITEM_TYPE

  @classmethod
  def toHTML(cls, service_name):
    '''
    Creates a HTML representation of the service name.
    @param service_name: the service name
    @type service_name: C{str}
    @return: the HTML representation of the service name
    @rtype: C{str}
    '''
    ns, sep, name = service_name.rpartition('/')
    result = ''
    if sep:
      result = ''.join(['<html><body>', '<span style="color:gray;">', str(ns), sep, '</span><b>', name, '</b></body></html>'])
    else:
      result = name
    return result

  @classmethod
  def getItemList(self, service):
    '''
    Creates the list of the items from service. This list is used for the 
    visualization of service data as a table row.
    @param service: the service data
    @type service: L{master_discovery_fkie.ServiceInfo}
    @return: the list for the representation as a row
    @rtype: C{[L{ServiceItem} or L{PySide.QtGui.QStandardItem}, ...]}
    '''
    items = []
    item = ServiceItem(service)
    item.setToolTip(''.join(['<html><body><h4>', service.name, '</h4><dl><dt>', service.uri,'</dt></dl></body></html>']))
    items.append(item)
    typeItem = QtGui.QStandardItem()
    ServiceItem.updateTypeView(service, typeItem)
    items.append(typeItem)
    return items

  @classmethod
  def updateTypeView(cls, service, item):
    '''
    Updates the representation of the column contains the type of the service.
    @param service: the service data
    @type service: L{master_discovery_fkie.ServiceInfo}
    @param item: corresponding item in the model
    @type item: L{ServiceItem}
    '''
    try:
      service_class = service.get_service_class(service.isLocal)
      item.setText(cls.toHTML(service_class._type))
      tooltip = ''.join(['<html><body>'])
      tooltip = ''.join([tooltip, '<h4>', service_class._type, '</h4>'])
      tooltip = ''.join([tooltip, '<h4>', 'Request', ':</h4><dl>'])
      tooltip = ''.join([tooltip, '<dt>', str(service_class._request_class.__slots__), '</dt>'])
      tooltip = ''.join([tooltip, '</dl>'])

      tooltip = ''.join([tooltip, '<h4>', 'Response', ':</h4><dl>'])
      tooltip = ''.join([tooltip, '<dt>', str(service_class._response_class.__slots__), '</dt>'])
      tooltip = ''.join([tooltip, '</dl>'])

      tooltip = ''.join([tooltip, '</body></html>'])
      item.setToolTip(tooltip)
    except:
#      import traceback
#      print traceback.format_exc()
      if not service.isLocal:
        tooltip = ''.join(['<html><body>'])
        tooltip = ''.join([tooltip, '<h4>', 'Service type is not available due to he running on another host.', '</h4>'])
        tooltip = ''.join([tooltip, '</body></html>'])
        item.setToolTip(tooltip)


  def __eq__(self, item):
    '''
    Compares the name of service.
    '''
    if isinstance(item, str) or isinstance(item, unicode):
      return self.service.name.lower() == item.lower()
    elif not (item is None):
      return self.service.name.lower() == item.service.name.lower()
    return False

  def __gt__(self, item):
    '''
    Compares the name of service.
    '''
    if isinstance(item, str) or isinstance(item, unicode):
      return self.service.name.lower() > item.lower()
    elif not (item is None):
      return self.service.name.lower() > item.service.name.lower()
    return False


class ServiceModel(QtGui.QStandardItemModel):
  '''
  The model to manage the list with services in ROS network.
  '''
  header = [('Name', 300),
            ('Type', -1)]
  '''@ivar: the list with columns C{[(name, width), ...]}'''
  
  def __init__(self):
    '''
    Creates a new list model.
    '''
    QtGui.QStandardItemModel.__init__(self)
    self.setColumnCount(len(ServiceModel.header))
    self.setHorizontalHeaderLabels([label for label, width in ServiceModel.header])

  def flags(self, index):
    '''
    @param index: parent of the list
    @type index: L{PySide.QtCore.QModelIndex}
    @return: Flag or the requestet item
    @rtype: L{PySide.QtCore.Qt.ItemFlag}
    @see: U{http://www.pyside.org/docs/pyside-1.0.1/PySide/QtCore/Qt.html}
    '''
    if not index.isValid():
      return QtCore.Qt.NoItemFlags
    return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

  def updateModelData(self, services):
    '''
    Updates the service list model. New services will be inserted in sorting 
    order. Not available services removed from the model.
    @param services: The dictionary with services 
    @type services: C{dict(service name : L{master_discovery_fkie.ServiceInfo})}
    '''
    service_names = services.keys()
    root = self.invisibleRootItem()
    for i in reversed(range(root.rowCount())):
      serviceItem = root.child(i)
      if not serviceItem.service.name in service_names:
        root.removeRow(i)
    for (name, service) in services.items():
      if not service is None:
        doAddItem = True
        for i in range(root.rowCount()):
          serviceItem = root.child(i)
          if (serviceItem == service.name):
            # update item
            serviceItem.service = service
            serviceItem.updateServiceView(root)
            doAddItem = False
            break
          elif (serviceItem > service.name):
            root.insertRow(i, ServiceItem.getItemList(service))
            doAddItem = False
            break
        if doAddItem:
          root.appendRow(ServiceItem.getItemList(service))
