import abc
import copy
import os
import numpy as np
import tqdm
from collections import deque
from . import stage as st
from .luminos_stage import luminos_stage as ls
from ..utils import gnuplot as gp


def _unique(seq):
    seen = set()
    return [seen.add(x) or x for x in seq if x not in seen]

class ScannerDesign:
    '''
    A list-style object containing a group of `scan` objects.

    Supports performing various nested scans and chains of scans.
    '''
    def __init__(self):
        self._get_pos_list = []
        self._set_pos_list = []

        self._steps = deque()
        self._scan_types = deque()

    def _add(self, scans):
        '''
        Adds a list of `scan` objects.  When `scan(...)`
        is called, all scans in the list will be run
        sequentially, and, if specified, the stages will
        go to the max power at the end of each scan.

        Args:
            scans(list(Scan)): List of `scan` objects.
        '''
        self._steps.append((scans, None))
        self._scan_types.append('scans')

        for scan in scans:
            self._get_pos_list_add(scan._get_pos_funcs)
            self._set_pos_list_add(scan._move_funcs)

    def _add_nested(self, nested_scan, outer_scan):
        '''
        Adds a nested scan step.  The nested scan
        performs the `nested_scan` scan in the
        `outer_scan` scan.

        Args:
            nested_scan(Scan): The nested scan.
            outer_scan(Scan): The outer scan.
        '''
        self._steps.append((nested_scan, outer_scan))
        self._scan_types.append('nested')

        self._get_pos_list_add(nested_scan._get_pos_funcs)
        self._set_pos_list_add(nested_scan._move_funcs)
        self._get_pos_list_add(outer_scan._get_pos_funcs)
        self._set_pos_list_add(outer_scan._move_funcs)

    def _add_nested_each_max(self, nested_scans, outer_scan):
        '''
        Adds a nested scan step that goes to max after
        each nested scan scan.

        Args:
            nested_scans(list(Scans)): A list of the nested
                scans.
            outer_scan(Scan): The outer scan.
        '''
        self._steps.append((nested_scans, outer_scan))
        self._scan_types.append('nested_goto_max')

        for nested_scan in nested_scans:
            self._get_pos_list_add(nested_scan._get_pos_funcs)
            self._set_pos_list_add(nested_scan._move_funcs)
        self._get_pos_list_add(outer_scan._get_pos_funcs)
        self._set_pos_list_add(outer_scan._move_funcs)

    def _get_pos_list_add(self, get_pos_list):
        self._get_pos_list.extend(get_pos_list)
        self._get_pos_list = _unique(self._get_pos_list)
        return self._get_pos_list

    def _set_pos_list_add(self, set_pos_list):
        self._set_pos_list.extend(set_pos_list)
        self._set_pos_list = _unique(self._set_pos_list)
        return self._set_pos_list

    def _get_stages_pos(self):
        pos = [get_pos() for get_pos in self._get_pos_list]
        return pos

    def _restore_stages_pos(self, pos):
        for p, mf in zip(pos, self._set_pos_list):
            mf(p)

    def _scan(self, scans, goto_max):
        # Get initial pos.
        pos_init = self._get_stages_pos()

        # Do all scans in step.
        coords_pows = []
        for scan in scans:
            coords_pows.append(scan.scan(goto_max))

        # Measure power at end of scans.
        pow_final_uW = scans[-1].power_meter.get_power_uW()

        return coords_pows

    def _scan_nested(self, scan, outer_scan, goto_max=True):
        # Get initial pos.
        pos_init = self._get_stages_pos()

        # Override and apply offsets
        # Probably `outer_scan` doesn't actually require this, just `scan` does.
        s_tmp = [None, None]
        for i, s in enumerate([outer_scan, scan]):
            if len(s.offsets):
                axes_pos = np.array([get_pos() for get_pos in s._get_pos_funcs])
                s._move_abs(axes_pos + s.offsets)
                s_tmp[i] = copy.copy(s.offsets)
                s.offsets = []

        # Do scan.
        coords_for_each, coords_pows = outer_scan.traverse_pattern(scan.scan,
            kwargs={'goto_max': False})
        print()

        # Sort all coords from both scans.
        coords_sorted = []
        for coord_for_each, coord_pow in zip(coords_for_each, coords_pows):
            for c, p in zip(coord_pow[0][0], coord_pow[0][1]):
                comb = (coord_for_each, c, p)
                coords_sorted.append(comb)
        coords_sorted_T =  np.array(coords_sorted).T
        idx_max_pow = np.argmax(coords_sorted_T[2])

        # Determine the max power coordinates, and the max power.
        for_every_coord_max_pow = coords_sorted_T[0][idx_max_pow]
        scan_coord_max_pow = coords_sorted_T[1][idx_max_pow]
        max_pow = coords_sorted_T[2][idx_max_pow]

        # If goto_max not set or below threshold, restore original positions.
        pow_final_uW = scan.power_meter.get_power_uW()
        if goto_max:
            self._restore_stages_pos(pos_init)
            scan._move_abs(scan_coord_max_pow)
            outer_scan._move_abs(for_every_coord_max_pow)
        else:
            self._restore_stages_pos(pos_init)

        # Only return max power coords and power value if threshold met.
        r = coords_sorted_T, (for_every_coord_max_pow, scan_coord_max_pow, max_pow)

        # Restore offsets
        if s_tmp[0] != None:
            outer_scan.offsets = s_tmp[0]
        if s_tmp[1] != None:
            scan.offsets = s_tmp[1]

        return r

    def _scan_nested_each_max(self, scans, outer_scan, goto_max=False):
        # Get initial pos.
        pos_init = self._get_stages_pos()

        # Do scan.
        max_pow_pos = []
        max_pows = []
        def scan_all():
            for scan in scans:
                _, coord_max_pow = scan.scan(goto_max=True)
            max_pow_pos.append(self._get_stages_pos())
            max_pows.append(coord_max_pow[1])
            return coord_max_pow

        outer_scan.traverse_pattern(scan_all)

        # Find max.
        idx_mp = np.argmax(max_pows)

        # Move to max pos if specified.
        if goto_max:
            self._restore_stages_pos(pos_init)
            self._restore_stages_pos(max_pow_pos[idx_mp])
        else:
            self._restore_stages_pos(pos_init)

        return max_pow_pos[idx_mp], max_pows[idx_mp]

    def scan(self, goto_max=True):
        for (scans, outer_scan), scan_type in zip(self._steps, self._scan_types):
            if scan_type == 'nested':
                res = self._scan_nested(scans, outer_scan, goto_max)
            elif scan_type == 'nested_goto_max':
                res = self._scan_nested_each_max(scans, outer_scan, goto_max)
            elif scan_type == 'scans':
                res = self._scan(scans, goto_max)
            else:
                assert False

        return res

    def __str__(self):
        recipe = ''

        for i, scans_loop in enumerate(self._steps):
            scan = scans_loop[0]
            loop = scans_loop[1]
            step_str = 'STEP %i:  ' % i
            scan_str = '    SCAN  '
            join_str = '\n' + ' '*len(scan_str) + '   THEN  '
            scan_str += join_str.join([scan.__class__.__name__ + ' USING ' +
                                      ','.join([axis.__class__.__name__ for axis in scan.axes])])

            if loop:
                loop_str = '\n' + ' '*len(step_str) + 'FOR EACH  '
                loop_str += loop.__class__.__name__ + ' USING ' + \
                            ','.join([axis.__class__.__name__ for axis in loop.axes])
            else:
                loop_str = ''

            recipe += step_str + scan_str + ' ' + loop_str + '\n'

        return recipe


