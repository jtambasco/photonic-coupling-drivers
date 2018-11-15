import abc
import time
import math

class PowerMeter(object, metaclass=abc.ABCMeta):
    '''
    Abstract base interface class for power meters.

    All power meter drivers should derive from this class
    and call `super.__init__(...)` in their constructor.
    '''
    def __init__(self):
        pass

    @abc.abstractmethod
    def get_analogue_current_A(self, analogue_voltage_V):
        '''
        Get the detector photocurrent [A].  This should be directly
        propertional to the detector analogue voltage [V] output.

        Args:
            analogue_voltage_V (float, np.array): Analogue voltage [V]
                representing the current.

        Returns:
            float, np.array: Analogue current [A] corresponding to
            the given analogue voltage [V].
        '''
        pass

    @abc.abstractmethod
    def get_responsivity_A_W(self):
        '''
        Returns the responsivity [A/W] of the detector.

        Returns:
            float: Responsivity [A/W] of the detector.
        '''
        pass

    @abc.abstractmethod
    def _get_power_W(self):
        '''
        Read the power meter.

        This function is not to be called.  One should prefer
        the not underscored getter functions which allow for
        averaging.

        Returns:
            float: The power in [W].
        '''
        pass

    @abc.abstractmethod
    def get_wavelength_m(self, wavelength_m):
        '''
        Gets the wavelength the power meter is set to read.

        Returns:
            float: The wavelength in [m] the power meter
            is operating in.
        '''
        pass

    @abc.abstractmethod
    def set_wavelength_m(self, wavelength_m):
        '''
        Sets the wavelength the power meter is set to read.

        Args:
            wavelength_m (int, float): The wavelength in
                [m] to set the power meter to.

        Returns:
            float: The wavelength the power meter is operating
                in.
        '''
        pass

    def set_wavelength_um(self, wavelength_um):
        return self.set_wavelength_m(wavelength_um * 1.e-6)

    def set_wavelength_nm(self, wavelength_nm):
        return self.set_wavelength_m(wavelength_nm * 1.e-9)

    def get_power_W(self, average=1, read_period_ms=250.):
        '''
        Read the power meter.

        Args:
            average (int): How many power readings should be
                averaged over before returning a power.
            read_period_ms (int, float): The time to wait between
                power readings.  Only makes sense if `average > 1`.

        Returns:
            float: The, perhaps averaged, power reading.
        '''
        powers = []
        if average > 1:
            for i in range(average):
                powers.append(self._get_power_W())
                time.sleep(read_period_ms / 1000.)
            avg_power = sum(powers) / float(len(powers))
        else:
            avg_power = self._get_power_W()
        return avg_power

    def get_power_mW(self, average=1, read_period_ms=None):
        return self.get_power_W(average, read_period_ms) * 1.e3

    def get_power_uW(self, average=1, read_period_ms=None):
        return self.get_power_W(average, read_period_ms) * 1.e6

    def get_power_nW(self, average=1, read_period_ms=None):
        return self.get_power_W(average, read_period_ms) * 1.e9

    def get_power_pW(self, average=1, read_period_ms=None):
        return self.get_power_W(average, read_period_ms) * 1.e12

    def get_power_dbm(self, average=1, read_period_ms=None):
        power_W = self.get_power_W()
        power_dBm = PowerMeter.watts_to_dbm(power_W)
        return power_dBm

    def get_wavelength_mm(self):
        return self.get_wavelength_m() * 1.e3

    def get_wavelength_um(self):
        return self.get_wavelength_m() * 1.e6

    def get_wavelength_nm(self):
        return self.get_wavelength_m() * 1.e9

    @staticmethod
    def dbm_to_watts(power_dbm):
        '''Converts [dBm] to [W].

        Args:
            power_dbm (int, float): Power in [dBm].

        Returns:
            float: Power in [W].
        '''
        power_W = 10.**(power_dbm/10.) / 1.e3
        return power_W

    @staticmethod
    def watts_to_dbm(power_W):
        '''Converts [W] to [dBm].

        Args:
            power_W (int, float): Power in [W].

        Returns:
            float: Power in [dBm].
        '''
        if power_W < 1.e-12:
            power_dbm = -1000.
        else:
            power_dbm = 10.*math.log10(power_W/1.e-3)
        return power_dbm

    def get_analogue_power_W(self, analogue_voltage_V):
        '''
        Calculates the power of the power meter based on the
        analogue voltage value read.  The analogue voltage
        should be directly related to the current.

        Args:
            analogue_voltage_V (float, np.array): Analogue voltage [V]
                representing the current.

        Returns:
            float, np.array: The power [W] corresponding to the
                given analogue voltage [V].
        '''
        curr_A = self.get_analogue_current_A(analogue_voltage_V)
        resp_A_W = self.get_responsivity_A_W()
        pow_W = curr_A / resp_A_W
        return pow_W
