import gpib
from . import laser as las
import time

class NewportVenturi(las.laser):
    def __init__(self, gpib_num, gpib_dev_num, units='mW'):
        self._dev = gpib.dev(gpib_num, gpib_dev_num)
        self.set_power_units(units)
        self._sleep = 0.1

    def _write(self, cmd):
        gpib.write(self._dev, cmd + '\r\n')
        time.sleep(self._sleep)

    def _read(self, num_bytes=100):
        data = gpib.read(self._dev, num_bytes)
        time.sleep(self._sleep)
        return data.decode('ascii')

    def _query(self, cmd, num_bytes=100):
        self._write(cmd)
        data = self._read(num_bytes)
        data = [d.strip() for d in data.split()[1:]]
        return data

    def get_power_W(self):
        power = float(self._query(':conf:tls:powe?')[0])
        if self._units == 'mW':
            power_W = power * 1.e-3
        elif self._units == 'dBm':
            power_W = las.laser.dbm_to_watts(power)
        return power_W

    def set_power_W(self, power_W):
        power_mW = power_W * 1.e3
        return float(self._query(':conf:tls:powe %.5f' % power_mW)[0])

    def get_on_or_off(self):
        on_off = self._query(':conf:tls:outp?')[0]
        return True if on_off == 'ON' else False

    def turn_on(self):
        return self._qurey(':conf:tls:outp on')[0]

    def turn_off(self):
        return self._query(':conf:tls:outp off')[0]

    def set_power_units(self, units):
        assert units in ('mW', 'dBm')
        units = self._query(':config:tls:unit %s' % units)[0]
        self._units = units
        return units

    def get_power_units(self):
        return self._query(':config:tls:unit?')[0]

    def get_wavelength_m(self):
        return float(self._query(':conf:tls:wave?')[0])

    def set_wavelength_m(self, wavelength_m):
        wavelength_nm = wavelength_m * 1.e9
        return float(self._query(':conf:tls:wave %.3f' \
                                 % wavelength_nm)[0])

    def start_sweep(self):
        self._query(':init')

    def get_sweep_start_wavelength_nm(self):
        return float(self._query(':conf:swee:start?')[1])

    def set_sweep_start_wavelength_nm(self, wavelength_nm):
        return float(self._query(':conf:swee:start %s %.3f'
                                 % (self._mode, wavelength_nm))[1])

    def get_sweep_stop_wavelength_nm(self):
        return float(self._query(':conf:swee:stop?')[1])

    def set_sweep_stop_wavelength_nm(self, wavelength_nm):
        return float(self._query(':conf:swee:stop %s %.3f' \
                                 % (self._mode, wavelength_nm))[1])

    def get_sweep_speed_nm_s(self):
        return float(self._query(':conf:swee:rate?')[0])

    def set_sweep_speed_nm_s(self, sweep_speed_nm_s):
        return float(self._query(':conf:swee:rate %.1f' % sweep_speed_nm_s)[0])

    def get_sweep_mode(self):
        return self._query(':conf:swee:mode?')[0]

    def set_sweep_mode(self, mode):
        mode = mode.lower()
        assert mode in ('cont', 'continuous', 'step', 'time')
        self._mode = mode
        return self._query(':conf:swee:mode %s' % mode)[0]

    def wait_command_complete(self):
        assert self._query('*opc?')[0] == '1/1'
        return True

    def set_num_sweeps(self, num_sweeps):
        '''
        Number of times to run the sweep when do
        sweep is run.  If `0`, the laser will
        run continuously.

        Args:
            num_sweeps(int): Number of times to run the sweep.
                0 for infinite repeats.

        Returns:
            int: Number of times the sweep will be run.
        '''
        num_sweeps = int(num_sweeps)
        assert 0 <= num_sweeps <= 10000
        return int(self._query(':conf:swee:coun %i' % num_sweeps)[0])

    def get_num_sweeps(self):
        return int(self._query(':conf:swee:coun?')[0])

    def sweep(self, start_wavelength_nm, stop_wavelength_nm,
              sweep_speed_nm_s, power_mW):
        self.set_sweep_start_wavelength_nm(start_wavelength_nm)
        self.set_sweep_stop_wavelength_nm(stop_wavelength_nm)
        self.set_sweep_speed_nm_s(sweep_speed_nm_s)
        self.set_power_mW(power_mW)
        self.start_sweep()
        return self.wait_command_complete()
