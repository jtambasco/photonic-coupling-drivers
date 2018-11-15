from . import power_meter as pm
from ..usb_usbtmc_info import usbtmc_from_serial
import os

class _Usbtmc(object):
    '''
    Basic read/write interface to USBTMC _devices.

    The PM100USB is USBTMC complant, so this class
    allows low level communication to it.

    Args:
        usbtmc_dev_number (int): USBTMC device number the
            power meter is.
    '''
    def __init__(self, usbtmc_dev_number):
        usbtmc = '/dev/usbtmc' + str(usbtmc_dev_number)
        self._dev = os.open(usbtmc, os.O_RDWR)

    def write(self, command):
        '''
        Send a string to the USBTMC device.

        Args:
            command (str): String to send.
        '''
        os.write(self._dev, str.encode(command))

    def read(self, number_of_characters=16):
        '''
        Read a string from the USBTMC device.

        Args:
            number_of_characters (int): Maximum number of
                characters to read.

        Returns:
            str: Response from the USBTMC device.
        '''
        resp = os.read(self._dev, number_of_characters)
        return resp

    def ask(self, command, number_of_characters=16):
        '''
        Write to, and then read from the USBTMC device.

        Args:
            command (str): String to send.
            number_of_characters (int): Maximum number of
                characters to read.

        Returns:
            str: Response from the USBTMC device.
        '''
        self.write(command)
        resp = self.read(number_of_characters)
        return resp

class Pm100Usb(_Usbtmc, pm.PowerMeter):
    '''
    Driver for the PM100USB allowing the power of the
    power meter to be read, and its wavelength to be
    set.

    Args:
        serial_number (str): Serial number listed on the PM100.
        wavelength (int, float): The wavelength the PM100
            should be calibrated to read.  If `None`, leaves
            the PM100\'s set wavelength unchanged.
    '''
    def __init__(self, serial_number, wavelength_m=None):
        usbtmc_dev_number = usbtmc_from_serial(serial_number)
        assert usbtmc_dev_number, ('Could not find USBTMC device.'
            '  Perhaps incorrect serial number provided.')
        super().__init__(usbtmc_dev_number[6:])
        if wavelength_m:
            self.set_wavelength_m(wavelength_m)

        self._min_analogue_voltage_V = 0.
        self._max_analogue_voltage_V = 2.

    def _get_power_W(self):
        resp = self.ask('MEAS:POW?')
        return float(resp)

    def set_wavelength_m(self, wavelength_m):
        assert 300.e-9 < wavelength_m < 3000.e-9, \
            'Wavelength is probably not in range.'
        wavelength_um = wavelength_m*1.e9
        self.write('SENS:CORR:WAV %f' % wavelength_um)
        return self.get_wavelength_m()

    def get_wavelength_m(self):
        resp = self.ask('SENS:CORR:WAV?')
        return float(resp)

    def get_autorange_on_off(self):
        resp = self.ask('POW:RANG:AUTO?')
        return bool(int(resp))

    def _set_autorange(self, on_off):
        self.write('POW:RANG:AUTO %i' % on_off)
        return self.get_autorange_on_off()

    def set_autorange_on(self):
        return self._set_autorange(True)

    def set_autorange_off(self):
        return self._set_autorange(False)

    def get_min_range_W(self):
        r = self.ask('POW:RANG? MIN')
        r = float(r.strip())
        return r

    def get_max_range_W(self):
        r = self.ask('POW:RANG?')
        r = float(r.strip())
        return r

    def get_min_range_A(self):
        r = self.ask('CURR:RANG? MIN')
        r = float(r.strip())
        return r

    def get_max_range_A(self):
        r = self.ask('CURR:RANG? MAX')
        r = float(r.strip())
        return r

    #def convert_current_A_to_power_W(self, analogue_voltage_V):
    #    pow_min = self.get_min_range_W()
    #    pow_max = self.get_max_range_W()

    #    m = (pow_max - pow_min) / 2.
    #    c = pow_min

    #    pow_W = m*analogue_voltage_V + c

    #    return pow_W

    def get_analogue_current_A(self, analogue_voltage_V):
        curr_min = self.get_min_range_A()
        curr_max = self.get_max_range_A()

        m = (curr_max - curr_min) / (self._max_analogue_voltage_V - \
                                     self._min_analogue_voltage_V)
        c = curr_min

        curr_A = m*analogue_voltage_V + c

        return curr_A

    def get_responsivity_A_W(self):
        return float(self.ask('CORR:POW:RESP?'))
