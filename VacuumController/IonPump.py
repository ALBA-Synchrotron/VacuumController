#    "$Name:  $";
#    "$Header: /siciliarep/CVS/tango_ds/Vacuum/VacuumController/IonPump.py,v 1.1 2007/08/28 10:39:17 srubio Exp $";
#=============================================================================
#
# file :        IonPump.py
#
# description : Python source for the IonPump and its commands. 
#                The class is derived from Device. It represents the
#                CORBA servant object which will be accessed from the
#                network. All commands which can be executed on the
#                IonPump are implemented in this file.
#
# project :     TANGO Device Server
#
# $Author: srubio@cells.es $
#
# $Revision: 1665 $
#
# $Log: IonPump.py,v $
# Revision 1.1  2007/08/28 10:39:17  srubio
# to access Ion Pumps as independent Devices
#
#
# copyleft :    Cells / Alba Synchrotron
#               Bellaterra
#               Spain
#
############################################################################
#
# This file is part of Tango-ds.
#
# Tango-ds is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# Tango-ds is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.
##########################################################################
#

import sys, time, traceback, re
import PyTango
from PyTango import DevState,DevFailed

try: import fandango
except: import PyTango_utils as fandango
import fandango.functional as fun
import fandango.device as device
from fandango.device import Dev4Tango,attr2str,fakeAttributeValue, fakeEventType
from fandango import callbacks

## @note Backward compatibility between PyTango3 and PyTango7
if 'PyDeviceClass' not in dir(PyTango): PyTango.PyDeviceClass = PyTango.DeviceClass
if 'PyUtil' not in dir(PyTango): PyTango.PyUtil = PyTango.Util
if 'Device_4Impl' not in dir(PyTango): PyTango.Device_4Impl = PyTango.Device_3Impl

from VacuumController import *

#==================================================================
#   IonPump Class Description:
#
#         <p>This device requires <a href="http://www.tango-controls.org/Documents/tools/fandango/fandango">Fandango module<a> to be available in the PYTHONPATH.</p>
#        Tango pseudo-Abstract Class for Ion Pumps, it's a firendly and minimalistic interface to each of the pumps managed through a DUAL or Splitter Device Server.
#
#==================================================================
#     Device States Description:
#
#   DevState.INIT :
#   DevState.ON : Everything works fine
#   DevState.UNKNOWN: It's impossible to communicate with the device
#   DevState.ALARM : Pressure Warning
#   DevState.ALARM : Pressure Interlock
#   DevState.FAULT : Cable Interlock
#   DevState.DISABLE : Manual Interlock
#   DevState.OFF : Channel switched off, it is the only state that doesn't rely on parent device state
#==================================================================


class IonPump(PseudoDev):
    """ 
    Tango pseudo-Abstract Class for Ion Pumps, it's a firendly and minimalistic interface to each of the pumps managed through a DUAL or Splitter Device Server.
    It inherits from PyTango_utils.device.DevChild, providing event management, logging, Object primitive class and many additional features.
    Last update: srubio@cells.es, 2010/10/18
    """


    #--------- Add you global variables here --------------------------

    MAX_ERRORS = 3
    
    OnOffCoding = {
        'ON':1, ## Any value>0 must be considered as ON!!!
        'Off': 0, #Write 0 30h HV power off
        #Write 1 31h HV power on (in compliance to the
        #Start/Protect and Fixed/Step selection made
        #using the related commands)
        #Read 0 30h HV off
        #Read 1 31h HV on
        #If full compatible MultiVac
        #Read 1 31h HV on in start/step V
        #Read 2 32h HV on in start/fixed V
        #Read 3 33h HV on in protect/step V
        #Read 4 34h HV on in protect/fixed V
        'PanelInterlock': -3, #Read -3 2Dh33h Power off caused by Interlock Panel
        'RemoteInterlock': -4, #Read -4 2Dh34h Power off caused by Remote I/O Interlock
        'CableInterlock': -5, #Read -3 2Dh33h Power off caused by Cable Interlock
        'HVTemperature': -8, #Read -8 2Dh38h Power off caused by HV Overtemperature
        'RemoteFault': -7, #Read -7 2Dh37h Power off caused by Remote I/O not Present or Remote I/O Fault
        'HVProtect': -6, #Read -6 2Dh36h Power off caused by HV Protect
        'HVShortCircuit': -7 #Read -7 2Dh37h Power off caused by HV Short Circuit
        }
        
    @staticmethod
    def getOrdinal(cadena):
        ''' Returns the last integer value that appears in a string '''
        valor = re.findall('\[([0-9]+)\]',str(cadena))
        return int(valor[-1]) if valor else None        
        
    def StateMachine(self,att,attr_value,new_state):
        """
        This method will be called from common.PseudoDev.event_received when a valid attribute value is received.
        It updates the self.Cache dictionary and returns the new_state value.
        """
        if att == self.ChannelName.split('[')[0].lower():
            if '[' in self.ChannelName and fun.isSequence(attr_value.value):
                attr_value.value = attr_value.value[self.getOrdinal(self.ChannelName)]
            self.Cache[self.ChannelName] = attr_value
            self.ChannelValue = attr_value.value
            if attr_value.quality in (PyTango.AttrQuality.ATTR_ALARM,PyTango.AttrQuality.ATTR_WARNING): 
                new_state = PyTango.DevState.ALARM
            elif attr_value.value<=self.LowRange: 
                new_state = PyTango.DevState.STANDBY
            else: 
                new_state = PyTango.DevState.ON
            date = attr_value.time if not hasattr(attr_value.time,'totime') else attr_value.time.totime()
            self.plog('info','Updated Pressure Value: %s at %s'%(attr_value.value,date))
        elif att == 'state':
            self.Cache[att] = attr_value
        else: 
            self.plog('warning','UNKNOWN ATTRIBUTE %s!!!!!'%attr_name)
            self.plog('debug','self.Channel=%s'%str(self.Channel))
            self.plog('debug','attr_name.split=%s'%str(attr_name.split('/')))
        return new_state


