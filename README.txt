#=============================================================================
# description : VacuumController Device Server, required by ALBA Vacuum devices
#
# $Author: srubio@cells.es $
#
# copyleft :    Cells / Alba Synchrotron
#               Bellaterra
#               Spain
#
############################################################################

#==================================================================
#   VacuumController Class Description:
#
#         This python module provides all common classes used by ALBA Vacuum Devices
#         It also provides a main VacuumController Server that imports all Vacuum classes from PYTHONPATH in a single Tango Server
#
#==================================================================

# associated classes; they will need VacuumController to be available in your PYTHONPATH:

# AxtranGaugeController, MKSGaugeController, PfeifferGaugeController,
# LeyboldGaugeController, LOCOSplitter, VarianDUAL, MidiVac, IonPump,
# VacuumGauge, MVC3GaugeController

# Other Dependencies
#
# https://svn.code.sf.net/p/tango-ds/code/DeviceClasses/Communication/SerialLine
# https://github.com/tango-controls/fandango


##########################################################################
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




