from .zaber import serial as zs
from . import tla_constants as tla
from .. import stage as st
import serial
import numpy as np
import time
import abc
import copy

def find_stages(num_com_ports_check=10, num_motors=6, restore_default_settings=False):
    ports_found = []
    com_port_numbers = [str(n) for n in range(num_com_ports_check)]
    for com_port_number in com_port_numbers:
        try:
            port = zs.BinarySerial('/dev/ttyUSB%s' % com_port_number)
            if restore_default_settings:
                tla.send_command(port, 0, 'Restore Settings', 0)
                for i in range(num_motors):
                    port.read()
                time.sleep(10.e-3)
            tla.send_command(port, 1, 'Return Device Id')
            r = port.read()
            if r.data == 1013:
                ports_found.append(com_port_number)

        except:
            pass
    return ports_found

class LuminosStages(st.Stages3):
    def __init__(self, com_port_number_input='luminos_input', com_port_number_output='luminos_output',
                 com_port_number_chip='luminos_chip', filename=None, C1_input=None, C2_input=None,
                 C1_output=None, C2_output=None, C1_z_chip=0., C2_z_chip=0., c1_c2_distance_mask_um=None,
                 input_x_axis_motor='x', input_y_axis_motor='y', input_z_axis_motor='z',
                 output_x_axis_motor='x', output_y_axis_motor='y', output_z_axis_motor='z',
                 chip_x_axis_motor='x', chip_y_axis_motor='y', chip_z_axis_motor='z',
                 ctr_in_out_xy_axes=False, update_position_absolute=100, restore_default_settings=False,
                 reverse_output_x_axis=True, home_input=False,
                 home_chip=False, home_output=False):
        self.pos_xyz_um_stack = []

        self.input  = LuminosStage(com_port_number_input, C1=C1_input, C2=C2_input,
                                   C1_z_chip=C1_z_chip, C2_z_chip=C2_z_chip,
                                   c1_c2_distance_mask_um=c1_c2_distance_mask_um,
                                   update_position_absolute=update_position_absolute,
                                   filename=filename, x_axis_motor=input_x_axis_motor,
                                   y_axis_motor=input_y_axis_motor, z_axis_motor=input_z_axis_motor,
                                   restore_default_settings=restore_default_settings,
                                   home=home_input)
        self.output = LuminosStage(com_port_number_output, C1=C1_output, C2=C2_output,
                                   C1_z_chip=C1_z_chip, C2_z_chip=C2_z_chip,
                                   c1_c2_distance_mask_um=c1_c2_distance_mask_um,
                                   update_position_absolute=update_position_absolute,
                                   filename=filename, x_axis_motor=output_x_axis_motor,
                                   y_axis_motor=output_y_axis_motor, z_axis_motor=output_z_axis_motor,
                                   reverse_axis_x=reverse_output_x_axis, restore_default_settings=restore_default_settings,
                                   home=home_output)
        self.chip   = LuminosStage(com_port_number_chip, filename=filename,
                                   update_position_absolute=update_position_absolute,
                                   x_axis_motor=chip_x_axis_motor, y_axis_motor=chip_y_axis_motor,
                                   z_axis_motor=chip_z_axis_motor,
                                   restore_default_settings=restore_default_settings,
                                   home=home_chip)

        stages_dict = {'input': self.input, 'output': self.output, 'chip': self.chip}
        super().__init__(stages_dict=stages_dict, filename=filename, ctr_in_out_xy_axes=ctr_in_out_xy_axes)

    def home(self):
        for stage in self.stages_dict.values():
            stage.home()