class Scan(metaclass=abc.ABCMeta):
    '''
    The general interface a `scan` should adhere to.

    A scan object consists of a set of axes, a pattern function
    defining the path of the axes, as well as a power meter.
    '''
    def __init__(self, axes, power_meter, offsets=[], *args, **kwargs):
        for axis in axes:
            assert issubclass(type(axis), st.Axis) or not axis

        assert len(offsets) in (0, len(axes)), 'Incorrect offset length.'
        self.offsets = np.array(offsets)

        self.axes = axes
        self.power_meter = power_meter
        self.dimensions = len(axes)
        self.pattern = self.__class__._pattern(*args, **kwargs)

        # Flat array of coords
        flat_shape = (np.product(self.pattern.shape[:-1]), self.pattern.shape[-1])
        self.pattern_flat = np.copy(self.pattern).reshape(flat_shape)

        # Determine if move_abs_um or move_abs_degree
        self._move_funcs = []
        self._get_pos_funcs = []
        self._min_max = []
        for axis in axes:
            if issubclass(type(axis), st.AxisLinear):
                self._move_funcs.append(axis.move_abs_um)
                self._get_pos_funcs.append(axis.get_current_position_um)
                self._min_max.append((axis.get_position_absolute_min_um(),
                                      axis.get_position_absolute_max_um()))
            elif issubclass(type(axis), st.AxisRotate):
                self._move_funcs.append(axis.move_abs_degree)
                self._get_pos_funcs.append(axis.get_current_position_degree)
                self._min_max.append((axis.get_position_absolute_min_degree(),
                                      axis.get_position_absolute_max_degree()))

    @staticmethod
    @abc.abstractmethod
    def _pattern(*args, **kwargs):
        '''
        An implementation of the pattern that will be swept.

        All the arguments passed to the constructor captured
        by *args and **kwargs will be passed to this function.

        Return:
            n-dimensional iterable: n-dimensional object that
                returns the coordinates to move to.  The object
                coordinates should be absolute (not relative)
                movements, were (0,0) is the assumed origin of
                the coordinates.
        '''
        pass

    def traverse_pattern(self, func=None, args=[], kwargs={}):
        '''
        Sequentially move the stages to each point in the pattern
        returned by `_pattern()`, calling `func(*args, **kwargs)`
        at each point.

        Args:
            func(function): The function to call at each point.
            args(list): The arguments to pass to `func`.
            kwargs(dict): The kwargs to pass to `func`.

        Returns:
            (list, list): The first list is a flattened version
                of the pattern coordinates, and the second list
                contains the results of calling func.
        '''
        # Backup and set xy axis speeds.
        _luminos_xy_speeds = deque()
        _luminos_xy_accel = deque()
        for axis in self.axes:
            if issubclass(type(axis), (ls.LuminosAxisX, ls.LuminosAxisY)):
                _luminos_xy_speeds.append(axis.get_speed())
                _luminos_xy_speeds.append(axis.get_acceleration())
                axis.set_speed(3000)
                axis.set_acceleration(100)

        axes_pos = np.array([get_pos() for get_pos in self._get_pos_funcs])

        # Apply offset
        if len(self.offsets):
            axes_pos += self.offsets

        coords = np.array([coord+axes_pos for coord in self.pattern_flat])

        for (min, max), coords_axis, axis in zip(self._min_max, coords.T, self.axes):
            assert np.all(min <= coords_axis), \
                'Pattern exceeds %s-axis minimum range.' % axis.name
            assert np.all(coords_axis <= max), \
                'Pattern exceeds %s-axis maximum range.' % axis.name

        results = [None]*coords.shape[0]
        for i, coord in enumerate(tqdm.tqdm(coords, ncols=80)):
            self._move_abs(coord)
            if func:
                results[i] = func(*args, **kwargs)

        # Restore xy axis speeds.
        for axis in self.axes:
            if issubclass(type(axis), (ls.LuminosAxisX, ls.LuminosAxisY)):
                axis.set_speed(_luminos_xy_speeds.popleft())
                axis.set_acceleration(_luminos_xy_speeds.popleft())

        return coords, results

    def scan(self, goto_max=True):
        '''
        Traverse the pattern returned by `_pattern()` and
        measure the power at each point.

        Args:
            goto_max(bool): If `True`, move the axes to the maximum
                power reading measured after the scan.  If `False`,
                return the axes to their original positions (where
                they were before starting scan).

        Returns:
            ((list, list), (2-tuple, float)): The first list is a
                flattened version of the pattern coordinates, and
                the second list contains power readings.  The 2-tuple
                are the (x,y) coordinates of the maximum power of the
                scan, and the float is the maximum power.
        '''
        # Store initial position.
        pos_init = np.array([get_pos() for get_pos in self._get_pos_funcs])

        # Traverse pattern and get max power.
        coords, powers = self.traverse_pattern(self.power_meter.get_power_W)
        powers = np.array(powers)
        coord_max_power = self._get_coord_max_power(coords, powers)

        # Either goto max or restore the initial position.
        if goto_max:
            self._move_abs(pos_init)
            self._move_abs(coord_max_power[0])
        else:
            self._move_abs(pos_init)

        return (coords, powers), coord_max_power

    def _move_abs(self, coord):
        #assert len(coord) == self.dimensions
        for point, move_abs in zip(coord, self._move_funcs):
            move_abs(point)

    def _get_coord_max_power(self, coords, powers):
        idx = np.argmax(powers)
        return coords[idx], powers[idx]

    def __str__(self):
        return self.__class__.__name__ + ': dim ' + str(self.dimensions) \
            + '; axes ' + ','.join([axis.__class__.__name__ for axis in self.axes])


