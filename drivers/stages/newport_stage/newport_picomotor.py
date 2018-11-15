import time
from .. import stage as st
from ... import usb_device as usb_dev

class PicomotorSystem:
    def __init__(self, usb):
        self._usb = usb

    def get_product_id(self):
        return self._usb.write_read('*IDN?\n\r')

    def wait_scan_done(self, poll_time_ms=50., timeout_ms=5000.):
        retries = int(round(timeout_ms / poll_time_ms))
        for _ in range(retries):
            status = self._usb.write_read('SD?\n\r').strip()
            if status == '0':
                time.sleep(poll_time_ms/1000.)
            elif status == '1':
                break
            else:
                raise RuntimeError('Invalid device reply.')
        return status

    def resolve_address_conflicts(self):
        self._usb.write('SC2\n\r')
        return self.wait_scan_done()

    def get_controllers_scan(self):
        self._usb.write('SC0\n\r')
        self.wait_scan_done()
        scan = self._usb.write_read('SC?\n\r')
        scan_bits = bin(int(scan))
        return scan_bits


class PicomotorStages(st.Stages3):
    def __init__(self, axis_controller_dict_input=None, axis_controller_dict_chip=None,
                 axis_controller_dict_output=None,
                 C1=None, C2=None, c1_c2_distance_mask_um=None, update_position_absolute=100., filename=None,
                 x_axis_motor='x', y_axis_motor='y', z_axis_motor='z', resolve_address_conflicts=False):

        PicomotorStages._usb = usb_dev.UsbDevice(0x104d, 0x4000)
        self.picomotor_system = PicomotorSystem(PicomotorStages._usb)
        if resolve_address_conflicts:
            self.picomotor_system.resolve_address_conflicts()

        #todo check this works!!

        stages_dict = {}

        self.input = PicomotorStage(axis_controller_dict_input, C1=C1, C2=C2,
                                    c1_c2_distance_mask_um=c1_c2_distance_mask_um,
                                    update_position_absolute=update_position_absolute,
                                    filename=filename, reverse_axis_x=False,
                                    reverse_axis_y=False, reverse_axis_z=False, x_axis_motor=x_axis_motor,
                                    y_axis_motor=y_axis_motor, z_axis_motor=z_axis_motor,
                                    resolve_address_conflicts=resolve_address_conflicts,
                                    picomotor_system=self.picomotor_system, PicomotorStage_usb=PicomotorStages._usb)

        stages_dict['input'] = self.input

        self.chip = PicomotorStage(axis_controller_dict_chip, C1=C1, C2=C2,
                                   c1_c2_distance_mask_um=c1_c2_distance_mask_um,
                                   update_position_absolute=update_position_absolute,
                                   filename=filename, reverse_axis_x=False,
                                   reverse_axis_y=False, reverse_axis_z=False, z_axis_motor='x',
                                   resolve_address_conflicts=resolve_address_conflicts,
                                   picomotor_system=self.picomotor_system, PicomotorStage_usb=PicomotorStages._usb)

        stages_dict['chip'] = self.chip

        self.output = PicomotorStage(axis_controller_dict_output, C1=C1, C2=C2,
                                     c1_c2_distance_mask_um=c1_c2_distance_mask_um,
                                     update_position_absolute=update_position_absolute,
                                     filename=filename, reverse_axis_x=True,
                                     reverse_axis_y=False, reverse_axis_z=False, x_axis_motor=x_axis_motor,
                                     y_axis_motor=y_axis_motor, z_axis_motor=z_axis_motor,
                                     resolve_address_conflicts=resolve_address_conflicts,
                                     picomotor_system=self.picomotor_system, PicomotorStage_usb=PicomotorStages._usb)

        stages_dict['output'] = self.output

        super().__init__(stages_dict=stages_dict, filename=filename)


