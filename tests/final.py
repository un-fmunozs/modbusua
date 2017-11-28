#!/usr/bin/env python
'''

'''
#---------------------------------------------------------------------------# 
# import the modbus libraries we need
#---------------------------------------------------------------------------# 
from pymodbus.server.async import StartTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from pymodbus.transaction import ModbusRtuFramer, ModbusAsciiFramer

#---------------------------------------------------------------------------# 
# import the twisted libraries we need
#---------------------------------------------------------------------------# 
from twisted.internet.task import LoopingCall

#---------------------------------------------------------------------------# 
# configure the service logging
#---------------------------------------------------------------------------# 
import logging
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)

#---------------------------------------------------------------------------# 
# DHT sensor configuration
#---------------------------------------------------------------------------#
import sys
import Adafruit_DHT

sensor = Adafruit_DHT.DHT11
pin = 23

# motor configuration
#---------------------------------------------------------------------------#
from threading import Thread

from time import sleep
import RPi.GPIO as GPIO
GPIO.setwarnings(False)
# Use BCM GPIO references
# instead of physical pin numbers
#GPIO.setmode(GPIO.BCM)
mode=GPIO.getmode()
GPIO.cleanup()

StepPinForward=11
StepPinBackward=15

GPIO.setmode(GPIO.BOARD)
GPIO.setup(StepPinForward, GPIO.OUT)
GPIO.setup(StepPinBackward, GPIO.OUT)
MUTEX_MOVING = False

def forward():
    global MUTEX_MOVING
    x = 6
    if MUTEX_MOVING:
        return
    MUTEX_MOVING = True
    GPIO.output(StepPinForward, GPIO.HIGH)
    print "forwarding running  motor "
    sleep(x)
    GPIO.output(StepPinForward, GPIO.LOW)
    MUTEX_MOVING = False
    return

def reverse():
    global MUTEX_MOVING
    x = 7
    if MUTEX_MOVING:
        return
    MUTEX_MOVING = True
    GPIO.output(StepPinBackward, GPIO.HIGH)
    print "backwarding running motor"
    sleep(x)
    GPIO.output(StepPinBackward, GPIO.LOW)
    MUTEX_MOVING = False
    return

#---------------------------------------------------------------------------# 
# define your callback process
#---------------------------------------------------------------------------# 
def updating_writer(a):
    ''' A worker process that runs every so often and
    updates live values of the context. It should be noted
    that there is a race condition for the update.

    :param arguments: The input arguments to the call
    '''
    log.debug("updating the context")
    context  = a[0]
    register = 3
    slave_id = 0x00
    address  = 0x00
    values   = context[slave_id].getValues(register, address, count=2)

    humidity, temperature = Adafruit_DHT.read_retry(sensor, pin)
    
    # Note that sometimes you won't get a reading and
    # the results will be null (because Linux can't
    # guarantee the timing of calls to read the sensor).  
    # If this happens try again!
    if humidity is None or temperature is None:
	print 'Temp={0:0.1f}*  Humidity={1:0.1f}%'.format(temperature, humidity)

    if humidity is None or temperature is None:
	humidity, temperature = (0, 0)

    #print 'Temp={0:0.1f}*  Humidity={1:0.1f}%'.format(temperature, humidity)
    #values   = [v + 1 for v in values]
    values[0] = temperature
    values[1] = humidity
    log.debug("new values: " + str(values))
    context[slave_id].setValues(register, address, values)


#---------------------------------------------------------------------------# 
# create your custom data block with callbacks
#--------------------------------------------------------------------------# 

from pymodbus.compat import iteritems, iterkeys, itervalues, get_next

class CustomDataBlock():
    def __init__(self, values):
        if isinstance(values, dict):
            self.values = values
        elif hasattr(values, '__iter__'):
            self.values = dict(enumerate(values))
        else: raise ParameterException(
            "Values for datastore must be a list or dictionary")
        self.default_value = get_next(itervalues(self.values)).__class__()
        self.address = get_next(iterkeys(self.values))

    @classmethod
    def create(klass):
        return klass([0x00] * 65536)

    def validate(self, address, count=1):
        if count == 0: return False
        handle = set(range(address, address + count))
        return handle.issubset(set(iterkeys(self.values)))

    def getValues(self, address, count=1):
        return [self.values[i] for i in range(address, address + count)]

    def setValues(self, address, values):
        log.debug("address: " + str(address) + " values: "+ str(values[0]))
        if address == 1:
            if self.values[address] != values[0]:
                if values[0] == False:
                    t = Thread(target=forward)
                    t.start()
                else:
                    t = Thread(target=reverse) 
                    t.start()   

        if isinstance(values, dict):
            for idx, val in iteritems(values):
                self.values[idx] = val
        else:
            if not isinstance(values, list):
                values = [values]
            for idx, val in enumerate(values):
                self.values[address + idx] = val



#---------------------------------------------------------------------------# 
# inicializar el datastorage
#---------------------------------------------------------------------------# 
block = CustomDataBlock([0]*100)
#block = ModbusSequentialDataBlock(0, [2]*100)
store = ModbusSlaveContext(
    di = ModbusSequentialDataBlock(0, [1]*100), #discrete input
    co = block, #coil
    hr = ModbusSequentialDataBlock(0, [3]*100), #holding registers
    ir = ModbusSequentialDataBlock(0, [4]*100)) #input registers
context = ModbusServerContext(slaves=store, single=True)

#---------------------------------------------------------------------------# 
# Inicializar la informacion del servidor modbus
#---------------------------------------------------------------------------# 
identity = ModbusDeviceIdentification()
identity.VendorName  = 'Compuerta Resiliencia'
identity.ProductCode = 'PM'
identity.VendorUrl   = 'http://github.com/bashwork/pymodbus/'
identity.ProductName = 'pymodbus Server'
identity.ModelName   = 'pymodbus Server'
identity.MajorMinorRevision = '1.0'

#---------------------------------------------------------------------------# 
# Rutina que actualiza el valor de la temperatura cada 5 segundos
#---------------------------------------------------------------------------# 
time = 5 # 5 seconds delay
loop = LoopingCall(f=updating_writer, a=(context,))
loop.start(time, now=False) # initially delay by time



# start server
StartTcpServer(context, identity=identity, address=("0.0.0.0", 502))
