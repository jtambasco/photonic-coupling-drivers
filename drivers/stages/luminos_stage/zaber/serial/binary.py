"""The 'binary' module contains all classes related to the Binary 
protocol.
"""

import serial
import struct
import logging
import sys

from .exceptions import TimeoutError, UnexpectedReplyError

# See https://docs.python.org/2/howto/logging.html#configuring-logging-
# for-a-library for info on why we have these two lines here.
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class BinaryCommand(object):
    """Models a single command in Zaber's Binary protocol.

    Attributes:
        device_number: An integer representing the number (*a.k.a.*
            address) of the device to which to send the command. A 
            device number of 0 indicates the command should be executed
            by all devices. 0-255.
        command_number: An integer representing the command to be sent
            to the device. Command numbers are listed in Zaber's
            `Binary Protocol Manual`_. 0-255.
        data: The data value to be transmitted with the command.
        message_id: The `message ID`_ of the command. 0-255, or None if
            not present.

    .. _Binary Protocol Manual: http://www.zaber.com/wiki/Manuals/Binary
        _Protocol_Manual#Quick_Command_Reference
    .. _message ID: http://www.zaber.com/wiki/Manuals/Binary_Protocol_Ma
        nual#Set_Message_Id_Mode_-_Cmd_102
    """
    def __init__(self, device_number, command_number, data = 0, 
            message_id = None):
        """
        Args:
            device_number: An integer specifying the number of the
                target device to which to send this command. 0-255.
            command_number: An integer specifying the command to be
                sent. 0-255.
            data: An optional integer containing the data value to be
                sent with the command. When omitted, *data* will be set
                to 0.
            message_id: An optional integer specifying a message ID to
                give to the message. 0-255, or None if no message ID is
                to be used.

        Raises:
            ValueError: An invalid value was passed.
        """
        if device_number < 0 or command_number < 0:
            raise ValueError("Device and command number must be between 0 "
                    "and 255.")
        self.device_number = device_number
        self.command_number = command_number
        self.data = data
        if message_id is not None and (message_id < 0 or message_id > 255):
            raise ValueError("Message ID must be between 0 and 255.")
        self.message_id = message_id

    def encode(self):
        """Encodes a 6-byte byte string to be transmitted to a device.

        Returns:
            A byte string of length 6, formatted according to Zaber's
            `Binary Protocol Manual`_.
        """
        packed = struct.pack("<2Bl",
                self.device_number, self.command_number, self.data)
        if self.message_id is not None:
            packed = packed[:5] + struct.pack("B", self.message_id)
        return packed

    def __str__(self):
        return "[{:d}, {:d}, {:d}]".format(self.device_number,
                self.command_number, self.data)

class BinaryDevice(object):
    """A class to represent a Zaber device in the Binary protocol.

    Attributes:
        port: A BinarySerial object which represents the port to which
            this device is connected.
        number: The integer number of this device. 1-255.
    """
    def __init__(self, port, number):
        """
        Args:
            port: A BinarySerial object to use as a parent port.
            number: An integer between 1 and 255 which is the number of
                this device.

        Raises:
            ValueError: The device number was invalid.
        """
        if number > 255 or number < 1:
            raise ValueError("Device number must be 1-255.")
        self.number = number
        self.port = port

    def send(self, *args):
        """Sends a command to this device, then waits for a response.

        Args:
            *args: Either a single BinaryCommand, or 1-3 integers
                specifying, in order, the command number, data value,
                and message ID of the command to be sent.

        Notes:
            The ability to pass integers to this function is provided
            as a convenience to the programmer. Calling 
            ``device.send(2)`` is equivalent to calling 
            ``device.send(BinaryCommand(device.number, 2))``.

            Note that in the Binary protocol, devices will only reply
            once they have completed a command. Since this function
            waits for a reply from the device, this function may block
            for a long time while it waits for a response. For the same
            reason, it is important to set the timeout of this device's
            parent port to a value sufficiently high that any command
            sent will be completed within the timeout.

            Regardless of the device address specified to this function,
            the device number of the transmitted command will be 
            overwritten with the number of this device.

            If the command has a message ID set, this function will return
            a reply with a message ID. It does not check whether the message
            IDs match.

        Raises:
            UnexpectedReplyError: The reply read was not send by this
                device.

        Returns: A BinaryReply containing the reply received.
        """
        if len(args) == 1 and isinstance(args[0], BinaryCommand):
            command = args[0]
        elif len(args) < 4:
            command = BinaryCommand(self.number, *args)

        command.device_number = self.number
        self.port.write(command)
        reply = self.port.read(command.message_id is not None)

        if reply.device_number != self.number:
            raise UnexpectedReplyError("Received an unexpected reply from "
                    "device number {0:d}".format(reply.device_number),
                    reply)
        return reply

    def home(self):
        """Sends the "home" command (1), then waits for the device to
        reply.
        
        Returns: A BinaryReply containing the reply received.
        """
        return self.send(1)

    def move_abs(self, position):
        """Sends the "move absolute" command (20), then waits for the
        device to reply.

        Args:
            position: The position in microsteps to which to move.
        
        Returns: A BinaryReply containing the reply received.
        """
        return self.send(20, position)

    def move_rel(self, distance):
        """Sends the "move relative" command (21), then waits for the
        device to reply.
        
        Args:
            distance: The distance in microsteps to which to move.
        
        Returns: A BinaryReply containing the reply received.
        """
        return self.send(21, distance)

    def move_vel(self, speed):
        """Sends the "move at constant speed" command (22), then waits
        for the device to reply.

        Args:
            speed: An integer representing the speed at which to move.

        Notes:
            Unlike the other "move" commands, the device replies
            immediately to this command. This means that when this
            function returns, it is likely that the device is still
            moving.
        
        Returns: A BinaryReply containing the reply received.
        """
        return self.send(22, speed)

    def stop(self):
        """Sends the "stop" command (23), then waits for the device to
        reply.
        
        Returns: A BinaryReply containing the reply received.
        """
        return self.send(23)

    def get_status(self):
        """Sends the "Return Status" command (54), and returns the 
        result.

        Returns:
            An integer representing a `status code`_, according to
            Zaber's Binary Protocol Manual.

        .. _status code: http://www.zaber.com/wiki/Manuals/Binary_Protoc
            ol_Manual#Return_Status_-_Cmd_54
        """
        return self.send(54).data



