
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
# $Log: PseudoDev.py,v $
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
from PyTango import DevState

try: import fandango
except: import PyTango_utils as fandango
import fandango.functional as fun
import fandango.device as device
from fandango.device import Dev4Tango,attr2str,fakeAttributeValue, fakeEventType
from fandango import callbacks

class PseudoDev(Dev4Tango):
    """ 
    Tango pseudo-Abstract Class for Ion Pumps, it's a firendly and minimalistic interface to each of the pumps managed through a DUAL or Splitter Device Server.
    It inherits from PyTango_utils.device.DevChild, providing event management, logging, Object primitive class and many additional features.
    It requires subclasses to implement a StateMachine(Att,Attr_Value,New_State) method that returns a new state value and updates attribute Cache.
    Last update: srubio@cells.es, 2010/10/18
    """
    MAX_ERRORS = 3
    
    def set_state(self,state,reason='',push=True):
        Dev4Tango.set_state(self,state)
        if reason: self.state_reason = reason
        if getattr(self,'UseEvents',False) and push:
            try: self.push_change_event('State')#,new_state,time.time(),PyTango.AttrQuality.ATTR_VALID)
            except Exception,e: self.trace('warning','%s.push_event(State=%s) failed!: %s'%(type(self).__name__,state,e))
            
#------------------------------------------------------------------
#    Device initialization
#------------------------------------------------------------------
    def init_device(self):
        if not hasattr(self,'LogLevel'): self.LogLevel = 'DEBUG'
        self.init_my_Logger()
        
        self.state_error,self.init_error,self.event_status='','',''
        self.Cache = fandango.CaselessDict() #A cache is needed to avoid timeouts affecting always_hook and read_attributes
        self.Errors = fandango.CaselessDict()
        self.state_reason = 'Device not initialized'      
        self.last_event_received = 0
        self.ChannelStatus = ''
        self.ChannelName = ''
        self.Channel = ''
        
        #Do not move this lines!, order matters
        self.info( "In "+self.get_name()+"::init_device()" )
        self.set_state(PyTango.DevState.INIT)
        self.get_device_properties(self.get_device_class())
        
#------------------------------------------------------------------
#    Device destructor
#------------------------------------------------------------------
    def delete_device(self):
        print "[Device delete_device method] for device",self.get_name()
        self.unsubscribe_external_attributes()
        
#------------------------------------------------------------------
#    Always excuted hook method
#------------------------------------------------------------------
    def always_executed_hook(self):
        self.debug("In PseudoDev.always_executed_hook()")
        last_time = self.ChannelValue.time.totime() if hasattr(self.ChannelValue,'time') else 0
        last_value = getattr(self.ChannelValue,'value',self.ChannelValue)        
        try:
            now = time.time()
            if self.init_error:
                self.warning(self.init_error), self.set_status(self.init_error)
                self.set_state(PyTango.DevState.FAULT)
                self.error('PseudoDev.always_executed_hook(): '+self.init_error)
            elif self.last_event_received and self.last_event_received < now-300.:
                msg = 'EVENTS NOT RECEIVED SINCE %s'%time.ctime(self.last_event_received)
                msg += '\nError: %s'%getattr(self,'events_error','')
                self.state_error = msg
                self.warning(msg), self.set_status(msg)
                self.set_state(PyTango.DevState.FAULT)
                self.error('PseudoDev.always_executed_hook(): '+msg)
        except Exception,e:
            self.error('Exception in always_executed_hook: \n%s'%traceback.format_exc())
    
