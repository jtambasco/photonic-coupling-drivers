from . import laser as las
from ..agilent_lightwave_connection import AgilentLightWaveConnection
from ..utils import gnuplot as gp
import time
import struct
import numpy as np
from scipy import interpolate
import os
import serial as ser

class LaserAgilent8164B(AgilentLightWaveConnection, las.LaserTunable):
    '''
    Controls the laser module in the Agilent 8164B.

    Args:
        gpib_num (int): The GPIB bus number the laser is on.
        gpib_dev_num (int): The device number the laser in on
            the bus.
        power_unit (str): Either \'W\' or \'dBm\' depending on what
            units the Agilent 8164B should use for the laser power.
        output_mode (str):
            'HIGH' -> The High Power output is regulated.
            'LOWS' -> The Low SSE output is regulated.
            'BHR' -> Both outputs are active but only the High Power output is Regulated.
            'BLR' -> Both outputs are active but only the Low SSE output is Regulated.
    '''
    def __init__(self, serial_port=None, gpib_num=None, gpib_dev_num=None, power_unit='W',
                 output_mode='high'):
        super().__init__(serial_port, gpib_num, gpib_dev_num)
        self._power_unit = self.set_unit(power_unit)
        self._set_output_mode(output_mode)

    def turn_on(self):
        # Turn laser on.
        self._write('outp1')
        # Open output shutter.
        self._write('sour0:pow:stat 1')
        return self.get_on_or_off()

    def turn_off(self):
        # Turn laser off.
        self._write('outp0')
        # Open output shutter.
        self._write('sour0:pow:stat 0')
        return self.get_on_or_off()

    def get_on_or_off(self):
        on_off = self._query('sour0:pow:stat?')
        return bool(int(on_off))

    def set_power_W(self, power_W):
        assert power_W < 5.e-3, 'Can\'t set power that high.'
        if self._power_unit == 'dBm':
            power_dbm = LaserAgilent8164B.watts_to_dbm(power_W)
            cmd = 'sour0:pow %fdbm' % power_dbm
        elif self._power_unit == 'W':
            cmd = 'sour0:pow %fw' % power_W
        self._write(cmd)
        return self.get_power_W()

    def get_power_W(self):
        inString = 'sour0:pow?'
        data = self._query(inString)
        return float(data)

    def set_wavelength_m(self, wavelength_m):
        cmd = 'sour0:wav %sM' % wavelength_m
        self._write(cmd)
        r = self.get_wavelength_m()
        return r

    def get_wavelength_m(self):
        cmd = 'sour0:wav?'
        r = float(self._query(cmd))
        return r

    def set_unit(self, unit):
        '''
        Sets the units the laser should operate in.

        This will affect in what units the laser power
        is displayed on the screen.

        Args:
            unit (str): Either \'dBm\' or \'W\'.

        Returns:
            str: The units the laser is oeprating in.
        '''
        assert unit.lower() in ('dbm', 'w')
        cmd = 'sour0:pow:unit %s' % unit
        self._write(cmd)
        self._power_unit = self.get_unit()
        return self._power_unit

    def get_unit(self):
        '''
        Gets the units the laser is operating in.

        The units affect in what units the laser power
        is displayed on the screen.

        Returns:
            str: The units the laser is oeprating in.
        '''
        inString = 'sour0:pow:unit?'
        data = self._query(inString)
        unit = int(data)
        if unit == 0:
            unit_str = 'dBm'
        else:
            unit_str = 'W'
        return unit_str

    def last_operation_completed(self):
        return self._query('*OPC?')

    def wait_for_last_operation_completed(self):
        finish = False
        while not finish:
            finish = self.last_operation_completed()
        return finish

    def _get_output_mode(self):
        m = self._query('outp0:path?')
        return m

    def _set_output_mode(self, mode):
        '''
        Sets the mode the power meter will operate in.

        Args:
            mode (str):
                HIGH -> The High Power output is regulated.
                LOWS -> The Low SSE output is regulated.
                BHR -> Both outputs are active but only the High Power output is Regulated.
                BLR -> Both outputs are active but only the Low SSE output is Regulated.

        Returns:
            str: The mode the laser is operating in.
        '''
        m = mode.lower()
        assert m in ('high', 'lows', 'bhr', 'blr')
        self._write('outp0:path %s' % m)
        return self._get_output_mode()

    def get_velocity_nm_s(self):
        return float(self._query('sour0:wav:swe:spe?'))

    def set_velocity_nm_s(self, velocity):
        assert float(sweep_speed_nm_per_sec) in (0.5, 1., 2., 5., 10., 20., 40., 80.), \
            'Invalid sweep speed choice; laser only supports certain sweep speeds nm/s.'
        self._write('sour0:wav:swe:spe %fnm/s' % sweep_speed_nm_per_sec)
        return self.get_velocity_nm_s()

    def wavelength_sweep(self,
                         start_wavelength_nm,
                         stop_wavelength_nm,
                         step_wavelength_nm,
                         max_power_W,
                         sweep_speed_nm_per_sec=5.,
                         filename=None):

        assert step_wavelength_nm >= 0.6e-3, '`step_wavelength_nm` to small.'

        laser_power_temp_W = self.get_power_W()
        laser_wavelength_temp_m = self.get_wavelength_m()
        power_meter_wavelength_temp_m = float(self._query('sens1:pow:wav?'))
        self._write('*RST')

        max_power_dbm = LaserAgilent8164B.watts_to_dbm(max_power_W)

        # Setup lasers and triggers.
        self._write('trig:conf loop')
        self._write('sour0:pow:stat 1')
        self._query('sour0:pow:stat?')
        self._write('trig0:outp stf')
        self._write('trig0:inp sws')
        self._write('sour0:wav:swe:star %fnm' % start_wavelength_nm)
        self._write('sour0:wav:swe:stop %fnm' % stop_wavelength_nm)
        self._write('sour0:wav:swe:step %fnm' % step_wavelength_nm)
        self.set_velocity_nm_s(sweep_speed_nm_per_sec)
        self._write('sour0:wav:swe:mode cont')
        self._write('sour0:wav:swe:llog 1')

        param_check = self._query('sour0:wav:swe:chec?').strip()
        if param_check != '0,OK':
            raise RuntimeError('Invalid sweep parameters: `%s`.' % param_check)

        max_selectable_power_W = float(self._query('sour0:wav:swe:pmax? %fnm,%fnm' %
                                                  (start_wavelength_nm, stop_wavelength_nm)))
        if max_power_W > max_selectable_power_W:
            raise RuntimeError('Invalid `max_power` choice.')
        self._write('sour0:pow %fW' % max_power_W)

        # This command doesn't work for our laser module: int(self._query('sour0:wav:swe:exp?'))
        # so it must be manually calculated.
        expected_triggers = int(self._query('sour0:wav:swe:exp?'))
        self._write('sour0:wav:swe 1')

        # Setup power meter.
        self._write('trig1:inp sme')
        self._write('sens1:pow:unit 1')
        self._write('sens1:pow:rang:auto 0')
        self._write('sens1:pow:rang %fdbm' % max_power_dbm)
        self._query('sens1:pow:rang?')
        centre_wavelength_nm = 0.5*(start_wavelength_nm+stop_wavelength_nm)
        self._write('sens1:pow:wav %fnm' % centre_wavelength_nm)

        averaging_time_msec = 1.
        self._write('sens1:func:par:logg %i,10us' % expected_triggers)

        # Set to one trigger per measurment.
        self._write('sens1:func:stat logg,star')

        finished = False
        while not finished:
            flag = int(self._query('source0:wav:sweep:flag?').strip())
            finished = bool(flag)

        self._write('sour0:wav:swe:soft')

        # Wait for log to complete.
        while self._query('sour0:wav:sweep:state?').strip() != '+0':
            time.sleep(0.1)

        # Version from manual.  Doesn't work.
        #while self._query('sens1:func:stat?').strip() != 'LOGGING_STABILITY,COMPLETE':
        #    self._query('sens1:func:stat?')
        #    time.sleep(50.e-3)

        # Get logged data.
        self._write('sens1:func:res?')
        r = self._read(2)
        assert r[0] == '#', 'A \'#\' should have been read first.'
        size_of_num_bytes = int(r[1])
        num_bytes = int(self._read(size_of_num_bytes))
        data = self._read_raw(num_bytes)
        _ = self._read(1) # Read the remaining '\n' character.
        data = [data[i:i+4] for i in range(0, len(data), 4)]
        powers = [struct.unpack('f', d)[0] for d in data]

        while int(self._query('sour0:wav:swe:flag?')) not in (flag+1, flag+2):
            time.sleep(50.e-3)

        self._write('sour0:read:data? llog')
        r = self._read(2)
        assert r[0] == '#', 'A \'#\' should have been read first.'
        size_of_num_bytes = int(r[1])
        num_bytes = int(self._read(size_of_num_bytes))
        data = self._read_raw(num_bytes)
        _ = self._read(1) # Read the remaining '\n' character.
        data = [data[i:i+8] for i in range(0, len(data), 8)]
        wavelengths = [struct.unpack('d', d)[0] for d in data]

        # Wait for sweep to finish incase it's still running.
        while int(self._query('sour0:wav:swe?')) != 0:
            time.sleep(50.e-3)

        self._write('*RST')
        self.set_power_W(laser_power_temp_W)
        self.set_wavelength_m(laser_wavelength_temp_m)
        self._write('sens1:pow:wav %em' % power_meter_wavelength_temp_m)

        # Save data to file if necessary.
        try:
            with open(filename, 'w') as fs:
                for w, p in zip(wavelengths, powers):
                    fs.write('%e,%e\n' % (w, p))
            script_dir = os.path.dirname(os.path.abspath(__file__))
            gp.Gnuplot(script_dir+'/agilent_laser_sweep.gpi', {'filename':filename})
        except TypeError:
            pass

        return wavelengths, powers

    def wavelength_sweep_interp(self,
                                start_wavelength_nm,
                                stop_wavelength_nm,
                                step_wavelength_nm,
                                max_power_W,
                                sweep_speed_nm_per_sec=5.,
                                filename=None):
        wavelengths, powers = self.wavelength_sweep(start_wavelength_nm,
                                                    stop_wavelength_nm,
                                                    step_wavelength_nm,
                                                    max_power_W,
                                                    sweep_speed_nm_per_sec,
                                                    filename)
        powers_interp = interpolate.interp1d(wavelengths, powers)
        return powers_interp