class BinaryReply(object):
    """Models a single reply in Zaber's Binary protocol.

    Attributes:
        device_number: The number of the device from which this reply
            was sent.
        command_number: The number of the command which triggered this
            reply.
        data: The data value associated with the reply.
        message_id: The message ID number, if present, otherwise None.
    """
    def __init__(self, reply, message_id = False):
        """
        Args:
            reply: A byte string of length 6 containing a binary reply
                encoded according to Zaber's Binary Protocol Manual.
            message_id: True if a message ID should be extracted from
                the reply, False if not.

        Notes:
            Because a Binary reply's message ID truncates the last byte
            of the data value of the reply, it is impossible to tell
            whether a reply contains a message ID or not. Therefore, the
            user must specify whether or not a message ID should be
            assumed to be present.

        Raises:
            TypeError: An invalid type was passed as *reply*. This may
                indicate that a unicode string was passed instead of a
                binary (ascii) string.
        """
        if isinstance(reply, bytes):
            self.device_number, self.command_number, self.data = \
                    struct.unpack("<2Bl", reply)
            if (message_id):
                # Use bitmasks to extract the message ID.
                self.message_id = (self.data & 0xFF000000) >> 24
                self.data = self.data & 0x00FFFFFF 
  
                # Sign extend 24 to 32 bits in the message ID case.
                # If the data is more than 24 bits it will still be wrong,
                # but now negative smaller values will be right.
                if 0 != (self.data & 0x00800000):
                    self.data = (int)((self.data | 0xFF000000) - (1 << 32))
            else: 
                self.message_id = None

        elif isinstance(reply, list):
            # Assume a 4th element is a message ID.
            if len(reply) > 3: message_id = True
            self.device_number = reply[0]
            self.command_number = reply[1]
            self.data = reply[2]
            self.message_id = reply[3] if message_id else None

        else:
            raise TypeError("BinaryReply must be passed a byte string "
                    "('bytes' type) or a list.")

    def encode(self):
        """Returns the reply as a binary string, in the form in which it
        would appear if it had been read from the serial port.

        Returns:
            A byte string of length 6 formatted according to the Binary
            Protocol Manual.
        """
        return struct.pack("<2Bl", self.device_number,
                self.command_number, self.data)

    def __str__(self):
        return "[{:d}, {:d}, {:d}]".format(self.device_number, 
                self.command_number, self.data)