class Rectangle(Scan):
    '''
    A two-dimensional `scan` in a rectangular shape along `axis_1` and
    `axis_2`.
    '''
    def __init__(self, axis_1, axis_2, power_meter,
                 axis_1_pts, axis_2_pts, axis_1_step, axis_2_step,
                 offset=(0,0), meander=True, origin='c'):
        axes = [axis_1, axis_2]
        Scan.__init__(self, axes, power_meter, offset,
                      axis_1_pts, axis_2_pts,
                      axis_1_step, axis_2_step,
                      meander, origin)

    def scan(self, goto_max=False, plot=False):
        r = Scan.scan(self, goto_max)
        (coords, powers), _ = r
        if plot:
            np.savetxt(plot, np.c_[self.pattern_flat.T[0], self.pattern_flat.T[1], powers], '%.6e', ',')
            root, _ = os.path.splitext(plot)
            filename_png = root + '.png'
            plot_args = {
                'filename': plot,
                'filename_png': filename_png,
                'axis_1': self.axes[0].name,
                'axis_2': self.axes[1].name
            }
            path = os.path.abspath(__file__)
            dir_path = os.path.dirname(path)
            gp.Gnuplot(dir_path + '/scanner.gpi', plot_args)
            os.system('display %s' % filename_png)
        return r

    @staticmethod
    def _pattern(axis_1_pts, axis_2_pts, axis_1_step, axis_2_step, meander, *args):
        pts = []
        coord = [None, None]
        axis_1_dist = (axis_1_pts-1) * axis_1_step
        axis_2_dist = (axis_2_pts-1) * axis_2_step
        parity = False
        for n_2 in np.arange(-axis_2_dist/2, (axis_2_dist+0.1*axis_2_step)/2, axis_2_step):
            parity ^= 1
            row = []
            coord[1] = n_2
            for n_1 in np.arange(-axis_1_dist/2, (axis_1_dist+0.1*axis_1_step)/2, axis_1_step):
                coord[0] = n_1
                row.append(np.array(coord))
            if parity and meander:
                pts.append(row[::-1])
            else:
                pts.append(row)

        return np.array(pts)

    @staticmethod
    def plot(pattern, filename='pattern.dat'):
        flat_shape = (np.product(pattern.shape[:-1]), pattern.shape[-1])
        pattern_flat = np.copy(pattern).reshape(flat_shape)
        np.savetxt(filename, pattern_flat)
        filename_image, _ = os.path.splitext(filename)
        filename_image += '.png'
        args = {
            'filename': filename,
            'filename_image': filename_image
        }

        path = os.path.abspath(__file__)
        dir_path = os.path.dirname(path)
        gp.Gnuplot(dir_path+'/pattern.gpi', args)


