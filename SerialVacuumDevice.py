#=============================================================================
#
# file :        SerialVacuumDevice.py
#
# description :
#
# project :    VacuumController Device Server
#
# $Author: srubio $
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


import threading,re,time,sys,traceback,gc,collections
from TangoDev import TangoDev
import PyTango, fandango
from fandango import Logger
from PyTango import DevState,DevFailed

# ---------------------------------------------------------------
#    Static methods of the module
# ---------------------------------------------------------------

def isWarning(cadena): 
    #return (not '?' in cadena) and (not '!' in cadena) or true
    if '?' in cadena: return True
    if '!' in cadena: return True
    return False

def getExpNumbers(numstring):
    """
    Using regular expressions ...
    [...] matches any of the characters inside
    r'...' means that it is interpreted as a raw string (w/o newlines and things like that)
    (exp)? means 0 or 1 matches, (exp)+ means matches >=1, (exp)* means matches >=0
    """
    regexp = r'([+-]?[0-9]+([.][0-9]+)?([Ee][+-]?[0-9]+([.][0-9]+)?)?)'
    trace = False
    if re.search(regexp,numstring): 
        #.group() and .group(0) is the first match, groups()[0] will not give the same!
        # the match group is a list with all the independent matches within the regexp, we take only the first (main)
        # re.match matches the beginning, re.search matches any point, re.findall gives a list with all the matches (each one is a group)
        #cadena = re.search(regexp,numstring).group(0)
        result = []
        matches = re.findall(regexp,numstring)
        if trace: self.debug('Matches are '+str(len(matches))+':'+str(matches)+';'+str(matches[0]))
        for m in matches:
            cadena = m[0] #The first match, the first group
            number = float(cadena)
            if trace: self.debug( cadena+ ' = '+str( number))
            result.append(number)
        if trace: self.debug( 'Matches are %s'%result)
        return result
    else: return None

class BlackBox(object):
    def __init__(self,size):
        self.size = size
        self.buffer = collections.deque(maxlen=size)
        self.lock = threading.Lock()
        
    def decorator(self,method):
        def wrapper(*args,**kwargs):
            t = time.time()
            r = method(*args,**kwargs)
            try:
                self.lock.acquire()
                self.buffer.append((t,method.__name__,args or None,kwargs or None,r))
            except Exception,e: raise e
            finally: self.lock.release()
            return r
        wrapper.__name__ = method.__name__
        return wrapper
    
    def save(self,filename):
        filename = filename.split('.')[0]+fandango.time2str(cad='_%Y%m%d_%H%M%S.')+'.'+filename.split('.')[-1]
        txt = self.to_string()
        open(filename,'w').write(txt)
        return filename
    
    def to_string(self):
        try:
            self.lock.acquire()
            return '\n'.join('\t'.join(map(str,t)) for t in list(self.buffer))
        except Exception,e: raise e
        finally: self.lock.release()


# ---------------------------------------------------------------
#    The SerialVacuumDevice Class
# ---------------------------------------------------------------

