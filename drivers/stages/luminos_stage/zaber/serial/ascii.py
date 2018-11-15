"""The 'ascii' module contains all classes related to the ASCII
protocol.
"""

import serial
import time
import logging

from .exceptions import TimeoutError, UnexpectedReplyError

# See https://docs.python.org/2/howto/logging.html#configuring-logging-
# for-a-library for info on why we have these two lines here.
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class AsciiAxis(object):
    """Represents one axis of an ASCII device.
    
    Attributes:
        parent: An AsciiDevice which represents the device which has
            this axis.
        number: The number of this axis. 1-9.
    """

    def __init__(self, device, number):
        """
        Args:
            device: An AsciiDevice which is the parent of this axis.
            number: The number of this axis. Must be 1-9.

        Raises:
            ValueError: The axis number was not between 1 and 9.
        """
        if number < 1 or number > 9:
            raise ValueError("Axis number must be between 1 and 9.")
        self.number = number
        self.parent = device

    def send(self, message):
        """Sends a message to the axis and then waits for a reply.

        Args:
            message: A string or AsciiCommand object containing a
                command to be sent to this axis.

        Notes:
            Regardless of the device address or axis number supplied in
            (or omitted from) the message passed to this function, this
            function will always send the command to only this axis.
            
            Though this is intended to make sending commands to a
            particular axis easier by allowing the user to pass in a
            "global command" (ie. one whose target device and axis are
            both 0), this can result in some unexpected behaviour. For
            example, if the user tries to call send() with an
            AsciiCommand which has a different target axis number than
            the number of this axis, they may be surprised to find that
            the command was sent to this axis rather than the one
            originally specified in the AsciiCommand.

        Examples:
            Since send() will automatically set (or overwrite) the
            target axis and device address of the message, all of the
            following calls to send() will result in identical ASCII
            messages being sent to the serial port::

                >>> axis.send("home")
                >>> axis.send(AsciiCommand("home"))
                >>> axis.send("0 0 home")
                >>> axis.send("4 8 home")
                >>> axis.send(AsciiCommand(1, 4, "home"))

        Raises:
            UnexpectedReplyError: The reply received was not sent by the
                expected device and axis.

        Returns: An AsciiReply object containing the reply received.
        """
        if isinstance(message, (str, bytes)):
            message = AsciiCommand(message)

        # Always send the AsciiCommand to *this* axis.
        message.axis_number = self.number

        reply = self.parent.send(message)
        if reply.axis_number != self.number:
            raise UnexpectedReplyError("Received a reply from an "
                    "unexpected axis: axis {}".format(reply.axis_number),
                    reply)
        return reply

    def home(self):
        """Sends the "home" command, then polls the axis until it is
        idle.

        Raises:
            UnexpectedReplyError: The reply received was not sent by the
                expected device and axis.

        Returns: An AsciiReply object containing the first reply
            received.
        """
        reply = self.send("home")
        self.poll_until_idle()
        return reply

    def move_abs(self, position, blocking = True):
        """Sends the "move abs" command to the axis to move it to the
        specified position, then polls the axis until it is idle.

        Args:
            position: An integer representing the position in
                microsteps to which to move the axis.
            blocking: An optional boolean, True by default. If set to
                False, this function will return immediately after
                receiving a reply from the device, and it will not poll
                the device further.

        Raises:
            UnexpectedReplyError: The reply received was not sent by the
                expected device and axis.

        Returns: An AsciiReply object containing the first reply
            received.
        """
        reply = self.send("move abs {0:d}".format(position))
        if blocking: self.poll_until_idle()
        return reply

    def move_rel(self, distance, blocking = True):
        """Sends the "move rel" command to the axis to move it by the
        specified distance, then polls the axis until it is idle.
        
        Args:
            distance: An integer representing the number of microsteps
                by which to move the axis.
            blocking: An optional boolean, True by default. If set to
                False, this function will return immediately after
                receiving a reply from the device, and it will not poll
                the device further.

        Raises:
            UnexpectedReplyError: The reply received was not sent by the
                expected device and axis.

        Returns: An AsciiReply object containing the first reply
            received.
        """
        reply = self.send("move rel {0:d}".format(distance))
        if blocking: self.poll_until_idle()
        return reply

    def move_vel(self, speed, blocking = False):
        """Sends the "move vel" command to make the axis move at the
        specified speed.

        Args:
            speed: An integer representing the speed at which to move
                the axis.
            blocking: An optional boolean, False by default. If set to
                True, this function will poll the device repeatedly
                until it reports that the axis is idle.

        Notes:
            Unlike the other two move commands, move_vel() does not by
            default poll the axis until it is idle. move_vel() will
            return immediately after receiving a response from the
            device unless the "blocking" argument is set to True.

        Raises:
            UnexpectedReplyError: The reply received was not sent by the
                expected device and axis.

        Returns: An AsciiReply object containing the first reply
            received.
        """
        reply = self.send("move vel {0:d}".format(speed))
        if blocking: self.poll_until_idle()
        return reply

    def stop(self):
        """Sends the "stop" command to the axis.

        Notes:
            The stop command can be used to pre-empt any movement
            command in order to stop the axis early. 

        Raises:
            UnexpectedReplyError: The reply received was not sent by the
                expected device and axis.

        Returns: An AsciiReply object containing the first reply
            received.
        """
        reply = self.send("stop")
        self.poll_until_idle()
        return reply

    def get_status(self):
        """Queries the axis for its status and returns the result.

        Raises:
            UnexpectedReplyError: The reply received was not sent by the
                expected device and axis.
        
        Returns:
            A string containing either "BUSY" or "IDLE", depending on
            the response received from the axis.
        """
        return self.send("").device_status

    def poll_until_idle(self):
        """Polls the axis and blocks until the device reports that the
        axis is idle.

        Raises:
            UnexpectedReplyError: The reply received was not sent by the
                expected device and axis.

        Returns: An AsciiReply object containing the last reply
            received.
        """
        return self.parent.poll_until_idle(self.number)