class RectangleXY(Rectangle):
    def __init__(self, stage, power_meter, x_pts, y_pts, x_step, y_step,
                 offset=(0,0), meander=True, origin='c'):
        axis_1 = stage.axes['x']
        axis_2 = stage.axes['y']
        Rectangle.__init__(self, axis_1, axis_2, power_meter,
                           y_pts, x_pts, y_step, x_step,
                           offset, meander, origin)

    @staticmethod
    def _pattern(axis_1_pts, axis_2_pts, axis_1_step, axis_2_step, meander, origin):
        pts = Rectangle._pattern(axis_1_pts, axis_2_pts, axis_1_step, axis_2_step, meander)
        ref = RectangleXY._set_origin(pts, origin)
        pts += ref
        return pts

    @staticmethod
    def _set_origin(pts, origin):
        assert origin in ('c', 'lm', 'rm', 'tm', 'bm', 'tl', 'tr', 'bl', 'br')
        if origin == 'c':
            ref = (0,0)
        elif origin == 'tl':
            ref = pts[0][-1]
        elif origin == 'tr':
            ref = pts[-1][-1]
        elif origin == 'bl':
            ref = pts[0][0]
        elif origin == 'br':
            ref = pts[-1][0]
        elif origin == 'tm':
            ref_x = 0
            ref_y = pts[0][-1][1]
            ref = (ref_x, ref_y)
        elif origin == 'bm':
            ref_x = 0
            ref_y = pts[0][0][1]
            ref = (ref_x, ref_y)
        elif origin == 'lm':
            ref_x = pts[0][-1][0]
            ref_y = 0
            ref = (ref_x, ref_y)
        elif origin == 'rm':
            ref_x = pts[-1][0][0]
            ref_y = 0
            ref = (ref_x, ref_y)
        return ref


