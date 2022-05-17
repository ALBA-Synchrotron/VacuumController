#    "$Name:  $";
#    "$Header: /siciliarep/CVS/tango_ds/Vacuum/VacuumController/VacuumGauge.py,v 1.1 2007/08/28 10:39:17 srubio Exp $";
#=============================================================================
#
# file :        VacuumGauge.py
#
# description : Python source for the VacuumGauge and its commands. 
#                The class is derived from Device. It represents the
#                CORBA servant object which will be accessed from the
#                network. All commands which can be executed on the
#                VacuumGauge are implemented in this file.
#
# project :     TANGO Device Server
#
# $Author: srubio $
#
# $Revision: 12127 $
#
# $Log: VacuumGauge.py,v $
# Revision 1.1  2007/08/28 10:39:17  srubio
# Vacuum Controller modified to access Gauges as independent Devices
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


import sys, time, traceback
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

import VacuumController
print(dir(VacuumController))
#import VacuumController.PseudoDev
print(VacuumController.PseudoDev)
from VacuumController import *

#==================================================================
#   VacuumGauge Class Description:
#
#        Tango pseudo-Abstract Class for Vacuum Gauges, it's a firendly and minimalistic interface to each of the gauges managed through a GaugeController Device Server.
#         <p>This device requires <a href="http://www.tango-controls.org/Documents/tools/fandango/fandango">Fandango module<a> to be available in the PYTHONPATH.</p>
#
#         The right CVS command to download it is:
#         cvs -d:pserver:anonymous@tango-ds.cvs.sourceforge.net:/cvsroot/tango-ds co    -r first    VacuumController
#
#==================================================================
#     Device States Description:
#
#   DevState.INIT :
#   DevState.ON :
#   DevState.ALARM :
#   DevState.FAULT :
#   DevState.DISABLE :
#==================================================================


class VacuumGauge(PseudoDev):
    """ 
    Tango Pseudo Abstract Class for Vacuum Gauges, it's a firendly and minimalistic interface to each of the gauges managed through a GaugeController Device Server.
    Last update: srubio@cells.es, 2010/10/18
    """


    #--------- Add you global variables here --------------------------
        
    def StateMachine(self,att,attr_value,new_state):
        """
        This method will be called from common.PseudoDev.event_received when a valid attribute value is received.
        It updates the self.Cache dictionary and returns the new_state value.
        """
        #READING CHANNEL STATUS
        if att == 'channelstate':
            channels=attr_value.value #It is a list of "Channel: Status" strings
            self.info('ChannelState received : %s'%str(channels)) #Channels is a tuple instead of a list!?!
            c_state = ''
            FLOAT = '[0-9](\.[0-9]{1,2})?[eE][+-][0-9]{2,2}$'
            if channels:
                for i,chann in enumerate(channels):
                    if (chann.split(':')[0].lower() == self.ChannelName #Check attribute name == channel name
                           or 
                       fandango.matchCl('p[0-9]',self.ChannelName) and i+1==int(self.ChannelName[1:]) #Check value index == channel number
                       ):
                        self.info('%s => %s'%(self.ChannelName,chann))
                        c_state=chann.split(':')[-1].lower().strip()
                        new_state = fun.matchMap([
                            ('.*off',PyTango.DevState.OFF),
                            ('misconn|negativ',PyTango.DevState.FAULT),
                            ('nogauge',PyTango.DevState.DISABLE),
                            ('lo.*',PyTango.DevState.STANDBY),
                            ('hi.*|protect', PyTango.DevState.ALARM),
                            (FLOAT,PyTango.DevState.ON),
                            ('.*',PyTango.DevState.UNKNOWN),
                            ], c_state)
                        break
                self.Cache[att].time = attr_value.time
                self.Cache[att].value = c_state.upper() #It will be 'OK' if the channel is enabled
                self.plog('info','Updated ChannelState: %s; new state is %s'%(self.Cache[att].value,new_state))
            else:
                self.plog('warning','ChannelState received has no value!: %s'%channels)
        #READING CHANNEL VALUE
        elif att == self.ChannelName:
            self.Cache[att] = attr_value
            self.plog('info','Updated Pressure Value: %s at %s'%(attr_value.value,attr_value.time))
        elif att == 'state':
            self.Cache[att] = attr_value
        else: 
            self.plog('warning','UNKNOWN ATTRIBUTE %s!!!!!'%attr_name)
            self.plog('debug','self.ChannelName=%s'%str(self.ChannelName))
            self.plog('debug','attr_name.split=%s'%str(attr_name.split('/')))
        return new_state
    
    