class AsciiCommand(object):
    """Models a single command in Zaber's ASCII protocol.

    Attributes:
        device_address: An integer representing the address of the 
            device to which to send this command.
        axis_number: The integer number of the particular axis which 
            should execute this command. An axis number of 0 specifies
            that all axes should execute the command, or that the
            command is "device scope".
        message_id: Optional. An integer to be used as a message ID.
            If a command has a message ID, then the device will send a
            reply with a matching message ID. A message_id value of
            None indicates that a message ID is not to be used.
            0 is a valid message ID.
        data: The bulk of the command. data includes a valid ASCII
            command and any parameters of that command, separated by
            spaces. A data value of "" (the empty string) is valid,
            and is often used as a "get status" command to query
            whether a device is busy or idle.
    """

    def __init__(self, *args):
        r"""
        Args:
            *args: A number of arguments beginning with 0 to 3 integers
                followed by one or more strings. 
                
        Notes:
            For every absent integer argument to ``__init__``, any string 
            argument(s) will be examined for leading integers. The first
            integer found (as an argument or as the leading part of a
            string) will set the ``device_address`` property, the second
            integer will be taken as the ``axis_number`` property, and
            the third integer found will be the ``message_id`` property.

            When a string argument contains text which can not be
            interpreted as an integer, all arguments which follow it
            are considered to be a part of the data. This is consistent
            with how ASCII commands are parsed by the Zaber device
            firmware.

            All leading '/' and trailing '\\r\\n' characters in string
            arguments are stripped when the arguments are parsed.

        Examples:
            The flexible argument structure of this constructor allows 
            commands to be constructed by passing in integers followed 
            by a command and its parameters, or by passing in one
            fully-formed, valid ASCII command string, or a mix of the
            two if the user desires.

            For example, all of the following constructors will create
            identical AsciiCommand objects::

                >>> AsciiCommand("/1 0 move abs 10000\r\n")
                >>> AsciiCommand("1 move abs 10000")
                >>> AsciiCommand(1, 0, "move abs 10000")
                >>> AsciiCommand(1, "move abs 10000")
                >>> AsciiCommand("1", "move abs", "10000")
                >>> AsciiCommand(1, "move abs", 10000)

        Raises:
            TypeError: An argument was passed to the constructor which
                was neither an integer nor a string.
        """
        self.data = ''
        attributes = iter(["device_address", "axis_number", "message_id"])
        for arg in args:
            if isinstance(arg, int):
                try: 
                    # If self.data has got something in it,
                    # then all remaining arguments are also data.
                    if self.data: raise StopIteration
                    next_attr = next(attributes)
                    setattr(self, next_attr, arg)
                except StopIteration:
                    self.data = ' '.join([self.data, str(arg)]) if self.data \
                            else str(arg)

            elif isinstance(arg, (bytes, str)):
                if isinstance(arg, bytes):
                    arg = arg.decode()

                # Trim leading '/' and trailing "\r\n".
                arg = arg.lstrip('/')
                arg = arg.rstrip('\r\n')

                tokens = arg.split(' ')
                for i, token in enumerate(tokens):
                    try: 
                        # As above: if data has already been found,
                        # all remaining arguments/tokens are also data.
                        if self.data: raise StopIteration
                        num = int(token) # Is it a number?
                        next_attr = next(attributes) # If it *is* a number...
                        setattr(self, next_attr, num) # ...set the next attribute.
                    except (ValueError, StopIteration):  
                        # If token is not a number, or if we are out of 
                        # attributes, the remaining text is data.
                        data = ' '.join(tokens[i:])
                        self.data = ' '.join([self.data, data]) if self.data \
                                else data
                        break
            else:
                raise TypeError("All arguments to AsciiCommand() must be "
                        "either strings or integers. An argument of type "
                        "{0:s} was passed.".format(str(type(arg))))

        # Set remaining attributes.
        if not hasattr(self, "device_address"): self.device_address = 0 
        if not hasattr(self, "axis_number"): self.axis_number = 0
        if not hasattr(self, "message_id"): self.message_id = None

    def encode(self):
        """Return a valid ASCII command based on this object's 
        attributes.
        
        The string returned by this function is a fully valid command,
        formatted according to Zaber's `Ascii Protocol Manual`_. 

        Returns:
            A valid, fully-formed ASCII command.
        """
        if self.message_id is not None:
            if self.data:
                return "/{0:d} {1:d} {2:d} {3:s}\r\n".format(
                        self.device_address, 
                        self.axis_number,
                        self.message_id, 
                        self.data).encode()
            else: return "/{0:d} {1:d} {2:d}\r\n".format(
                    self.device_address,
                    self.axis_number, 
                    self.message_id).encode()

        if self.data:
            return "/{0:d} {1:d} {2:s}\r\n".format(
                    self.device_address,
                    self.axis_number, 
                    self.data).encode()
        else: return "/{0:d} {1:d}\r\n".format(
                self.device_address,
                self.axis_number).encode()

    def __str__(self):
        """Returns an encoded ASCII command, without the newline
        terminator.

        Returns:
            A string containing an otherwise-valid ASCII command,
            without the newline (ie. "\r\n") at the end of the string
            for ease of printing.
        """
        string = self.encode().rstrip(b"\r\n")
        # A little bit of type-checking for Python 2/3 compatibility.
        if not isinstance(string, str):
            string = string.decode()
        return string

