import usb.core
import usb.util
import time

class UsbDevice:
    def __init__(self, id_vendor, id_product):
        dev = usb.core.find(idVendor=id_vendor, idProduct=id_product)
        self._dev = dev
        if dev is None:
            raise ValueError('Device not found')

        # set the active configuration. With no arguments, the first
        # configuration will be the active one
        dev.set_configuration()

        # get an endpoint instance
        cfg = dev.get_active_configuration()
        intf = cfg[(0,0)]

        self._ep_out = usb.util.find_descriptor(
            intf,
            custom_match = \
            lambda e: \
                usb.util.endpoint_direction(e.bEndpointAddress) == \
                usb.util.ENDPOINT_OUT)

        self._ep_in = usb.util.find_descriptor(
            intf,
            custom_match = \
            lambda e: \
                usb.util.endpoint_direction(e.bEndpointAddress) == \
                usb.util.ENDPOINT_IN)

        assert self._ep_out is not None
        assert self._ep_in is not None

    def write(self, data):
        return self._dev.write(self._ep_out.bEndpointAddress, data)

    def read_raw(self):
        data_raw = self._dev.read(self._ep_in.bEndpointAddress, self._ep_in.wMaxPacketSize)
        return data_raw

    def read(self):
        data_raw = self.read_raw()
        data = ''.join([chr(d) for d in data_raw])
        return data

    def write_read(self, data):
        self.write(data)
        return self.read()

    def write_read_raw(self, data):
        self.write(data)
        return self.read_raw()