class PicomotorStage(st.Stage):

    def __init__(self, axis_controller_dict, C1=None, C2=None,
                 c1_c2_distance_mask_um=None, update_position_absolute=100.,
                 filename=None, reverse_axis_x=False,
                 reverse_axis_y=False, reverse_axis_z=False, x_axis_motor='x',
                 y_axis_motor='y', z_axis_motor='z', resolve_address_conflicts=False,
                 picomotor_system=None, PicomotorStage_usb=None):

        # if not PicomotorStage._usb:
        #     print('connecting to usb')
        #     PicomotorStage._usb = usb_dev.UsbDevice(0x104d, 0x4000)
        #     PicomotorStage.picomotor_system = PicomotorSystem(PicomotorStage._usb)
        #     if resolve_address_conflicts:
        #         PicomotorStage.picomotor_system.resolve_address_conflicts()


        if not picomotor_system and not PicomotorStage_usb:
            try:
                PicomotorStage._usb = usb_dev.UsbDevice(0x104d, 0x4000)
                self.picomotor_system = PicomotorSystem(PicomotorStage._usb)
                if resolve_address_conflicts:
                    self.picomotor_system.resolve_address_conflicts()
            except:
                print('usb connection fail')
        else:
            PicomotorStage._usb = PicomotorStage_usb
            self.picomotor_system = picomotor_system

        axes_dict = {}
        for axis in axis_controller_dict:
            try:
                axes_dict[axis] = PicomotorAxisABC(PicomotorStage._usb, axis_controller_dict[axis][0],
                                                   motor_number=axis_controller_dict[axis][1],
                                                   update_position_absolute=update_position_absolute)
            except:
                print('something went wrong connecting')

        if ('A' in axes_dict.keys()) and ('B' in axes_dict.keys()):
            axes_dict['y'] = PicomotorYAxis(axes_dict['A'], axes_dict['B'], reverse_axis_y)
        if ('APrime' in axes_dict.keys()) and ('BPrime' in axes_dict.keys()):
            axes_dict['z'] = PicomotorZAxis(axes_dict['APrime'], axes_dict['BPrime'], reverse_axis_z)
        if 'C' in axes_dict.keys():
            axes_dict['x'] = PicomotorXAxis(axes_dict['C'], reverse_axis_x)

        super().__init__(axes_dict=axes_dict, C1=C1, C2=C2,
                         c1_c2_distance_mask_um=c1_c2_distance_mask_um,
                         reverse_axis_x=reverse_axis_x,
                         reverse_axis_y=reverse_axis_y, reverse_axis_z=reverse_axis_z,
                         x_axis_motor=x_axis_motor, y_axis_motor=y_axis_motor,
                         z_axis_motor=z_axis_motor, filename=filename)

    @staticmethod
    def _write(usb, data):
        return usb.write(data)

    @staticmethod
    def _read(usb):
        return usb.read().strip()

    def _write_motor(self, command, motor_number):
        controller_number = self._controller_number_ab if motor_number in (1,2,3,4) \
            else self._controller_number_c
        data = '%i>%i%s\n\r' % (controller_number, motor_number, command)
        self._write(self._usb, data)

    def _write_read_motor(self, command, motor_number):
        self._write_motor(command, motor_number)
        return self._read(self._usb)

class PicomotorAxis(st.Axis):
    def __init__(self, usb, controller_number, motor_number, reverse_axis=False, update_position_absolute=100):
        motor_number = int(motor_number)
        assert motor_number in (1, 2, 3, 4, 5), 'Invalid axis `%i` given.' % motor_number
        self._usb = usb
        self._controller_number = controller_number
        self._motor_number = motor_number
        super().__init__(reverse_axis=reverse_axis, update_position_absolute=update_position_absolute)

    def _write_motor(self, command):
        data = '%i>%i%s\n\r' % (self._controller_number, self._motor_number, command)
        return PicomotorStage._write(self._usb, data)

    def _write_read_motor(self, command):
        self._write_motor(command)
        return self._read()

    def _read(self):
        return PicomotorStage._read(self._usb)[2:]

    def wait_motor_moved(self, poll_time_ms=50., timeout_ms=60.e3):
        retries = int(round(timeout_ms / poll_time_ms))
        for _ in range(retries):
            status = self._write_read_motor('MD?')
            if status == '0':
                time.sleep(poll_time_ms/1000.)
            elif status == '1':
                break
            else:
                raise RuntimeError('Invalid device reply.')
        return status