class LuminosStage(st.Stage):
    def __init__(self, com_port_number, C1=None, C2=None,
                 C1_z_chip=0., C2_z_chip=0., update_position_absolute=100,
                 c1_c2_distance_mask_um=None, calibrate_c_axis=False,
                 filename=None, reverse_axis_x=False,
                 x_axis_motor='x', y_axis_motor='y', z_axis_motor='z',
                 reverse_axis_y=False, reverse_axis_z=False,
                 restore_default_settings=False, home=False):

        self._com_port_number = com_port_number
        self._set_serial_connection(com_port_number)

        axes_idx, axes_dict = self._get_axes_dict(update_position_absolute=update_position_absolute,
                                                  reverse_axis_x=reverse_axis_x,
                                                  reverse_axis_y=reverse_axis_y,
                                                  reverse_axis_z=reverse_axis_z,
                                                  home=home)

        if restore_default_settings:
            self.set_default_settings()

        for axis in axes_dict.values():
            # Emprirically chosen 'slow' default speeds that seem to
            # give good movement.
            if axis.name == 'z':
                s = axis.set_speed(100)
            else:
                s = axis.set_speed(600)

            a = axis.set_acceleration(22)
            r = axis.set_microstep_resolution(128)

        super().__init__(axes_dict=axes_dict, C1=C1, C2=C2,
                         C1_z_chip=C1_z_chip, C2_z_chip=C2_z_chip,
                         c1_c2_distance_mask_um=c1_c2_distance_mask_um,
                         reverse_axis_x=reverse_axis_x,
                         reverse_axis_y=reverse_axis_y, reverse_axis_z=reverse_axis_z,
                         x_axis_motor=x_axis_motor, y_axis_motor=y_axis_motor,
                         z_axis_motor=z_axis_motor, filename=filename)

    def _get_axes_dict(self, update_position_absolute, reverse_axis_x, reverse_axis_y, reverse_axis_z, home):

        axes_idx = {'x': 2, 'y': 3, 'z': 1, 'roll': 4, 'yaw': 5, 'pitch': 6}

        axes_dict = {
            'x': LuminosAxisX(self._port, axes_idx['x'], reverse_axis_x,
                              update_position_absolute, home),
            'y': LuminosAxisY(self._port, axes_idx['y'], reverse_axis_y,
                              update_position_absolute, home),
            'z': LuminosAxisZ(self._port, axes_idx['z'], reverse_axis_z,
                              update_position_absolute, home),
            'roll': LuminosAxisRoll(self._port, axes_idx['roll'], False,
                                    update_position_absolute, home),
            'pitch': LuminosAxisPitch(self._port, axes_idx['pitch'], False,
                                      update_position_absolute, home),
            'yaw': LuminosAxisYaw(self._port, axes_idx['yaw'], False,
                                  update_position_absolute, home),
        }

        return axes_idx, axes_dict

    def _set_serial_connection(self, com_port_number):
        try:
            int(com_port_number)
            com_port = '/dev/ttyUSB%i' % int(com_port_number)
        except ValueError:
            com_port = '/dev/%s' % com_port_number
            self._port = zs.BinarySerial(com_port, timeout=20)
        return self._port

    def set_default_settings(self):
        return self._send_command('Restore Settings', 0)

    def set_manual_mode(self):
        del self._port
        self._port = None
        return self._port

    def set_computer_mode(self):
        self._set_serial_connection(self._com_port_number)
        for axis_label, axis in self.axes.items():
            if axis_label in ('x', 'y', 'z'):
                axis._position_absolute = axis.get_current_position_nm()
                if axis.axis_reversed == True:
                    axis._position_absolute = axis._position_absolute_max_nm - axis._position_absolute
            elif axis_label in ('roll', 'yaw', 'pitch'):
                axis._position_absolute = axis.get_current_position_arc_second()
        return self._port

    def _binary_command(self, command_name, command_data=None):
        bc = tla.binary_command(0, command_name, command_data)
        return bc

    def _write_data_to_non_volatile(self, byte_offset, byte_data, device_index):
        assert 0 <= byte_offset <= 127, 'Address to read must be from 0 to 127.'
        byte3  = 1 << 7 | byte_offset
        byte4  = byte_data
        cd = byte3 | byte4 << 8
        tla.send_command(self._port, device_index, 'Read Or Write Memory', cd)
        if device_index == 0:
            data = [self._port.read().data >> 8 for i, _ in enumerate(self.axes_physical)]
        else:
            data = self._port.read().data >> 8
        return data

    def _read_data_from_non_volatile(self, byte_offset, device_index):
        assert 0 <= byte_offset <= 127, 'Address to read must be from 0 to 127.'
        cd = byte_offset
        tla.send_command(self._port, device_index, 'Read Or Write Memory', cd)
        if device_index == 0:
            r = [self._port.read() for i, _ in enumerate(self.axes_physical)]
            data_byte = [v.data >> 8 for v in r]
        else:
            r = self._port.read()
            data_byte = r.data >> 8
        return data_byte

    def _send_command(self, command_name, command_data=None):
        tla.send_command(self._port, 0, command_name, command_data)
        r = [eval(self._port.read().__str__()) for _ in self.axes_physical]
        return r

    def home(self):
        r = self._send_command('Home')
        for axis in self.axes_physical.values():
            axis._position_absolute = 0.
        return r

    def flash_leds(self, num_flashes=5, delay_flashes_sec=1.):
        on = True
        for i in range(num_flashes):
            for axis in self.axes_physical.values():
                if on:
                    axis.turn_leds_off()
                    on = False
                else:
                    axis.turn_leds_on()
                    on = True
            time.sleep(delay_flashes_sec)
            for axis in self.axes_physical:
                axis.turn_leds_on()