#------------------------------------------------------------------
#    Device constructor
#------------------------------------------------------------------
    def __init__(self, cl, name):
        PyTango.Device_4Impl.__init__(self, cl, name)
        VacuumGauge.init_device(self)

#------------------------------------------------------------------
#    Device destructor
#------------------------------------------------------------------
    def delete_device(self):
        self.info("[Device delete_device method] for device%s"%self.get_name())
        PseudoDev.delete_device(self)


#------------------------------------------------------------------
#    Device initialization
#------------------------------------------------------------------
    def init_device(self):
        try:
            PseudoDev.init_device(self)
            
            if not self.check_Properties(['GaugeController','Channel']):
                self.init_error+="GaugeController,Channel properties are mandatory, edit them and launch Init()"
                self.error(self.init_error)
                self.set_state(PyTango.DevState.FAULT)
                return
            else:
                self.ChannelName = (self.Channel.split()[0] if fun.isString(self.Channel) else fun.first(c for c in self.Channel if c.lower() not in ('State','ChannelState'))).lower()
                targets = ['State',self.ChannelName,'ChannelState']                
                self.debug('Creating cache values for %s:%s' % (self.GaugeController,targets))                
                for attribute in targets:
                    da = PyTango.DeviceAttribute()
                    da.name,da.time,da.value = (self.GaugeController+'/'+attribute),PyTango.TimeVal.fromtimestamp(0),None
                    self.Cache[attribute] = da
                    self.Errors[attribute] = 0
                    
                self.subscribe_external_attributes(self.GaugeController,targets)
            
            self.info('Ready to accept request ...')
            self.info('-'*80)
        except Exception,e:
            print 'Exception in %s.init_device():'%self.get_name()
            print traceback.format_exc()
            raise e

#------------------------------------------------------------------
#    Always excuted hook method
#------------------------------------------------------------------
    def always_executed_hook(self):
        self.debug("In always_executed_hook()")
        try:
            PseudoDev.always_executed_hook(self)
            try: 
                self.read_ChannelStatus()
                if self.dev_state()==PyTango.DevState.ON: channelstatus='Gauge is ON, %s'%self.ChannelStatus
                else: channelstatus='Gauge Status is "%s", check Controller "%s"'%(self.ChannelStatus.upper() or str(self.get_state()),self.GaugeController)
            except Exception,e: 
                self.error('Unable to update ChannelStatus: %s'%traceback.format_exc())
                channelstatus = 'Unable to update ChannelStatus: %s' % (str(e).replace('\n','')[:30]+'...')
            self.set_status('\n\r'.join(s for s in [self.init_error,self.state_error,channelstatus,self.Description,self.event_status] if s))
            self.debug('In %s always_executed_hook() at %s: State=%s ; Status=%s'%(self.get_name(),time.ctime(),self.dev_state(),self.get_status()))
        except Exception,e:
            self.error('Exception in always_executed_hook: \n%s'%traceback.format_exc())
        self.debug("Out of always_executed_hook()")
        
#==================================================================
#
#    VacuumGauge read/write attribute methods
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
        #attr_Pressure_read = self.ChannelValue
        #attr.set_value(attr_Pressure_read)
        state=self.dev_state()
        #av = self.ExternalAttributes[(self.GaugeController+'/'+self.Channel).lower()].read() #Reading from Tau or Cache should be the same
        av = self.Cache[self.ChannelName]
        value,date = av.value,av.time if not hasattr(av.time,'totime') else av.time.totime()
        if not self.LowRange or not fun.matchCl('lo.*',str(self.Cache['ChannelState'].value)):
            quality = fun.matchMap([
                ('ON|MOVING',
                    PyTango.AttrQuality.ATTR_VALID),
                ('ALARM',
                    PyTango.AttrQuality.ATTR_ALARM),
                ('.*',
                    PyTango.AttrQuality.ATTR_INVALID),
                ],state)
        
        else: #If Status==LOW, then the pressure value is replaced by the LowRange value (wanted like this for pressure profile visualization)
            value,quality = min([self.LowRange,(value or self.LowRange)]),PyTango.AttrQuality.ATTR_ALARM
            date = self.Cache['ChannelState'].time if not hasattr(self.Cache['ChannelState'].time,'totime') else self.Cache['ChannelState'].time.totime()
            
        self.debug('read_Pressure(): state is %s, value is %s, quality is %s.'%(state,value,quality))
        if 'set_attribute_value_date_quality' in dir(PyTango):
            PyTango.set_attribute_value_date_quality(attr,float(value),date,quality)
        else: attr.set_value_date_quality(float(value),date,quality)
        
