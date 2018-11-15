import serial as ser
from collections import deque
from . import laser as las
from . import sacher_maxon_epos2 as sme

class _Communication:
    def __init__(self, port, baud_rate=57600):
        self._ser = ser.Serial(port, baud_rate)
        self._read_buffer = deque()

    def write(self, cmd):
        self._ser.write((cmd+'\r\n').encode())
        assert cmd == self.read()
        self._read_buffer.append(self.read())
        if self._read_buffer[0] == 'O.K.':
            self._read_buffer.popleft()

    def read(self):
        return self._ser.readline().decode().strip()

    def query(self, cmd):
        self.write(cmd)
        return self._read_buffer.popleft()

class _Piezo:
    def __init__(self, communication):
        self._comm = communication

    def is_installed(self):
        return bool(int(self._comm.query(':p:inst?')))

    def enable(self):
        return self._comm.write(':p:ena 1')

    def disable(self):
        return self._comm.write(':p:ena 0')

    def is_enabled(self):
        return self._comm.query(':p:ena?')

    def set_offset_V(self, offset_V):
        offset_V = round(offset_V, 3)
        assert -13.5 <= offset <= 13.5, 'Offset voltage not in range.'
        return self._comm.write(':p:offs %.3f' % offset_V)

    def set_offset_mV(self, offset_mV):
        return self.offset_V(offset_mV / 1e3)

    def get_offset_V(self):
        return float(self._comm.query(':p:offs?'))

    def get_offset_mV(self):
        return 1e3*self.get_offset_mV()

    def set_waveform(self, waveform):
        waveform = waveform.lower()
        assert waveform in ('off', 'sinewave', 'triangle')
        waveforms = {'off': 0, 'sinewave': 1, 'triangle': 2}
        return self._comm.write(':p:freq:gen %i' % waveforms[waveform])

    def get_waveform(self, waveform):
        return self._comm.query(':p:freq:gen ?').lower()

    def set_phase_deg(self, phase):
        assert 0. <= phase <= 360.
        return self._comm.write(':p:freq:gen:pha %.1f' % phase)

    def get_phase_deg(self):
        return float(self._comm.query(':p:freq:gen:pha?'))

    def set_freq_Hz(self, frequency):
        assert 0. <= frequency <= 100e3
        return self._comm.write(':p:freq %.1fHz' % frequency)

    def set_freq_kHz(self, frequency):
        return self.set_freq_Hz(frequency * 1e3)

    def get_freq_Hz(self):
        return self._comm.query(':p:freq?')

    def get_freq_kHz(self, frequency):
        return self.get_freq_Hz()

class _System:
    def __init__(self, communication):
        self._comm = communication

    def get_hours_running(self):
        self._comm.query(':syst:l:h?')

    def set_baud_rate(self, baud_rate):
        assert baud_rate in (9600, 19200, 38400, 57600)
        return self._comm.write(':syst:baud %i' % baud_rate)

    def get_baud_rate(self):
        return self._comm.query(':syst:baud?')

    def set_echo(self, echo):
        assert echo in (True, False)
        return self._comm.write(':syst:echo %i' % echo)

    def get_echo(self):
        return bool(int(self._comm.query(':syst:echo?')))

    def set_acknowledge(self, acknowledge):
        assert acknowledge in (True, False)
        return self._comm.write(':syst:ack %i' % acknowledge)

    def get_acknowledge(self):
        return bool(int(self._comm.query(':syst:acknowledge?')))

class _Laser:
    def __init__(self, communication):
        self._comm = communication

    def set_i_p_mode(self, i_p_mode):
        i_p_mode = i_p_mode.lower()
        assert i_p_mode in ('i', 'p')
        return self._comm.write(':l:mod %s' % i_p_mode)

    def get_i_p_mode(self):
        return self._comm.query(':l:mod?')

    def turn_on(self):
        return self._comm.write(':l:stat 1')

    def turn_off(self):
        return self._comm.write(':l:stat 0')

    def get_on_or_off(self):
        return self._comm.query(':l:stat?')

    def get_current_A(self):
        return float(self._comm.query(':l:curr?'))

    def set_current_A(self, current):
        return self._comm.write(':l:curr %.3fA' % current)

    def get_current_mA(self):
        return self.get_current_A() * 1e3

    def set_current_mA(self, current):
        return self.set_current_A(current / 1e3)

    def get_voltage_V(self):
        return float(self._comm.query(':l:volt?'))

    def set_power_W(self):
        raise NotImplementedError()

    def get_power_W(self):
        raise NotImplementedError()

    def set_ext_modulation(self, modulate):
        assert modulate in (True, False)
        return self._comm.write(':l:modu:ena %i' % modulate)

    def get_ext_modulation(self):
        return self._comm.query(':l:modu:ena?')

class _LaserCavity(_Laser, sme.MaxonEpos2, las.LaserTunable):
    def __init__(self, communication, wavelength_nm, velocity_nm_s,
                 acceleration_nm_s2, deceleration_nm_s2):
        _Laser.__init__(self, communication)
        sme.MaxonEpos2.__init__(self,
                                wavelength_nm,
                                velocity_nm_s,
                                acceleration_nm_s2,
                                deceleration_nm_s2)

class _Tec:
    def __init__(self, communication):
        self._comm = communication

    def set_temperature_C(self, temperature):
        assert -5 <= temperature <= 65
        return self._comm.write(':tec:temp %.3f' % temperature)

    def get_temperature_C(self):
        return float(self.query(':tec:temp?'))

    def get_target_temperature_C(self):
        return float(self.query(':tec:temp:s?'))

class SacherLasertechnik:
    def __init__(self, port, wavelength_nm=None, velocity_nm_s=None,
                 acceleration_nm_s2=None, deceleration_nm_s2=None):
        communication = _Communication(port)
        self.piezo = _Piezo(communication)
        self.system = _System(communication)
        self.laser = _LaserCavity(communication,
                                  wavelength_nm=wavelength_nm,
                                  velocity_nm_s=velocity_nm_s,
                                  acceleration_nm_s2=acceleration_nm_s2,
                                  deceleration_nm_s2=deceleration_nm_s2)
        self.tec = _Tec(communication)
