'''
Collection of transaction based abstractions
'''
import hmac
import hashlib

import sys
import struct
import socket
from binascii import b2a_hex, a2b_hex

from pymodbus.exceptions import ModbusIOException, NotImplementedException
from pymodbus.exceptions import InvalidMessageRecievedException
from pymodbus.constants  import Defaults
from pymodbus.interfaces import IModbusFramer
from pymodbus.utilities  import checkCRC, computeCRC
from pymodbus.utilities  import checkLRC, computeLRC
from pymodbus.compat import iterkeys, imap, byte2int

#---------------------------------------------------------------------------#
# Logging
#---------------------------------------------------------------------------#
import logging
_logger = logging.getLogger(__name__)

SECRET = 'secret-shared-key'
HMACLEN = 40

#---------------------------------------------------------------------------#
# Modbus TCP Message
#---------------------------------------------------------------------------#
class ModbusSocketFramerHMAC(IModbusFramer):
    ''' Modbus Socket Frame controller

    Before each modbus TCP message is an MBAP header which is used as a
    message frame.  It allows us to easily separate messages as follows::

        [         MBAP Header                 ] [ Function Code] [ Data ]
        [ tid ][ pid ][ length ][ uid ] [hmac]
          2b     2b     2b        1b     40b      1b           Nb

        while len(message) > 0:
            tid, pid, length`, uid = struct.unpack(">HHHB", message)
            request = message[0:7 + length - 1`]
            message = [7 + length - 1:]

        * length = uid + function code + data
        * The -1 is to account for the uid byte
    '''

    def __init__(self, decoder):
        ''' Initializes a new instance of the framer

        :param decoder: The decoder factory implementation to use
        '''
        self.__buffer = b''
        self.__header = {'tid':0, 'pid':0, 'len':0, 'uid':0}
        self.__hsize  = 0x07 + HMACLEN
        self.decoder  = decoder

    #-----------------------------------------------------------------------#
    # Private Helper Functions
    #-----------------------------------------------------------------------#
    def checkFrame(self):
        '''
        Check and decode the next frame Return true if we were successful
        '''
        if len(self.__buffer) > self.__hsize:
            self.__header['tid'], self.__header['pid'], \
            self.__header['len'], self.__header['uid'], self.__header['hmac'] = struct.unpack(
                    '>HHHB40s', self.__buffer[0:self.__hsize])
            print self.__header['hmac'], self.__header['len']
            # someone sent us an error? ignore it
            if self.__header['len'] < 2:
                self.advanceFrame()
            # we have at least a complete message, continue
            elif len(self.__buffer) - self.__hsize + 1 >= self.__header['len']:
                return True
        # we don't have enough of a message yet, wait
        return False

    def advanceFrame(self):
        ''' Skip over the current framed message
        This allows us to skip over the current message after we have processed
        it or determined that it contains an error. It also has to reset the
        current frame header handle
        '''
        length = self.__hsize + self.__header['len'] - 1
        self.__buffer = self.__buffer[length:]
        self.__header = {'tid':0, 'pid':0, 'len':0, 'uid':0}

    def isFrameReady(self):
        ''' Check if we should continue decode logic
        This is meant to be used in a while loop in the decoding phase to let
        the decoder factory know that there is still data in the buffer.

        :returns: True if ready, False otherwise
        '''
        return len(self.__buffer) > self.__hsize

    def addToFrame(self, message):
        ''' Adds new packet data to the current frame buffer

        :param message: The most recent packet
        '''
        self.__buffer += message

    def getFrame(self):
        ''' Return the next frame from the buffered data

        :returns: The next full frame buffer
        '''
        length = self.__hsize + self.__header['len'] - 1
        print self.__buffer, self.__buffer[self.__hsize:length]
        return self.__buffer[self.__hsize:length]

    def populateResult(self, result):
        '''
        Populates the modbus result with the transport specific header
        information (pid, tid, uid, checksum, etc)

        :param result: The response packet
        '''
        result.transaction_id = self.__header['tid']
        result.protocol_id = self.__header['pid']
        result.unit_id = self.__header['uid']

    #-----------------------------------------------------------------------#
    # Public Member Functions
    #-----------------------------------------------------------------------#
    def processIncomingPacket(self, data, callback):
        ''' The new packet processing pattern

        This takes in a new request packet, adds it to the current
        packet stream, and performs framing on it. That is, checks
        for complete messages, and once found, will process all that
        exist.  This handles the case when we read N + 1 or 1 / N
        messages at a time instead of 1.

        The processed and decoded messages are pushed to the callback
        function to process and send.

        :param data: The new packet data
        :param callback: The function to send results to
        '''
        _logger.debug(' '.join([hex(byte2int(x)) for x in data]))
        self.addToFrame(data)
        while True:
            if self.isFrameReady():
                if self.checkFrame():
                    self._process(callback)
                else: self.resetFrame()
            else:
                if len(self.__buffer):
                    # Possible error ???
                    if self.__header['len'] < 2:
                        self._process(callback, error=True)
                break

    def _process(self, callback, error=False):
        """
        Process incoming packets irrespective error condition 
        """
        data = self.getRawFrame() if error else self.getFrame()
        print data, "data"
        result = self.decoder.decode(data)
        if result is None:
            raise ModbusIOException("Unable to decode request")
        elif error and result.function_code < 0x80:
            raise InvalidMessageRecievedException(result)
        else:
            self.populateResult(result)
            self.advanceFrame()
            callback(result)  # defer or push to a thread?

    def resetFrame(self):
        ''' Reset the entire message frame.
        This allows us to skip ovver errors that may be in the stream.
        It is hard to know if we are simply out of sync or if there is
        an error in the stream as we have no way to check the start or
        end of the message (python just doesn't have the resolution to
        check for millisecond delays).
        '''
        self.__buffer = b''
        self.__header = {}

    def getRawFrame(self):
        """
        Returns the complete buffer 
        """
        return self.__buffer

    def buildPacket(self, message):
        ''' Creates a ready to send modbus packet

        :param message: The populated request/response to send
        '''
        data = message.encode()
        digest_maker = hmac.new(SECRET, '', hashlib.sha1)
        digest_maker.update(data)
        digest = digest_maker.hexdigest()

        packet = struct.pack('>HHHB40sB',
            message.transaction_id,
            message.protocol_id,
            len(data) + 2 ,
            message.unit_id,
            digest, 
            message.function_code) + data 
        return packet


#---------------------------------------------------------------------------#
# Exported symbols
#---------------------------------------------------------------------------#
__all__ = [
    "ModbusSocketFramer", 
]