class BinarySerial(object):
    """A class for interacting with Zaber devices using the Binary protocol.

    This class defines a few simple methods for writing to and reading
    from a device connected over the serial port.
    """

    def __init__(self, port, baud = 9600, timeout = 5, inter_char_timeout = 0.01):
        """Creates a new instance of the BinarySerial class.

        Args:
            port: A string containing the name of the serial port to
                which to connect.
            baud: An integer representing the baud rate at which to
                communicate over the serial port.
            timeout: A number representing the number of seconds to wait
                for a reply. Fractional numbers are accepted and can be
                used to specify times shorter than a second.
            inter_char_timeout : A number representing the number of seconds
                to wait between bytes in a reply. If your computer is bad at
                reading incoming serial data in a timely fashion, try 
                increasing this value.

        Notes:
            This class will open the port immediately upon
            instantiation. This follows the pattern set by PySerial,
            which this class uses internally to perform serial
            communication.

        Raises:
            TypeError: The port argument passed was not a string.
        """
        if not isinstance(port, str):
            raise TypeError("port must be a string.")
        try:
            self._ser = serial.serial_for_url(port, do_not_open=True)
            self._ser.baudrate = baud
            self._ser.timeout = timeout
            self._ser.interCharTimeout = inter_char_timeout
            self._ser.open()
        except AttributeError:
            # serial_for_url not supported; use fallback
            self._ser = serial.Serial(port, baud, timeout = timeout, interCharTimeout = inter_char_timeout)

    def write(self, *args):
        r"""Writes a command to the port.

        This function accepts either a BinaryCommand object, a set
        of integer arguments, a list of integers, or a string. 
        If passed integer arguments or a list of integers, those
        integers must be in the same order as would be passed to the
        BinaryCommand constructor (ie. device number, then command
        number, then data, and then an optional message ID).

        Args:
            *args: A BinaryCommand to be sent, or between 2 and 4
                integer arguements, or a list containing between 2 and
                4 integers, or a string representing a 
                properly-formatted Binary command.
                
        Notes:
            Passing integers or a list of integers is equivalent to
            passing a BinaryCommand with those integers as constructor
            arguments.

            For example, all of the following are equivalent::

                >>> write(BinaryCommand(1, 55, 1000))
                >>> write(1, 55, 1000)
                >>> write([1, 55, 1000])
                >>> write(struct.pack("<2Bl", 1, 55, 1000))
                >>> write('\x01\x37\xe8\x03\x00\x00')

        Raises:
            TypeError: The arguments passed to write() did not conform
                to the specification of ``*args`` above.
            ValueError: A string of length other than 6 was passed.
        """
        if len(args) == 1:
            message = args[0]
            if isinstance(message, list):
                message = BinaryCommand(*message)
        elif 1 < len(args) < 5:
            message = BinaryCommand(*args)
        else:
            raise TypeError("write() takes at least 1 and no more than 4 "
                    "arguments ({0:d} given)".format(len(args)))

        if isinstance(message, str):
            logger.debug("> %s", message)
            if len(message) != 6:
                raise ValueError("write of a string expects length 6.")

            # pyserial doesn't handle hex strings.
            if sys.version_info > (3, 0):
                data = bytes(message, "UTF-8") 
            else:
                data = bytes(message) 

        elif isinstance(message, BinaryCommand):
            data = message.encode()
            logger.debug("> %s", message)

        else:
            raise TypeError("write must be passed several integers, or a "
                    "string, list, or BinaryCommand.")

        self._ser.write(data)

    def read(self, message_id = False):
        """Reads six bytes from the port and returns a BinaryReply.

        Args:
            message_id: True if the response is expected to have a 
                message ID. Defaults to False.

        Returns:
            A BinaryCommand containing all of the information read from
            the serial port.

        Raises: 
            zaber.serial.TimeoutError: No data was read before the 
                specified timeout elapsed.
        """
        reply = self._ser.read(6)
        if len(reply) != 6:
            logger.debug("< Receive timeout!")
            raise TimeoutError("read timed out.")
        parsed_reply = BinaryReply(reply, message_id)
        logger.debug("< %s", parsed_reply)
        return parsed_reply

    def flush(self):
        """Flushes the buffers of the underlying serial port."""
        self._ser.flush()

    def open(self):
        """Opens the serial port."""
        self._ser.open()

    def close(self):
        """Closes the serial port."""
        self._ser.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._ser.close()

    @property
    def timeout(self):
        """The number of seconds to wait for input while reading.
        
        The ``timeout`` property accepts floating point numbers for
        fractional wait times.
        """
        return self._ser.timeout

    @timeout.setter
    def timeout(self, t):
        self._ser.timeout = t

    @property
    def baudrate(self):
        """The baud rate at which to read and write.

        The default baud rate for the Binary protocol is 9600. T-Series
        devices are only capable of communication at 9600 baud.
        A-Series devices can communicate at 115200, 57600, 38400,
        19200, and 9600 baud.

        Note that this changes the baud rate of the computer on which
        this code is running. It does not change the baud rate of
        connected devices.
        """
        return self._ser.baudrate

    @baudrate.setter
    def baudrate(self, b):
        if b not in (115200, 57600, 38400, 19200, 9600):
            raise ValueError("Invalid baud rate: {:d}. Valid baud rates are "
                    "115200, 57600, 38400, 19200, and 9600.".format(b))
        self._ser.baudrate = b

