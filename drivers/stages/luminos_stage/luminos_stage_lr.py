from . import luminos_stage as ls
from .. import stage as st

class LuminosStagesLR(st.Stages3):

    def __init__(self, com_port_number_input='luminos_lr_input', com_port_number_output='luminos_lr_output',
                 com_port_number_chip='luminos_lr_chip', filename=None, C1_input=None, C2_input=None,
                 C1_output=None, C2_output=None, C1_z_chip=0., C2_z_chip=0., c1_c2_distance_mask_um=None,
                 input_x_axis_motor='x', input_y_axis_motor='y', input_z_axis_motor='z',
                 output_x_axis_motor='x', output_y_axis_motor='y', output_z_axis_motor='z',
                 chip_z_axis_motor='z',
                 ctr_in_out_xy_axes=False, update_position_absolute=100, restore_default_settings=False,
                 reverse_output_x_axis=True, home_input=False,
                 home_chip=False, home_output=False):
        self.pos_xyz_um_stack = []

        self.input = LuminosStageLR(com_port_number_input, C1=C1_input, C2=C2_input,
                                    C1_z_chip=C1_z_chip, C2_z_chip=C2_z_chip,
                                    c1_c2_distance_mask_um=c1_c2_distance_mask_um,
                                    update_position_absolute=update_position_absolute,
                                    filename=filename, x_axis_motor=input_x_axis_motor,
                                    y_axis_motor=input_y_axis_motor, z_axis_motor=input_z_axis_motor,
                                    restore_default_settings=restore_default_settings,
                                    home=home_input)

        self.output = LuminosStageLR(com_port_number_output, C1=C1_output, C2=C2_output,
                                     C1_z_chip=C1_z_chip, C2_z_chip=C2_z_chip,
                                     c1_c2_distance_mask_um=c1_c2_distance_mask_um,
                                     update_position_absolute=update_position_absolute,
                                     filename=filename, x_axis_motor=output_x_axis_motor,
                                     y_axis_motor=output_y_axis_motor, z_axis_motor=output_z_axis_motor,
                                     reverse_axis_x=reverse_output_x_axis, restore_default_settings=restore_default_settings,
                                     home=home_output)

        self.chip = LuminosStageLR(com_port_number_chip, filename=filename,
                                       update_position_absolute=update_position_absolute,
                                       z_axis_motor=chip_z_axis_motor,
                                       restore_default_settings=restore_default_settings,
                                       home=home_chip)

        stages_dict = {'input': self.input, 'output': self.output, 'chip': self.chip}
        super().__init__(stages_dict=stages_dict, filename=filename, ctr_in_out_xy_axes=ctr_in_out_xy_axes)

    def home(self):
        for stage in self.stages_dict.values():
            stage.home()

class LuminosStageLR(ls.LuminosStage):

    def __init__(self, com_port_number, C1=None, C2=None,
                 C1_z_chip=0., C2_z_chip=0., update_position_absolute=100,
                 c1_c2_distance_mask_um=None, calibrate_c_axis=False,
                 filename=None, reverse_axis_x=False,
                 x_axis_motor='x', y_axis_motor='y', z_axis_motor='z',
                 reverse_axis_y=False, reverse_axis_z=False,
                 restore_default_settings=False, home=False):

        assert com_port_number in ['luminos_lr_input', 'luminos_lr_chip', 'luminos_lr_output'], \
            'This com port number must be "luminos_lr_input", "luminos_lr_chip", or "luminos_lr_output'

        self.com_port_number = com_port_number

        super().__init__(com_port_number, C1=C1, C2=C2,
                         C1_z_chip=C1_z_chip, C2_z_chip=C2_z_chip, update_position_absolute=update_position_absolute,
                         c1_c2_distance_mask_um=c1_c2_distance_mask_um, calibrate_c_axis=calibrate_c_axis,
                         filename=filename, reverse_axis_x=reverse_axis_x,
                         x_axis_motor=x_axis_motor, y_axis_motor=y_axis_motor, z_axis_motor=z_axis_motor,
                         reverse_axis_y=reverse_axis_y, reverse_axis_z=reverse_axis_z,
                         restore_default_settings=restore_default_settings, home=home)

    def _get_axes_dict(self, update_position_absolute, reverse_axis_x, reverse_axis_y, reverse_axis_z, home):

        if self.com_port_number in ['luminos_lr_input', 'luminos_lr_output']:

            axes_idx = {'x': 2, 'y': 3, 'z': 1, 'roll': 4, 'yaw': 5, 'pitch': 6}

            axes_dict = {
                'x': LuminosAxisXLR(self._port, axes_idx['x'], reverse_axis_x,
                                  update_position_absolute, home),
                'y': LuminosAxisYLR(self._port, axes_idx['y'], reverse_axis_y,
                                  update_position_absolute, home),
                'z': LuminosAxisZLR(self._port, axes_idx['z'], reverse_axis_z,
                                  update_position_absolute, home),
                'roll': LuminosAxisRollLR(self._port, axes_idx['roll'], False,
                                        update_position_absolute, home),
                'pitch': LuminosAxisPitchLR(self._port, axes_idx['pitch'], False,
                                          update_position_absolute, home),
                'yaw': LuminosAxisYawLR(self._port, axes_idx['yaw'], False,
                                      update_position_absolute, home),
            }

            return axes_idx, axes_dict

        else:

            axes_idx = {'z': 1}

            axes_dict = {
                'z': LuminosAxisZLR(self._port, axes_idx['z'], reverse_axis_z,
                                    update_position_absolute, home, absolute_max_nm=12800e3),
            }

            return axes_idx, axes_dict

