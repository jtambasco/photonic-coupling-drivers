from .. import stage as st
import abc
import visa
import time
import Gpib


def find_stages(num_gpib_ports_check=10, gpib_device_nums_check=4, timeout_gpib_read_ms=100):
    gpib_stages_found = []
    rm = visa.ResourceManager('@py')
    for gpib_port_num in range(num_gpib_ports_check):
        for gpib_device_num in range(gpib_device_nums_check):
            try:
                gpib_str = 'GPIB%i::%i::INSTR' % (gpib_port_num, gpib_device_num)
                gpib_stage = rm.open_resource(gpib_str)
                gpib_stage.timeout = timeout_gpib_read_ms

                r_scum0 = gpib_stage.query('VN?')[2:].strip()
                r_scum1 = gpib_stage.query('SVN?')[2:].strip()

                if r_scum0 and r_scum0[0] == '$':
                    found0 = True
                    for c in r_scum0[1:]:
                        if not c.isdigit():
                            found0 = False
                else:
                    found0 = False

                if r_scum1 and r_scum1[0] == '$':
                    found1 = True
                    for c in r_scum1[1:]:
                        if not c.isdigit():
                            found1 = False
                else:
                    found1 = False

                if found0 or found1:
                    gpib_stages_found.append([gpib_port_num, gpib_device_num])

            except Gpib.gpib.GpibError:
                pass
    return gpib_stages_found

class NewportStages(st.Stages2):
    def __init__(self, gpib_port_num, gpib_device_input_num, gpib_device_output_num,
                 C1_input=None, C2_input=None, C1_output=None, C2_output=None,
                 c1_c2_distance_mask_um=None, set_defaults_on_startup=False,
                 update_position_absolute=100,
                 centre_stage_and_set_home=False, x_axis_motor='x', y_axis_motor='y',
                 z_axis_motor='z', filename=None):
        stages_dict = {'input': NewportStage(gpib_port_num, gpib_device_input_num,
                                C1=C1_input, C2=C2_input,
                                c1_c2_distance_mask_um=None,
                                update_position_absolute=update_position_absolute,
                                set_defaults_on_startup=set_defaults_on_startup,
                                centre_stage_and_set_home=centre_stage_and_set_home,
                                x_axis_motor=x_axis_motor, y_axis_motor=y_axis_motor,
                                z_axis_motor=z_axis_motor),
                       'output': NewportStage(gpib_port_num, gpib_device_output_num,
                                 C1=C1_output, C2=C2_output,
                                 c1_c2_distance_mask_um=None,
                                 update_position_absolute=update_position_absolute,
                                 set_defaults_on_startup=set_defaults_on_startup,
                                 centre_stage_and_set_home=centre_stage_and_set_home,
                                 x_axis_motor=x_axis_motor, y_axis_motor=y_axis_motor,
                                 z_axis_motor=z_axis_motor)}
        super().__init__(stages_dict=stages_dict, filename=filename)

    def home(self):
        r1 = self.input.home()
        r2 = self.output.home()
        return r1, r2

