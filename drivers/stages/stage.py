import abc
import math
import numpy as np
import time
import os
import json
import copy
from . import logger as log

class abstractstatic(staticmethod):
    '''
    Property class to enforce an abstract static
    function in a dervied class.
    '''
    __slots__ = ()
    def __init__(self, function):
        super(abstractstatic, self).__init__(function)
        function.__isabstractmethod__ = True
    __isabstractmethod__ = True

class Stages(object, metaclass=abc.ABCMeta):
    '''
    Interface class for multiple stages.

    Attributes:
        _pos_xyz_um_stack (list): A FIFO storing the
            (x, y, z) coordinates of the stage.

    Args:
        stages_dict (dict): A dictionary continaing the
            all the stages.  Valid dictionary keys include
            \'input\', \'output\' and \'chip\'.  Valid
            dictionary values are objects derived from the
            `Stage` class.
        filename (str, file, None): A string or open filestream
            to save the x, y and z coordinates of the stage to.
            If `None`, doesn\'t store any data.
    '''
    def __init__(self, stages_dict, filename=None):
        self.stages_dict = stages_dict
        self._pos_xyz_um_stack = []
        self.pos_xyz_um_stack = []

    @abc.abstractmethod
    def _push_pos_xyz(self, stack):
        pass

    @abc.abstractmethod
    def _pop_pos_xyz(self, stack):
        pass

    def _push_pos_xyz_stack(self):
        return self._push_xyz_um(self._pos_xyz_um_stack)

    def _pop_pos_xyz_stack(self, retract_fibres=True):
        return self._pop_xyz_um(self._pos_xyz_um_stack, retract_fibres)

    def push_pos_xyz_stack(self):
        '''
        Pushes (x, y, z) stage coordinates to the stack.
        '''
        return self._push_pos_xyz(self.pos_xyz_um_stack)

    def pop_pos_xyz_stack(self, retract_fibres=True):
        '''
        Pops (x, y, z) stage coordinates from the stack
        and moves the stage to those coordinates.
        '''
        return self._pop_pos_xyz(self.pos_xyz_um_stack, retract_fibres)

class Stages2(Stages, metaclass=abc.ABCMeta):
    '''
    Interface class for a set of two stages; an
    input and an output stage.
    '''
    def __init__(self, stages_dict, filename=None):
        super().__init__(stages_dict, filename)
        self.input  = stages_dict['input']
        self.output = stages_dict['output']

        if filename:
            logger = log.LoggerStages2(filename, self)
            self.input._set_logger(logger)
            self.output._set_logger(logger)

    def _push_pos_xyz(self, stack):
        xyz = {}
        xyz['in'] = self.input.get_current_position_um()
        xyz['out'] = self.output.get_current_position_um()
        stack.append(xyz)
        return stack

    def _pop_pos_xyz(self, stack, retract_fibres=True):
        xyz = stack.pop()
        x_in, y_in, z_in = xyz['in']
        x_out, y_out, z_out = xyz['out']

        # Pull fibres away from chip.
        if retract_fibres:
            self.input.z.move_rel_um(-50)
            self.output.z.move_rel_um(-50)

        # Move everything into place.
        self.input.x.move_abs_um(x_in)
        self.input.y.move_abs_um(y_in)
        self.output.x.move_abs_um(x_out)
        self.output.y.move_abs_um(y_out)

        # Move input and output fibres to their correct position.
        self.input.z.move_abs_um(z_in)
        self.output.z.move_abs_um(z_out)

        return stack

