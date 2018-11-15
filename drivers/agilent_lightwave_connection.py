import gpib
import serial as ser

class AgilentLightWaveConnection():
    def __init__(self, serial_port=None, gpib_num=None, gpib_dev_num=None):
        assert serial_port or (gpib_num and gpib_dev_num)
        if gpib_num and gpib_dev_num:
            self._dev = gpib.dev(gpib_num, gpib_dev_num)
            self._gpib_used = True
        elif serial_port:
            self._dev = ser.Serial('/dev/'+serial_port, 38400)
            self._gpib_used = False

    def _write(self, cmd):
        if self._gpib_used:
            gpib.write(self._dev, cmd)
        else:
            self._dev.write(cmd.encode())

    def _read(self, num_bytes=100):
        if self._gpib_used:
            data = gpib.read(self._dev, num_bytes)
        else:
            data = self._dev.readline(num_bytes)
        return data.decode('ascii')

    def _read_raw(self, num_bytes=100):
        if self._gpib_used:
            data = gpib.read(self._dev, num_bytes)
        else:
            data = self._dev.read(num_bytes)
        return data

    def _query(self, cmd, num_bytes=100):
        self._write(cmd)
        data = self._read(num_bytes)
        return data

    def _query_raw(self, cmd, num_bytes=100):
        self._write(cmd)
        data = self._read_raw(num_bytes)
        return data
