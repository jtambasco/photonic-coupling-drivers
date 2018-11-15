from .agilent_lightwave_connection import AgilentLightWaveConnection
from .lasers.agilent_8164B_laser import LaserAgilent8164B
from .power_meters.agilent_8164B_power_meter import PowerMeterAgilent8164B

class AgilentLightWaveSystem(AgilentLightWaveConnection):
    '''
    Driver for the Agilent Lightwave.
    Args:
        gpib_num (int): The number of the GPIB bus
            the power meter is sitting on.
        gpib_dev_num (int): The device number that
            the power meter is on the aforementioned bus.
        power_meter_channel_num (int): Either `1` or `2`
            depending on which power metre channel to use.
        output_mode (str):
            'HIGH' -> The High Power output is regulated.
            'LOWS' -> The Low SSE output is regulated.
            'BHR' -> Both outputs are active but only the
                High Power output is Regulated.
            'BLR' -> Both outputs are active but only the
                Low SSE output is Regulated.
        power_unit (str): Either \'W\' or \'dBm\' depending
            on whether the power units should be displayed
            in [W] or [dBm] on the Agielent 8164B\'s screen.
    '''
    def __init__(self, gpib_num, gpib_dev_num):
        super().__init__(gpib_num, gpib_dev_num)
        if not self.get_lock_status():
            self.set_unlock()

    def get_lock_status(self):
        lock_status = bool(int(self._query('lock?')))
        return lock_status

    def set_lock(self, password='1234'):
        assert len(password) == 4, 'Password should be 4 characters long.'
        self._write('lock 1,%s' % password)
        return self.get_lock_status()

    def set_unlock(self, password='1234'):
        assert len(password) == 4, 'Password should be 4 characters long.'
        self._write('lock 0,%s' % password)
        return self.get_lock_status()

    def get_modules_installed(self):
        return self._query('*OPT?').strip().replace(' ', '').split(',')

    def get_latest_error(self):
        return self._query('syst:err?')

    def clear_error_list(self):
        self._write('*CLS')
        return self.get_latest_error()

    def set_preset(self):
        self._write('*RST')

class AgilentLightWave():
    def __init__(self, gpib_num, gpib_dev_num, power_meter_channel_num='0',
                 laser_output_mode='high', power_unit='W'):

        self.system = AgilentLightWaveSystem(gpib_num, gpib_dev_num)
        self.system.set_preset()

        self.laser = LaserAgilent8164B(gpib_num,
                                       gpib_dev_num,
                                       power_unit,
                                       laser_output_mode)
        self.power_meter = PowerMeterAgilent8164B(gpib_num,
                                                  gpib_dev_num,
                                                  power_meter_channel_num,
                                                  power_unit)