class Stages3(Stages, metaclass=abc.ABCMeta):
    '''
    Interface class for a set of three stages; an
    input, an output stage and a chip stage.
    '''
    def __init__(self, stages_dict, filename=None, ctr_in_out_xy_axes=False):
        super().__init__(stages_dict, filename)
        self.chip   = stages_dict['chip']
        self.input  = stages_dict['input']
        self.output = stages_dict['output']

        if filename:
            logger = log.LoggerStages3(filename, self)
            self.chip._set_logger(logger)
            self.input._set_logger(logger)
            self.output._set_logger(logger)

        if ctr_in_out_xy_axes:
            self.ctr_in_out_xy_axes()

    def _ctr_in_out_x_axes(self, x_ctr_around_line_um=None):
        if x_ctr_around_line_um is None:
            x_ctr_around_line_um = (self.input.x.get_position_absolute_max_um()-\
                    self.input.x.get_position_absolute_min_um()) / 2.
        x_curr_in_um = self.input.x.get_current_position_um()
        x_curr_out_um = self.output.x.get_current_position_um()
        x_ctr_um = 0.5*(x_curr_in_um + x_curr_out_um)
        x_move_rel_um = x_ctr_around_line_um - x_ctr_um
        return x_move_rel_um

    def _ctr_in_out_y_axes(self, y_ctr_around_line_um=None):
        if y_ctr_around_line_um is None:
            y_ctr_around_line_um = (self.input.y.get_position_absolute_max_um()-\
                    self.input.y.get_position_absolute_min_um()) / 2.
        y_curr_in_um = self.input.y.get_current_position_um()
        y_curr_out_um = self.output.y.get_current_position_um()
        y_ctr_um = 0.5*(y_curr_in_um + y_curr_out_um)
        y_move_rel_um = y_ctr_around_line_um - y_ctr_um
        return y_move_rel_um

    def ctr_in_out_x_axes(self, x_ctr_around_line_um=None):
        '''
        Centres the input and output x-axes.

        The axes are centred around around x_ctr_around_line_um.  This
        function is useful for, say, centering the x-axis of, say, the
        Luminos Stages which have a small range, such they have maximum
        swing.

        The fibres are first pulled away (in `z`) before the stages are
        centred.  After the centering the fibres are pushed back (in `z`).

        Args:
            x_ctr_around_line_um (float, None): The position in x
                around which to centre the stages.  If `None`, half
                the maximum swing of the stages will be used.

        Returns:
            float: The distance the x-axes are away from
            `x_ctr_around_line_um`.
        '''
        x_move_rel_um = self._ctr_in_out_x_axes(x_ctr_around_line_um)

        # Pull fibres away.
        self.input.z.move_rel_um(-20.)
        self.output.z.move_rel_um(-20.)

        # Centre everything.
        x_in = self.input.x.move_rel_um(x_move_rel_um)
        x_out = self.output.x.move_rel_um(x_move_rel_um)
        z_chip = self.chip.z.move_rel_um(x_move_rel_um)

        # Put fibres back.
        self.input.z.move_rel_um(20.)
        self.output.z.move_rel_um(20.)

        return x_in, x_out, z_chip

    def ctr_in_out_y_axes(self, y_ctr_around_line_um=None):
        '''
        Centres the input and output y-axes.

        The axes are centred around around y_ctr_around_line_um.  This
        function is useful for, say, centering the y-axis of, say, the
        Luminos Stages which have a small range, such they have maximum
        swing.

        The fibres are first pulled away (20um in `z`) before the stages are
        centred.  After the centering the fibres are pushed back (20um in `z`).

        Args:
            y_ctr_around_line_um (float, None): The position in y
                around which to centre the stages.  If `None`, half
                the maximum swing of the stages will be used.

        Returns:
            float: The distance the y-axes are away from
            `y_ctr_around_line_um`.
        '''
        y_move_rel_um = self._ctr_in_out_y_axes(y_ctr_around_line_um)

        # Pull fibres away.
        self.input.z.move_rel_um(-20.)
        self.output.z.move_rel_um(-20.)

        # Centre everything.
        y_in = self.input.y.move_rel_um(y_move_rel_um)
        y_out = self.output.y.move_rel_um(y_move_rel_um)
        y_chip = self.chip.y.move_rel_um(y_move_rel_um)

        # Put fibres back.
        self.input.z.move_rel_um(20.)
        self.output.z.move_rel_um(20.)

        return y_in, y_out, y_chip

    def ctr_in_out_xy_axes(self, x_ctr_around_line_um=None, y_ctr_around_line_um=None):
        '''
        Convenience function that centres in both `x` and `y`.

        Essentially calls `ctr_in_out_x_axes` and `ctr_in_out_y_axes`.
        '''
        x_move_rel_um = self._ctr_in_out_x_axes(x_ctr_around_line_um)
        y_move_rel_um = self._ctr_in_out_y_axes(y_ctr_around_line_um)

        # Pull fibres away.
        self.input.z.move_rel_um(-20.)
        self.output.z.move_rel_um(-20.)

        # Centre everything.
        x_in = self.input.x.move_rel_um(x_move_rel_um)
        x_out = self.output.x.move_rel_um(x_move_rel_um)
        z_chip = self.chip.z.move_rel_um(x_move_rel_um)
        y_in = self.input.y.move_rel_um(y_move_rel_um)
        y_out = self.output.y.move_rel_um(y_move_rel_um)
        y_chip = self.chip.y.move_rel_um(y_move_rel_um)

        # Put fibres back.
        self.input.z.move_rel_um(20.)
        self.output.z.move_rel_um(20.)

        return x_in, x_out, z_chip, y_in, y_out, y_chip

    def move_rel_um_x_long(self, move_rel_x_um, move_rel_output_x_um=None, x_ctr_around_line_um=None):
        '''
        Moves both stages in x distances that are greater than they
        could normally move.

        The long movement is accomplished by moving the chip.
        Essentially, the stages are first centred around
        `x_ctr_around_line_um` and then the chip is moved (in z) the
        appropriate distance.  This should leave the x-axis
        of the stages with maximum swing in a desired direction
        as well having effectively moved the input and output
        a large distance.

        Args:
            move_rel_x_um (int, float): Distance to move
                the input in `x`.  If no output is specified,
                the output will also be moved this same
                distance.  Can be greater than the
                maximum distance in `x` the stage can move.
            move_rel_output_x_um (int, float): Distance to move
                the output in `x`.  Can be greater than the
                maximum distance in `x` the stage can move.
            x_ctr_around_line_um (float, None): The position in x
                around which to centre the stages.  If `None`, half
                the maximum swing of the stages will be used.

        Returns:
            float: The input stage\'s  (x,y,z) coordinates.
            float: The output stage\'s  (x,y,z) coordinates.
            float: The chip stage\'s (x,y,z) coordinates.
        '''
        if not move_rel_output_x_um:
            move_rel_x_um = move_rel_output_x_um

        assert abs(move_rel_x_um - move_rel_output_x_um) < self.input.x.get_position_absolute_max_um(), \
                'Difference between x moves is too large.'

        x_move_rel_um = self._ctr_in_out_x_axes(x_ctr_around_line_um)

        x_move_rel_long_chip = 0.5*(move_rel_x_um + move_rel_output_x_um)
        x_move_rel_long_in = x_move_rel_long_chip - move_rel_x_um
        x_move_rel_long_out = x_move_rel_long_chip - move_rel_output_x_um

        c = self.chip.z.move_rel_um(x_move_rel_um + x_move_rel_long_chip)
        i = self.input.x.move_rel_um(x_move_rel_um + x_move_rel_long_in)
        o = self.output.x.move_rel_um(x_move_rel_um + x_move_rel_long_out)

        return i, o, c

    def move_rel_um_c_long(self, move_rel_c_um, move_rel_output_c_um=None, c_ctr_around_line_um=None):
        '''
        Same as `move_rel_um_x_long` except along the C-axis.
        '''
        if not move_rel_output_c_um:
            move_rel_output_c_um = move_rel_c_um

        x_rel_in_um, y_rel_in_um, z_rel_in_um = self.input.c._get_xyz_rel_move_um(move_rel_c_um)
        x_rel_out_um, y_rel_out_um, z_rel_out_um = self.output.c._get_xyz_rel_move_um(move_rel_output_c_um)

        # Move rel in z if negative movement.
        if z_rel_in_um < 0.:
            zi = self.input.z.move_rel_um(z_rel_in_um)
        if z_rel_out_um < 0.:
            zo = self.output.z.move_rel_um(z_rel_out_um)

        # Move chip
        xi, xo, c = self.move_rel_um_x_long(x_rel_in_um, x_rel_out_um, c_ctr_around_line_um)

        # Move rel in z if positive movement.
        if z_rel_in_um >= 0.:
            zi = self.input.z.move_rel_um(z_rel_in_um)
        if z_rel_out_um >= 0.:
            zo = self.output.z.move_rel_um(z_rel_out_um)

        # Move rel in y.
        self.input.y.move_rel_um(y_rel_in_um)
        self.output.y.move_rel_um(y_rel_out_um)

        return (xi,zi), (xo,zo), c

    def move_rel_um_xc_long(self, move_rel_xc_um, move_rel_output_xc_um=None, xc_ctr_around_line_um=None):
        '''
        Same as `move_rel_um_x_long` except along the XC-axis.
        '''
        if not move_rel_output_xc_um:
            move_rel_output_xc_um = move_rel_xc_um

        if self.input.c and self.output.c:
            r = self.move_rel_um_c_long(move_rel_xc_um, move_rel_output_xc_um, xc_ctr_around_line_um)
        else:
            r = self.move_rel_um_x_long(move_rel_xc_um, move_rel_output_xc_um, xc_ctr_around_line_um)
        return r

    def _push_pos_xyz(self, stack):
        xyz = {}
        xyz['in'] = self.input.get_current_position_um()
        xyz['out'] = self.output.get_current_position_um()
        xyz['chip'] = self.chip.get_current_position_um()
        stack.append(xyz)
        return stack

    def _pop_pos_xyz(self, stack, retract_fibres=True):
        xyz = stack.pop()
        x_in, y_in, z_in = xyz['in']
        x_out, y_out, z_out = xyz['out']
        x_chip, y_chip, z_chip = xyz['chip']

        # Pull fibres away from chip.
        if retract_fibres:
            self.input.z.move_rel_um(-50)
            self.output.z.move_rel_um(-50)

        # Move everything into place.
        self.input.x.move_abs_um(x_in)
        self.input.y.move_abs_um(y_in)
        self.output.x.move_abs_um(x_out)
        self.output.y.move_abs_um(y_out)
        self.chip.x.move_abs_um(x_chip)
        self.chip.y.move_abs_um(y_chip)
        self.chip.z.move_abs_um(z_chip)

        # Move input and output fibres to their correct position.
        self.input.z.move_abs_um(z_in)
        self.output.z.move_abs_um(z_out)

        return stack

