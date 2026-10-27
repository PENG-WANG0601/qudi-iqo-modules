# -*- coding: utf-8 -*-

"""
Laser pulse extraction that takes the laser pulse positions from the loaded AWG waveform instead
of detecting them in the count data, so the result does not depend on count levels or
integration time.

Copyright (c) 2021, the qudi developers. See the AUTHORS.md file at the top-level directory of this
distribution and on <https://github.com/Ulm-IQO/qudi-iqo-modules/>

This file is part of qudi.

Qudi is free software: you can redistribute it and/or modify it under the terms of
the GNU Lesser General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.

Qudi is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License along with qudi.
If not, see <https://www.gnu.org/licenses/>.
"""

import numpy as np

from qudi.logic.pulsed.pulse_extractor import PulseExtractorBase


class LaserWindowExtractor(PulseExtractorBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_warning = None

    def _warn_once(self, message):
        # The analysis loop calls the extraction every tick; repeat a warning only if it changes.
        if message != self._last_warning:
            self._last_warning = message
            self.log.warning(message)

    # detection_delay default: measured on the 2Foci MultiHarp setup (Rabi calibration,
    # 2026-10-25): photons arrive 750 ns after the AWG laser marker.
    def ungated_laser_windows(self, count_data, detection_delay=750.0e-9, window_pre=100.0e-9,
                              window_post=300.0e-9):
        """ Cut one fixed window per laser pulse at the laser positions of the loaded waveform.

        number_of_lasers == 1: the whole recorded trace is returned as the single pulse (e.g.
        decay/charge sequences whose interesting data spans the full cycle).
        number_of_lasers > 1: window i covers
            [laser_on_i + detection_delay - window_pre, laser_off_i + detection_delay + window_post]
        on the counter time axis; all windows have the length of the longest laser pulse.

        @param numpy.ndarray count_data: 1D raw timetrace of an ungated fast counter
        @param float detection_delay: time from the AWG laser marker to the photons on the counter
                                      time axis (AOM/EOM response, cables, detector, sync offset)
        @param float window_pre: extra time kept before each laser pulse
        @param float window_post: extra time kept after each laser pulse

        @return dict: laser_counts_arr (2D: laser number, time bin), laser_indices_rising/falling
        """
        count_data = np.asarray(count_data)
        number_of_lasers = int(self.measurement_settings.get('number_of_lasers', 0))

        if number_of_lasers == 1:
            self._last_warning = None
            return {'laser_counts_arr': count_data.reshape(1, -1).astype('int64'),
                    'laser_indices_rising': np.zeros(1, dtype='int64'),
                    'laser_indices_falling': np.array([count_data.size - 1], dtype='int64')}

        info = self.sampling_information or dict()
        try:
            sample_rate = float(info['pulse_generator_settings']['sample_rate'])
            rising = np.asarray(info['laser_rising_bins'], dtype=float)
            falling = np.asarray(info['laser_falling_bins'], dtype=float)
        except (KeyError, TypeError):
            sample_rate, rising, falling = None, np.empty(0), np.empty(0)

        if sample_rate is None or rising.size != number_of_lasers or falling.size != number_of_lasers:
            self._warn_once(
                f'laser_windows: the loaded waveform has {rising.size} laser pulses but '
                f'number_of_lasers is {number_of_lasers}. No pulses extracted. Check that the '
                f'measured asset is the one loaded on the AWG and that "Invoke settings" is on.'
            )
            return {'laser_counts_arr': np.zeros((max(number_of_lasers, 1), 1), dtype='int64'),
                    'laser_indices_rising': np.zeros(max(number_of_lasers, 1), dtype='int64'),
                    'laser_indices_falling': np.zeros(max(number_of_lasers, 1), dtype='int64')}

        bin_width = float(self.fast_counter_settings['bin_width'])
        rising_bins = np.rint(rising / sample_rate / bin_width).astype('int64')
        falling_bins = np.rint(falling / sample_rate / bin_width).astype('int64')
        delay_bins = int(round(detection_delay / bin_width))
        pre_bins = max(0, int(round(window_pre / bin_width)))
        post_bins = max(0, int(round(window_post / bin_width)))
        num_col = int(np.max(falling_bins - rising_bins)) + pre_bins + post_bins

        starts = rising_bins + delay_bins - pre_bins
        indices = starts[:, None] + np.arange(num_col)
        outside = starts.min() < 0 or starts.max() + num_col > count_data.size

        # When one record is exactly one loop of the waveform (ungated counting of a repeating
        # sequence), photons delayed past the end of the loop are recorded at the start of the next
        # sweep, i.e. at the start of this same histogram -> wrap around instead of losing them.
        loop_samples = info.get('number_of_samples')
        loop_bins = None if loop_samples is None else loop_samples / sample_rate / bin_width
        is_one_loop = loop_bins is not None and abs(loop_bins - count_data.size) <= 2

        if outside and is_one_loop:
            laser_arr = np.take(count_data, indices, mode='wrap')
            self._last_warning = None
        else:
            if outside:
                self._warn_once(
                    'laser_windows: some windows reach outside the recorded trace and are '
                    'zero-filled there. Check detection_delay / window_pre / window_post and the '
                    'record length.'
                )
            else:
                self._last_warning = None
            pad = num_col + abs(delay_bins)
            laser_arr = np.pad(count_data, pad)[indices + pad]
        return {'laser_counts_arr': laser_arr.astype('int64'),
                'laser_indices_rising': rising_bins + delay_bins,
                'laser_indices_falling': falling_bins + delay_bins}
