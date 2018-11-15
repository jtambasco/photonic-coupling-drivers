"""The exceptions module contains special exceptions to be raised by
this library.
"""

class TimeoutError(Exception):
    """Raised when a read operation exceeded its specified time limit."""
    pass

class UnexpectedReplyError(Exception):
    """Raised when a reply was read from an unexpected device."""
    
    def __init__(self, message, reply = None):
        """
        Args:
            message: The error message to display.
            reply: The unexpected reply which caused this exception to
                be raised.

        Notes:
            This exception preserves the unexpected reply for which it
            was thrown. You can access it through the *reply* attribute.
        """
        super(UnexpectedReplyError, self).__init__(message)
        
        self.reply = reply