#------------------------------------------------------------------
#    Device constructor
#------------------------------------------------------------------
    def __init__(self, cl, name):
        PyTango.Device_4Impl.__init__(self, cl, name)
        IonPump.init_device(self)

#------------------------------------------------------------------
#    Device destructor
#------------------------------------------------------------------
    def delete_device(self):
        print "[Device delete_device method] for device",self.get_name()
        PseudoDevice.delete_device(self)


#------------------------------------------------------------------
#    Device initialization
#------------------------------------------------------------------
    def init_device(self):
        try:
            PseudoDev.init_device(self)

            self.ChannelValue=None
            self.ChannelDate=0
            
            if not self.check_Properties(['IonPumpController','Channel']):
                self.init_error+="IonPumpController and Channel properties are mandatory, edit them and launch Init()"
                self.error(self.init_error)
                self.set_state(PyTango.DevState.UNKNOWN)
                return
            else:
                self.ChannelName = fun.first(c for c in self.Channel if not fun.matchCl('(*state*|*status*)',c))
                targets = ['State',self.ChannelName.split('[')[0]]
                self.debug('Creating cache values for %s:%s' % (self.IonPumpController,targets))
                for attribute in targets:
                    da = PyTango.DeviceAttribute()
                    da.name,da.time,da.value = (self.IonPumpController+'/'+attribute),PyTango.TimeVal.fromtimestamp(0),None
                    self.Cache[attribute] = da
                    self.Errors[attribute] = 0
                
                self.subscribe_external_attributes(self.IonPumpController,targets)
            
            self.info('Ready to accept request ...')
            self.info('-'*80)
        except Exception,e:
            self.init_error+=traceback.format_exc()
            self.error(self.init_error)
            self.set_state(PyTango.DevState.UNKNOWN)            

#------------------------------------------------------------------
#    Always excuted hook method
#------------------------------------------------------------------
    def always_executed_hook(self):
        self.debug("In always_executed_hook()")
        try:
            PseudoDev.always_executed_hook(self)
            try: 
                if self.get_state()==PyTango.DevState.ON: channelstatus='Pump is ON, pressure is %3.2e mbar'%self.ChannelValue
                else: channelstatus='Pump Status is %s, check Controller %s'%(self.ChannelStatus.upper() or str(self.get_state()),self.IonPumpController)
            except Exception,e:
                self.error('Unable to update ChannelStatus: %s'%traceback.format_exc())
                channelstatus = 'Unable to update ChannelStatus: %s' % (str(e).replace('\n','')[:30]+'...')                    
            self.set_status('\n\r'.join(s for s in [self.init_error,self.state_error,channelstatus,self.Description,self.event_status] if s))                    
            self.debug('In %s always_executed_hook() at %s: State=%s ; Status=%s'%(self.get_name(),time.ctime(),self.get_state(),self.get_status()))
        except Exception,e:
            self.error('Exception in always_executed_hook: %s'%str(e))
        self.debug("Out of always_executed_hook()")            
        
#==================================================================
#
#    IonPump read/write attribute methods
#
#==================================================================
#------------------------------------------------------------------
#    Read Attribute Hardware
#------------------------------------------------------------------
    def read_attr_hardware(self,data):
        self.debug("In "+ self.get_name()+ "::read_attr_hardware()")