class Diamond(Rectangle):
    def __init__(self, axis_1, axis_2, power_meter,
                 axis_1_pts, axis_2_pts, axis_1_step, axis_2_step,
                 offset=(0,0), meander=True, origin='c'):
        Rectangle.__init__(axis_1, axis_2, power_meter,
                           axis_1_pts, axis_2_pts, axis_1_step, axis_2_step,
                           offset=(0,0), meander=True, origin='c')

    @staticmethod
    def _pattern(axis_1_pts, axis_2_pts,
                 axis_1_step, axis_2_step,
                 meander):
        pattern = Rectangle._pattern(axis_1_pts, axis_2_pts,
                                     axis_1_step, axis_2_step,
                                     meander)
        t = np.array([[np.cos(np.pi/4),-np.sin(np.pi/4)],
                      [np.sin(np.pi/4),np.cos(np.pi/4)]])
        return np.dot(pattern, t)


class Line(Scan):
    def __init__(self, axis, power_meter, axis_pts, axis_step, origin='c'):
        self.origin = origin
        Scan.__init__(self, [axis], power_meter, [], axis_pts, axis_step, origin)

    @staticmethod
    def _pattern(axis_pts, axis_step, origin='c'):
        pts = np.arange(0., axis_pts*axis_step, axis_step)
        if origin == 'c':
            pts -= pts[-1]/2
        elif origin == 'r':
            pts -= pts[-1]
        elif origin == 'l':
            pass
        pts = np.array([[p] for p in pts])
        return pts


class OptimiseRectZ(ScannerDesign):
    def __init__(self, power_meter,
                 stage,
                 axis_x_pts, axis_y_pts, axis_z_pts,
                 axis_x_step, axis_y_step, axis_z_step,
                 offset=(0,0)):
        ScannerDesign.__init__(self)

        # Always step backwards in z.
        if axis_z_step >= 0:
            axis_z_step = -axis_z_step

        rect = Rectangle(stage.x, stage.y, power_meter, axis_x_pts,
                         axis_y_pts, axis_x_step, axis_y_step, offset)
        lz = Line(stage.z, power_meter, axis_z_pts, axis_z_step, 'l')

        self._add_nested(rect, lz)


