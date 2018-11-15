from . import power_meter as pm
import visa
import serial as ser
import time
import numpy as np

class Newport2832c(pm.PowerMeter):
    '''
    Driver to control the Newport 2832-C power metre allowing
    for its power to be read and wavelength to be set.

    Args:
        gpib_num (int): The number of the GPIB bus that
            the power metre is on.
        gpib_dev_num (int): The number of the device that
            the Newport 2832-C is on the specified bus.
        channel (str): Either \'a\' or \'b\' depending on
            which of the two channels the Newport 2832-C has
            that is desired to be used.
    '''
    def __init__(self, channel, gpib_num=None, gpib_dev_num=None, com_port_num=None):
        assert (gpib_num and gpib_dev_num) or com_port_num
        self.channel = channel.lower()
        assert self.channel in ('a', 'b'), 'Invalid channel choice %s.' % channel

        self._min_analogue_voltage_V = 0.
        self._max_analogue_voltage_V = 2.5

        if gpib_num and gpib_dev_num:
            self.gpib_mode = True
            rm = visa.ResourceManager('@py')
            self._dev = rm.open_resource('GPIB%i::%i::INSTR' % (gpib_num, gpib_dev_num))
            self._set_units('W')
        elif com_port_num:
            self.gpib_mode = False
            self._dev = ser.Serial(com_port_num, 9600, timeout=0.1)
            echo_init = self.get_rs232_echo()
            self.set_rs232_echo(False)
            if echo_init:
                self._dev.read()

        super().__init__()

    def verify_channel(func):
        def _verify_channel(name, *args, **kwargs):
            channel = channel.upper()
            assert channel in ('A', 'B')
            return func(name, *args, **kwargs)
        return _verify_channel

    def set_rs232_echo(self, status):
        status = bool(int(status))
        assert status in (True, False)
        self._write('ECHO %i' % status)
        return self.get_rs232_echo()

    def get_rs232_echo(self):
        return self._query('ECHO?')

    def _read(self):
        if self.gpib_mode:
            reply = self._dev.read()
        else:
            reply = self._dev.readline()
        reply = reply.decode().strip()
        return reply

    def _write(self, cmd):
        self._dev.write((cmd+'\r').encode())
        time.sleep(0.01) # Needed otherwise messes up if a read directly follows.
                         # Alternatively, one could poll the status bit and read
                         # when the status bit says there's a reply.
        return cmd

    def _query(self, cmd):
        cmd = self._write(cmd)
        r = self._read()
        return r

    def _get_power_W(self):
        power_W_str = self._query('R_%s?' % self.channel)
        power_W = float(power_W_str)
        return power_W

    def set_wavelength_m(self, wavelength):
        wavelength_nm = wavelength * 1.e9
        cmd = 'LAMBDA_%s %i' % (self.channel, wavelength_nm)
        self._write(cmd)
        return self.get_wavelength_m()

    def get_wavelength_m(self):
        cmd = 'LAMBDA_%s?' % self.channel
        wavelength_str = self._query(cmd)
        wavelength_nm = float(wavelength_str)
        wavelength_m = wavelength_nm * 1.e-9
        return wavelength_m

    def _set_units(self, units):
        units = units.lower()
        assert units in ('a', 'w', 'w/cm', 'dbm', 'db', 'rel'), \
                'Not a valid unit choice %s.' % units
        cmd = 'UNITS_%s %s' % (self.channel, units)
        self._write(cmd)
        return self._get_units()

    def _get_units(self):
        cmd = 'UNITS_%s?' % self.channel
        units = self._query(cmd)
        return units

    def get_external_trigger(self):
        return int(self._query('EXT?'))

    def set_external_trigger(self, state):
        state = int(state)
        assert state in (0, 1)
        self._write('EXT %i' % state)
        return get_external_trigger()

    def set_external_trigger_edge(self, edge):
        edge = edge.lower()
        assert edge in ('rising', 'falling')
        edge_bool = 0 if edge == 'falling' else '1'
        self.write('EXTEDGE %i' % edge_bool)
        return self.get_external_trigger_edge()

    def get_external_trigger_edge(self):
        edge_bool = bool(int(self._query('EXTEDGE?')))
        if edge_bool:
            edge = 'rising'
        else:
            edge = 'falling'
        return edge

    @verify_channel
    def start_data_acquisition(self, channel):
        self._write('RUN_%s' % channel)

    @verify_channel
    def stop_data_acquisition(self, channel):
        self._write('STOP_%s' % channel)

    @verify_channel
    def set_data_store(self, channel, state):
        state = int(state.upper())
        assert state in (False, True)
        self._write('DSE_%s %i' % (channel, int(state)))
        return self.get_data_store(channel)

    @verify_channel
    def get_data_store(self, channel):
        return int(self._query('DSE_%s?'))

    @verify_channel
    def get_data_buffer_size(self, channel):
        return int(self._query('DSSIZE_%s?' % channel))

    @verify_channel
    def set_data_buffer_size(self, channel, size):
        size = int(size)
        assert 1 <= size <= 1000
        self._write('DSSIZE_%s %i' % (channel, size))
        return self.get_data_buffer_size()

    @verify_channel
    def get_data_buffer_units(self, channel):
        unit_str = self._query('DSUNITS_%s?' % channel)
        return unit_str

    @verify_channel
    def set_data_buffer_units(self, channel):
        unit_str = self._query('DSUNITS_%s' % channel)
        return unit_str

    @verify_channel
    def get_data_buffer_counts(self, channel):
        return int(self._query('DSCNT_%s?' % channel))

    @verify_channel
    def clear_data_buffer(self, channel):
        self._write('DSCLR_%s' % channel)
        return self.get_data_buffer_counts()

    @verify_channel
    def get_data_buffer_sample(self, channel, sample_number):
        ''' 1 is the oldest sample and 1000 is the newest. '''
        sample_number = int(sample_number)
        assert 1 <= sample_number <= 1000
        power = self._query('DS_%s %i' % (channel, sample_number))
        return power

    @verify_channel
    def get_data_buffer_samples(self, channel):
        new_data_count = get_data_buffer_counts()
        data = np.empty(new_data_count)
        for i in range(new_data_count):
            data[i] = self.get_data_buffer_sample(channel, i)

    @verify_channel
    def get_responsivity_A_W(self, channel):
        return float(self._query('RESP_%s?' % channel))

    @verify_channel
    def get_range(self, channel):
        return int(self._query('RANGE_%s?' % channel))

    @verify_channel
    def get_max_current_A(self, channel):
        max_curr = {
            0: 2.51e-9,
            1: 2.51e-8,
            2: 2.51e-7,
            3: 2.51e-6,
            4: 2.51e-5,
            5: 2.51e-4,
            6: 2.51e-3
        }

        r = self.get_range(self.channel)
        return max_curr[r]

    def get_analogue_current_A(self, analogue_voltage_V):
        curr_min = 0
        curr_max = self.get_max_range_A(self.channel)

        m = (curr_max - curr_min) / (self._max_analogue_voltage_V - \
                                     self._min_analogue_voltage_V)
        c = curr_min

        curr_A = m*analogue_voltage_V + c

        return curr_A
