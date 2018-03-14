#=============================================================================
#
# file :        VacuumController.py
#
# description : VacuumController Device Server, required by ALBA Vacuum devices
#
# project :    VacuumController Device Server
#
# $Author: srubio@cells.es $
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

#==================================================================
#   VacuumController Class Description:
#
#         This python module provides all common classes used by ALBA Vacuum Devices
#         It also provides a main VacuumController Server that imports all Vacuum classes from PYTHONPATH in a single Tango Server
#
#==================================================================

import sys,os,traceback
import PyTango,fandango
if 'PyUtil' not in dir(PyTango): PyTango.PyUtil = PyTango.Util

from PseudoDev import *
from SerialVacuumDevice import *

try: 
    __RELEASE__ = (l for l in open(os.path.dirname(os.path.abspath(__file__))+'/CHANGES').readlines() if l.startswith('VERSION')).next().split('=',1)[-1].strip()
    klasses = [v for v in locals().values() if isinstance(v,PyTango.DeviceClass)]
    for k in klasses:
        setattr(k,'__RELEASE__',__RELEASE__)
        k.attr_list['VersionNumber'] = [[PyTango.DevString,PyTango.SCALAR,PyTango.READ],]
        setattr(k,'read_VersionNumber',lambda self,attr:attr.set_value(__RELEASE__))
except Exception,e: __RELEASE__ = traceback.format_exc()
print '> ',__RELEASE__

    
#==================================================================
#
#    Vacuum Device Servers class main method
#
#==================================================================
if __name__ == '__main__':
    try:
        py = PyTango.PyUtil(sys.argv)
        #######################################################################
        ## DO NOT CHANGE THE ORDER IN WHICH THE CLASSES ARE LOADED, IT IS NOT TRIVIAL
        db = fandango.get_database()
        classes = db.get_device_class_list('VacuumController/%s'%sys.argv[1])[1::2]
        
        k = 'MKSGaugeController'
        if not classes or k in classes:
            try:
                from MKSGaugeController.MKSGaugeController import *
                py.add_class(MKSGaugeControllerClass,MKSGaugeController,'MKSGaugeController')
                print('%s class added'%k)
            except:
                print('Unable to import %s Class: %s'%(k,traceback.format_exc()))
        k = 'MVC3GaugeController'
        if not classes or k in classes:
            try:
                from MVC3GaugeController.MVC3GaugeController import *
                py.add_class(MVC3GaugeControllerClass,MVC3GaugeController)
                print('%s class added'%k)
            except:
                print('Unable to import %s Class: %s'%(k,traceback.format_exc()))
        k = 'PfeifferGaugeController'
        if not classes or k in classes:
            try:
                from PfeifferGaugeController.PfeifferGaugeController import *
                py.add_TgClass(PfeifferGaugeControllerClass,PfeifferGaugeController,'PfeifferGaugeController')
                print('%s class added'%k)
            except:
                print('Unable to import %s Class: %s'%(k,traceback.format_exc()))
        k = 'LeyboldGaugeController'
        if not classes or k in classes:
            try:
                from LeyboldGaugeController.LeyboldGaugeController import *
                py.add_TgClass(LeyboldGaugeControllerClass,LeyboldGaugeController,'LeyboldGaugeController')
                print('%s class added'%k)
            except:
                print('Unable to import %s Class: %s'%(k,traceback.format_exc()))
        k = 'AxtranGaugeController'
        if not classes or k in classes:
            try:
                py.add_TgClass(AxtranGaugeControllerClass,AxtranGaugeController,'AxtranGaugeController')
                from AxtranGaugeController.AxtranGaugeController import *
                print('%s class added'%k)
            except:
                print('Unable to import %s Class: %s'%(k,traceback.format_exc()))
        k = 'VacuumGauge'
        if not classes or k in classes:
            try:
                from VacuumGauge.VacuumGauge import *
                py.add_class(VacuumGaugeClass,VacuumGauge,'VacuumGauge')
                print('%s class added'%k)
            except:
                print('Unable to import %s Class: %s'%(k,traceback.format_exc()))
        
        #######################################################################
        ## DO NOT CHANGE THE ORDER IN WHICH THE CLASSES ARE LOADED, IT IS NOT TRIVIAL

        k = 'VarianDUAL'
        if not classes or k in classes:
            try:
                from VarianDUAL.VarianDUAL import *
                py.add_class(VarianDUALClass,VarianDUAL,'VarianDUAL')
                print('%s class added'%k)
            except:
                print('Unable to import %s Class: %s'%(k,traceback.format_exc()))
        k = 'MidiVac'
        if not classes or k in classes:
            try:
                from MidiVac.MidiVac import *
                py.add_class(MidiVacClass,MidiVac,'MidiVac')
                print('%s class added'%k)
            except:
                print('Unable to import %s Class: %s'%(k,traceback.format_exc()))
        k = 'SplitterBox'
        if not classes or k in classes:
            try:
                from SplitterBox import SplitterBox,SplitterBoxClass
                py.add_class(SplitterBoxClass,SplitterBox,'SplitterBox')
                print('%s class added'%k)
            except:
                print('Unable to import %s Class: %s'%(k,traceback.format_exc()))
        k = 'IonPump'
        if not classes or k in classes:
            try:
                from IonPump.IonPump import *
                py.add_class(IonPumpClass,IonPump,'IonPump')
                print('%s class added'%k)
            except:
                print('Unable to import %s Class: %s'%(k,traceback.format_exc()))

        # Commented due to problems with 64 bits in Tango8
        #k = 'Serial'
        #try:
        #    py.add_Cpp_TgClass('Serial','Serial')
        #except:
        #    print('Unable to import %s Class: %s'%(k,traceback.format_exc()))

        k = 'DDebug'
        if not classes or k in classes:
            try:
                from fandango.dynamic import CreateDynamicCommands
                from fandango.device import DDebug,DDebugClass
                py.add_class(DDebugClass,DDebug,'DDebug')
                CreateDynamicCommands(DDebug,DDebugClass)
                print('%s class added'%k)
            except:
                print('Unable to import %s Class: %s'%(k,traceback.format_exc()))
        
        U = PyTango.Util.instance()
        U.server_init()
        U.server_run()

    except PyTango.DevFailed,e:
        print '-------> Received a DevFailed exception:',e
        traceback.print_exc()
    except Exception,e:
        print '-------> An unforeseen exception occured....',e
        traceback.print_exc()