class Cross(Scan):
    def __init__(self, axis_1, axis_2, power_meter,
                 axis_1_pts, axis_2_pts, axis_1_step, axis_2_step,
                 offset=(0,0)):
        Scan.__init__(self, [axis_1, axis_2,], power_meter, offset,
                      axis_1_pts, axis_2_pts, axis_1_step, axis_2_step)


    @staticmethod
    def _pattern(axis_1_pts, axis_2_pts, axis_1_step, axis_2_step):
        l1 = Line._pattern(axis_1_pts, axis_1_step, 'c')
        l1 = np.concatenate((l1.T, [np.zeros(l1.size)])).T
        l2 = Line._pattern(axis_2_pts, axis_2_step, 'c')
        l2 = np.concatenate(([np.zeros(l2.size)], l2.T)).T
        pts = np.concatenate((l1, l2))
        return pts

    @staticmethod
    def plot(pattern, filename='pattern.dat'):
        return Rectangle.plot(pattern, filename)


class CrossXY(Cross):
    def __init__(self, stage, power_meter, axis_x_pts,
                 axis_y_pts, axis_x_step, axis_y_step,
                 offset=(0,0)):
        Cross.__init__(self, stage.x, stage.z, power_meter,
                       axis_x_pts, axis_y_pts,
                       axis_x_step, axis_y_step,
                       offset)


class Line2(ScannerDesign):
    def __init__(self, axis_1, axis_2, power_meter, axis_1_pts,
                 axis_2_pts, axis_1_step, axis_2_step):
        origin = 'c'

        lx = Line(axis_1, power_meter, axis_1_pts, axis_1_step, origin)
        ly = Line(axis_2, power_meter, axis_2_pts, axis_2_step, origin)

        ScannerDesign.__init__(self)
        self._add([ly])
        self._add([lx])


class OptimiseLine2XY_Z(ScannerDesign):
    def __init__(self, power_meter,
                 stage,
                 axis_x_pts, axis_y_pts, axis_z_pts,
                 axis_x_step, axis_y_step, axis_z_step,
                 offset=(0,0)):
        ScannerDesign.__init__(self)

        # Always step backwards in z.
        if axis_z_step >= 0:
            axis_z_step = -axis_z_step

        line2 = Line2(stage.x, stage.y, power_meter,
                      axis_x_pts, axis_y_pts,
                      axis_x_step, axis_y_step)
        lz = Line(stage.z, power_meter, axis_z_pts, axis_z_step, 'l')

        ns = [step[0][0] for step in line2._steps]
        self._add_nested_each_max(ns, lz)