class PicomotorAxisLinear(PicomotorAxis, st.AxisLinear):
    def __init__(self, usb, controller_number, motor_number, reverse_axis=False, update_position_absolute=100):
        self._step_size_nm = 10.
        super().__init__(usb, controller_number, motor_number=motor_number, reverse_axis=reverse_axis,
                         update_position_absolute=update_position_absolute)

    def _move_abs_nm(self, distance_from_home_nm):
        steps = distance_from_home_nm / self._step_size_nm
        self._write_motor('PA%i' % steps)
        self.wait_motor_moved()
        r = self.get_current_position_nm()
        return r

    def _get_current_position_nm(self):
        r = float(self._write_read_motor('PA?')) * self._step_size_nm
        return r

    def _get_home_position(self):
        r = float(self._write_read_motor('DH?'))
        return r

    def _set_home_position(self):
        self._write_motor('DH')
        # r = self._get_home_position()
        # return r

class PicomotorAxisABC(PicomotorAxisLinear):
    def __init__(self, usb, controller_number, motor_number, reverse_axis=False, update_position_absolute=100):
        super().__init__(usb, controller_number, motor_number=motor_number, reverse_axis=reverse_axis,
                         update_position_absolute=update_position_absolute)

    @property
    def _position_absolute_min_nm(self):
        return 0.

    @property
    def _position_absolute_max_nm(self):
        return 1.e9

class PicomotorYZAxis(st.AxisY):
    def __init__(self, a_axis, b_axis, reverse_axis=False):
        self._a_axis = a_axis
        self._b_axis = b_axis
        super().__init__(reverse_axis)

    #todo add set home feature - finds hardware limit and sets that to zero
    #todo use 2d scan to find two spots
    #todo check step size with fibre array
    #todo optimise spot size separation with 2d scans
    #todo add chip with manual x axis
    #todo couple fibre to chip

    #todo add all home function
    #todo add centre all axes function

    @property
    def _position_absolute_min_nm(self):
        return 0.

    @property
    def _position_absolute_max_nm(self):
        return 3.e6

    def _move_abs_nm(self, distance_from_home_nm):
        step_nm = 10.e3
        curr_pos_nm = self._get_current_position_nm()
        total_rel_move_nm = abs(distance_from_home_nm - curr_pos_nm)
        while total_rel_move_nm >= step_nm:
            self._a_axis.move_rel_nm(step_nm)
            self._b_axis.move_rel_nm(step_nm)
            total_rel_move_nm -= step_nm
        r1 = self._a_axis._move_abs_nm(distance_from_home_nm)
        r2 = self._b_axis._move_abs_nm(distance_from_home_nm)
        r = 0.5 * (r1 + r2)
        return r

    def _get_current_position_nm(self):
        r1 = self._a_axis.get_current_position_nm()
        r2 = self._b_axis.get_current_position_nm()
        r = 0.5 * (r1 + r2)
        return r

    def get_home_position(self):
        r1 = self._a_axis._get_home_position()
        r2 = self._b_axis._get_home_position()
        return r1, r2

    def set_home_position(self):
        r1 = self._a_axis._set_home_position()
        r2 = self._b_axis._set_home_position()
        return r1, r2

class PicomotorYAxis(PicomotorYZAxis):
    def __init__(self, a_axis, b_axis, reverse_axis=False):
        PicomotorYZAxis.__init__(self, a_axis, b_axis, reverse_axis)

class PicomotorZAxis(PicomotorYZAxis):
    def __init__(self, a_prime_axis, b_prime_axis, reverse_axis=False):
        PicomotorYZAxis.__init__(self, a_prime_axis, b_prime_axis, reverse_axis)

class PicomotorXAxis(st.AxisX):
    def __init__(self, c_axis, reverse_axis=False):
        self._c_axis = c_axis
        super().__init__(reverse_axis)

    @property
    def _position_absolute_min_nm(self):
        return 0.

    @property
    def _position_absolute_max_nm(self):
        return 3.e6

    @property
    def _movement_compensation(self):
        return [150 / 127., 102 / 127.]

    def _move_abs_nm(self, distance_from_home_nm):
        return self._c_axis._move_abs_nm(distance_from_home_nm)

    def _get_current_position_nm(self):
        return self._c_axis._get_current_position_nm()

    def get_home_position(self):
        return self._c_axis._get_home_position()

    def set_home_position(self):
        r = self._c_axis._set_home_position()
        return r