#---- Pressure attribute State Machine -----------------
    def is_Pressure_allowed(self, req_type):
        if self.dev_state() in [
            PyTango.DevState.UNKNOWN,
            PyTango.DevState.DISABLE,
            PyTango.DevState.OFF,
            PyTango.DevState.FAULT,
            #PyTango.DevState.STANDBY,
            PyTango.DevState.INIT,]:
            #    End of Generated Code
            #    Re-Start of Generated Code
            return False
        return True
    
#------------------------------------------------------------------
#    Read ChannelStatus attribute
#------------------------------------------------------------------
    def read_ChannelStatus(self, attr=None):
        self.debug("In read_ChannelStatus()")

        state=self.dev_state()
        av = self.Cache['ChannelState']
        pressure = (self.Cache[self.ChannelName].value or 0.)
        self.debug("In read_ChannelStatus(): %s.ChannelState.read() = %s"%(self.GaugeController,av.value))
        value,quality = fun.matchMap([
            ('ON|MOVING',
                ('%3.2e mbar'%pressure if (self.LowRange and pressure>self.LowRange) else 'LO<%1.1e'%self.LowRange,PyTango.AttrQuality.ATTR_VALID)),
            ('INIT|UNKNOWN',
                (str(state),PyTango.AttrQuality.ATTR_ALARM)),
            ('.*',
                (av.value,PyTango.AttrQuality.ATTR_ALARM)),
            ],state)        
        
        self.ChannelStatus = value
        self.debug('read_ChannelStatus(): state is %s, value is %s, quality of attributes is %s.'%(state,value,quality))
        if attr is not None:
            if 'set_attribute_value_date_quality' in dir(PyTango):
                PyTango.set_attribute_value_date_quality(attr,value,date,quality)
            else: 
                date = av.time if not hasattr(av.time,'totime') else av.time.totime()
                attr.set_value_date_quality(value,date,quality)   


#------------------------------------------------------------------
#    Read Controller attribute
#------------------------------------------------------------------
    def read_Controller(self, attr):
        self.debug("In read_Controller()")
        
        #    Add your own code here
        attr.set_value(self.GaugeController+'/'+self.ChannelName)


#==================================================================
#
#    VacuumGauge command methods
#
#==================================================================

#------------------------------------------------------------------
#    On command:
#
#    Description: 
#------------------------------------------------------------------
    def On(self):
        self.debug("In On()")
        #    Add your own code here
        #Device(self.GaugeController).command_inout('CC_On',self.Channel)
        self.launch_external_command(self.GaugeController,'CC_On',self.ChannelName)
        #self.set_state(PyTango.DevState.ON)


#------------------------------------------------------------------
#    Off command:
#
#    Description: 
#------------------------------------------------------------------
    def Off(self):
        self.debug("In Off()")
        #    Add your own code here
        #Device(self.GaugeController).command_inout('CC_Off',self.Channel)
        self.launch_external_command(self.GaugeController,'CC_Off',self.ChannelName)
        #self.set_state(PyTango.DevState.DISABLE)


#==================================================================
#
#    VacuumGaugeClass class definition
#
#==================================================================
class VacuumGaugeClass(PyTango.PyDeviceClass):

    #    Class Properties
    class_property_list = {
        }


    #    Device Properties
    device_property_list = {
        'GaugeController':
            [PyTango.DevString,
            "Gauge Controller used to read the gauge measure",
            [''] ],
        'Channel':
            [PyTango.DevString,
            "Channel of the Controller used to read this gauge",
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
        'On':
            [[PyTango.DevVoid, ""],
            [PyTango.DevVoid, ""],
            {
                'Display level':PyTango.DispLevel.EXPERT,
             } ],
        'Off':
            [[PyTango.DevVoid, ""],
            [PyTango.DevVoid, ""],
            {
                'Display level':PyTango.DispLevel.EXPERT,
             } ],
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
#    VacuumGaugeClass Constructor
#------------------------------------------------------------------
    def __init__(self, name):
        PyTango.PyDeviceClass.__init__(self, name)
        self.set_type(name);
        print "In VacuumGaugeClass  constructor"

#==================================================================
#
#    VacuumGauge class main method
#
#==================================================================
if __name__ == '__main__':
    try:
        py = PyTango.PyUtil(sys.argv)
        py.add_TgClass(VacuumGaugeClass,VacuumGauge,'VacuumGauge')

        U = PyTango.Util.instance()
        U.server_init()
        U.server_run()

    except PyTango.DevFailed,e:
        print '-------> Received a DevFailed exception:',e
    except Exception,e:
        print '-------> An unforeseen exception occured....',e