class ScanRoutines(object):
    def __init__(self, stages, power_meter):
        self.inp = stages.input
        self.out = stages.output
        self.pm = power_meter

    def _take_image(self, stage, x_pts, y_pts, x_step_um, y_step_um,
                    filename=None, goto_max=False, meander=False):
        r = RectangleXY(stage, self.pm, x_pts, y_pts, x_step_um, y_step_um, (0,0), meander, 'c')
        pos_pows =  r.scan(goto_max, filename)
        return pos_pows

    def take_image_input(self, x_pts, y_pts, x_step_um, y_step_um,
                         filename='input.dat', goto_max=False):
        return self._take_image(self.inp, x_pts, y_pts, x_step_um, y_step_um,
                                filename, goto_max, False)

    def take_image_output(self, x_pts, y_pts, x_step_um, y_step_um,
                          filename='output.dat', goto_max=False):
        return self._take_image(self.out, x_pts, y_pts, x_step_um, y_step_um,
                                filename, goto_max, False)

    def _goto_max_rect(self, stage, x_pts, y_pts, x_step_um, y_step_um):
        c = RectangleXY(stage, self.pm, x_pts, y_pts, x_step_um, y_step_um, meander=False)
        pos_pows = c.scan(True)
        return pos_pows

    def goto_max_rect_input(self, x_pts, y_pts, x_step_um, y_step_um):
        return self._goto_max_rect(self.inp, x_pts, y_pts, x_step_um, y_step_um)

    def goto_max_rect_output(self, x_pts, y_pts, x_step_um, y_step_um):
        return self._goto_max_rect(self.out, x_pts, y_pts, x_step_um, y_step_um)

    def _goto_max_line2XY(self, stage, x_pts, y_pts, x_step_um, y_step_um):
        c = Line2(stage.x, stage.y, self.pm, x_pts, y_pts, x_step_um, y_step_um)
        pos_pows = c.scan(True)
        return pos_pows

    def goto_max_line2XY_input(self, x_pts, y_pts, x_step_um, y_step_um):
        return self._goto_max_line2XY(self.inp, x_pts, y_pts, x_step_um, y_step_um)

    def goto_max_line2XY_output(self, x_pts, y_pts, x_step_um, y_step_um):
        return self._goto_max_line2XY(self.out, x_pts, y_pts, x_step_um, y_step_um)

    def _goto_max_line2XY_z(self, stage, x_pts, y_pts, z_pts, x_step_um,
                          y_step_um, z_step_um):
        o = OptimiseLine2XY_Z(self.pm, stage, x_pts, y_pts, z_pts,
                              x_step_um, y_step_um, z_step_um)
        pos_pows = o.scan(True)
        return pos_pows

    def goto_max_line2XY_z_input(self, x_pts, y_pts, z_pts, x_step_um, y_step_um, z_step_um):
        return self._goto_max_line2XY_z(self.inp, x_pts, y_pts, z_pts, x_step_um, y_step_um, z_step_um)

    def goto_max_line2XY_z_output(self, x_pts, y_pts, z_pts, x_step_um, y_step_um, z_step_um):
        return self._goto_max_line2XY_z(self.out, x_pts, y_pts, z_pts, x_step_um, y_step_um, z_step_um)

    def _goto_max_rect_z(self, stage, x_pts, y_pts, z_pts, x_step_um,
                          y_step_um, z_step_um):
        o = OptimiseRectZ(self.pm, stage, x_pts, y_pts, z_pts,
                          x_step_um, y_step_um, z_step_um)
        pos_pows = o.scan(True)
        return pos_pows

    def goto_max_rect_z_input(self, x_pts, y_pts, z_pts, x_step_um, y_step_um, z_step_um):
        return self._goto_max_rect_z(self.inp, x_pts, y_pts, z_pts, x_step_um, y_step_um, z_step_um)

    def goto_max_rect_z_output(self, x_pts, y_pts, z_pts, x_step_um, y_step_um, z_step_um):
        return self._goto_max_rect_z(self.out, x_pts, y_pts, z_pts, x_step_um, y_step_um, z_step_um)

    def _goto_max_cross(self, stage, x_pts, y_pts, x_step_um, y_step_um):
        c = CrossXY(stage, self.pm, x_pts, y_pts, x_step, y_step)
        pos_pows = c.scan(True)
        return pos_pows

    def goto_max_cross_input(self, x_pts, y_pts, x_step_um, y_step_um):
        return self._goto_max_cross(self.inp, x_pts, y_pts, x_step_um, y_step_um)

    def goto_max_cross_output(self, x_pts, y_pts, x_step_um, y_step_um):
        return self._goto_max_cross(self.out, x_pts, y_pts, x_step_um, y_step_um)

    def find_waveguide_rect(self, x_pts=7, y_pts=7, x_step_um=1, y_step_um=1,
                            offset=(0,-3)):
        r_inp = RectangleXY(self.inp, self.pm,
                            x_pts, y_pts, x_step_um, y_step_um,
                            offset, True, 'c')
        r_out = RectangleXY(self.out, self.pm,
                            x_pts, y_pts, x_step_um, y_step_um,
                            offset, True, 'c')
        sd = ScannerDesign()
        sd._add_nested(r_out, r_inp)
        return sd.scan(True)

    def find_waveguide_cross(self, x_pts=7, y_pts=7, x_step_um=3, y_step_um=3,
                            offset=(0,-3)):
        r_inp = CrossXY(self.inp, self.pm,
                        x_pts, y_pts, x_step_um, y_step_um,
                        offset)
        r_out = CrossXY(self.out, self.pm,
                        x_pts, y_pts, x_step_um, y_step_um,
                        offset)
        sd = ScannerDesign()
        sd._add_nested(r_out, r_inp)
        return sd.scan(True)

    def centre_x_y(self):
        self.inp.x.move_abs_um(250)
        self.out.x.move_abs_um(250)
        self.inp.y.move_abs_um(250)
        self.out.y.move_abs_um(250)