class Stage(object, metaclass=abc.ABCMeta):
    '''
    Abstract interface class for a stage.

    A class that should be derived off of to implement a
    stage with N axes.

    Attributes:
        num_stages (int): The number of stages that
            have been created.
        x (AxisX): The x-axis.
        y (AxisX): The y-axis.
        z (AxisX): The z-axis.
        roll (AxisRoll): The roll-axis.
        pitch (AxisPitch): The pitch-axis.
        yaw (AxisYaw): The yaw-axis.
        c (AxisChip): The chip-axis.
        xc (AxisX or AxisChip): The chip-axis if it exists,
            otherwise the x-axis.
        axes (dict): Dictionary of all axes (includes c, xc
            and cx).
        axes_physics (dict): Dictionary of all physical axes
            (does not includes c, xc and cx).

    Args:
        axis (dict): A dictionary continaing the all the
            stages.  Valid dictionary keys include
            \'x\', \'y\', \'z\', \'roll\', c'pitch\' and
            \'yaw\'.  Valid dictionary values are objects
            derived from the `Axis` class.
        C1 (tuple(float, float, float)): Three floats
            representing (x,y,z) of the first coordinate.
            `C1` is used as the first coordinate for the `c`
            axis.  If `None`, no `c` axis will be created.
        C2 (tuple(float, float, float)): Three floats
            representing (x,y,z) of the second coordinate.
            `C2` is used as the first coordinate for the `c`
            axis.  If `None`, no `c` axis will be created.
        filename (str, file, None): A string or open filestream
            to save the x, y and z coordinates of the stage to.
            If `None`, doesn\'t store any data.
        reverse_axis_x (bool): Reverses the x-axis\'s direction;
            0 -> x_max and x_max becomes 0.
        reverse_axis_y (bool): Reverses the y-axis\'s direction;
            0 -> y_max and y_max becomes 0.
        reverse_axis_z (bool): Reverses the z-axis\'s direction;
            0 -> z_max and z_max becomes 0.
        x_axis_motor (str): The motor axis to assign to x-axis
            movements.  Can either be 'x', 'y' or 'z'.
        y_axis_motor (str): The motor axis to assign to y-axis
            movements.  Can either be 'x', 'y' or 'z'.
        z_axis_motor (str): The motor axis to assign to z-axis
            movements.  Can either be 'x', 'y' or 'z'.
    '''
    num_stages = 0

    def __init__(self, axes_dict, C1=None, C2=None, c1_c2_distance_mask_um=None,
                 C1_z_chip=None, C2_z_chip=None,
                 reverse_axis_x=False, reverse_axis_y=False, reverse_axis_z=False,
                 x_axis_motor='x', y_axis_motor='y', z_axis_motor='z',
                 filename=None):
        Stage.num_stages += 1
        self.axes = axes_dict

        # Assign None to any axes that weren't provided.
        axes_str = tuple(['x', 'y', 'z', 'roll', 'pitch', 'yaw'])
        for axis_str in axes_str:
            if axis_str not in self.axes:
                self.axes[axis_str] = None

        # Swap x, y and z axes.
        self.axes['x'], self.axes['y'], self.axes['z'] = self.axes[x_axis_motor], \
            self.axes[y_axis_motor], self.axes[z_axis_motor]

        self.axes_physical = copy.copy(self.axes)

        if None not in (C1, C2, C1_z_chip, C2_z_chip):
            c1 = copy.copy(C1)
            c2 = copy.copy(C2)
            self.set_c_axis(c1, c2, C1_z_chip, C2_z_chip, c1_c2_distance_mask_um)
        else:
            self.axes['c'] = None

        if self.axes['c']:
            self.axes['xc'] = self.axes['c']
        else:
            self.axes['xc'] = self.axes['x']
        self.axes['cx'] = self.axes['xc']

        # More convenient ways to access the axes.
        for axis_str, axis in self.axes.items():
            setattr(self, axis_str, axis)

        if filename:
            logger = log.LoggerStage(filename, self)
            self._set_logger(logger)

    def __del__(self):
        self.num_stages -= 1

    def __str__(self):
        return 'Stage with %s axes.' % ', '.join(self.axes_physical.keys())

    def _set_logger(self, logger):
        self.x._set_logger(logger)
        self.y._set_logger(logger)
        self.z._set_logger(logger)
        return logger

    def _clear_logger(self):
        logger = None
        self.x._set_logger(logger)
        self.y._set_logger(logger)
        self.z._set_logger(logger)
        return logger

    def get_current_position_nm(self):
        '''
        Gets the current position of the stages in [nm].

        Returns:
            float: x-coordinate.
            float: y-coordinate.
            float: z-coordinate.
        '''
        if self.x:
            x = self.x.get_current_position_nm()
        else:
            x = None
        if self.y:
            y = self.y.get_current_position_nm()
        else:
            y = None
        if self.z:
            z = self.z.get_current_position_nm()
        else:
            z = None
        return (x, y, z)

    def get_current_position_arc_second(self):
        '''
        Gets the current position of the stages in [arc second].

        Returns:
            float: roll-coordinate.
            float: pitch-coordinate.
            float: yaw-coordinate.
        '''
        if self.roll:
            r = self.roll.get_current_position_arc_second()
        else:
            r = None
        if self.pitch:
            p = self.pitch.get_current_position_arc_second()
        else:
            p = None
        if self.yaw:
            y = self.yaw.get_current_position_arc_second()
        else:
            y = None
        return (r, p, y)

    def get_current_position_um(self):
        return tuple(v/1000. if v != None else None \
                for v in self.get_current_position_nm())

    def get_current_position_degree(self):
        return tuple(v/3600. if v != None else None \
                for v in self.get_current_position_arc_second())

    def get_current_position_um_degree(self):
        um = list(self.get_current_position_um())
        deg = list(self.get_current_position_degree())
        um.extend(deg)
        return tuple(um)

    def set_c_axis(self, C1, C2, C1_z_chip, C2_z_chip, c1_c2_distance_mask_um=None):
        '''
        Defines the `c` axis.

        C1=(x1,y1,z1) and C2=(x2,y2,z2) are the two coordinates through
        which the C-axis will pass.

        Args:
            C1 (tuple(float, float, float)): Three floats
                representing (x,y,z) of the first coordinate.
                `C1` is used as the first coordinate for the `c`
                axis.  If `None`, no `c` axis will be created.
            C2 (tuple(float, float, float)): Three floats
                representing (x,y,z) of the second coordinate.
                `C2` is used as the first coordinate for the `c`
                axis.  If `None`, no `c` axis will be created.
        '''
        C1[0] *= -1.
        C2[0] *= -1.
        C1[0] += C1_z_chip
        C2[0] += C2_z_chip

        self.axes['c'] = AxisChip(self.axes['x'], self.axes['y'], self.axes['z'],
                                  C1, C2, c1_c2_distance_mask_um)

    def move_abs_nm(self, pos_x, pos_y, pos_z):
        if pos_x:
            self.x.move_abs_nm(pos_x)
        if pos_y:
            self.y.move_abs_nm(pos_y)
        if pos_z:
            self.z.move_abs_nm(pos_z)
        return pos_x, pos_y, pos_z

    def move_abs_um(self, pos_x, pos_y, pos_z):
        if pos_x:
            pos_x *= 1.e3
        if pos_y:
            pos_y *= 1.e3
        if pos_z:
            pos_z *= 1.e3
        return self.move_abs_nm(pos_x, pos_y, pos_z)

    def move_abs_arc_second(self, pos_roll, pos_pitch, pos_yaw):
        if pos_roll:
            self.roll.move_abs_arc_second(pos_roll)
        if pos_pitch:
            self.pitch.move_abs_arc_second(pos_pitch)
        if pos_yaw:
            self.yaw.move_abs_arc_second(pos_yaw)
        return pos_roll, pos_pitch, pos_yaw

    def move_abs_degree(self, pos_roll, pos_pitch, pos_yaw):
        if pos_roll:
            pos_roll *= 3600.
        if pos_pitch:
            pos_pitch *= 3600.
        if pos_yaw:
            pos_yaw *= 3600.
        return self.move_abs_arc_second(pos_roll, pos_pitch, pos_yaw)

    def move_abs_um_degree(self, pos_x, pos_y, pos_z, pos_roll, pos_pitch, pos_yaw):
        r1 = list(self.move_abs_um(pos_x, pos_y, pos_z))
        r2 = list(self.move_abs_degree(pos_roll, pos_pitch, pos_yaw))
        r1.extend(r2)
        return r1

    def write_position_um_to_json(self, filename):
        pos = self.get_current_position_um()
        with open(filename, 'w') as fs:
            json.dump(pos, fs)
        return pos

    def write_position_degree_to_json(self, filename):
        pos = self.get_current_position_degree()
        with open(filename, 'w') as fs:
            json.dump(pos, fs)
        return pos

    def write_position_um_degree_to_json(self, filename):
        pos = self.get_current_position_um_degree()
        with open(filename, 'w') as fs:
            json.dump(pos, fs)
        return pos

    @staticmethod
    def load_position_from_json(filename):
        with open(filename, 'r') as fs:
            pos = json.load(fs)
        return pos