class LuminosAxis(st.Axis, zs.BinaryDevice):
    def __init__(self, port, device_index, reverse_axis=False, update_position_absolute=100,
                 home=False, config_mask_set=0x08A0, config_mask_unset=0xC35F):
        assert 0 < device_index < 20, 'The suggested motor ID is probably wrong.'

        self.device_index = device_index
        self._port = port

        zs.BinaryDevice.__init__(self, port, device_index)
        super().__init__(reverse_axis, update_position_absolute=update_position_absolute)

        if home:
            self.home()

        # Get current device mode.
        current_status_word = self._get_device_mode()

        ## Check if stages need to be homed.
        #if not current_status_word & 1<<7:
        #    raise RuntimeError('Axis needs to be homed.')

        # Check correct status bits set: Set Device Mode - Cmd 40
        # Mask for target setting.
        target_mask_set = config_mask_set
        target_mask_unset = config_mask_unset ^ 0xFFFF

        # Combine
        target_status_word = current_status_word | target_mask_set
        target_status_word &= target_mask_unset

        # If status word is incorrect, rewrite it.
        if current_status_word != target_status_word:
            self._set_device_mode(target_status_word)

    def move_rel(self):
        raise AttributeError('Don\'t call this function.')

    def move_abs(self):
        raise AttributeError('Don\'t call this function.')

    def _binary_command(self, command_name, command_data):
        bc = tla.binary_command(self.device_index, command_name, command_data)
        return bc

    def _send_command(self, command_name, command_data=None):
        tla.send_command(self._port, self.device_index, command_name, command_data)
        r = self._port.read()
        return r

    def _move_abs_steps(self, steps):
        r = self._send_command('Move Absolute', steps)
        return r

    def _get_device_mode(self):
        device_mode = self._send_command('Return Setting', 40).data
        return device_mode

    def _set_device_mode(self, device_mode):
        device_mode = self._send_command('Set Device Mode', device_mode)
        return device_mode.data

    def _set_device_mode_bit(self, bit_number):
        dm = self._get_device_mode()
        dm |= 1 << bit_number
        self._set_device_mode(dm)
        return dm

    def _unset_device_mode_bit(self, bit_number):
        dm = self._get_device_mode()
        dm &= 0 << bit_number
        self._set_device_mode(dm)
        return dm

    def get_device_mode_bit_status(self, bit_number):
        dm = self._get_device_mode()
        b = True if dm & 1 << bit_number else False
        return b

    def turn_leds_off(self):
        dm1 = self._set_device_mode_bit(14) # 14 -> Power LED
        dm2 = self._set_device_mode_bit(15) # 15 -> Serial LED
        return dm2

    def turn_leds_on(self):
        dm1 = self._unset_device_mode_bit(14) # 14 -> Power LED
        dm2 = self._unset_device_mode_bit(15) # 15 -> Serial LED
        return dm2

    def enable_motor_knob(self):
        return self._unset_device_mode_bit(3) # 3 -> Motor knob

    def disable_motor_knob(self):
        return self._set_device_mode_bit(3) # 3 -> Motor knob

    def enable_manual_move_reply(self):
        return self._unset_device_mode_bit(5) # 5 -> Manual move tracking

    def disable_manual_move_reply(self):
        return self._set_device_mode_bit(5) # 5 -> Manual move tracking

    def enable_circular_phase_microstepping(self):
        return self._set_device_mode_bit(11)

    def disable_circular_phase_microstepping(self):
        return self._unset_device_mode_bit(11)

    def enable_anti_backlash_routine(self):
        return self._set_device_mode_bit(1) # 1 -> Anti-backlash routine.

    def disable_anti_backlash_routine(self):
        return self._unset_device_mode_bit(1) # 1 -> Anti-backlash routine.

    def enable_anti_sticktion_routine(self):
        return self._set_device_mode_bit(2) # 2 -> Anti-sticktion.

    def disable_anti_sticktion_routine(self):
        return self._unset_device_mode_bit(2) # 2 -> Anti-sticktion.

    def enable_move_tracking(self):
        return self._set_device_mode_bit(4)

    def disable_move_tracking(self):
        return self._unset_device_mode_bit(4)

    def _set_maximum_position_steps(self, steps_from_home):
        return self._send_command('Set Maximum Position', steps_from_home)

    def get_speed(self):
        return int(self._send_command('Return Setting', 42).data)

    def set_speed(self, speed):
        return int(self._send_command('Set Target Speed', speed).data)

    def get_acceleration(self):
        return int(self._send_command('Return Setting', 43).data)

    def set_acceleration(self, acceleration):
        return int(self._send_command('Set Acceleration', acceleration).data)

    def get_microstep_resolution(self):
        return int(self._send_command('Return Setting', 37).data)

    def set_microstep_resolution(self, microstep_resolution):
        assert microstep_resolution in (1, 2, 4, 8, 16, 32, 64, 128)
        r = self._send_command('Set Microstep Resolution', microstep_resolution)
        return int(r.data)

    def home(self):
        return self._send_command('Home')