class NewportStage(st.Stage):
    def __init__(self, gpib_port_num, gpib_device_num, C1=None, C2=None,
                 c1_c2_distance_mask_um=None, update_position_absolute=100.,
                 calibrate_xT_zT_axes=False, filename=None, reverse_axis_x=False,
                 reverse_axis_y=False, reverse_axis_z=False, x_axis_motor='x',
                 y_axis_motor='y', z_axis_motor='z', timeout_ms=1000.,
                 set_defaults_on_startup=False, centre_stage_and_set_home=False):

        rm = visa.ResourceManager('@py')
        gpib_str = 'GPIB%i::%i::INSTR' % (gpib_port_num, gpib_device_num)
        gpib_stage = rm.open_resource(gpib_str)
        gpib_stage.timeout = timeout_ms

        # Flush the buffer in case any previous results are left.
        NewportStage._flush_buffer(gpib_stage)

        self.system = NewportSystem(gpib_stage, set_defaults_on_startup)

        axes_dict = {
                    'x': NewportXAxis(gpib_stage=gpib_stage, reverse_axis=reverse_axis_x),
                    'y': NewportYAxis(gpib_stage=gpib_stage, reverse_axis=reverse_axis_y),
                    'z': NewportZAxis(gpib_stage=gpib_stage, reverse_axis=reverse_axis_z)
                }

        super().__init__(axes_dict=axes_dict, C1=C1, C2=C2,
                         c1_c2_distance_mask_um=c1_c2_distance_mask_um,
                         update_position_absolute=update_position_absolute,
                         update_position_absolute=update_position_absolute,
                         calibrate_xT_zT_axes=calibrate_xT_zT_axes,
                         reverse_axis_x=reverse_axis_x,
                         reverse_axis_y=reverse_axis_y, reverse_axis_z=reverse_axis_z,
                         x_axis_motor=x_axis_motor, y_axis_motor=y_axis_motor,
                         z_axis_motor=z_axis_motor, filename=filename)

        if centre_stage_and_set_home:
            self.centre_axes_and_set_home()

    def centre_axes_and_set_home(self):
        r = []
        for axis in self.axes.values():
            try:
                r.append(axis.centre_axis_and_set_home())
            except AttributeError:
                pass
        return r

    def home(self):
        r = []
        for axis in self.axes.values():
            try:
                r.append(axis.home())
            except AttributeError:
                pass
        return r

    def get_motors_on_off(self):
        on_off_state = [axis.get_motor_on_off() for axis in self.axes.values() if axis]
        return on_off_state

    def set_motors_off(self):
        for axis in self.axes.values():
            if axis:
                axis.set_motor_off()
        return self.get_motors_on_off()

    def set_motors_on(self):
        for axis in self.axes.values():
            if axis:
                axis.set_motor_on()
        return self.get_motors_on_off()

    @staticmethod
    def _send_command(gpib_stage, device_str, command, data=None):
        cmd_str = device_str + command + ' '
        if data is not None:
            cmd_str += str(data)
        gpib_stage.write(cmd_str)

    @staticmethod
    def _send_read_command(gpib_stage, device_str, command, data=None):
        cmd_str = device_str + command + ' '
        if data is not None:
            cmd_str += str(data)
        r = gpib_stage.query(cmd_str).strip()
        return r

    @staticmethod
    def _read_command(gpib_stage):
        r = gpib_stage.read()
        return r

    @staticmethod
    def _flush_buffer(gpib_stage):
        timeout_temp = gpib_stage.timeout
        gpib_stage.timeout = 100
        r = None
        while r != '':
            r = NewportStage._read_command(gpib_stage)
        gpib_stage.timeout = timeout_temp

class NewportSystem(object):
    Configuration = {'Limit Halt': 0, 'Query Echo': 2, 'ASCII Command': 4,
            'Carriage Return Command Termination': 7, 'Line Feed Command Termination': 8,
            'EOI Command': 9, 'CR\LF': 10, 'CR Commands CR\LF Response Termination': 11,
            'Hexadecimal': 12, '2nd Generation Serial Poll Bit Format': 13,
            'SRQ On Message': 14}

    def __init__(self, gpib_stage, set_defaults_on_startup=False):
        self.gpib_stage = gpib_stage
        self.axis_str = '' # System doesn't have an axis prefix like x, y and z.

        if set_defaults_on_startup:
            # Manually set stage to appropriate settings.
            # Page 135 of Newport PM500-c manual for explanation of (S)ENAINT $6617.
            self._send_command('SENAINT $6617')
            time.sleep(0.05)
            self._send_command('ENAINT $6617')
            time.sleep(0.05)
            self._send_command('SRSTART')
            time.sleep(0.05)
            self._send_command('RSTART')
            time.sleep(3)

        # Make sure SCUM 0.
        self.set_scum_0()
        time.sleep(0.05)

    def _send_command(self, command, data=None):
        return NewportStage._send_command(self.gpib_stage, self.axis_str, command, data)

    def _send_read_command(self, command, data=None):
        return NewportStage._send_read_command(self.gpib_stage, self.axis_str, command, data)

    def _read_command(self):
        return NewportStage._read_command()

    def _read_configuration(self):
        c = self._send_read_command(self.scum_str+'ENAINT?').strip()
        c = bin(int('0x'+c[3:], 16))
        return c

    def _write_configuration(self, configuration):
        assert not configuration >> 16, 'Configuration byte has bits set above bit 16.'
        c = '$%s' % hex(configuration)[2:]
        r = self._send_command(self.scum_str+'ENAINT', c)
        return r

    def _modify_configuration(self, bits_to_set, bits_to_unset):
        NewportStage._flush_buffer(self.gpib_stage) # Flush buffer in case.
        conf = self._read_configuration()

        mask_set = 0
        for b in bits_to_set:
            mask_set |= 1 << NewportSystem.Configuration[b]

        mask_unset = 0
        for b in bits_to_unset:
            mask_unset |= 1 << NewportSystem.Configuration[b]
        mask_unset = ~mask_unset

        conf |= mask_set
        conf &= mask_unset
        r = self._write_configuration(conf)

        self.restart_system()

        return r

    def set_scum_0(self):
        self.scum_str = ''
        return self._send_read_command('SCUM', '0')

    def set_scum_1(self):
        self.scum_str = 'S'
        return self._send_read_command('SCUM', '1')

    def check_scum(self):
        s = self._send_read_command('SCUM?')
        s = int(float(s[2:]))
        return s

    def set_factory_defaults(self):
        self._send_command('SDEFEE')
        time.sleep(1)
        self._send_command('DEFEE')
        time.sleep(1)
        r = self.restart_system()
        return r

    def restart_system(self):
        self._send_command('SRSTART')
        time.sleep(1)
        self._send_command('RSTART')
        time.sleep(3)
        self.scum_str = 'S' if self.check_scum() else ''
        return self.scum_str

