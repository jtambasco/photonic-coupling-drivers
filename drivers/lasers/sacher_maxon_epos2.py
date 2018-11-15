import ctypes as ct
import time
import tqdm
from . import laser as las

_char = ct.c_int8
_int8 = ct.c_int8
_byte = ct.c_uint8
_short = ct.c_int16
_long = ct.c_int32
_word = ct.c_uint16
_dword = ct.c_uint32
_bool = ct.c_int32
_p = ct.pointer

def _cast(c_value, c_type):
    ptr = ct.cast(ct.byref(c_value), ct.POINTER(c_type))
    return ptr.contents.value

def _cast_u32_to_float(value_u32):
    return _cast(value_u32, ct.c_float)

def _cast_float_u32(value_double):
    return _cast(value_float, ct.c_uint32)

class MaxonEpos2:
    def __init__(self,
                 wavelength_nm=None,
                 velocity_nm_s=None,
                 acceleration_nm_s2=None,
                 deceleration_nm_s2=None):
        self._lib = ct.CDLL('libEposCmd.so')

        self._handle = ct.c_void_p()
        self._error_code = ct.c_uint32(0)
        self._error_code_ref = ct.byref(self._error_code)
        self._node_id = ct.c_uint32(1)

        # Initialisation flowchart from Sacher
        self._open_device('EPOS2', 'MAXON SERIAL V2', 'USB', 'USB0')
        self._set_protocol_stack_settings(100, 1000000)
        self._clear_fault_state()
        if self.get_state() == 'ST_ENABLED':
            self._set_disable_state()
        #self._set_encoder_parameters(512, 4) # Error saying sensor type 4 is out of range.
        assert self.get_state() == 'ST_DISABLED'
        operation_mode = 'Position Profile Mode'
        if self._get_operation_mode() != operation_mode:
            self._set_operation_mode(operation_mode)
        v, a, d = self.get_position_profile()
        if v > 11400/180 or \
                a > 20000/180 or \
                d > 20000/180:
            self.set_position_profile(1, 1, 1)

        # Motor [step] <-> Wavelength [nm] coefficients
        self._A = -6.31908E-12
        self._B = 0.000163586
        self._C = 1582.65

        # Absolute maximum motor range
        self._wl_min = 1500.
        self._wl_max = 1640.
        self._bow = self._determine_bow()
        self._motor_min = self.get_motor_pos_from_wavelength(self._wl_min)
        self._motor_max = self.get_motor_pos_from_wavelength(self._wl_max)

        # Wavelength [nm] per motor revolution
        self._step_per_rev = 102400
        self._nm_per_rev = \
            self.get_wavelength_from_motor_pos(self._step_per_rev) - self._C
        self._nm_per_step = self._nm_per_rev / self._step_per_rev
        self._max_step_per_sec = 11400

        # Set parameters if specified
        if wavelength_nm:
            self.set_wavelength_nm(wavelength_nm)

        pos_profile = list(self.get_position_profile())
        if velocity_nm_s:
            pos_profile[0] = velocity_nm_s
        if acceleration_nm_s2:
            pos_profile[1] = acceleration_nm_s2
        if deceleration_nm_s2:
            pos_profile[2] = deceleration_nm_s2
        self.set_position_profile(*pos_profile)

    def _read_stored_position(self):
        return self._read_memory(0x2081, 0, 4)

    def _write_stored_position(self, value):
        return self._write_memory(0x2081, 0, ct.c_int32(value), 4)

    def calc_motor_acc(self, nm_per_sec_sec):
        acc = nm_per_sec_sec / self._nm_per_step
        return acc # [step/s/s]

    def _open_device(self, device_name, protocol_stack_name, interface_name,
                    port_name):
        dn = ct.c_char_p(device_name.encode())
        psn = ct.c_char_p(protocol_stack_name.encode())
        inter = ct.c_char_p(interface_name.encode())
        pn = ct.c_char_p(port_name.encode())
        self._handle = self._lib.VCS_OpenDevice(dn,
                                                psn,
                                                inter,
                                                pn,
                                                self._error_code_ref)
        assert not self._error_code.value, 'Cannot connect to motor controller.'

    def _set_protocol_stack_settings(self, timeout_ms, baud_rate=1000000):
        r = self._lib.VCS_SetProtocolStackSettings(self._handle,
                                                  _dword(baud_rate),
                                                  _dword(timeout_ms),
                                                  self._error_code_ref)
        assert r

    def _clear_fault_state(self):
        r = self._lib.VCS_ClearFault(self._handle,
                                    self._node_id,
                                    self._error_code_ref)
        assert r

    def _set_encoder_parameters(self, counts, sensor_type):
        r = self._lib.VCS_SetEncoderParameter(self._handle,
                                              self._node_id,
                                              _word(512),
                                              _word(4),
                                              self._error_code_ref)
        assert r

    def _get_encoder_parameters(self):
        counts = _word()
        sensor_type = _word()
        r = self._lib.VCS_SetEncoderParameter(self._handle,
                                             self._node_id,
                                             ct.byref(counts),
                                             ct.byref(sensor_type),
                                             self._error_code_ref)
        return counts.value, sensor_type.value

    def _get_operation_mode(self):
        pp = _int8()
        r = self._lib.VCS_GetOperationMode(self._handle,
                                          self._node_id,
                                          ct.byref(pp),
                                          self._error_code_ref)
        assert r

        pp_lookup = {
            1: 'Position Profile Mode',
            3: 'Position Velocity Mode',
            6: 'Homing Mode',
            7: 'Interpolated Position Mode',
            -1: 'Position Mode',
            -2: 'Velocity Mode',
            -3: 'Current Mode',
            -5: 'Master Encoder Mode',
            -6: 'Step Direction Mode',
        }

        return pp_lookup[pp.value]

    def _set_operation_mode(self, mode):
        pp_lookup = {
            'Position Profile Mode': 1,
            'Position Velocity Mode': 3,
            'Homing Mode': 6,
            'Interpolated Position Mode': 7,
            'Position Mode': -1,
            'Velocity Mode': -2,
            'Current Mode': -3,
            'Master Encoder Mode': -5,
            'Step Direction Mode': -6,
        }

        mode_num = _int8(pp_lookup[mode])
        r = self._lib.SetOperationMode(self._handle,
                                      self._node_id,
                                      mode_num,
                                      self._error_code_ref)
        assert r

    def set_position_profile(self, velocity, acceleration, deceleration):
        assert 0.008 <= velocity <= 35
        assert acceleration <= 25
        assert deceleration <= 25

        velocity *= 180
        acceleration *= 180
        deceleration *= 180

        v = _dword(round(velocity))
        a = _dword(round(acceleration))
        d = _dword(round(deceleration))
        r = self._lib.VCS_SetPositionProfile(self._handle,
                                            self._node_id,
                                            v,
                                            a,
                                            d,
                                            self._error_code_ref)
        assert r

        # Set save all parameters (register 4112d)
        evas = ct.c_uint32(0x65766173) # 'e' 'v' 'a' 's'
        num_bytes_written = _dword()
        r = self._lib.VCS_SetObject(self._handle,
                                   self._node_id,
                                   _word(0x1010), # Address 4112d
                                   _byte(1), # Subindex 1
                                   ct.byref(evas), # Data
                                   _dword(4), # Write all 4 bytes of the data
                                   ct.byref(num_bytes_written), # Number of bytes written
                                   self._error_code_ref)
        assert r

    def get_position_profile(self):
        v = _dword()
        a = _dword()
        d = _dword()
        r = self._lib.VCS_GetPositionProfile(self._handle,
                                            self._node_id,
                                            ct.byref(v),
                                            ct.byref(a),
                                            ct.byref(d),
                                            self._error_code_ref)
        assert r

        v = v.value / 180.
        a = a.value / 180.
        d = d.value / 180.

        return v, a, d

    def get_velocity_nm_s(self):
        v, _, _ = self.get_position_profile()
        return v

    def set_velocity_nm_s(self, velocity_nm_s):
        _, a, d = self.get_position_profile()
        self.set_position_profile(velocity_nm_s, a, d)

    def _get_movement_state(self):
        status = _bool()
        r = self._lib.VCS_GetMovementState(self._handle,
                                          self._node_id,
                                          ct.byref(status),
                                          self._error_code_ref)
        assert r
        return bool(status.value)

    def _move_rel(self, rel_move_steps):
        delta_wl_nm = self.get_wavelength_from_motor_pos(rel_move_steps) - \
                      self.get_wavelength_from_motor_pos(0)
        delta_wl_nm = abs(round(delta_wl_nm))
        sleep_interv_s = 0.2

        ab = _bool(False)
        im = _bool(True)
        rm = _long(rel_move_steps)
        self._set_enable_state()
        r = self._lib.VCS_MoveToPosition(self._handle,
                                         self._node_id,
                                         rm,
                                         ab,
                                         im,
                                         self._error_code_ref)
        assert r

        while not self._get_movement_state():
            print(self._get_motor_current())
            #time.sleep(sleep_interv_s)
        print(self._get_motor_current())
        self._set_disable_state()
        print(self._get_motor_current())

    def set_wavelength_m(self, wavelength_m):
        '''
        Moves the motor to a wavelength [nm].

        Process:
            1. get current position from register + offset
            2. get target position from wavelength
            3. 2. - 1.  to get relative move to wavelength position
            4. do relative move by 3.
            5. VCS_GetPositionIs to read encoder
            6. update home: 1. + 5. -> 0x2081
            7. get wavelength

        Args:
            wavelength (float): Target wavelength [nm] to move to.

        Returns:
            (float): Actual wavelength moved to.
        '''

        wavelength_nm = wavelength_m * 1.e9

        pos_reg = self._read_stored_position() # 1.
        target_pos = self.get_motor_pos_from_wavelength(wavelength_nm) # 2.
        pos_encoder_before = self._get_current_position()
        assert self._motor_min <= target_pos <= self._motor_max
        rel_move_steps = target_pos - pos_reg # 3.

        # 4.
        self._set_enable_state()
        if rel_move_steps <= 0:
            self._move_rel(rel_move_steps)
        else:
            self._move_rel(rel_move_steps-10000)
            self._move_rel(10000)
        self._set_disable_state()

        pos_encoder_after = self._get_current_position() # 5.
        pos_encoder_rel = pos_encoder_after - pos_encoder_before

        ## 6.
        pos_reg_new = pos_reg + pos_encoder_rel
        self._write_memory(0x2081, 0, ct.c_int32(pos_reg_new), 4)

        wl = self.get_wavelength_from_motor_pos(pos_reg_new) # 7.

        return wl

    def _get_current_position(self):
        pos = _long()
        r = self._lib.VCS_GetPositionIs(self._handle,
                                       self._node_id,
                                       ct.byref(pos),
                                       self._error_code_ref)
        assert r
        return pos.value

    def _set_enable_state(self):
        r = self._lib.VCS_SetEnableState(self._handle,
                                        self._node_id,
                                        self._error_code_ref)
        assert r

    def _set_disable_state(self):
        r = self._lib.VCS_SetDisableState(self._handle,
                                         self._node_id,
                                         self._error_code_ref)
        assert r

    def get_state(self):
        st = ct.pointer(_word())
        r = self._lib.VCS_GetState(self._handle,
                                  self._node_id,
                                  st,
                                  self._error_code_ref)
        assert r

        state = st.contents.value
        if state == 0x0000:
            state = 'ST_DISABLED'
        elif state == 0x0001:
            state = 'ST_ENABLED'
        elif state == 0x0002:
            state = 'ST_QUICKSTOP'
        elif state == 0x0003:
            state = 'ST_FAULT'

        return state

    def get_error_code(self):
        return hex(self._error_code.value)

    def stop_move(self):
        r = self._lib.VCS_HaltPositionMovement(self._handle,
                                               self._node_id,
                                               self._error_code_ref)
        assert r

    def _read_memory(self, object_index, object_subindex, bytes_to_read):
        oi = _word(object_index)
        osi = _byte(object_subindex)
        btr = _dword(bytes_to_read)
        data = ct.c_int32()
        bytes_read = ct.pointer(_dword())
        r = self._lib.VCS_GetObject(self._handle,
                                   self._node_id,
                                   oi,
                                   osi,
                                   ct.byref(data),
                                   btr,
                                   bytes_read,
                                   self._error_code_ref)
        assert r

        return data.value

    def _write_memory(self, object_index, object_subindex, data,
                     num_bytes_to_write):
        oi = _word(object_index)
        osi = _byte(object_subindex)
        nbtw = _dword(num_bytes_to_write)
        num_bytes_written = _dword()

        r = self._lib.VCS_SetObject(self._handle,
                                    self._node_id,
                                    oi,
                                    osi,
                                    ct.byref(data),
                                    nbtw,
                                    ct.byref(num_bytes_written),
                                    self._error_code_ref)
        assert r
        return num_bytes_written

    def _get_wavelength_range_nm(self):
        value = self._read_memory(0x200C, 4, 4)
        wl_min_nm = (value >> 16) / 10
        wl_max_nm = (value & 0x0000ffff) / 10
        return wl_min_nm, wl_max_nm

    def _get_wavelength_motor_pos_coefs(self):
        A = ct.c_uint32(self._read_memory(0x200C, 1, 4))
        B = ct.c_uint32(self._read_memory(0x200C, 2, 4))
        C = ct.c_uint32(self._read_memory(0x200C, 3, 4))
        A = _cast_u32_to_float(A)
        B = _cast_u32_to_float(B)
        C = _cast_u32_to_float(C)
        return A, B, C

    def get_wavelength_from_motor_pos(self, position):
        assert self._motor_min <= position <= self._motor_max
        A = self._A
        B = self._B
        C = self._C
        wl_nm = A*position**2 + B*position + C
        return wl_nm

    def _solve_quadratic(self, wavelength):
        A = self._A
        B = self._B
        C = self._C

        k = -B/(2*A)
        j = B**2/(4*A**2) - (C-wavelength)/A
        j = j**0.5
        assert j.imag == 0

        return k, j

    def get_motor_pos_from_wavelength(self, wavelength):
        assert self._wl_min <= wavelength <= self._wl_max

        k, j = self._solve_quadratic(wavelength)
        if self._bow == 'neg':
            pos = k - j
        elif self._bow == 'pos':
            pos = k + j

        return round(pos)

    def get_wavelength_m(self):
        pos_reg = self._read_stored_position()
        pos = pos_reg
        return self.get_wavelength_from_motor_pos(pos) * 1e-9

    def _determine_bow(self):
        vals = []
        for wavelength in [self._wl_min, self._wl_max]:
            k, j = self._solve_quadratic(wavelength)
            vals.append(k-j)
            vals.append(k+j)

        if vals[0] < 0 < vals[2]:
            bow = 'neg'
        elif vals[1] < 0 < vals[3]:
            bow = 'pos'
        else:
            assert False

        return bow

    def update_motor_position(self, measured_wavelength_nm):
        new_motor_pos = \
            self.get_motor_pos_from_wavelength(measured_wavelength_nm)
        self._write_stored_position(new_motor_pos)

    def set_default_settings(self):
        r = self._lib.VCS_Restore(self._handle,
                                  self._node_id,
                                  self._error_code_ref)
        assert r

    def _get_motor_current(self):
        curr = _short()
        r = self._lib.VCS_GetCurrentIs(self._handle,
                                       self._node_id,
                                       ct.byref(curr),
                                       self._error_code_ref)
        assert r
        return curr.value

    def _get_motor_parameters(self):
        nom_curr = _word()
        max_curr = _word()
        therm_tc = _word()
        r = self._lib.VCS_GetDcMotorParameter(self._handle,
                                              self._node_id,
                                              ct.byref(nom_curr),
                                              ct.byref(max_curr),
                                              ct.byref(therm_tc),
                                              self._error_code_ref)
        assert r
        return nom_curr.value, max_curr.value, therm_tc.value