class AsciiDevice(object):
    """Represents an ASCII device.
    
    Attributes:
        port: The port to which this device is connected.
        address: The address of this device. 1-99.
    """

    def __init__(self, port, address):
        """
        Args:
            port: An AsciiSerial object representing the port to which
                this device is connected. 
            address: An integer representing the address of this
                device. It must be between 1-99.

        Raises:
            ValueError: The address was not between 1 and 99.
        """
        if address < 1 or address > 99:
            raise ValueError("Address must be between 1 and 99.")
        self.address = address
        self.port = port

    def axis(self, number):
        """Returns an AsciiAxis with this device as a parent and the
        number specified.

        Args:
            number: The number of the axis. 1-9.

        Notes:
            This function will always return a *new* AsciiAxis instance.
            If you are working extensively with axes, you may want to
            create just one set of AsciiAxis objects by directly using
            the AsciiAxis constructor instead of this function to avoid
            creating lots and lots of objects.

        Returns:
            A new AsciiAxis instance to represent the axis specified.
        """
        return AsciiAxis(self, number)

    def send(self, message):
        r"""Sends a message to the device, then waits for a reply.

        Args:
            message: A string or AsciiCommand representing the message
                to be sent to the device.

        Notes:
            Regardless of the device address specified in the message,
            this function will always send the message to this device.
            The axis number will be preserved. 

            This behaviour is intended to prevent the user from
            accidentally sending a message to all devices instead of
            just one. For example, if ``device1`` is an AsciiDevice 
            with an address of 1, device1.send("home") will send the
            ASCII string "/1 0 home\\r\\n", instead of sending the
            command "globally" with "/0 0 home\\r\\n".

        Raises:
            UnexpectedReplyError: The reply received was not sent by
                the expected device.

        Returns:
            An AsciiReply containing the reply received.
        """
        if isinstance(message, (str, bytes)):
           message = AsciiCommand(message) 

        # Always send an AsciiCommand to *this* device.
        message.device_address = self.address

        self.port.write(message)

        reply = self.port.read()
        if (reply.device_address != self.address
            or reply.axis_number != message.axis_number
            or reply.message_id != message.message_id):
            raise UnexpectedReplyError("Received an unexpected reply from "
                    "device with address {0:d}, axis {1:d}".format(
                        reply.device_address, reply.axis_number),
                    reply)
        return reply

    def poll_until_idle(self, axis_number = 0):
        """Polls the device's status, blocking until it is idle.

        Args:
            axis_number: An optional integer specifying a particular
                axis whose status to poll. axis_number must be between
                0 and 9. If provided, the device will only report the
                busy status of the axis specified. When omitted, the
                device will report itself as busy if any axis is moving.

        Raises:
            UnexpectedReplyError: The reply received was not sent by
                the expected device.

        Returns:
            An AsciiReply containing the last reply received.
        """
        while True:
            reply = self.send(AsciiCommand(self.address, axis_number, ""))
            if reply.device_status == "IDLE": break
            time.sleep(0.05)
        return reply

    def home(self):
        """Sends the "home" command, then polls the device until it is
        idle.

        Returns:
            An AsciiReply containing the first reply received.
        """
        reply = self.send("home")
        self.poll_until_idle()
        return reply

    def move_abs(self, position, blocking = True):
        """Sends the "move abs" command to the device to move it to the
        specified position, then polls the device until it is idle.

        Args:
            position: An integer representing the position in
                microsteps to which to move the device.
            blocking: An optional boolean, True by default. If set to
                False, this funciton will return immediately after
                receiving a reply from the device and it will not poll
                the device further.

        Raises:
            UnexpectedReplyError: The reply received was not sent by
                the expected device.

        Returns:
            An AsciiReply containing the first reply received.
        """
        reply = self.send("move abs {0:d}".format(position))
        if blocking: self.poll_until_idle()
        return reply

    def move_rel(self, distance, blocking = True):
        """Sends the "move rel" command to the device to move it by the
        specified distance, then polls the device until it is idle.
        
        Args:
            distance: An integer representing the number of microsteps
                by which to move the device.
            blocking: An optional boolean, True by default. If set to
                False, this function will return immediately after
                receiving a reply from the device, and it will not poll
                the device further.

        Raises:
            UnexpectedReplyError: The reply received was not sent by
                the expected device.

        Returns:
            An AsciiReply containing the first reply received.
        """
        reply = self.send("move rel {0:d}".format(distance))
        if blocking: self.poll_until_idle()
        return reply

    def move_vel(self, speed, blocking = False):
        """Sends the "move vel" command to make the device move at the
        specified speed.

        Args:
            speed: An integer representing the speed at which to move
                the device.
            blocking: An optional boolean, False by default. If set to
                True, this function will poll the device repeatedly
                until it reports that it is idle.

        Notes:
            Unlike the other two move commands, move_vel() does not by
            default poll the device until it is idle. move_vel() will
            return immediately after receiving a response from the
            device unless the "blocking" argument is set to True.

        Raises:
            UnexpectedReplyError: The reply received was not sent by
                the expected device.

        Returns:
            An AsciiReply containing the first reply received.
        """
        reply = self.send("move vel {0:d}".format(speed))
        if blocking: self.poll_until_idle()
        return reply

    def stop(self):
        """Sends the "stop" command to the device.

        Notes:
            The stop command can be used to pre-empt any movement
            command in order to stop the device early. 

        Raises:
            UnexpectedReplyError: The reply received was not sent by
                the expected device.

        Returns:
            An AsciiReply containing the first reply received.
        """
        reply = self.send("stop")
        self.poll_until_idle()
        return reply

    def get_status(self):
        """Queries the device for its status and returns the result.

        Raises:
            UnexpectedReplyError: The reply received was not sent by
                the expected device.

        Returns:
            A string containing either "BUSY" or "IDLE", depending on
            the response received from the device.
        """
        return self.send("").device_status

