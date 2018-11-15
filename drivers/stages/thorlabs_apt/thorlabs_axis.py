import time
from serial.tools.list_ports import comports
from .. import stage as st

import os
dir_path = os.path.dirname(os.path.realpath(__file__))
import sys
sys.path.append(dir_path)
from thorpy.comm.port import Port

# Stages print weird response if constructed
# in the class, so constructing them globally.
def create_stages(serial_number):
    serial_ports = [(x[0], x[1], dict(y.split('=', 1) for y in x[2].split(' ') if '=' in y)) for x in comports()]
    serial_numbers = [info['SER'] for _, _, info in serial_ports if 'SER' in info.keys()]

    if serial_number in serial_numbers:
        device = None
        for dev, _, info in serial_ports:
            if dev[:11] == '/dev/ttyUSB':
                try:
                    if info['SER'] == serial_number:
                        device = dev
                except KeyError:
                    pass

        p = Port.create(device, serial_number)
        axis = p.get_stages()[1]
    else:
        axis = None

    return axis

class ThorlabsAptAxis(st.Axis):
    def __init__(self, serial_number, reverse_axis=False, logger=None,
                 update_position_absolute=100):
        self.axis = create_stages(serial_number)
        assert self.axis, 'Invalid serial number.'
        super().__init__(reverse_axis, logger, update_position_absolute)

class ThorlabsAptAxisLinear(ThorlabsAptAxis, st.AxisLinear):
    def __init__(self, serial_number, velocity_mm_s=2.5, acceleration_mm_s_s=5,
                 reverse_axis=False, logger=None,
                 update_position_absolute=100):
        self.name = 'linear'
        super().__init__(serial_number, reverse_axis, logger,
                         update_position_absolute)

    def _move_abs_nm(self, distance_from_home_nm):
        self.axis.position = distance_from_home_nm / 1e6
        time.sleep(0.2)

        while self._in_motion():
            time.sleep(0.1)

        return self._get_current_position_nm()

    def _get_current_position_nm(self):
        return self.axis.position * 1e6

    def set_velocity_mm_s(self, velocity_mm_s):
        s.max_velocity = velocity_mm_s
        return self.get_velocity_mm_s()

    def get_velocity_mm_s(self):
        return s.max_velocity

    def set_acceleration_mm_s_s(self, acceleration_mm_s_s):
        s.acceleration = acceleration_mm_s_s
        return get_acceleration_mm_s_s()

    def get_acceleration_mm_s_s(self):
        return s.acceleration

    def home(self):
        self.axis.home()

    def _in_motion(self):
        in_motion = self.axis.status_in_motion_forward or \
                    self.axis.status_in_motion_reverse or \
                    self.axis.status_in_motion_jogging_forward or \
                    self.axis.status_in_motion_jogging_reverse or \
                    self.axis.status_in_motion_homing
        return in_motion

    @property
    def _position_absolute_min_nm(self):
        return 0.

    @property
    def _position_absolute_max_nm(self):
        return 25. * 1e6