class Axis(object, metaclass=abc.ABCMeta):
    '''
    Interface class used to define an arbitrary axis.
    '''
    def __init__(self, reverse_axis=False, logger=None, update_position_absolute=100):
        self.axis_reversed = reverse_axis
        self._update_position_absolute_limit = update_position_absolute
        self._update_position_absolute_counter = 0
        self._logger = logger

    def _get_current_position(self):
        # This function doesn't reverse with the axis for the parent.
        return self._position_absolute

    def _set_logger(self, logger):
        self._logger = logger
        return self._logger

    def _clear_logger(self):
        self._logger = None
        return self._logger

    def _update_position_absolute(self):
        if self._update_position_absolute:
            if self._update_position_absolute_counter >= self._update_position_absolute_limit:
                self._position_absolute = self._get_current_position()
                self._update_position_absolute_counter = 0
            self._update_position_absolute_counter += 1
        return self._position_absolute

    def position_absolute_within_bounds(self, position):
        raise NotImplementedError

class AxisLinear(Axis, metaclass=abc.ABCMeta):
    def __init__(self, reverse_axis=False, logger=None, update_position_absolute=100):
        # `_position absolute` is in [nm].
        self._position_absolute = self._get_current_position_nm()
        self._position_absolute_start = self._position_absolute
        super().__init__(reverse_axis, logger, update_position_absolute)

    @abc.abstractmethod
    def _move_abs_nm(self, distance_from_home_nm):
        pass

    @abc.abstractmethod
    def _get_current_position_nm(self):
        pass

    @abc.abstractproperty
    def _position_absolute_min_nm(self):
        '''
        Gets the minimum absolute position the axis can
        move to.

        Returns:
            float: The minimum absolute position the axis
            can move to.
        '''
        pass

    @abc.abstractproperty
    def _position_absolute_max_nm(self):
        '''
        Gets the maximum absolute position the axis can
        move to.

        Returns:
            float: The maximum absolute position the axis
            can move to.
        '''
        pass

    def _move_abs(self, distance_from_home_nm):
        if self.axis_reversed:
            distance_from_home_nm = self._position_absolute_max_nm - distance_from_home_nm

        if distance_from_home_nm == self._position_absolute:
            # Don't issue a move or log if the position hasn't changed.
            r = distance_from_home_nm
        else:
            self._position_absolute = distance_from_home_nm
            self._position_absolute = self.position_absolute_within_bounds(self._position_absolute)
            r = self._move_abs_nm(self._position_absolute)

            if self._logger:
                self._logger.log()

        if self._update_position_absolute_counter == self._update_position_absolute:
            self._update_position_absolute()
        self._update_position_absolute_counter += 1

        return r

    def _move_rel(self, distance_nm):
        if self.axis_reversed:
            distance_nm *= -1.

        if distance_nm == 0.:
            # Don't issue a move or log if the position hasn't changed.
            r = distance_nm
        else:
            self._position_absolute += distance_nm
            self._position_absolute = self.position_absolute_within_bounds(self._position_absolute)
            r = self._move_abs_nm(self._position_absolute)
            self._update_position_absolute()

            if self._logger:
                self._logger.log()

        return r

    def _get_current_position(self):
        # This function doesn't reverse with the axis for the parent.
        return self._get_current_position_nm()

    def position_absolute_within_bounds(self, position_absolute):
        '''
        Checks whether an absolute position is within bounds.

        Will throw a `ValueError` if the position is not
        within the maximum and minimum bounds.

        Returns:
            float: The absolute position passed in.
        '''
        if position_absolute < self.get_position_absolute_min_nm():
            raise ValueError('%s-axis target movement `%.3f` [um] is too small.' \
                             % (self.name, position_absolute/1000.))
        if position_absolute > self.get_position_absolute_max_nm():
            raise ValueError('%s-axis target movement `%.3f` [um] is too large.' \
                             % (self.name, position_absolute/1000.))
        return position_absolute

    def move_abs_nm(self, distance_from_home_nm):
        '''
        Move axis to absolute position in [nm] from home.

        Args:
            distance_from_home_nm (float): Distance in [nm]
                from the import home position to move.

        Returns:
            float: The position of the axis in [nm] after the
                movement.
        '''
        return self._move_abs(distance_from_home_nm)

    def move_abs_um(self, distance_from_home_um):
        '''
        Convenience function for `move_abs_nm` in [um].
        '''
        return self._move_abs(distance_from_home_um * 1000.) / 1000.

    def move_abs_mm(self, distance_from_home_mm):
        '''
        Convenience function for `move_abs_nm` in [mm].
        '''
        return self._move_abs(distance_from_home_mm * 1e6) / 1e6

    def move_rel_nm(self, distance_nm):
        '''
        Move axis a relative distance from its current position
        in [nm].

        distance_nm (float): The relative distance in [nm] to move
            from the current position.

        Returns:
            float: The position of the axis in [nm] after the
                movement.
        '''
        r = self._move_rel(distance_nm)
        return r

    def move_rel_um(self, distance_um):
        '''
        Convenience function for `move_rel_nm` in [um].
        '''
        r = self.move_rel_nm(distance_um * 1000.)
        return r / 1000.

    def move_rel_mm(self, distance_mm):
        '''
        Convenience function for `move_rel_nm` in [mm].
        '''
        r = self.move_rel_nm(distance_mm * 1e6)
        return r / 1e6

    def get_current_position_nm(self):
        '''
        Gets the current position of the axis in [nm].

        Returns:
            float: The current position of the axis (relative
                to home) in [nm].
        '''
        pos_abs_nm = self._get_current_position()
        if self.axis_reversed:
            pos_abs_nm = self._position_absolute_max_nm - pos_abs_nm
        return pos_abs_nm

    def get_current_position_um(self):
        '''
        Convenience function for `get_current_position_nm` in [um].
        '''
        return self.get_current_position_nm() / 1000.

    def get_current_position_mm(self):
        '''
        Convenience function for `get_current_position_nm` in [mm].
        '''
        return self.get_current_position_nm() / 1e6

    def get_absolute_position_start_nm(self):
        '''
        Gets the position relative to home in [nm] of the
        axis when the class was created.

        Returns:
            float: The position relative to home in [nm] of the
                axis when the class was created.
        '''
        return self._position_absolute_start

    def get_absolute_position_start_um(self):
        '''
        Convenience function for `get_absolute_position_start_nm` in [um].
        '''
        return self._position_absolute_start / 1000.

    def get_position_absolute_min_nm(self):
        '''
        Gets the minimum position relative to home in [nm]
        that the stage can move to.

        Returns:
            float: The minimum position relative to home in [nm]
                that the stage can move to.
        '''
        return self._position_absolute_min_nm

    def get_position_absolute_min_um(self):
        '''
        Convenience function for `get_position_absolute_min_nm` in [um].
        '''
        return self._position_absolute_min_nm / 1000.

    def get_position_absolute_max_nm(self):
        '''
        Gets the maximum position relative to home in [nm]
        that the stage can move to.

        Returns:
            float: The maximum position relative to home in [nm]
                that the stage can move to.
        '''
        return self._position_absolute_max_nm

    def get_position_absolute_max_um(self):
        '''
        Convenience function for `get_position_absolute_max_um` in [um].
        '''
        return self._position_absolute_max_nm / 1000.

