import abc
import math
import numpy as np
from scipy import interpolate
from tqdm import tqdm
import time

class Laser(object, metaclass=abc.ABCMeta):
    '''
    Abstract base interface class for lasers.

    All laser drivers should derive from this class
    and call `super.__init__(...)` in their constructor.
    '''
    @abc.abstractmethod
    def turn_on(self):
        '''Turns the laser on.

        Returns:
            bool: `True` if the laser is on, `False` if the laser is off.
                (Should be `True`.)
        '''
        pass

    @abc.abstractmethod
    def turn_off(self):
        '''Turns the laser off.

        Returns:
            bool: `True` if the laser is off, `False` if the laser is on.
                (Should be `False`.)
        '''
        pass

    @abc.abstractmethod
    def get_on_or_off(self):
        '''Checks if the laser is on or off.

        Returns:
            bool: `True` if the laser is off, `False` if the laser is on.
        '''
        pass

    @abc.abstractmethod
    def set_power_W(self, power_W):
        '''Sets the power of the laser in [W].

        Args:
            power_W (int, float): power in [W] to set the laser to.

        Returns:
            float: The power of the laser.
        '''
        pass

    @abc.abstractmethod
    def get_power_W(self):
        '''Gets the power of the laser in [W].

        Returns:
            float: The power of the laser in [W].
        '''
        pass

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
        power_dbm = 10.*math.log10(power_W/1.e-3)
        return power_dbm

    def set_power_mW(self, power_mW):
        return self.set_power_W(power_mW * 1.e-3) * 1.e3

    def set_power_uW(self, power_uW):
        return self.set_power_W(power_uW * 1.e-6) * 1.e6

    def set_power_dbm(self, power_dbm):
        power_W = self.dbm_to_watts(power_dbm)
        return self.set_power_W(power_W)

    def get_power_mW(self):
        return self.get_power_W()* 1.e3

    def get_power_uW(self):
        return self.get_power_W() * 1.e6

    def get_power_nW(self):
        return self.get_power_W() * 1.e9

    def get_power_pW(self):
        return self.get_power_W() * 1.e12

    def get_power_dbm(self):
        return self.watts_to_dbm(self.get_power_W())


class LaserTunable(Laser, metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def set_wavelength_m(self, wavelength_m):
        '''Sets the wavelength in [m] of the laser.

        Args:
            wavelength_m (int, float): The wavelength in metres to
                set the laser to.

        Returns:
            float: The wavelength in metres the laser was set to.
        '''
        pass

    @abc.abstractmethod
    def get_wavelength_m(self):
        '''Gets the wavelength in [m] of the laser.

        Returns:
            float: The wavelength in metres the laser is set to.
        '''
        pass

    @abc.abstractmethod
    def get_velocity_nm_s(self):
        pass

    @abc.abstractmethod
    def set_velocity_nm_s(self, velocity):
        pass

    def set_wavelength_um(self, wavelength):
        return self.set_wavelength_m(wavelength * 1.e-3) * 1.e3

    def set_wavelength_um(self, wavelength):
        return self.set_wavelength_m(wavelength * 1.e-6) * 1.e6

    def set_wavelength_nm(self, wavelength):
        return self.set_wavelength_m(wavelength * 1.e-9) * 1.e9

    def get_wavelength_mm(self):
        return self.get_wavelength_m() * 1.e3

    def get_wavelength_um(self):
        return self.get_wavelength_m() * 1.e6

    def get_wavelength_nm(self):
        return self.get_wavelength_m() * 1.e9

    def get_wavelength_power_scan_manual(self, start_wavelength_nm, stop_wavelength_nm,
                                         step_wavelength_nm, power_meters=None,
                                         delay_wavelength_changes_s=1., filename=None):
        '''
        Performs a wavelength sweep.

        Manually changes the laser power and the measures.  Does not use the in-built sweep
        function like Thach's sweep does.

        Args:
            start_wavelength_nm (int, float): The minimum wavelength value to start the sweep.
            stop_wavelength_nm (int, float): The maximum wavelength value to stop the sweep.
            step_wavelength_nm (int, float): The wavelength stepsize.
            power_meters (PowerMeter,list,None): The constructed power meter object that should be
                read as the wavelength is swept.  If a list of `PowerMeter` is given, all power meters
                in the list will be read.  `None` if no power meter should be read.
            power_meter_units (str): 'W' if the power should be read and returned in Watts, or
                'dBm' if the power should be read and returned in 'dBm'.
            delay_wavelength_changes_s (int, float): The delay in seconds between laser wavelength
                changes.
            filename (None,str): The name of the file to save the wavelength and power data
                to.  The data is not saved to a file if `None`.

        Returns:
            list: The first item is a float list of the wavelengths swept.  Subsequent
                items in the list are power meter readings given in the same order as in
                `power_meters.`
        '''

        if filename:
            fs = open(filename, 'w')

        # Wavelengths to measure.
        wavelengths_nm = np.arange(start_wavelength_nm, stop_wavelength_nm, step_wavelength_nm)

        # Convert parameters of power_meters.
        try:
            power_meters.__iter__
        except AttributeError:
            power_meters = [power_meters]

        # Store initial settings.
        laser_wavelength_m = self.get_wavelength_m()
        power_meter_wavelength_m = [pm.get_wavelength_m() for pm in power_meters]

        # Set power meters to average wavelength in scan.
        for pm in power_meters:
            pm.set_wavelength_nm(0.5*(start_wavelength_nm+stop_wavelength_nm))

        # Turn laser on.
        self.turn_on()

        # Measure powers.
        p_store = []
        progress_bar = tqdm(wavelengths_nm)
        for w in progress_bar:
            self.set_wavelength_nm(w)
            time.sleep(delay_wavelength_changes_s)
            p = [pm.get_power_nW() for pm in power_meters]
            p_store.append(p)

            if filename:
                w_p = [w]
                w_p.extend(p)
                s = ','.join([str(v) for v in w_p])
                fs.write(s+'\n')

            progress_bar.set_description('Power: %0.3e' % p[0])

        # Turn laser off.
        self.turn_off()

        # Organise wavelengths and powers.
        p_store_T = zip(*p_store)
        r = [wavelengths_nm]
        r.extend(p_store_T)

        if filename:
            fs.close()

        # Restore initial settings.
        self.set_wavelength_m(laser_wavelength_m)
        for pm, wl in zip(power_meters, power_meter_wavelength_m):
            pm.set_wavelength_nm(wl)

        return r

    def wavelength_sweep_manual_interp(self,
                                       start_wavelength_nm,
                                       stop_wavelength_nm,
                                       step_wavelength_nm,
                                       power_meters,
                                       delay_wavelength_changes_s=1.,
                                       filename=None):
        wavelengths, powers = self.get_wavelength_power_scan_manual(
                                                    start_wavelength_nm,
                                                    stop_wavelength_nm,
                                                    step_wavelength_nm,
                                                    power_meters,
                                                    delay_wavelength_changes_s=1.,
                                                    filename=None)
        powers_interp = interpolate.interp1d(wavelengths, powers)
        return powers_interp