class AsciiReply(object):
    """Models a single reply in Zaber's ASCII protocol.

    Attributes:
        message_type: A string of length 1 containing either '@', '!',
            or '#', depending on whether the message type was a 
            "reply", "alert", or "info", respectively. Most messages
            received from Zaber devices are of type "reply", or '@'.
        device_address: An integer between 1 and 99 representing the
            address of the device from which the reply was sent.
        axis_number: An integer between 0 and 9 representing the axis
            from which the reply was sent. An axis number of 0
            represents a reply received from the device as a whole.
        message_id: An integer between 0 and 255 if present, or None
            otherwise.
        reply_flag: A string of length two, containing either "OK" or
            "RJ", depending on whether the command was accepted or
            rejected by the device. Value will be None for device replies
            that do not have a reply flag, such as info and alert messages.
        device_status: A string of length 4, containing either "BUSY"
            or "IDLE", depending on whether the device is moving or 
            stationary.
        warning_flag: A string of length 2, usually "--". If it is not
            "--", it will be one of the two-letter warning flags
            described in the `Warning Flags section`_ of the Ascii
            Protocol Manual.
        data: A string containing the response data.
        checksum: A string of length 2 containing two characteres
            representing a hexadecimal checksum, or None if a checksum
            was not found in the reply.

    .. _Warning Flags section: http://www.zaber.com/wiki/Manuals/ASCII_
        Protocol_Manual#Warning_Flags
    """

    def __init__(self, reply_string):
        """
        Args:
            reply_string: A string in one of the formats described in
                Zaber's `Ascii Protocol Manual`_. It will be parsed by
                this constructor in order to populate the attributes of
                the new AsciiReply.

        Raises:
            ValueError: The string could not be parsed.

        .. _Ascii Protocol Manual: http://www.zaber.com/wiki/Manuals/AS
            CII_Protocol_Manual
        """
        reply_string = reply_string.strip("\r\n")

        if len(reply_string) < 5:
            raise ValueError("Reply string too short to be a valid reply.")

        # CHECK CHECKSUM
        # All message types could have a checksum.
        if reply_string[-3] == ':':
            self.checksum = reply_string[-2:]
            reply_string = reply_string[:-3]
            # Test checksum
            sum = 0
            for ch in reply_string[1:]:
                try: sum += ord(ch)
                except TypeError: sum += ch     # bytes() elements are ints.
            # Truncate to last byte and XOR + 1, as per the LRC.
            # Convert to HEX but keep only last 2 digits, left padded by 0's
            correct_checksum = "{:02X}".format(((sum & 0xFF) ^ 0xFF) + 1)[-2:]
            if self.checksum != correct_checksum:
                raise ValueError("Checksum incorrect. Found {:s}, expected "
                        "{:s}. Possible data corruption detected.".format(
                            self.checksum, correct_checksum))
        else: 
            self.checksum = None

        # SET ATTRIBUTES
        self.message_type = reply_string[0]

        # We iterate over the attributes so we can use next()
        # instead of hardcoding string indices.
        tokens = iter(reply_string[1:].split())

        try:
            # All replies have a device address & axis number.
            self.device_address = int(next(tokens))
            self.axis_number = int(next(tokens))

            # @ is the "Reply" type
            if reply_string[0] == '@':
                t = next(tokens)
                try:
                    self.message_id = int(t)
                    self.reply_flag = next(tokens)
                except ValueError:
                    self.message_id = None
                    self.reply_flag = t

                self.device_status = next(tokens)
                self.warning_flag = next(tokens)
                self.data = next(tokens)

            # # is the "Info" type
            elif reply_string[0] == '#':
                self.device_status = None
                self.warning_flag = None
                self.reply_flag = None
                try:
                    t = next(tokens)
                    try:
                        self.message_id = int(t)
                        self.data = next(tokens)
                    except StopIteration:
                        self.data = ''
                    except ValueError:
                        self.message_id = None
                        self.data = t
                except StopIteration:
                    self.message_id = None
                    self.data = ''

            # ! is the "Alert" type
            elif reply_string[0] == '!':
                self.message_id = None
                self.device_status = next(tokens)
                self.warning_flag = next(tokens)
                self.data = None
                self.reply_flag = None
                return  # Return early to leave the data field as None

            else:
                raise ValueError("Invalid response type: %c" % (reply_string[0],))

        except StopIteration:
            raise ValueError("Incomplete response: {}".format(reply_string))

        # Add any remaining tokens together as the data field.
        try:
            while True:
                self.data = self.data + ' ' + next(tokens)
        except StopIteration:
            pass

    def encode(self):
        """Encodes the AsciiReply's attributes back into a valid string
        resembling the string which would have created the AsciiReply.

        Returns:
            A string in the format described in Zaber's `Ascii Protocol
            Manual`_.

        .. _Ascii Protocol Manual: http://www.zaber.com/wiki/Manuals/AS
            CII_Protocol_Manual
        """
        if self.message_type == '@':
            retstr = "@{:02d} {:d} {:s} {:s} {:s} {:s}".format(
                    self.device_address, self.axis_number, self.reply_flag,
                    self.device_status, self.warning_flag, self.data) \
                    if self.message_id is None else \
                    "@{:02d} {:d} {:02d} {:s} {:s} {:s} {:s}".format(
                            self.device_address, self.axis_number,
                            self.message_id, self.reply_flag,
                            self.device_status, self.warning_flag, self.data)
        elif self.message_type == '#':
            retstr = "#{:02d} {:d} {:s}".format(self.device_address,
                    self.axis_number, self.data) \
                    if self.message_id is None else \
                    "#{:02d} {:d} {:02d} {:s}".format(
                            self.device_address, self.axis_number,
                            self.message_id, self.data)
        elif self.message_type == '!':
            retstr = "!{:02d} {:d} {:s} {:s}".format(self.device_address,
                    self.axis_number, self.device_status, self.warning_flag) \
                    if self.message_id is None else \
                    "!{:02d} {:d} {:s} {:s}".format(self.device_address,
                            self.axis_number, self.message_id, 
                            self.device_status, self.warning_flag)

        if self.checksum is not None:
            return "{:s}:{:s}\r\n".format(retstr, self.checksum)
        else:
            return "{:s}\r\n".format(retstr)

    def __str__(self):
        """Returns a reply string resembling the string which would have
        created this AsciiReply.

        Returns:
            The same string as is returned by encode().
        """
        return self.encode()