class AxisRotate(Axis, metaclass=abc.ABCMeta):
    '''
    Interface class for a rotational axis (roll, pitch or yaw).
    '''
    def __init__(self, reverse_axis=False, logger=None, update_position_absolute=100):
        # `_position absolute` is in [arcsecond].
        self._position_absolute = self._get_current_position_arc_second()
        self._position_absolute_start = self._position_absolute
        super().__init__(reverse_axis, logger, update_position_absolute)

    @abc.abstractmethod
    def _move_abs_arc_second(self, distance_from_home_arc_second):
        pass

    @abc.abstractmethod
    def _get_current_position_arc_second(self):
        pass

    @abc.abstractproperty
    def _position_absolute_min_arc_second(self):
        '''
        Gets the minimum absolute position the axis can
        move to.

        Returns:
            float: The minimum absolute position the axis
            can move to.
        '''
        pass

    @abc.abstractproperty
    def _position_absolute_max_arc_second(self):
        '''
        Gets the maximum absolute position the axis can
        move to.

        Returns:
            float: The maximum absolute position the axis
            can move to.
        '''
        pass

    def _move_abs(self, angle_from_home_arc_second):
        if self.axis_reversed:
            angle_from_home_arc_second = self._position_absolute_max_arc_second - angle_from_home_arc_second

        if angle_from_home_arc_second == self._position_absolute:
            # Don't issue a move or log if the position hasn't changed.
            r = angle_from_home_arc_second
        else:
            self._position_absolute = angle_from_home_arc_second
            self._position_absolute = self.position_absolute_within_bounds(self._position_absolute)
            r = self._move_abs_arc_second(self._position_absolute)

            if self._logger:
                self._logger.log()

        self._update_position_absolute()

        return r

    def _move_rel(self, angle_arc_second):
        if self.axis_reversed:
            angle_arc_second *= -1.

        if angle_arc_second == 0.:
            # Don't issue a move or log if the position hasn't changed.
            r = angle_arc_second
        else:
            self._position_absolute += angle_arc_second
            self._position_absolute = self.position_absolute_within_bounds(self._position_absolute)
            r = self._move_abs_arc_second(self._position_absolute)
            self._update_position_absolute()

        return r

    def _get_current_position(self):
        # This function doesn't reverse with the axis for the parent.
        return self._get_current_position_arc_second()

    def position_absolute_within_bounds(self, position_absolute):
        '''
        Checks whether an absolute position is within bounds.

        Will throw a `ValueError` if the position is not
        within the maximum and minimum bounds.

        Returns:
            float: The absolute position passed in.
        '''
        if position_absolute < self.get_position_absolute_min_arc_second():
            raise ValueError('%s-axis target movement `%.3f` [degree] is too small.' \
                             % (self.name, position_absolute/3600.))
        if position_absolute > self.get_position_absolute_max_arc_second():
            raise ValueError('%s-axis target movement `%.3f` [degree] is too large.' \
                             % (self.name, position_absolute/3600.))
        return position_absolute

    def move_abs_arc_second(self, angle_from_home_arc_second):
        '''
        Move axis to absolute position in [arc second] from home.

        Args:
            distance_from_home_arc_second (float): Distance in [arc second]
                from the import home position to move.

        Returns:
            float: The position of the axis in [arc second] after the
                movement.
        '''
        return self._move_abs(angle_from_home_arc_second)

    def move_abs_degree(self, angle_from_home_degree):
        '''
        Convenience function for `move_abs_arc` in [degree].
        '''
        return self._move_abs(angle_from_home_degree * 3600.) / 3600.

    def move_rel_arc_second(self, angle_arc_second):
        '''
        Move axis a relative distance from its current position
        in [arc second].

        distance_arc second (float): The relative distance in [arc second] to move
            from the current position.

        Returns:
            float: The position of the axis in [arc second] after the
                movement.
        '''
        return self._move_rel(angle_arc_second)

    def move_rel_degree(self, angle_degree):
        '''
        Convenience function for `move_rel_arc_second` in [degree].
        '''
        return self._move_rel(angle_degree * 3600.) / 3600.

    def get_current_position_arc_second(self):
        '''
        Gets the current position of the axis in [arc second].

        Returns:
            float: The current position of the axis (relative
                to home) in [arc second].
        '''
        pos_abs_arc_second = self._get_current_position()
        if self.axis_reversed:
            pos_abs_arc_second = self._position_absolute_max_arc_second - pos_abs_arc_second
        return pos_abs_arc_second

    def get_current_position_degree(self):
        '''
        Convenience function for `get_current_position_arc_second` in [degree].
        '''
        return self.get_current_position_arc_second() / 3600.

    def get_absolute_position_start_arc_second(self):
        '''
        Gets the position relative to home in [arc second] of the
        axis when the class was created.

        Returns:
            float: The position relative to home in [arc second] of the
                axis when the class was created.
        '''
        return self._position_absolute_start

    def get_absolute_position_start_degree(self):
        '''
        Convenience function for `get_absolute_position_start_arc_second` in [degree].
        '''
        return self._position_absolute_start / 3600.

    def get_position_absolute_min_arc_second(self):
        '''
        Gets the minimum position relative to home in [arc second]
        that the stage can move to.

        Returns:
            float: The minimum position relative to home in [arc second]
                that the stage can move to.
        '''
        return self._position_absolute_min_arc_second

    def get_position_absolute_min_degree(self):
        '''
        Convenience function for `get_position_absolute_min_arc_second` in [arc second].
        '''
        return self._position_absolute_min_arc_second / 3600.

    def get_position_absolute_max_arc_second(self):
        '''
        Gets the maximum position relative to home in [arc second]
        that the stage can move to.

        Returns:
            float: The maximum position relative to home in [arc second]
                that the stage can move to.
        '''
        return self._position_absolute_max_arc_second

    def get_position_absolute_max_degree(self):
        '''
        Convenience function for `get_position_absolute_max_degree` in [degree].
        '''
        return self._position_absolute_max_arc_second / 3600.