#------------------------------------------------------------------
#    Read Pressure attribute
#------------------------------------------------------------------
    def read_Pressure(self, attr):
        self.debug("In "+self.get_name()+"::read_Pressure()")
        
        #    Add your own code here
        state=self.get_state()        
        if str(state) in ('ON','MOVING'):
            quality=PyTango.AttrQuality.ATTR_VALID
        elif str(state)=='ALARM':
            quality=PyTango.AttrQuality.ATTR_ALARM
        elif str(state)=='STANDBY':
            quality=PyTango.AttrQuality.ATTR_WARNING
        else:
            self.error('The State of the device is %s, it changes quality of attributes to INVALID.'%str(state))
            quality=PyTango.AttrQuality.ATTR_INVALID
        
        #value,date = self.ChannelValue,self.ChannelDate
        av = self.Cache[self.ChannelName]
        value,date = av.value,av.time if not hasattr(av.time,'totime') else av.time.totime()
        self.debug('read_Pressure(): state is %s, value is %s, quality is %s.'%(state,value,quality))
        if 'set_attribute_value_date_quality' in dir(PyTango):
            PyTango.set_attribute_value_date_quality(attr,float(value),date,quality)
        else: attr.set_value_date_quality(float(value),date,quality)        
        
#---- Pressure attribute State Machine -----------------
    def is_Pressure_allowed(self, req_type):
        if self.get_state() in [
            PyTango.DevState.UNKNOWN,
            PyTango.DevState.DISABLE,
            PyTango.DevState.OFF,
            #PyTango.DevState.FAULT, #Because it may be readable in case of pressure interlock!
            #PyTango.DevState.STANDBY,
            PyTango.DevState.INIT,]:
            #    End of Generated Code
            #    Re-Start of Generated Code
            return False
        return True
    
##------------------------------------------------------------------
##    Read Current attribute
##------------------------------------------------------------------
    #def read_Current(self, attr):
        #print "In ", self.get_name(), "::read_Current()"
        
        ##    Add your own code here
        #state=self.get_state()        
        #if str(state) in ('ON','MOVING'):
            #quality=PyTango.AttrQuality.ATTR_VALID
        #elif str(state)=='ALARM':
            #quality=PyTango.AttrQuality.ATTR_ALARM
        #else:
            #self.error('The State of the device is %s, it changes quality of attributes to INVALID.'%str(state))
            #quality=PyTango.AttrQuality.ATTR_INVALID
        
        ##value,date = self.ChannelValue,self.ChannelDate
        #av = self.Cache[self.ChannelName]
        #value,date = av.value,av.time.totime()         
        #self.debug('read_Pressure(): state is %s, value is %s, quality is %s.'%(state,value,quality))
        #if 'set_attribute_value_date_quality' in dir(PyTango):
            #PyTango.set_attribute_value_date_quality(attr,float(value),date,quality)
        #else: attr.set_value_date_quality(float(value),date,quality) 
        
#---- Pressure attribute State Machine -----------------
    #def is_Current_allowed(self, req_type):
        #if self.get_state() in [PyTango.DevState.UNKNOWN,
                                #PyTango.DevState.DISABLE,
                    #PyTango.DevState.OFF]:
            ##    End of Generated Code
            ##    Re-Start of Generated Code
            #return False
        #return True
        
#------------------------------------------------------------------
#    Read Voltage attribute
#------------------------------------------------------------------
    #def read_Voltage(self, attr):
        #print "In ", self.get_name(), "::read_Voltage()"
        
        ##    Add your own code here
        #state=self.get_state()        
        #if str(state) in ('ON','MOVING'):
            #quality=PyTango.AttrQuality.ATTR_VALID
        #elif str(state)=='ALARM':
            #quality=PyTango.AttrQuality.ATTR_ALARM
        #else:
            #self.error('The State of the device is %s, it changes quality of attributes to INVALID.'%str(state))
            #quality=PyTango.AttrQuality.ATTR_INVALID
        
        ##value,date = self.ChannelValue,self.ChannelDate
        #av = self.Cache[self.ChannelName]
        #value,date = av.value,av.time.totime()         
        #self.debug('read_Pressure(): state is %s, value is %s, quality is %s.'%(state,value,quality))
        #if 'set_attribute_value_date_quality' in dir(PyTango):
            #PyTango.set_attribute_value_date_quality(attr,float(value),date,quality)
        #else: attr.set_value_date_quality(float(value),date,quality) 
        
#---- Voltage attribute State Machine -----------------
    #def is_Voltage_allowed(self, req_type):
        #if self.get_state() in [PyTango.DevState.UNKNOWN,
                                #PyTango.DevState.DISABLE,
                    #PyTango.DevState.OFF]:
            ##    End of Generated Code
            ##    Re-Start of Generated Code
            #return False
        #return True     


