from . import power_meter as pm
from ..agilent_lightwave_connection import AgilentLightWaveConnection

class PowerMeterAgilent8164B(AgilentLightWaveConnection, pm.PowerMeter):
    '''
    Driver for the Agilent 8164B power meter module that
    can read power and set the wavelength as well as
    specify in what units the Agilent 8164B should operate
    in.

    Args:
        gpib_num (int): The number of the GPIB bus
            the power meter is sitting on.
        gpib_dev_num (int): The device number that
            the power meter is on the aforementioned bus.
        channel_num (int): Either `1` or `2` depending on
            which power metre channel to use.
        power_unit (str): Either \'W\' or \'dBm\' depending
            on whether the power units should be displayed
            in [W] or [dBm] on the Agielent 8164B\'s screen.
    '''
    def __init__(self, gpib_num, gpib_dev_num, channel_num, power_unit='W'):
        super().__init__(gpib_num, gpib_dev_num)
        self._channel_num = int(channel_num)
        self.set_unit(power_unit)
        self.set_auto_range()

    def _get_power_W(self):
        instr = 'fetc1:chan%i:pow?' % self._channel_num
        power = float(self._query(instr))
        if self._unit == 'dbm':
            power = pm.PowerMeter.dbm_to_watts(power)
        return power

    def set_wavelength_m(self, wavelength_m):
        cmd = 'sens1:chan' + str(self._channel_num) + ':pow:wav ' + str(wavelength_m) + 'm'
        self._write(cmd)
        r = self.get_wavelength_m()
        return r

    def get_wavelength_m(self):
        cmd = 'sens1:chan' + str(self._channel_num) + ':pow:wav?'
        wl_m_str = self._query(cmd)
        wl_m = float(wl_m_str)
        return wl_m

    def set_unit(self, unit):
        '''
        Sets the units the power meter will display on screen.

        Args:
            unit (str): Either \'W\' or \'dBm\' depending on
                whether the power units should be displayed in
                [W] or [dBm] on the Agielent 8164B\'s screen.

        Returns:
            str: The unit the power meter is set to display.
                Either \'W\' or \'dBm\'
        '''
        assert unit.lower() in ('dbm', 'w')
        cmd = 'sens1:chan' + str(self._channel_num) + ':pow:unit ' + unit
        self._write(cmd)
        r = self.get_unit()
        self._unit = unit.lower()
        return r

    def get_unit(self):
        '''
        Gets the units the power meter is set to display.

        Returns:
            str: The unit the power meter is set to display.
                Either \'W\' or \'dBm\'
        '''
        cmd = 'sens1:chan' + str(self._channel_num) + ':pow:unit?'
        data = self._query(cmd)
        unit =  int(data)
        if unit == 0:
            r = 'dBm'
        else:
            r = 'W'
        return r

    def get_averaging_time_s(self):
        cmd = 'sens1:chan' + str(self._channel_num) + ':pow:atim?'
        data = self._query(cmd)
        return data

    def set_averaging_time_s(self, averaging_time_s):
        cmd = 'sens1:chan' + str(self._channel_num) + ':pow:atim %fs' % averaging_time_s
        data = self._write(cmd)
        return self.get_averaging_time_s()

    def set_auto_range(self):
        '''
        Turns on auto-range.

        Returns:
            bool: `1` if auto-range is switched on and
                `0` if auto-range is switched off.
        '''
        self._write('sens1:pow:range:auto 1')
        r = self.get_auto_range()
        return r

    def unset_auto_range(self):
        '''
        Turns off auto-range.

        Returns:
            bool: `1` if auto-range is switched on and
                `0` if auto-range is switched off.
        '''
        self._write('sens1:pow:range:auto 0')
        r = self.get_auto_range()
        return r

    def get_power_meter_range(self):
        data = self.ask('sens1:chan' + str(self._channel_num) + ':pow:range?')
        return float(data)

    def set_power_meter_range(self, max_power_dbm):
        """Set the power meter range, range in dBm"""
        self._write('sens1:chan' + str(self._channel_num) + ':pow:range ' + \
                        str(max_power_dbm) + 'dbm')
        return self.get_power_meter_range()

    def get_auto_range(self):
        '''
        Checks what the auto-range is set to.

        Returns:
            bool: `1` if auto-range is switched on and
                `0` if auto-range is switched off.
        '''
        data = self._query('sens1:pow:range:auto?')
        r = bool(int(data))
        return r