class AxisX(AxisLinear, metaclass=abc.ABCMeta):
    '''
    Interface class for an x-axis.

    The x-axis is the horizontal axis that moves along the chip.

    Attributes:
        name (str): The name of the axis, \'x\'.
    '''
    def __init__(self, reverse_axis=False, logger=None, update_position_absolute=100):
        self.name = 'x'
        super().__init__(reverse_axis, logger, update_position_absolute)

class AxisY(AxisLinear, metaclass=abc.ABCMeta):
    '''
    Interface class for an y-axis.

    The y-axis is the horizontal axis that moves along the chip.

    Attributes:
        name (str): The name of the axis, \'y\'.
    '''
    def __init__(self, reverse_axis=False, logger=None, update_position_absolute=100):
        self.name = 'y'
        super().__init__(reverse_axis, logger, update_position_absolute)

class AxisZ(AxisLinear, metaclass=abc.ABCMeta):
    '''
    Interface class for an z-axis.

    The z-axis is the horizontal axis that moves along the chip.

    Attributes:
        name (str): The name of the axis, \'z\'.
    '''
    def __init__(self, reverse_axis=False, logger=None, update_position_absolute=100):
        self.name = 'z'
        super().__init__(reverse_axis, logger, update_position_absolute)

class AxisRoll(AxisRotate, metaclass=abc.ABCMeta):
    '''
    Interface class for an roll-axis.

    The roll-axis is the horizontal axis that moves along the chip.

    Attributes:
        name (str): The name of the axis, \'roll\'.
    '''
    def __init__(self, reverse_axis=False, logger=None, update_position_absolute=100):
        self.name = 'roll'
        super().__init__(reverse_axis, logger, update_position_absolute)