class LuminosAxisLinear(LuminosAxis, st.AxisLinear):
    __metaclass__ = abc.ABCMeta

    def __init__(self, port, device_index, reverse_axis=False, update_position_absolute=100,
                 home=False, config_mask_set=0x08A0, config_mask_unset=0xC35F):
        super().__init__(port, device_index, reverse_axis, update_position_absolute=update_position_absolute,
                         home=home, config_mask_set=config_mask_set, config_mask_unset=config_mask_unset)

    @abc.abstractproperty
    def nm_per_step(self):
        pass

    def _move_abs_nm(self, distance_from_home_nm):
        steps = distance_from_home_nm / self.nm_per_step
        r = self._move_abs_steps(steps)
        return r.data * self.nm_per_step

    def _get_current_position_nm(self):
        pos_abs_steps = self._send_command('Return Current Position').data
        pos_abs_nm = pos_abs_steps * self.nm_per_step

        if not self._position_absolute_min_nm <= pos_abs_nm <= self._position_absolute_max_nm:
            raise RuntimeError('Position not in range.')

        return pos_abs_nm

    def _set_maximum_position_nm(self, distance_from_home_nm):
        return self._set_maximum_position_steps(distance_from_home_nm / self.nm_per_step)

    def _set_maximum_position_um(self, distance_from_home_um):
        return self._set_maximum_position_nm(distance_from_home_um*1000.)

class LuminosAxisRotate(LuminosAxis, st.AxisRotate):
    __metaclass__ = abc.ABCMeta

    def __init__(self, port, device_index, reverse_axis=False, update_position_absolute=100,
                 home=False, config_mask_set=0x08A0, config_mask_unset=0xC35F):
        super().__init__(port, device_index, reverse_axis, update_position_absolute=update_position_absolute,
                         home=home, config_mask_set=config_mask_set, config_mask_unset=config_mask_unset)

    @abc.abstractproperty
    def arc_second_per_step(self):
        pass

    def _move_abs_arc_second(self, angle_from_home_arc_second):
        steps = angle_from_home_arc_second / self.arc_second_per_step
        r = self._move_abs_steps(steps)
        return r.data * self.arc_second_per_step

    def _get_current_position_arc_second(self):
        pos_abs_steps = self._send_command('Return Current Position').data
        pos_abs_arc_second = pos_abs_steps * self.arc_second_per_step

        retry = 1
        while retry < 3 and not self._position_absolute_min_arc_second <= pos_abs_arc_second <= \
                self._position_absolute_max_arc_second:
            pos_abs_steps = self._send_command('Return Current Position').data
            pos_abs_arc_second = pos_abs_steps * self.arc_second_per_step
            retry += 1
            time.sleep(0.1)

        if not self._position_absolute_min_arc_second <= pos_abs_arc_second <= \
                self._position_absolute_max_arc_second:
           raise RuntimeError('Position not in range.')

        return pos_abs_arc_second

    def _set_maximum_position_arc_second(self, angle_from_home_arc_second):
        return self._set_maximum_position_steps(angle_from_home_arc_second / self.arc_second_per_step)

    def _set_maximum_position_degree(self, angle_from_home_degree):
        return self._set_maximum_position_arc_second(angle_from_home_degree*3600.)