class NewportAxis(st.Axis):
    def __init__(self, gpib_stage, axis_str, reverse_axis=False, update_position_absolute=100):
        assert axis_str in ('X', 'Y', 'Z'), 'Invalid axis string `%s` given.' % axis_str
        self.axis_str = axis_str
        self.gpib_stage = gpib_stage
        super().__init__(reverse_axis, update_position_absolute=update_position_absolute)

    def _send_command(self, command, data=None):
        return NewportStage._send_command(self.gpib_stage, self.axis_str, command, data)

    def _send_read_command(self, command, data=None):
        return NewportStage._send_read_command(self.gpib_stage, self.axis_str, command, data)

    def _read_command(self):
        return NewportStage._read_command()

    def centre_axis_and_set_home(self):
        r = self._send_read_command('F', '0')
        self.wait_axis_completed_command()
        return r

    def home(self):
        r = self._send_read_command('F')
        self.wait_axis_completed_command()
        return r

    def wait_axis_completed_command(self):
        time.sleep(0.01)
        s = self.axis_str + 'B'
        while s == self.axis_str + 'B':
            s = self._send_read_command('STAT?')
            time.sleep(0.02)

        assert s[1] != 'L', 'The axis has reached its limit.'
        assert s[1] != 'E', 'An error has occured.'
        assert s[1] != 'M', 'The motor is off.'

        return s

class NewportAxisLinear(NewportAxis, st.AxisLinear):
    def __init__(self, gpib_stage, axis_str, reverse_axis=False, update_position_absolute=100) :
        super().__init__(gpib_stage, axis_str, reverse_axis, update_position_absolute=update_position_absolute)

    def _move_abs_nm(self, distance_from_home_nm):
        self._send_read_command('G', distance_from_home_nm / 1000.)
        self.wait_axis_completed_command()
        r = self.get_current_position_nm()
        return r

    def _get_current_position_nm(self):
        r = self._send_read_command('G?').strip()
        r = float(r[2:]) * 1000.
        self.wait_axis_completed_command()
        return r

    def get_motor_on_off(self):
        return not bool(float(self._send_read_command('M?')[3:]))

    def set_motor_off(self):
        self._send_read_command('M')
        return self.get_motor_on_off()

    def set_motor_on(self):
        self._send_read_command('T')
        self._position_absolute = self.get_current_position_nm()
        return self.get_motor_on_off()

class NewportXAxis(NewportAxisLinear, st.AxisX):
    def __init__(self, gpib_stage, reverse_axis=False, update_position_absolute=100):
        super().__init__(gpib_stage, 'X', reverse_axis, update_position_absolute=update_position_absolute)

    @property
    def _position_absolute_min_nm(self):
        return -100000.e3

    @property
    def _position_absolute_max_nm(self):
        return 100000.e3

class NewportYAxis(NewportAxisLinear, st.AxisY):
    def __init__(self, gpib_stage, reverse_axis=False, update_position_absolute=100):
        super().__init__(gpib_stage, 'Y', reverse_axis, update_position_absolute=update_position_absolute)

    @property
    def _position_absolute_min_nm(self):
        return -100000.e3

    @property
    def _position_absolute_max_nm(self):
        return 100000.e3

class NewportZAxis(NewportAxisLinear, st.AxisZ):
    def __init__(self, gpib_stage, reverse_axis=False, update_position_absolute=100):
        super().__init__(gpib_stage, 'Z', reverse_axis, update_position_absolute=update_position_absolute)

    @property
    def _position_absolute_min_nm(self):
        return -100000.e3

    @property
    def _position_absolute_max_nm(self):
        return 100000.e3