class AxisYaw(AxisRotate, metaclass=abc.ABCMeta):
    '''
    Interface class for an yaw-axis.

    The yaw-axis is the horizontal axis that moves along the chip.

    Attributes:
        name (str): The name of the axis, \'yaw\'.
    '''
    def __init__(self, reverse_axis=False, logger=None, update_position_absolute=100):
        self.name = 'pitch'
        super().__init__(reverse_axis, logger, update_position_absolute)

class AxisPitch(AxisRotate, metaclass=abc.ABCMeta):
    '''
    Interface class for an pitch-axis.

    The pitch-axis is the horizontal axis that moves along the chip.

    Attributes:
        name (str): The name of the axis, \'pitch\'.
    '''
    def __init__(self, reverse_axis=False, logger=None, update_position_absolute=100):
        self.name = 'yaw'
        super().__init__(reverse_axis, logger, update_position_absolute)

class AxisChip(object):
    '''
    Transformed axis to move between linearly along a line
    defined by two points.

    Attributes:
        c1_um (np.array): The (x,y,z) [um] for the first coordinate.
        c2_um (np.array): The (x,y,z) [um] for the second coordinate.
    '''
    def __init__(self, x_axis, y_axis, z_axis, c1_um, c2_um,
                 c1_c2_distance_mask_um=None, reverse_axis=False):
        self.x_axis = x_axis
        self.y_axis = y_axis
        self.z_axis = z_axis

        self.c1_um = np.array(c1_um)
        self.c2_um = np.array(c2_um)
        c1c2_um = self.c2_um - self.c1_um
        if reverse_axis:
            c1c2_um *= -1.
        self._d = np.linalg.norm(c1c2_um)
        if c1_c2_distance_mask_um:
            self._e = self._d / c1_c2_distance_mask_um
        else:
            self._e = 1.
        self._v = c1c2_um / c1c2_um[0] * self._e

    def _get_xyz_rel_move_um(self, rel_move_um):
        x, y, z = rel_move_um*self._v
        return x, y, z

    def _get_xyz_rel_move_nm(self, rel_move_nm):
        c = self._get_xyz_rel_move_um(rel_move_nm/1000.)
        return tuple(v*1000. for v in c)

    def move_rel_um(self, distance_rel_um):
        x_rel, y_rel, z_rel = self._get_xyz_rel_move_um(distance_rel_um)
        if z_rel < 0.:
            z_rel = self.z_axis.move_rel_um(z_rel)
            x_rel = self.x_axis.move_rel_um(x_rel)
        else:
            x_rel = self.x_axis.move_rel_um(x_rel)
            z_rel = self.z_axis.move_rel_um(z_rel)
        y_rel = self.y_axis.move_rel_um(y_rel)
        return np.linalg.norm((x_rel, y_rel, z_rel))

    def move_rel_nm(self, distance_rel_nm):
        return self.move_rel_um(distance_rel_nm/1000.)

    def get_current_position_nm(self):
        '''
        Gets the current position along the axis in [nm].

        This function does not return the position along
        the C-axis, rather, the current absolute position
        of the x and z axes.

        Returns:
            x (float): The absolute value of x.
            z (float): The absolute value of z.
        '''
        x_pos_nm = self.x_axis.get_current_position_nm()
        y_pos_nm = self.y_axis.get_current_position_nm()
        z_pos_nm = self.z_axis.get_current_position_nm()
        return x_pos_nm, y_pos_nm, z_pos_nm

    def get_current_position_um(self):
        pos = self.get_current_position_nm()
        return tuple(p/1000. for p in pos)

    def get_distance_c1_to_c2_nm(self):
        return self.get_distance_c1_to_c2_um()*1000.

    def get_distance_c1_to_c2_um(self):
        return self._d

    def get_distance_from_c1_um(self, c_um):
        c = np.array(c_um)
        return np.linalg.norm(c-self.c1_um)

    def get_distance_from_c2_um(self, c_um):
        c = np.array(c_um)
        return np.linalg.norm(c-self.c2_um)

