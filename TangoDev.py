
import sys
import time
from PyTango import DeviceProxy,EventType,DevFailed,DevState

class TangoDev: # by Fulvio
    def __init__(self, tangoDevice):    
        try:
            self.tangoDevice = tangoDevice
            self.Connect(self.tangoDevice)
        except Exception, e:
            #raise RuntimeError, str(e)
            print 'Fatal Exception when connecting to device %s: %s'%(tangoDevice,str(e))
            
    def __del__(self):
        print 'In TangoDev.__del__()'
        del self.dp
        
    # Connect to the device server
    def Connect(self, tangoDevice):
        try:
            self.dp = DeviceProxy(self.tangoDevice)
        except DevFailed:
            exctype, value = sys.exc_info()[:2]
            str_aux = ""
            for err in value:
                str_aux += "reason\t" + err["reason"] + "\n" + "description\t" + err["desc"] + "\n" + "origin\t" + err["origin"] + "\n" + "severity\t" + err["severity"] + "\n"
            print str_aux #QtGui.QMessageBox.critical(self.ti, str(self.tangoDevice) , str_aux)
            self.dp = None
            #raise RuntimeError, "Error when connecting"
            
    def get_attributes(self):
        try:
            self.attrs = self.dp.attribute_list_query()
            return self.attrs
        except DevFailed:
            exctype, value = sys.exc_info()[:2]
            str_aux = ""
            for err in value:
                str_aux += "reason\t" + err["reason"] + "\n" + "description\t" + err["desc"] + "\n" + "origin\t" + err["origin"] + "\n" + "severity\t" + err["severity"] + "\n"
            print str_aux #QtGui.QMessageBox.critical(self.ti, str(self.tangoDevice) , str_aux)

    # Subscribe events
    def SubscribeChangeEvent(self, attr):
        try:
            ev = self.dp.subscribe_event(attr, EventType.CHANGE, self.ti, [])
            return ev
        except DevFailed:
            exctype, value = sys.exc_info()[:2]
            str_aux = ""
            for err in value:
                str_aux += "reason\t" + err["reason"] + "\n" + "description\t" + err["desc"] + "\n" + "origin\t" + err["origin"] + "\n" + "severity\t" + err["severity"] + "\n"
            print str_aux #QtGui.QMessageBox.critical(self.ti, str(self.tangoDevice) , str_aux)
            
    # Subscribe events
    def UnsubscribeChangeEvent(self, attr):
        try:
            self.dp.unsubscribe_event(attr, EventType.CHANGE, self.ti, [])
        except DevFailed:
            exctype, value = sys.exc_info()[:2]
            str_aux = ""
            for err in value:
                str_aux += "reason\t" + err["reason"] + "\n" + "description\t" + err["desc"] + "\n" + "origin\t" + err["origin"] + "\n" + "severity\t" + err["severity"] + "\n"
            print str_aux #QtGui.QMessageBox.critical(self.ti, str(self.tangoDevice) , str_aux)
            
    def SetInfo(self, info_list):
        try:
            self.dp.set_attribute_config(info_list)
        except DevFailed:
            exctype, value = sys.exc_info()[:2]
            str_aux = ""
            for err in value:
                str_aux += "reason\t" + err["reason"] + "\n" + "description\t" + err["desc"] + "\n" + "origin\t" + err["origin"] + "\n" + "severity\t" + err["severity"] + "\n"
            print str_aux #QtGui.QMessageBox.critical(self.ti, str(self.tangoDevice) , str_aux)

    # Read an attribute
    def Read(self, attr_name):
        try:
            attr = self.dp.read_attribute(attr_name)
            return attr.value
        except DevFailed:
            exctype, value = sys.exc_info()[:2]
            str_aux = ""
            for err in value:
                str_aux += "reason\t" + err["reason"] + "\n" + "description\t" + err["desc"] + "\n" + "origin\t" + err["origin"] + "\n" + "severity\t" + err["severity"] + "\n"
            print str_aux #QtGui.QMessageBox.critical(self.ti, str(self.tangoDevice) , str_aux)
            
    # Write an attribute
    def Write(self, attr_name, value):
        try:
            #attr = self.dp.read_attribute(attr_name)
            #attr = AttributeValue()
            #attr.name = attr_name
            #attr.value = value
            #attr.dim_x = len(value)
            self.dp.write_attribute(attr_name,value)
        except DevFailed:
            exctype, value = sys.exc_info()[:2]
            str_aux = ""
            for err in value:
                str_aux += "reason\t" + err["reason"] + "\n" + "description\t" + err["desc"] + "\n" + "origin\t" + err["origin"] + "\n" + "severity\t" + err["severity"] + "\n"
            print str_aux #QtGui.QMessageBox.critical(self.ti, str(self.tangoDevice) , str_aux)

    