#------------------------------------------------------------------
#    Read ChannelStatus attribute
#------------------------------------------------------------------
    def read_ChannelStatus(self, attr=None):
        self.debug("In read_ChannelStatus()")
        
        state=self.get_state()
        if str(state)=='ON':
            quality=PyTango.AttrQuality.ATTR_VALID
            value = '%3.2e mbar'%(self.Cache[self.ChannelName].value)
        else:
            quality=PyTango.AttrQuality.ATTR_ALARM
            value = str(state)
        date = time.time()
        
        self.ChannelStatus = value
        self.debug('read_ChannelStatus(): state is %s, value is %s, quality of attributes is %s.'%(state,value,quality))
        if attr is not None:
            if 'set_attribute_value_date_quality' in dir(PyTango):
                PyTango.set_attribute_value_date_quality(attr,value,date,quality)
            else: attr.set_value_date_quality(value,date,quality)        


#------------------------------------------------------------------
#    Read Controller attribute
#------------------------------------------------------------------
    def read_Controller(self, attr):
        print "In ", self.get_name(), "::read_Controller()"
        
        #    Add your own code here
        attr.set_value(self.IonPumpController+'/'+self.ChannelName)


#==================================================================
#
#    IonPump command methods
#
#==================================================================

#------------------------------------------------------------------
#    On command:
#
#    Description: 
#------------------------------------------------------------------
    def On(self):
        print "In ", self.get_name(), "::On()"
        #    Add your own code here
        self.set_state(PyTango.DevState.ON)


#------------------------------------------------------------------
#    Off command:
#
#    Description: 
#------------------------------------------------------------------
    def Off(self):
        print "In ", self.get_name(), "::Off()"
        #    Add your own code here
        self.set_state(PyTango.DevState.DISABLE)


#==================================================================
#
#    IonPumpClass class definition
#
#==================================================================
class IonPumpClass(PyTango.PyDeviceClass):

    #    Class Properties
    class_property_list = {
        }


    #    Device Properties
    device_property_list = {
        'IonPumpController':
            [PyTango.DevString,
            "IonPumpController used to read the pump measure",
            [''] ],
        'Channel':
            [PyTango.DevVarStringArray,
            "Channel of the IonPumpController used to read this pump",
            [ "P1" ] ],
        'LowRange':
            [PyTango.DevDouble,
            "Pressure values below this value will be shown as LO<VALUE",
            [ 1.0e-12 ] ],
        'Description':
            [PyTango.DevString,
            "This string field will appear in the status and can be used to add extra information about equipment location",
            [''] ],
        'UseEvents':
            [PyTango.DevBoolean,
            "true/false",
            [False] ],
        'PollingCycle': #2013, added from PyStateComposer
            [PyTango.DevLong,
            "Default period for polling all device states.",
            [ 3000 ] ],
        }


    #    Command definitions
    cmd_list = {
        #'On':
            #[[PyTango.DevVoid, ""],
            #[PyTango.DevVoid, ""],
            #{
                #'Display level':PyTango.DispLevel.EXPERT,
             #} ],
        #'Off':
            #[[PyTango.DevVoid, ""],
            #[PyTango.DevVoid, ""],
            #{
                #'Display level':PyTango.DispLevel.EXPERT,
             #} ],
        }


    #    Attribute definitions
    attr_list = {
        'Pressure':
            [[PyTango.DevDouble,
            PyTango.SCALAR,
            PyTango.READ],
            {
                'unit':"mbar",
                'format':"%3.2e",
            }],
        #'Current':
            #[[PyTango.DevDouble,
            #PyTango.SCALAR,
            #PyTango.READ],
            #{
                #'unit':"mA",
                #'format':"%3.2e",
            #}],
        #'Voltage':
            #[[PyTango.DevDouble,
            #PyTango.SCALAR,
            #PyTango.READ],
            #{
                #'unit':"V",
                #'format':"%3.2e",
            #}],                        
        'ChannelStatus':
            [[PyTango.DevString,
            PyTango.SCALAR,
            PyTango.READ]],
        'Controller':
            [[PyTango.DevString,
            PyTango.SCALAR,
            PyTango.READ]],
        }


#------------------------------------------------------------------
#    IonPumpClass Constructor
#------------------------------------------------------------------
    def __init__(self, name):
        PyTango.PyDeviceClass.__init__(self, name)
        self.set_type(name);
        print "In IonPumpClass  constructor"

#==================================================================
#
#    IonPump class main method
#
#==================================================================
if __name__ == '__main__':
    try:
        py = PyTango.PyUtil(sys.argv)
        py.add_TgClass(IonPumpClass,IonPump,'IonPump')

        U = PyTango.Util.instance()
        U.server_init()
        U.server_run()

    except PyTango.DevFailed,e:
        print '-------> Received a DevFailed exception:',e
    except Exception,e:
        print '-------> An unforeseen exception occured....',e