class LuminosAxisX(LuminosAxisLinear, st.AxisX):
    def __init__(self, port, device_index, reverse_axis=False, update_position_absolute=100,
                 home=False, config_mask_set=0x08A0, config_mask_unset=0xC35F):
                 super().__init__(port, device_index, reverse_axis, update_position_absolute=update_position_absolute,
                                  home=home, config_mask_set=config_mask_set, config_mask_unset=config_mask_unset)

    @property
    def nm_per_step(self):
        return 4.

    @property
    def _position_absolute_min_nm(self):
        return 0.

    @property
    def _position_absolute_max_nm(self):
        return 524.288e3

class LuminosAxisY(LuminosAxisLinear, st.AxisY):
    def __init__(self, port, device_index, reverse_axis=False, update_position_absolute=100,
                 home=False, config_mask_set=0x08A0, config_mask_unset=0xC35F):
        super().__init__(port, device_index, reverse_axis, update_position_absolute=update_position_absolute,
                         config_mask_set=config_mask_set, config_mask_unset=config_mask_unset)

    @property
    def nm_per_step(self):
        return 4.

    @property
    def _position_absolute_min_nm(self):
        return 0.

    @property
    def _position_absolute_max_nm(self):
        return 524.288e3

class LuminosAxisZ(LuminosAxisLinear, st.AxisZ):
    def __init__(self, port, device_index, reverse_axis=False, update_position_absolute=100,
                 home=False, config_mask_set=0x08A0, config_mask_unset=0xC35F):
        super().__init__(port, device_index, reverse_axis, update_position_absolute=update_position_absolute,
                         config_mask_set=config_mask_set, config_mask_unset=config_mask_unset)

    @property
    def nm_per_step(self):
        return 100.

    @property
    def _position_absolute_min_nm(self):
        return 0.

    @property
    def _position_absolute_max_nm(self):
        return 16000.e3

class LuminosAxisRoll(LuminosAxisRotate, st.AxisRoll):
    def __init__(self, port, device_index, reverse_axis=False, update_position_absolute=100,
                 home=False, config_mask_set=0x08A0, config_mask_unset=0xC35F):
        super().__init__(port, device_index, reverse_axis, update_position_absolute=update_position_absolute,
                         config_mask_set=config_mask_set, config_mask_unset=config_mask_unset)

    @property
    def arc_second_per_step(self):
        return 0.1

    @property
    def _position_absolute_min_arc_second(self):
        return 0.

    @property
    def _position_absolute_max_arc_second(self):
        return 3.9*3600.

class LuminosAxisYaw(LuminosAxisRotate, st.AxisYaw):
    def __init__(self, port, device_index, reverse_axis=False, update_position_absolute=100,
                 home=False, config_mask_set=0x08A0, config_mask_unset=0xC35F):
        super().__init__(port, device_index, reverse_axis, update_position_absolute=update_position_absolute,
                         config_mask_set=config_mask_set, config_mask_unset=config_mask_unset)

    @property
    def arc_second_per_step(self):
        return 0.2

    @property
    def _position_absolute_min_arc_second(self):
        return 0.

    @property
    def _position_absolute_max_arc_second(self):
        return 3.9*3600.

class LuminosAxisPitch(LuminosAxisRotate, st.AxisPitch):
    def __init__(self, port, device_index, reverse_axis=False, update_position_absolute=100,
                 home=False, config_mask_set=0x08A0, config_mask_unset=0xC35F):
        super().__init__(port, device_index, reverse_axis, update_position_absolute=update_position_absolute,
                         config_mask_set=config_mask_set, config_mask_unset=config_mask_unset)

    @property
    def arc_second_per_step(self):
        return 0.2

    @property
    def _position_absolute_min_arc_second(self):
        return 0.

    @property
    def _position_absolute_max_arc_second(self):
        return 3.9*3600.