class SerialVacuumDevice(TangoDev,Logger):
    """
    Class created to manage any kind of slow devices (mainly Vacuum) controlled through Serial Port.
    #         Last update: srubio@cells.es, 2007/09/20
    
    The arguments are:
    
        :param tangoDevice: serial device to communicate with
        :param period: time for refreshing all read commands, divided 
			by the number of pollings it will fix the minimum time 
			between two serial communications
        :param threadname: name of the thread
        :param wait: maximum time that the device server will wait 
			for an answer from the serial line
        :param retries: number of times that read commands are retried 
			if no answer is received
        :param log: logging level
    """
    def __init__(self,tangoDevice,period=.1,threadname=None,wait=2, retries=3,log='DEBUG',blackbox=0):
        print "In SerialVacuumDevice::init_device(",tangoDevice,")"

        self.init = False
        self.trace = False
                
        self.readList = fandango.SortedDict() #Dictionary
        self.writeList = fandango.SortedDict() #Dictionary
        self.pollingList = fandango.SortedDict()
        self.PostCommand = []        
        self.args = (0,0) #Tuple
        self.kwargs = {'nada':0} #Dictionary

        self.blankChars = set([ '\n', '\r', ' ', '>' ])
        ## period (seconds): It will be divided between the number 
        # of pollings to determine the pause between readings
        self.period = max(period,.020)
        ## waitTime(seconds): It will be the maximum time that the 
        # device server will wait for an answer from the serial line.        
        self.waitTime = max(wait,.020)
        self.retries = retries
        
        self.lasttime = 0 #Used to store the time of the last communication
        self.lastrecv = ''
        self.lastsend = ''
        self.lasterror = ''
        self.lasterror_epoch = 0
        self.maxreadtime = 0
        self.errors = -1
        self.error_rate = 0
        self.error_rate_epoch = time.time()
        self.comms = 0
        self.stop_threads=False
        self._last_read = ''

        #Inherited: .tangoDevice = name, .dp = deviceproxy
        self.threadname = threadname    
        self.lock=threading.RLock();
        self.event=threading.Event();
        self.threadname=threadname
        self.updateThread = None
        
        TangoDev.__init__(self,tangoDevice)
        self.call__init__(Logger,'SVD('+tangoDevice+')',format='%(levelname)-8s %(asctime)s %(name)s: %(message)s')
        try: self.setLevel(log)
        except: print 'Unable to set SerialVacuumDevice.LogLevel'
        self.errors = 0
        
        if blackbox: 
            self.blackbox = BlackBox(blackbox)
            self.dp.command_inout = self.blackbox.decorator(self.dp.command_inout)
            self.serialComm = self.blackbox.decorator(self.serialComm)
            print 'SerialVacuumDevice.BlackBox(%d) created'%self.blackbox.size
        else: self.blackbox = None
        
    def __del__(self):
        self.info( 'In SerialVacuumDevice.__del__()')
        try:
            self.stop()
            if hasattr(self,'updateThread'):
                del self.updateThread
        except Exception,e:
            self.error( 'Exception while killing SerialVacuumDevice: '+str(e))
        TangoDev.__del__(self)
        
    def add_new_error(self,description="Serial Line Error"):
        now = time.time()
        if (now-self.error_rate_epoch) > 3600: 
            self.error_rate=0
            self.error_rate_epoch=now
        self.errors+=1            
        self.error_rate+=1
        self.lasterror = description        
        self.lasterror_epoch = now
        
    def getSerialClass(self):
        #Checking Serial Line Tango Class
        if getattr(self,'serialClass',None) is None:
            try:
                self.serialClass = self.dp.info().dev_class
                if self.serialClass == 'PySerial': 
                    self.sendComm = self.sendCommPySerial
                else: 
                    self.sendComm = self.sendCommCppSerial
            except:
                self.serialClass = None
        return self.serialClass

    def getReport(self):
        status=''
        if len(self.lastrecv):
            status = status+'Comms at '+time.strftime('%H:%M:%S',time.localtime(self.lasttime))+':\n\t"'+self.lastsend+'" -> "'+self.lastrecv+'"\n'
        if self.errors:
            status = status+str(self.errors)+' CommsErrors.\n'
        if self.error_rate:
            status = status+'Errors/Second: '+str(self.error_rate)+'/'+str(time.time()-self.error_rate_epoch)+'\n'
        if self.lasterror:
            status = status+'LastError: %s\n%s\n' % (time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(self.lasterror_epoch)),self.lasterror)
        return status    
        
    def addComm(self,_key,_val=None):
        self.lock.acquire()
        if _val is None:
            self.info('SerialVacuumDevice::addComm: Adding '+_key+' to the list of Read Commands')
            self.readList[_key]=_val
            self.comms+=1
        else:
            self.info( 'SerialVacuumDevice::addComm: Adding '+_key+','+_val+' to the list of Write Commands: %s'%self.writeList.keys())
            self.writeList[_key]=_val
        self.lock.release()

    def getComm(self,_key):
        self.lock.acquire()
        result=self.readList[_key]#.copy()
        self.lock.release()
        ##The value returned should be always scalar, although there is a tuple in the list
        if type(result)==type((0,0)):
            return result[0]
        else:
            return result
        
    def setPolledComm(self,_key,_period):
        """ srubio 9.2007: This command has been added to allow 
			management of the hardware commandspolling through Tango 
			polling properties
        """
        if not _key in self.readList.keys():
            self.addComm(_key)
        if _period is None or not _period or _period<0:
            if _key in self.pollingList.keys():
                self.pollingList.pop(_key)
        else:
            self.pollingList[_key]=_period,0. #period,lastread
        return
        
    def setPolledNext(self,_key):
        if _key in self.pollingList:
            _period = self.pollingList[_key][0]
            self.setPolledComm(_key,_period)
        else: 
            self.warning('.setPolledNext(%s): key not in polled list!\n\t%s'
                           %(_key,self.pollingList.keys()))
        
    def start(self):
        if self.updateThread:
            if self.updateThread.isAlive():
                self.warning('SerialVacuumDevice.start() not allowed, Thread is still Working!!!')
                return
            else: del self.updateThread
        self.info('SerialVacuumDevice.start()')
        self.event.clear()
        self.updateThread = threading.Thread(None,self.updateHW,self.threadname)
        self.updateThread.setDaemon(True)
        self.updateThread.start()
        
    def stop(self):
        print 'In SerialVacuumDevice.stop() ...'
        self.event.set()
        self.updateThread.join(self.waitTime)
        if self.updateThread.isAlive():
            self.warning( 'Thread '+self.updateThread.getName()+' doesn''t Stop!')
        else:
            self.warning( 'Thread '+self.updateThread.getName()+' Stop')
        return
        
    def updateHW(self):#,args,kwargs):
        """ srubio 9.2007: this method has been modified to manage devices which polling frequency has been configured from Tango
            The rest of devices will be polled at the frequency set by the 'Refresh' property ... it will be always the minimum pause between connections
        """
        trace = True
        self.Alive=True
        
        while not self.event.isSet():
            #if self.trace: print 'Updating Hardware Values'
            pause = self.period/(len(self.readList) or 1.)
            self.debug('Start of cycle, period = %s s, pause = %s s/comm'%(self.period,pause))
                    
            #This check is needed to avoid last commands in the list to be removed by continuous start/stop
            keys = sorted(self.readList.keys())
            self.debug('readList.keys(): %s'%keys)
            if self._last_read and self._last_read<keys[-1]:
                keys = [k for k in keys if k>self._last_read]
                if self.trace: self.info('Thread stopped at %s before finishing the cycle!, continues with %s'%(self._last_read,keys))
                    
            for rd in keys:
                self.debug('In updateHW(%s), checking write commands'%rd)
                #First the write commands
                #-----------------------------------------------------------------------
                for wr in self.writeList.keys():
                    if self.event.isSet(): break
                    if self.trace: self.info( 'There\'s %d'%len(self.writeList) +' write commands pending: %s'%str(self.writeList.keys()))
                    try:
                        result=self.serialComm(self.writeList[wr],False,self.PostCommand)
                    except Exception,e:
                        self.error('updateHW(%s): Serial Line write access failed with exception!: \n%s' % (wr,traceback.format_exc()))
                        self.add_new_error('%s:SerialWriteException:%s'%(rd,str(e)))
                        result = ""
                    finally:
                        self.lock.acquire()
                        self.writeList.pop(wr)
                        self.lock.release()             
                        self.event.wait(pause)
                if self.event.isSet(): break
                #End of the write part
                
                #Then the reading commands
                #-----------------------------------------------------------------------
                self._last_read = rd
                if rd in self.pollingList.keys(): #When a period is specified for a Command this is readed only at this certain period, by default all the commands are readed continuously
                    nxt = self.pollingList[rd][1]+self.pollingList[rd][0]
                    now = time.time()
                    if now<nxt: #If the time for the command to be read has not been reached the bucle jumps to the next command
                        self.event.wait(pause/4.)
                        if self.trace: 
                            self.debug('Command %s has %s polling, continue ...'
                                       %(rd,self.pollingList[rd][0]*1000))
                        continue 
                    else: #If the time has been reached the list is updated and we proceed to read the serial port
                        self.pollingList[rd]=self.pollingList[rd][0],now #period,last_read

                self.debug('In updateHW(%s)'%rd)
                for i in range(self.retries+1):
                    # Only for read commands, several retries are executed
                    # Write commands should have its own verification for that!
                    result = ''
                    if i: (self.errors<15 and self.warning or self.debug)( 'updateHW(%s): Communication failed, retrying %d/%d'%(rd,i,self.retries))
                    try:
                        result=self.serialComm(rd,True,self.PostCommand)
                        if len(result): 
                            #self.errors = 0
                            break
                        elif self.lastsend: 
                            raise Exception,'SVD(%s)_NothingReceived!'%rd.strip()
                        else:
                            raise Exception,self.lasterror
                    except Exception,e:
                        if (time.time()-self.lasterror_epoch)>10:
                            self.error('updateHW(%s): Serial Line read access failed with exception!: %s'%(rd,'SVD' in str(e) and str(e) or traceback.format_exc()))
                        self.add_new_error('%s:SerialReadException:%s'%(rd,str(e)))
                        self.event.wait(pause/2.)

                #-----------------------------------------------------------------------
                self.lock.acquire()
                self.readList[rd]=result
                if result: self.debug('%s = "%s"' % (rd,result))
                self.lock.release()
                if self.trace: self.debug('Waiting %f before next communication'%pause)
                self.event.wait(pause)
                if self.event.isSet():
                    self.warning( 'WARNING: Something enabled SerialVacuumDevice.Event before Wait ends!')
                pass
            if not self.init: self.info('\n===================> First Serial Line update cycle completed\n')
            self.init = True
            self.debug('End of reading cycle, last read was %s'%self._last_read)
            self.event.wait(pause/3.)
        self.info('Out of updateHW()')
        self.Alive=False
        return
                
    ## This command is being overriden at INIT!!!
    #def sendComm(self, commCode, READ=True):
        #if self.trace: self.debug('In sendComm(%s): using %s class' % (commCode,self.getSerialClass()))
        #if self.getSerialClass() == 'PySerial':
            #self.dp.command_inout("FlushInput")
            #self.dp.command_inout("FlushOutput")
            #self.dp.command_inout("Write",array.array('B',commCode))
        #else: #Class is 'Serial'
            #self.dp.command_inout("DevSerFlush",PyTango.Release().version_number<700 and '2' or 2)
            #self.dp.command_inout("DevSerWriteString",commCode)
            #self.dp.command_inout("DevSerWriteChar",[13])
            
    # If sendComm == sendCommPySerial
    def sendCommPySerial(self, commCode, READ=True):
        """ Sends a command to the serial device using the ALBA's PySerial """
        if self.trace: self.debug('In sendComm(%s): using %s class' % (commCode,self.getSerialClass()))
        self.dp.command_inout("FlushInput")
        self.dp.command_inout("FlushOutput")
        self.dp.command_inout("Write",array.array('B',commCode))
            
    # If sendComm == sendCommCppSerial
    def sendCommCppSerial(self, commCode, READ=True):
        """ Sends a command to the serial device using the ESRF's Tango Serial """
        if self.trace: self.debug('In sendComm(%s): using %s class' % (commCode,self.getSerialClass()))
        #if not int(time.time())%60: 
        self.dp.command_inout("DevSerFlush",PyTango.Release().version_number<700 and '2' or 2)
        if not commCode.endswith('\r'): commCode+='\r'
        #Using DevSerWriteChar instead of DevSerWriteString to avoid memory leaks in PyTango8
        self.dp.command_inout("DevSerWriteChar",map(ord,commCode))
        #self.dp.command_inout("DevSerWriteString",commCode)
        #self.dp.command_inout("DevSerWriteChar",[13])
        
    def readComm(self, commCode, READ=True, emulation=False):
        ## A WAIT TIME HAS BEEN NECESSARY BEFORE READING THE BUFFER
        # This wait is divided in smaller periods
        # In each period is tested what has been received from the serial port
        # The wait will finish when after receiving some information there's silence again
        t0, result, retries = fandango.now(),'',0
        if not hasattr(self,'_Dcache'): 
			self._Dcache = {}
        if emulation and commCode in self._Dcache: 
			return self._Dcache[commCode]
			
        wtime = 0.0; result = ""; rec = ""; lastrec = ""; div=4.; 
        before=time.time(); after=before+0.001
        
        while wtime<self.waitTime and not (not len(rec) \
			and len(lastrec.replace(commCode,'').replace('\r','').replace('\n',''))):
            
            #if self.trace and retries: 
            #    print('In readComm(%s)(%d) Waiting %fs for answer ...'
            #        %(commCode,retries,self.waitTime))
            retries += 1			
            
            #The wait condition aborts after waitTime or nothing read after something different from \r or \n.
            #Between reads a pause of TimeWait/10.0 is performed.
            #I've tried to make smaller the time that the thread spends waiting for an answer ... more attempts to improve has been inefficient do to imprecission of the time.sleep method
            
            last=before
            after=time.time()
            pause = self.waitTime/div - (after-before)
            fandango.wait(max(pause,0)) #time.sleep(max(pause,0))
            before=time.time();
            lastrec=lastrec+rec
            
            if self.getSerialClass() == 'PySerial':
                nchars = self.dp.read_attribute('InputBuffer').value
                rec = self.dp.command_inout("Read",nchars)
            else: #Class is 'Serial'
                #rec = self.dp.command_inout("DevSerReadRaw")
                rec = self.dp.command_inout("DevSerReadString",0)
                
            rec.rstrip().lstrip()
            
            lrclean = lastrec.replace(commCode,'').replace('\r','').replace('\n','')
            rrclean = rec.replace('\r','\\r').replace('\n','\\n')
            if self.trace and rrclean: 
                #self.debug
                print( 'received('+str(wtime)+';'+str(after-last)+';'
                    +str(len(lrclean))+';'+str(len(rec))+"): '" + rrclean+"'")
					
            result += rec
            wtime += self.waitTime/div

        self._Dcache[commCode] = result
        readtime = fandango.now()-t0
        self.maxreadtime = max((self.maxreadtime,readtime))
        if self.trace:
            print('ReadComm(%s) = %s done in %f seconds (max = %f, + %f)' % 
                (commCode,result.strip(),readtime,self.maxreadtime,fandango.now()-self.lasttime))

        return result
    
        
    def serialComm(self, commCode, READ=True, PostCommand=[]):
        """   It is an extended version of sendCommand, needed if a confirmation is received after the first command and a second command is needed for the value.
        The format for a PostCommand is a tuple: (Command,ACK,NACK)
        """
        self.trace = True #not READ
        
        try:
            self.dp.ping()
            self.dp.state()
        except:
            msg = 'serialComm(%s): serialLine %s  not available!'%(commCode,self.tangoDevice)
            self.error(msg)
            self.lastsend = self.lastrecv = ''
            raise Exception('SerialLineNotAvailable!')
        
        if self.getSerialClass() == 'PySerial':
            self.dp.command_inout("Open")
            
        ## If the command is not a READ command the answer from the device will be ignored.
        ## Later check of the writing status should be done in higher level code.
        result=''; begin=time.time()
        for ncomm in range(len(PostCommand)+1):
            if self.trace: self.debug( 'ncomm=%d'%ncomm+'; lenpostcommand=%d'%(len(PostCommand)+1))
            if ncomm>0:
                if self.trace: self.debug('%d:%s'%(ncomm,PostCommand[ncomm-1]))
                if result!=PostCommand[ncomm-1][1]:
                    if result!=PostCommand[ncomm-1][2]:
                        if self.trace: self.debug('Received UNKNOWN thing: '+result)
                        self.add_new_error('%s Received UNKNOWN thing: %s' % (commCode,result))
                    if self.trace: self.debug( 'Received NACK: '+result)
                    return result
                else: self.debug( 'Received ACK: '+result)
            
            self.lastsend = not ncomm and commCode or PostCommand[ncomm-1][0]
            self.sendComm(self.lastsend)
            result=self.readComm(commCode,READ)
            
            ## 1-Remove blanks from the end
            for c in reversed(result):
                if c not in self.blankChars: break
                result=result[0:len(result)-1]
                #if self.trace: print 'r:',result,':r\n'
            
            ## 2-Remove echo & blanks from the beginning
            if commCode in result:
                while len(commCode) and len(result) and commCode[0]==result[0]:
                    commCode=commCode[1:]
                    result=result[1:]
                    #if self.trace: print 'c:',commCode,':c\nr:',result,':r\n'
            for c in result:
                if c not in self.blankChars: break
                result=result[1:]
                #if self.trace: print 'r:',result,':r\n'
                
            ## 3-The rest is the result
            self.lasttime = end = time.time()
            self.lastrecv = result            
            if result: 
                self.errors=0
                if self.trace: self.debug( 'serialComm(%s): Result Clean(%s ms): %s -> %s'%(commCode,str(1e3*(end-begin)),commCode,result))            
            else: self.add_new_error('serialComm(%s) received NOTHING'%commCode)
            
        ## 4-Parse result, determine if it is number or not, etc ...
        ## It must be done in the tango device side!!!
        if self.getSerialClass() == 'PySerial':
            self.dp.command_inout("Close")
        return result


#td = SerialVacuumDevice('alba01:10000','ws/vacuum/rocket01-1')
#td = SerialVacuumDevice('ws/vacuum/rocket01-2')
#td.serialComm('W') #Echo off for MidiVac
#td.serialComm('PZ')
    