class AsciiSerial(object):
    """A class for interacting with Zaber devices using the ASCII protocol.

    Attributes:
        baudrate: An integer representing the desired communication
            baud rate. Valid bauds are 115200, 57600, 38400, 19200, and
            9600.
        timeout: A number representing the number of seconds to wait
            for input before timing out. Floating-point numbers can be
            used to specify times shorter than one second. A value of
            None can also be used to specify an infinite timeout. A
            value of 0 specifies that all reads and writes should be 
            non-blocking (return immediately without waiting). Defaults
            to 5.
    """
    def __init__(self, port, baud = 115200, timeout = 5, inter_char_timeout = 0.01):
        """
        Args:
            port: A string containing the name or URL of the serial port to
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
            When *port* is not None, this constructor immediately
            opens the serial port. There is no need to call open()
            after creating this object, unless you passed None as
            *port*.

        Raises:
            ValueError: An invalid baud rate was specified.
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
            self._ser = serial.Serial(port, baud, timeout = timeout, interCharTimeout=inter_char_timeout)

    def write(self, command):
        """Writes a command to the serial port.

        Args:
            command: A string or AsciiCommand representing a command
                to be sent.
        """
        if isinstance(command, (str, bytes)):
            command = AsciiCommand(command)
        if not isinstance(command, AsciiCommand):
            raise TypeError("write must be passed a string or AsciiCommand.")
        logger.debug("> %s", command)

        # From "Porting Python 2 Code to Python 3":
        # "...when you receive text in binary data, you should
        # immediately decode it. And if your code needs to send text as
        # binary data then encode it as late as possible.
        # This allows your code to work with only [unicode] text
        # internally and thus eliminates having to keep track of what
        # type of data you are working with."
        # See https://docs.python.org/3/howto/pyporting.html#text-versu
        # s-binary-data
        self._ser.write(command.encode())

    def read(self):
        """Reads a reply from the serial port.

        Raises:
            zaber.serial.TimeoutError: The duration specified by *timeout* 
                elapsed before a full reply could be read.
            ValueError: The reply read could not be parsed and is
                invalid.

        Returns:
            An `AsciiReply` containing the reply received.
        """
        line = self._ser.readline()
        if not line:
            logger.debug("< Receive timeout!")
            raise TimeoutError("read timed out.")
        decoded_line = line.decode()
        logger.debug("< %s", decoded_line.rstrip("\r\n"))
        return AsciiReply(decoded_line)

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
        self.close()

    @property
    def timeout(self):
        return self._ser.timeout

    @timeout.setter
    def timeout(self, t):
        self._ser.timeout = t

    @property
    def baudrate(self):
        return self._ser.baudrate

    @baudrate.setter
    def baudrate(self, b):
        if b not in (115200, 57600, 38400, 19200, 9600):
            raise ValueError("Invalid baud rate: {:d}. Valid baud rates are "
                    "115200, 57600, 38400, 19200, and 9600.".format(b))
        self._ser.baudrate = b