#------------------------------------------------------------------
#    Event Received Hook
#------------------------------------------------------------------
    def plog(self,prio,s):
        print '%s %s %s: %s' % (prio.upper(),time.strftime('%Y-%m-%d %H:%M:%S',time.localtime()),self.get_name(),s)
        
    def event_received(self,source,type_,attr_value):
        """
        This function manages the States of the device
        Initializes ChannelValue and ChannelStatus to keep the values of attributes
        """
        self.last_event_received = time.time()
        #self.info,debug,error,warning should not be used here to avoid conflicts with tau.core logging
        log = self.plog
        log('info','*'*80)
        log('info','In .event_received(%s(%s),%s,%s)'%(type(source).__name__,source,fakeEventType[type_],type(attr_value).__name__))
        if fakeEventType[type_] == 'Config': return
        source = fandango.tango.get_model_name(source)
        params = fandango.tango.parse_tango_model(source)
        tango_host,dev_name,att,attr_name = '%s:%s'%(params['host'],params['port']),\
            params['devicename'],params['attributename'],'%s/%s'%(params['devicename'],params['attributename'])
        error = ('Error'==fakeEventType[type_])
        try:
            #Get actual State
            state = new_state = self.get_state() 
            if att == 'state' and not error: dState = attr_value.value
            else: dState = self.Cache['state'].value
            log('info','In .event_received(%s): parent state is %s'%(source,dState))
            
            if dState not in (None,PyTango.DevState.INIT,PyTango.DevState.UNKNOWN):
                if not error:
                    if isinstance(attr_value,PyTango.DeviceAttribute) or isinstance(attr_value,fakeAttributeValue):
                        new_state = self.StateMachine(att,attr_value,new_state)
                        if new_state == PyTango.DevState.UNKNOWN and state != PyTango.DevState.UNKNOWN:
                            #StateMachine == UNKNOWN mean that an unparsable value is received, so it is considered as an error and Errors count is checked before switching state
                            self.Errors[att]+=1
                            if self.Errors[att]<self.MAX_ERRORS: new_state = state
                        else:
                            self.Errors[att] = 0
                    else:
                        log('warning','event_received(%s,%s): no further actions for this value type ... %s' % (source,fakeEventType[type_],type(attr_value)))
                elif error:
                    self.Errors[att] += 1
                    try: reasons = [e.reason for e in attr_value.args]
                    except: reasons = []
                    error_value = {'state':None,self.Channel:None,'channelstate':'UNKNOWN'}.get(att,None)
                    #if any([r in err_reason for r in #Discarding well-known common Exceptions
                        #['MKS','VarianDUAL','API_AttributeFailed','AttrNotAllowed','TimeOut','Timeout']]):
                        #print 'In IonPump(%s).push_event(%s): Attribute Reading not allowed (%s)'%(self.get_name(),att_name,err_reason)                    
                    log('warning','In event_received(%s) ... received an error! %d/%d: \n%s '%(source,self.Errors[att],self.MAX_ERRORS,reasons))
                    if self.Errors[att]>=self.MAX_ERRORS: 
                        self.state_reason ='MAX_ERRORS limit (%d) reached for attribute %s, resetting the value to %s' % (self.MAX_ERRORS,attr_name,error_value) 
                        if self.Cache[att].value!=error_value: log('warning',self.state_reason)
                        self.Cache[att].value = error_value
                        new_state = PyTango.DevState.UNKNOWN
                
                #Update State, If dState=ON and state=INIT then state will not change until HVStatus is read
                #new_state = dState if dState is not PyTango.DevState.ON else new_state
            
            #If not able to read Controller's State
            else:
                #In UNKNOWN State is assumed that is useless to communicate with the Parent device
                log('debug','In .event_received(%s): %s.State is %s, events are ignored.'%(source,dev_name,dState))
                new_state=PyTango.DevState.UNKNOWN # Use of states other than UNKNOWN is confussing and unpredictable!
                self.state_reason = '%s state is %s'%(dev_name,dState if dState is not None else 'NotRunning')
                self.ChannelValue = None
                for k in self.Cache:
                    if k.lower()=='state':
                        continue
                    elif 'state' in k.lower(): #ChannelState 
                        self.Cache[k].value = 'UNKNOWN'
                    else:
                        self.Cache[k].value = None
                
        except Exception,e: 
            horreur = traceback.format_exc()
            message = 'exception in event_received(%s): %s\n%s'% (source,e,horreur)
            if self.get_state()!=PyTango.DevState.UNKNOWN:
                self.state_error=str(e).replace('\n','')[:80]+'...'
            log('error',(message))
            self.Errors[att] += 1
            error_value = {'state':None,self.Channel:None,'channelstate':'UNKNOWN'}.get(att,None)
            if self.Errors[att]>=self.MAX_ERRORS and self.Cache[att].value!=error_value:
                log('warning','MAX_ERRORS limit (%d) reached for attribute %s, resetting the value to %s' % (self.MAX_ERRORS,attr_name,error_value))
                self.Cache[att].value = error_value
                if att=='state': new_state = PyTango.DevState.UNKNOWN
            
        if new_state!=state:
            log('info','State Changed!!! %s -> %s'%(state,new_state))
            self.set_state(new_state)
        self.event_status = 'Last event received at %s'%time.ctime(self.last_event_received)
        log('debug','Out of .event_received(%s) ...........'%(source))
        log('debug','*'*80)        
        