import sys
import numpy as np
import os
import shutil
import time
import itertools as it
import collections
import ctypes as ct
import os
import copy
sys.path.append(os.path.dirname(__file__))
from ThreadStoppable import ThreadStoppable

class Idq801(object):
    def __init__(self, deviceId=-1, timestamp_buffer_size=int(1e6), integration_time_ms=0.5*1e3,
                 coincidence_window_bins=1000, max_retry=3, delay_retry_sec=0.01,
                 clean_data_directory=False, data_directory='Idq801Data', processing='external'):
        self._max_retry = max_retry
        self._set_check_delay = delay_retry_sec # Delay in seconds between setting and
                                                # checking that a parameter was set.
        self._data_directory = data_directory
        self._wait_for_settings = 1

        self._processing_dict = {'i': 'internal', 'e': 'external'}
        processing = processing.lower()
        assert processing in self._processing.values()
        self._processing = processing

        if not os.path.isdir(data_directory):
            os.mkdir(data_directory)

        if clean_data_directory:
            self.clean_data_directory()

        module_path = os.path.dirname(__file__) + '/'
        if sys.platform == 'linux':
            self.idq801Lib = ct.CDLL(module_path+'libtdcbase.so')
        elif sys.platform == 'win32':
            self.idq801Lib = ct.CDLL(module_path+'./tdcbase.dll')
        else:
            raise OSError('Invalid operating system')

        if self.idq801Lib.TDC_init(deviceId):
            raise RuntimeError('Could not connect to the ID801 counter.')

        # Initial parameters.
        self.unset_channel(-1)
        self.set_timestamp_buffer_size(timestamp_buffer_size)
        self.integration_time_ms = integration_time_ms
        if self._processing == self._processing_dict['i']:
            self.set_integration_time(integration_time_ms)
        else:
            self.set_integration_time(1.e-3) # 1us integration time.
        self.set_coincidence_window_bins(1000)
        self._time_last_get_timestamps = time.time()
        self.channel_delays = {
            '1': 0,
            '2': 0,
            '3': 0,
            '4': 0,
            '5': 0,
            '6': 0,
            '7': 0,
            '8': 0
        }
        self.set_channel_delays_ns(self.channel_delays)
        self.accidental_delay = 0

    def __del__(self):
        self.idq801Lib.TDC_deInit()

    def _set_value(self, set_value, setter, getter):
        '''  Sets a value and makes sure it was set.
        '''
        attempt = 0
        is_set = False
        while not is_set and attempt < self._max_retry:
            attempt += 1
            setter(set_value)
            time.sleep(self._set_check_delay)
            try:
                if list(set_value) == list(getter()):
                    is_set = True
            except TypeError:
                if set_value == getter():
                    is_set = True

        if not is_set:
            raise RuntimeError('Unable to set the value using %s to %s after %i attempts.' \
                    % (setter.__name__, str(set_value), self._max_retry))

    def _get_device_params(self):
        cm = ct.c_int32()
        cw = ct.c_int32()
        ew = ct.c_int32()
        self.idq801Lib.TDC_getDeviceParams(ct.byref(cm), ct.byref(cw), ct.byref(ew))
        return (cm, cw, ew)

    def _set_processing(self, processing):
        processing = processing.lower()
        assert processing in self._processing_dict.values()
        self._processing = processing
        if processing == self._processing_dict['i']:
            self.set_integration_time(self.integration_time_ms)
        return self._processing

    def set_processing_internal(self):
        return self._set_processing('internal')

    def set_processing_external(self):
        return self._set_processing('external')

    def clean_data_directory(self):
        '''
        Deletes all data in the `Idq801Data` directory.
        '''
        shutil.rmtree(self._data_directory, ignore_errors=True)
        os.mkdir(self._data_directory)

    def get_timebase(self):
        self.idq801Lib.TDC_getTimebase.restype = ct.c_double
        tb = self.idq801Lib.TDC_getTimebase()
        return tb

    def get_mask_channels(self):
        cm, _, _ = self._get_device_params()
        return cm.value

    def get_status_channels(self):
        cm, cw, ew = self._get_device_params()
        channels_enabled = [bool(int(c)) for c in bin(cm.value)[2:]][::-1]
        padLength = 8-len(channels_enabled)
        channels_enabled.extend([False]*padLength)
        return tuple(channels_enabled)

    def get_enabled_channels(self):
        channels_status = self.get_status_channels()
        channels_enabled = tuple(i+1 for i,v in enumerate(channels_status) if v == True)
        return channels_enabled

    def get_disabled_channels(self):
        channels_status = self.get_status_channels()
        channels_disabled = tuple(i+1 for i,v in enumerate(channels_status) if v == False)
        return channels_disabled

    def is_channel_enabled(self, channel):
        assert 1 <= channel <= 8, 'Invalid choice channel range.'
        channel -= 1
        channel_status = self.get_status_channels()[channel]
        return channel_status

    def _get_channel_mask(self, channel, set_unset):
        def channel_mask_from_channel_list(channels_enabled):
            channel_mask = 0
            for b in channels_enabled[::-1]:
                channel_mask = (channel_mask << b-1) | True
            return channel_mask

        set_unset = set_unset.lower()
        assert set_unset in ('set', 'unset'), \
                'Invalid `set_unset` choice %s.' % set_unset

        if isinstance(channel, str):
            channel = channel.lower()
        if channel == 'all' or channel == -1:
            channel_mask = 0xff
        elif channel in range(1, 9):
            channel_mask = 1 << channel
        elif isinstance(channel, collections.Iterable):
            channel_mask = channel_mask_from_channel_list(channel)
        else:
            raise TypeError('Invalid `channel` choice.')

        if set_unset == 'unset':
            channel_mask ^= 0xff

        return channel_mask

    def _set_unset_channel(self, channel, set_unset):
        self._channel_mask = self._get_channel_mask(channel, set_unset)
        self._set_value(self._channel_mask, self.idq801Lib.TDC_enableChannels,
                        self.get_mask_channels)
        return self._channel_mask

    def set_channel(self, channel):
        ''' Choose which channels to enable.
            Options include:
                * -1 or 'all' for (all channels).
                * A single number for channel to be enabled.
                * An iterable containing the channels
                  to be enables. e.g. (1,4,5)
                * Default is no channels are enabled.
        '''
        return self._set_unset_channel(channel, 'set')

    def unset_channel(self, channel):
        ''' Choose which channels to disable.
            Options include:
                * -1 or 'all' for (all channels).
                * A single number for channel to be disabled.
                * An iterable containing the channels
                  to be disables. e.g. (1,4,5)
                * Default is no channels are disabled.
        '''
        return self._set_unset_channel(channel, 'unset')

    def get_coincidence_window_bins(self):
        cm, cw, ew = self._get_device_params()
        return cw.value

    def get_coincidence_window_ns(self):
        bin = self.get_timebase()
        return bin * self.get_coincidence_window_bins() * 1e9

    def set_coincidence_window_bins(self, coincidence_window_bins):
        coincidence_window_bins = int(coincidence_window_bins)
        if not 0 < coincidence_window_bins <= 65535:
            raise ValueError('The chosen number of coincidence \
                    window bins is not in the range (0,65535].')
        self._set_value(coincidence_window_bins, self.idq801Lib.TDC_setCoincidenceWindow,
                        self.get_coincidence_window_bins)

    def set_coincidence_window_ns(self, coincidence_window_ns):
        bin = self.get_timebase()
        coincidence_window_bins = int(coincidence_window_ns * 1e-9 / bin)
        return self.set_coincidence_window_bins(coincidence_window_bins)

    def get_integration_time(self):
        cm, cw, ew = self._get_device_params()
        return ew.value

    def freeze_buffers(self):
        self.idq801Lib.TDC_freezeBuffers(True)

    def unfreeze_buffers(self):
        self.idq801Lib.TDC_freezeBuffers(False)

    def set_integration_time(self, window_time_ms):
        window_time_ms = round(window_time_ms)
        if self._processing == self._processing_dict['i']:
            if not 0 < window_time_ms <= 65535:
                raise ValueError('The chosen exposure window is not \
                        in the range (0,65535].  Can\'t do more than 65.5s \
                        integration time internally.')
            self._set_value(self.window_time_ms, self.idq801Lib.TDC_setExposureTime,
                            self.get_integration_time)

    def get_data_lost_status(self):
        ''' Returns true if data is being lost, and false
            if data is not being lost.
        '''
        # Get the status of the lost latch.
        lost = ct.c_int32()
        self.idq801Lib.TDC_getDataLost(ct.byref(lost))
        latch = lost.value

        # Calls the function again to clear the lost latch.
        self.idq801Lib.TDC_getDataLost(ct.byref(lost))

        return latch

    def get_timestamp_buffer_size(self):
        size = ct.c_int32()
        self.idq801Lib.TDC_getTimestampBufferSize(ct.byref(size))
        return size.value

    def set_timestamp_buffer_size(self, size):
        ''' `size` is the amount of timestamps that the
            the counter will store.  Range is 1->1000000
        '''
        self._set_value(size, self.idq801Lib.TDC_setTimestampBufferSize,
                self.get_timestamp_buffer_size)

    def get_timestamps(self, clear_retrieved_timestamps=True, trim_time_s=None):
        '''
        Gets all the time stamps in the buffer and returns
        a dictionary corresponding to the timestamps in each
        channel.

        args:
            clear_retrieved_timestamps(bool): Clears the timestamp
                buffer of the IDQ801 after reading.
            trim_time_s(float, None): The amount of timestamps, in
                seconds, from the import first timestamps to keep.
                If `None`, all timestamps are returned.  Multiple
                channels are all trimmed starting from the lowest
                timestamps of all the channels combined.

        returns:
            dict: A dictionary containing numpy arrays with the
                timestamps of each channel.  The time from the
                last calling of this function is also returned
                in the dictionary.

        '''
        if self.get_timestamp_buffer_size() == 0:
            raise RuntimeError('The timestamp buffer size is 0. \
                    Can\'t get timestamps.  Need to set the timestamp \
                    buffer.')

        r  = ct.c_int32(clear_retrieved_timestamps)
        ts = (ct.c_int64*self.get_timestamp_buffer_size())()
        c  = (ct.c_int8*self.get_timestamp_buffer_size())()
        v  = ct.c_int32()
        self.idq801Lib.TDC_getLastTimestamps(r, ts, c, ct.byref(v))
        time_read = time.time()
        time_diff = time_read - self._time_last_get_timestamps
        self._time_last_get_timestamps = time_read

        channel = np.frombuffer(c, dtype=np.int8)
        channel_masks = [channel == i for i in range(4) if self._channel_mask & (1<<i)]
        timestamps = np.frombuffer(ts, dtype=np.int64)
        timestamps_masked = {str(c+1):timestamps[c_m] for c, c_m in enumerate(channel_masks)}
        timestamps_masked.update((k, v[v > 0]) for k, v in timestamps_masked.items())

        last_counts = []
        if trim_time_s:
            for timestamps in timestamps_masked.values():
                if timestamps.size:
                    first_count =  timestamps[0]
                    last_counts.append(first_count + int(trim_time_s / self.get_timebase() + 0.5))
            if len(last_counts):
                last_count = np.min(last_counts)

                for channel, timestamps in timestamps_masked.items():
                    if timestamps.size:
                        last_idx = np.searchsorted(timestamps, last_count, 'right')
                        timestamps_masked[channel] = timestamps[:last_idx-1]

        timestamps_masked['time_diff'] = time_diff

        return timestamps_masked

    def _get_coins(self, timestamps_1, timestamps_2, method='2'):
        t2 = np.array(timestamps_2, dtype=np.int64)

        assert method in ('1', '2'), 'Invalid method chosen.'
        if method == '1':
            t1 = np.empty(len(timestamps_1) + 2, dtype=np.int64)
            t1[0] = 0
            t1[-1] = np.iinfo(np.int64).max
            t1[1:-1] = timestamps_1

            t2_pos = np.searchsorted(t1, t2)

            t1_pos_forw = t2_pos
            t1_pos_back = t2_pos - 1
            t1_pos_back[t1_pos_back == -1] = 0
            dt_forw = (np.abs(t1[t1_pos_forw] - t2) <= self.get_coincidence_window_bins())
            dt_back = (np.abs(t1[t1_pos_back] - t2) <= self.get_coincidence_window_bins())

            coin_forw_args = dt_forw.nonzero()[0]
            coin_back_args = dt_back.nonzero()[0]

            coins_forw = np.c_[t1_pos_forw[coin_forw_args] - 1, coin_forw_args]
            coins_back = np.c_[t1_pos_back[coin_back_args] - 1, coin_back_args]
            coins = np.vstack((coins_back, coins_forw))
        elif method == '2':
            t1 = np.array(timestamps_1, dtype=np.int64)

            l = np.searchsorted(t1, t2 - self.get_coincidence_window_bins()/2)
            r = np.searchsorted(t1, t2 + self.get_coincidence_window_bins()/2)
            args = np.where(l != r)[0]
            coins = np.c_[r[args], args]

        return coins

    def get_coin_counts(self, coin_channels, accidentals_delay_ns=None, trim_time_s=None):
        bin = self.get_timebase()
        timestamps = self.get_timestamps(clear_retrieved_timestamps=True,
                                         trim_time_s=trim_time_s)
        time_diff = timestamps['time_diff']
        timestamps.pop('time_diff', None)

        coin_counts = {}
        acc_counts = {}

        # Get singles counts
        for c in coin_channels:
            if str(c) in timestamps:
                coin_counts[str(c)] = len(timestamps[str(c)])
            else:
                coin_counts[str(c)] = 0

        coin_combinations = list(it.combinations(coin_channels, 2))

        for c in coin_combinations:
            #Get coincidence counts
            if str(c[0]) in timestamps and str(c[1]) in timestamps:
                coin_counts[str(c[0]) + '/' + str(c[1])] = len(self._get_coins(timestamps[str(c[0])],
                                                                               timestamps[str(c[1])]))
            else:
                coin_counts[str(c[0]) + '/' + str(c[1])] = 0

        if accidentals_delay_ns != None:
            accidentals_delay_bin = int(accidentals_delay_ns * 1e-9 / bin)
            for c in coin_combinations:
                # Get accidental counts
                if str(c[0]) in timestamps and str(c[1]) in timestamps:
                    acc_counts[str(c[0]) + '/' + str(c[1])] = len(self._get_coins(timestamps[str(c[0])],
                                                                                  timestamps[str(c[1])]+
                                                                                  accidentals_delay_bin))
                else:
                    acc_counts[str(c[0]) + '/' + str(c[1])] = 0

        return coin_counts, acc_counts, timestamps

    def scan_channel_delay(self, coin_channels, scan_channel, scan_range_ns, integration_time=1.0):
        '''
        Scans channel delay electronically - integrates once then applies delays to the timestamps to find coins
        Args:
            coin_channels: channels to look at coins
            scan_channel: channel to scan
            scan_range_ns: +/- range of delay in ns
            integration_time: initial integration time

        Returns: max coin reading, delay in ns of the max, all coin counts, delay range

        '''
        current_delays_bins = self.get_channel_delays_bins()

        self.set_channel_delays_ns({str(coin_channels[0]): 0,
                                    str(coin_channels[1]): 0})

        bin = self.get_timebase()
        self.get_timestamps()
        time.sleep(integration_time)
        original_timestamps = self.get_timestamps()
        delay_range = range(-scan_range_ns, scan_range_ns + 1)
        coin_counts = np.zeros(len(delay_range))

        timestamps = copy.deepcopy(original_timestamps)

        for idd, d in enumerate(delay_range):
            timestamps[str(scan_channel)] = copy.deepcopy(original_timestamps[str(scan_channel)]) + int(d*1e-9/bin)
            coin_counts[idd] = len(self._get_coins(timestamps[str(coin_channels[0])],
                                                   timestamps[str(coin_channels[1])]))

            print('delay channel = %s, delay = %s ns, coin counts = %s' % (scan_channel, d, int(coin_counts[idd])))

        max_coin = np.max(coin_counts)
        max_coin_delay = delay_range[np.argmax(coin_counts)]

        self.set_channel_delays_bins(current_delays_bins)

        return max_coin, max_coin_delay, coin_counts, delay_range

    def get_timestamps_continuous(self, seconds=-1):
        ''' Runs `gets_timestamps` continuously in a separate
            thread for `seconds` amount of seconds in a loop.
            If seconds == -1, it doesn't timeout.  Returns a
            thread object that can be stopped and started.
        '''
        time.sleep(self._wait_for_settings)
        clear_retrieved_timestamps=True
        t = ThreadStoppable(self.get_timestamps, seconds, True, \
                args=(clear_retrieved_timestamps,))
        return t

    def write_timestamps_to_file(self):
        ''' Writes the timestamps in the buffer to a
            file.
        '''
        timestamp_dir = 'Timestamps'
        if not os.path.isdir(self._data_directory+'/'+timestamp_dir):
            os.mkdir(self._data_directory+'/'+timestamp_dir)

        filename_prefix = self._data_directory + '/' + timestamp_dir \
                + '/' + 'timestamp_channel_'
        filenames = [filename_prefix + str(i) + '.dat' \
                for i in range(1,9)]

        for fn in filenames:
            if not os.path.exists(fn):
                open(fn, 'w').close()

        ts = self.get_timestamps(clear_retrieved_timestamps=True)

        for i, fn in enumerate(filenames):
            with open(fn, 'a') as fs:
                try:
                    for t in ts[str(i+1)]:
                        fs.write(str(t)+'\n')
                except KeyError:
                    pass

    def write_timestamps_to_file_continuous(self, seconds=-1):
        ''' Runs `write_timestamps_to_file` continuously in a separate
            thread for `seconds` amount of seconds in a loop.  If
            seconds == -1, it doesn't timeout.  Returns a thread object
            that can be stopped and started.
        '''
        time.sleep(self._wait_for_settings)
        t = ThreadStoppable(self.write_timestamps_to_file, seconds)
        return t

    def get_counters(self):
        ''' Returns a list of the most recent value of
            of the counters.
        '''
        counters = (ct.c_int32*19)()
        self.idq801Lib.TDC_getCoincCounters(counters, None)
        return list(counters)

    def get_counters_continuous(self, seconds=-1):
        ''' Runs `get_counters` continuously in a separate thread for
            `seconds` amount of seconds in a loop.  If seconds == -1,
            it doesn't timeout.  Returns a thread object that can be
            stopped and started.
        '''
        time.sleep(self._wait_for_settings)
        t = ThreadStoppable(self.get_counters, seconds, True)
        return t

    def write_counters_to_file(self, filename='counters.dat'):
        ''' Writes the most recent values of the internal
            counters and coincidence counters to a file
            named `filename`.
        '''
        fn = self._data_directory + '/' + filename
        if not os.path.exists(fn):
            with open(fn, 'w') as fs:
                header = ('1,2,3,4,5,6,7,8,1/2,1/3,1/4,2/3,2/4,3/4,'
                          '1/2/3,1/2/4,1/3/4,2/3/4,1/2/3/4')
                fs.write('#'+header+'\n')

        counters = self.get_counters()
        counters_str = ','.join([str(c) for c in counters])

        with open(fn, 'a') as fs:
            fs.write(counters_str+'\n')

    def write_counters_to_file_continuous(self, seconds=-1, filename='counters.dat'):
        ''' Runs `write_counters_to_file` continuously in a separate
            thread for `seconds` amount of seconds in a loop.  If
            seconds == -1, it doesn't timeout.  Returns a thread
            object that can be stopped and started.
        '''
        time.sleep(self._wait_for_settings)
        t = ThreadStoppable(self.write_counters_to_file, seconds, \
                False, args=(filename,))
        return t

    def _get_channel_delays(self):
        channels = range(8)
        channels = (ct.c_int32 * len(channels))(*channels)
        self.idq801Lib.TDC_getChannelDelays(channels)
        return channels

    def get_channel_delays_bins(self):
        return list(self._get_channel_delays())

    def get_channel_delays_ns(self):
        bin = self.get_timebase()
        delays_bins = list(self._get_channel_delays())
        return [d*1e9*bin for d in delays_bins]

    def set_channel_delays_bins(self, delays_bins):
        delays = (ct.c_int * len(delays_bins))(*delays_bins)
        return self._set_value(delays, self.idq801Lib.TDC_setChannelDelays, self._get_channel_delays)

    def set_channel_delays_ns(self, delays_ns_dict):
        '''
        Set channel delays in ns. The delays are in a dictionary.
        Args:
            delays_ns_dict:

        Returns:

        '''
        delays_ns = self.get_channel_delays_ns()
        for channel in delays_ns_dict.keys():
            self.channel_delays[str(channel)] = delays_ns[int(channel)-1]
            delays_ns[int(channel)-1] = delays_ns_dict[str(channel)]
        bin = self.get_timebase()
        delays_bins = [int(d*1e-9/bin) for d in delays_ns]
        return self.set_channel_delays_bins(delays_bins)

def main():
   idq801 = Idq801()
   idq801.clean_data_directory()
   idq801.set_channel((1,2))
   #t1 = idq801.write_counters_to_file_continuous(2)
   #t2 = idq801.write_timestamps_to_file_continuous(2)
#
if __name__ == '__main__':
   main()