class LuminosAxisLR(ls.LuminosAxis):
    def __init__(self, port, device_index, reverse_axis=False, update_position_absolute=100,
                 home=False):

        super().__init__(port, device_index, reverse_axis, update_position_absolute=update_position_absolute,
                        home=home)

class LuminosAxisLinearLR(ls.LuminosAxisLinear):
    def __init__(self, port, device_index, reverse_axis=False, update_position_absolute=100,
                 home=False):

        super().__init__(port, device_index, reverse_axis, update_position_absolute=update_position_absolute,
                         home=False)

class LuminosAxisRotateLR(ls.LuminosAxisRotate):
    def __init__(self, port, device_index, reverse_axis=False, update_position_absolute=100,
                 home=False):

        super().__init__(port, device_index, reverse_axis, update_position_absolute=update_position_absolute,
                         home=False)

class LuminosAxisXLR(ls.LuminosAxisX):
    def __init__(self, port, device_index, reverse_axis=False, update_position_absolute=100,
                 home=False):
        # todo home variable is not used - should it be passed with the super?
        super().__init__(port, device_index, reverse_axis, update_position_absolute=update_position_absolute)

    @property
    def nm_per_step(self):
        return 20.

    @property
    def _position_absolute_min_nm(self):
        return 0.

    @property
    def _position_absolute_max_nm(self):
        return 2621.440e3

class LuminosAxisYLR(ls.LuminosAxisY):
    def __init__(self, port, device_index, reverse_axis=False, update_position_absolute=100,
                 home=False):

        super().__init__(port, device_index, reverse_axis, update_position_absolute=update_position_absolute)

    @property
    def nm_per_step(self):
        return 20.

    @property
    def _position_absolute_min_nm(self):
        return 0.

    @property
    def _position_absolute_max_nm(self):
        return 2621.440e3

class LuminosAxisZLR(ls.LuminosAxisZ):
    def __init__(self, port, device_index, reverse_axis=False, update_position_absolute=100,
                 home=False, absolute_max_nm=16000e3):
        self.absolute_max_nm = absolute_max_nm

        super().__init__(port, device_index, reverse_axis, update_position_absolute=update_position_absolute)

    @property
    def nm_per_step(self):
        return 100.

    @property
    def _position_absolute_min_nm(self):
        return 0.

    @property
    def _position_absolute_max_nm(self):
        # todo for the chip stage this is 12800.e3
        return self.absolute_max_nm

class LuminosAxisRollLR(ls.LuminosAxisRoll):
    def __init__(self, port, device_index, reverse_axis=False, update_position_absolute=100,
                 home=False):

        super().__init__(port, device_index, reverse_axis, update_position_absolute=update_position_absolute)

    @property
    def arc_second_per_step(self):
        return 0.1

    @property
    def _position_absolute_min_arc_second(self):
        return 0.

    @property
    def _position_absolute_max_arc_second(self):
        return 3. * 3600.

class LuminosAxisYawLR(ls.LuminosAxisYaw):
    def __init__(self, port, device_index, reverse_axis=False, update_position_absolute=100,
                 home=False):

        super().__init__(port, device_index, reverse_axis, update_position_absolute=update_position_absolute)

    @property
    def arc_second_per_step(self):
        return 0.2

    @property
    def _position_absolute_min_arc_second(self):
        return 0.

    @property
    def _position_absolute_max_arc_second(self):
        return 3. * 3600.

class LuminosAxisPitchLR(ls.LuminosAxisPitch):

    def __init__(self, port, device_index, reverse_axis=False, update_position_absolute=100,
                 home=False):

        super().__init__(port, device_index, reverse_axis, update_position_absolute=update_position_absolute)

    @property
    def arc_second_per_step(self):
        return 0.2

    @property
    def _position_absolute_min_arc_second(self):
        return 0.

    @property
    def _position_absolute_max_arc_second(self):
        return 3. * 3600.