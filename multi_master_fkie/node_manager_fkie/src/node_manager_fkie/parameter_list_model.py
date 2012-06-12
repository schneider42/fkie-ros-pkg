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

class ParameterItem(QtGui.QStandardItem):
  '''
  The parameter item is stored in the parameter model. This class stores the name 
  and value of a parameter of ROS parameter server. The name of the parameter is 
  represented in HTML.
  '''

  ITEM_TYPE = QtGui.QStandardItem.UserType + 38

  def __init__(self, key, value, parent=None):
    '''
    Initialize the item object.
    @param key: the name of the parameter
    @type key: C{str}
    @param value: the value of the parameter
    @type value: C{str}
    '''
    QtGui.QStandardItem.__init__(self, self.toHTML(key))
    self.key = key
    '''@ivar: the name of parameter '''
    self.value = value
    '''@ivar: the value of the parameter '''

  def updateParameterView(self, parent):
    '''
    Updates the view of the parameter on changes.
    @param parent: the item containing this item
    @type parent: L{PySide.QtGui.QStandardItem}
    '''
    if not parent is None:
      # update type view
      child = parent.child(self.row(), 1)
      if not child is None:
        self.updateValueView(self.value, child)

  def type(self):
    return TopicItem.ITEM_TYPE

  @classmethod
  def toHTML(cls, key):
    '''
    Creates a HTML representation of the parameter name.
    @param key: the parameter name
    @type key: C{str}
    @return: the HTML representation of the parameter name
    @rtype: C{str}
    '''
    ns, sep, name = key.rpartition('/')
    result = ''
    if sep:
      result = ''.join(['<html><body>', '<span style="color:gray;">', str(ns), sep, '</span><b>', name, '</b></body></html>'])
    else:
      result = name
    return result

  @classmethod
  def getItemList(self, key, value):
    '''
    Creates the list of the items. This list is used for the 
    visualization of the parameter as a table row.
    @param key: the parameter name
    @type key: C{str}
    @param value: the value of the parameter
    @type value: each value, that can be converted to C{str} using L{str()}
    @return: the list for the representation as a row
    @rtype: C{[L{ParameterItem}, ...]}
    '''
    items = []
    item = ParameterItem(key, value)
    items.append(item)
    typeItem = QtGui.QStandardItem(key)
    ParameterItem.updateValueView(value, typeItem)
    items.append(typeItem)
    return items

  @classmethod
  def updateValueView(cls, value, item):
    '''
    Updates the representation of the column contains the value of the parameter.
    @param value: the value of the parameter
    @type value: each value, that can be converted to C{str} using L{str()}
    @param item: corresponding item in the model
    @type item ServiceItem
    '''
    item.setText(str(value))

  def __eq__(self, item):
    '''
    Compares the name of parameter.
    '''
    if isinstance(item, str) or isinstance(item, unicode):
      return self.key.lower() == item.lower()
    elif not (item is None):
      return self.key.lower() == item.key.lower()
    return False

  def __gt__(self, item):
    '''
    Compares the name of parameter.
    '''
    if isinstance(item, str) or isinstance(item, unicode):
      return self.key.lower() > item.lower()
    elif not (item is None):
      return self.key.lower() > item.key.lower()
    return False


class ParameterModel(QtGui.QStandardItemModel):
  '''
  The model to manage the list with parameter in ROS network.
  '''
  header = [('Parameter', 300),
            ('Value', -1)]
  '''@ivar: the list with columns C{[(name, width), ...]}'''
  
  def __init__(self):
    '''
    Creates a new list model.
    '''
    QtGui.QStandardItemModel.__init__(self)
    self.setColumnCount(len(ParameterModel.header))
    self.setHorizontalHeaderLabels([label for label, width in ParameterModel.header])

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

  def updateModelData(self, parameters):
    '''
    Updates the parameter list model. New parameter will be inserted in sorting 
    order. Not available parameter removed from the model.
    @param parameters: The dictionary with parameter 
    @type parameters: C{dict(parameter name : value)}
    '''
    parameter_names = parameters.keys()
    root = self.invisibleRootItem()
    # remove not available items
    for i in reversed(range(root.rowCount())):
      parameterItem = root.child(i)
      if not parameterItem.key in parameter_names:
        root.removeRow(i)
    # add new items
    for (name, value) in parameters.items():
      doAddItem = True
      for i in range(root.rowCount()):
        parameterItem = root.child(i)
        if (parameterItem == name):
          # update item
          parameterItem.value = value
          parameterItem.updateParameterView(root)
          doAddItem = False
          break
        elif (parameterItem > name):
          root.insertRow(i, ParameterItem.getItemList(name, value))
          doAddItem = False
          break
      if doAddItem:
        root.appendRow(ParameterItem.getItemList(name, value))
