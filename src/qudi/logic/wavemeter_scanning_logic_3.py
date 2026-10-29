# -*- coding: utf-8 -*-
"""
This file contains the qudi logic to continuously read data from a wavemeter device and eventually interpolates the
 acquired data with the simultaneously obtained counts from a time_series_reader_logic. It is intended to be used in
 conjunction with the high_finesse_wavemeter.py.

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

from PySide6 import QtCore
import numpy as np
import time
import matplotlib.pyplot as plt
import scipy.interpolate as interpolate

from qudi.core.connector import Connector
from qudi.core.configoption import ConfigOption
from qudi.core.module import LogicBase
from qudi.util.mutex import Mutex
from qudi.interface.data_instream_interface import StreamingMode, SampleTiming
from qudi.interface.data_instream_interface import DataInStreamConstraints
from qudi.util.datafitting import FitContainer, FitConfigurationsModel
from qudi.core.statusvariable import StatusVar
from qudi.util.network import netobtain
from typing import Tuple, Optional, Sequence, Union, List, Dict, Any, Mapping
from lmfit.model import ModelResult as _ModelResult
from qudi.util.datastorage import TextDataStorage
from scipy import constants


class WavemeterLogic(LogicBase):
    """
    Example config for copy-paste:

    wavemeter_scanning_logic:
        module.Class: 'wavemeter_scanning_logic_3.WavemeterLogic'
        options:
            count_channel: 'PFI8'  # optional, time series channel used as counts (needed if >1 active)
            paused_channels: ['PFI9']  # optional, time series channels paused while scanning
        connect:
            streamer: wavemeter
            counterlogic: time_series_reader_logic
    """
    # declare signals
    sigDataChanged = QtCore.Signal(object, object, object, object, object, object, object)
    sigStatusChanged = QtCore.Signal(bool)
    sigStatusChangedDisplaying = QtCore.Signal()
    sigNewWavelength2 = QtCore.Signal(object, object)
    sigFitChanged = QtCore.Signal(str, dict)  # fit_name, fit_results
    sigCountChannelChanged = QtCore.Signal(list, str)  # available channels, selected channel
    sigChannelDataChanged = QtCore.Signal(object)  # plot data of the other channels (dict)
    _sigNextWavelength = QtCore.Signal()  # internal signal

    # declare connectors
    _streamer = Connector(name='streamer', interface='DataInStreamInterface')
    # access on timeseries logic and thus nidaq instreamer
    _timeserieslogic = Connector(name='counterlogic', interface='TimeSeriesReaderLogic')

    # TODO status vars...
    # config options
    _count_channel_name = ConfigOption(name='count_channel', default=None, missing='nothing')
    _paused_channel_names = ConfigOption(name='paused_channels', default=list(), missing='nothing')
    _fit_config_model = StatusVar(name='fit_configs', default=list())
    # display and save all time series channels, not only the count channel
    _all_channels = StatusVar(name='all_channels', default=False)
    # plot the other channels on a separate (right) y-axis
    _separate_y_axes = StatusVar(name='separate_y_axes', default=False)

    def __init__(self, *args, **kwargs):
        """
        """
        super().__init__(*args, **kwargs)

        # locking for thread safety
        self.threadlock = Mutex()
        self.complete_histogram = False
        self._fit_container = None
        self.x_axis_hz_bool = False  # by default display wavelength
        self._is_wavelength_displaying = False
        self._delay_time = None
        self._stop_flag = False
        # count channel selected in the GUI (not saved, so every start uses the "count_channel"
        # ConfigOption as default)
        self._selected_count_channel = None
        # column of the count channel within the interleaved time series raw data
        self._count_channel_index = 0
        self._count_channel_number = 1

        # Data arrays #timings, counts, wavelength, wavelength in Hz
        self._trace_data = np.empty((4, 0), dtype=np.float64)
        self.timings = []
        self.counts = []
        self.wavelength = []
        self.frequency = []
        # counts of all time series channels: channel name -> list aligned with self.timings
        self.channel_counts = dict()
        self._scan_channels = list()
        self._scan_count_channel = None
        # per channel histograms: channel name -> array over histogram_axis
        self.channel_histogram = dict()
        self.channel_envelope_histogram = dict()
        self._channel_rawhisto = dict()
        self._channel_sumhisto = dict()
        self._channel_envelope = dict()

        self._bins = 200
        self._data_index = 0
        self._xmin_histo = 500.0e-9  # in SI units, default starting range
        self._xmax_histo = 750.0e-9
        self._xmin = 1  # default; to be changed upon first iteration
        self._xmax = -1
        self.number_of_displayed_points = 1000
        self.fit_histogram = True

        return

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """
        self._fit_container = FitContainer(config_model=self._fit_config_model)
        self._selected_count_channel = None  # start with the configured default (PFI8)
        self._last_fit_result = None

        # connect to time series
        self._time_series_logic = self._timeserieslogic()

        # create a new x axis from xmin to xmax with bins points
        self.histogram_axis = np.linspace(self._xmin_histo, self._xmax_histo, self._bins)
        self.histogram = np.zeros(self._bins)
        self.envelope_histogram = np.zeros(self._bins)
        self.rawhisto = np.zeros(self._bins)
        self.sumhisto = np.ones(self._bins) * 1.0e-10

        self._time_series_logic.sigStatusChanged.connect(
            self._on_time_series_status_changed, QtCore.Qt.QueuedConnection)
        self._time_series_logic.sigChannelSettingsChanged.connect(
            self._on_time_series_channels_changed, QtCore.Qt.QueuedConnection)
        return

    def on_deactivate(self):
        """ De-initialisation performed during deactivation of the module.
                """
        # Stop measurement
        if self._is_wavelength_displaying:
            self.stop_displaying_current_wavelength()
        elif self.module_state() == 'locked':
            self.stop_scanning()

        self._time_series_logic.sigStatusChanged.disconnect(self._on_time_series_status_changed)
        self._time_series_logic.sigChannelSettingsChanged.disconnect(
            self._on_time_series_channels_changed)
        return

    @QtCore.Slot(bool, bool)
    def _on_time_series_status_changed(self, running: bool, recording: bool) -> None:
        """Stop wavemeter scanning when the time series reader stops externally."""
        if not running and self.module_state() == 'locked':
            self.stop_scanning()

    @QtCore.Slot(list, list)
    def _on_time_series_channels_changed(self, enabled: list, averaged: list) -> None:
        self.sigCountChannelChanged.emit(list(enabled), self.count_channel or '')

    @property
    def count_channel_options(self) -> List[str]:
        """ Time series channels that can be used as count channel (the active ones) """
        return list(self._time_series_logic.active_channel_names)

    @property
    def count_channel(self) -> Optional[str]:
        """ Time series channel used as counts. Selection in the GUI takes precedence over the
        "count_channel" ConfigOption; falls back to the first active time series channel.
        """
        channels = self.count_channel_options
        for name in (self._selected_count_channel, self._count_channel_name):
            if name:
                matches = [ch for ch in channels if ch.lower() == name.lower()]
                if matches:
                    return matches[0]
        return channels[0] if channels else None

    @property
    def all_channels(self) -> bool:
        """ Display and save all time series channels, not only the count channel """
        return bool(self._all_channels)

    @QtCore.Slot(bool)
    def set_all_channels(self, enabled: bool) -> None:
        self._all_channels = bool(enabled)

    @property
    def separate_y_axes(self) -> bool:
        """ Plot the other channels on their own y-axis (GUI and saved thumbnail) """
        return bool(self._separate_y_axes)

    @QtCore.Slot(bool)
    def set_separate_y_axes(self, enabled: bool) -> None:
        self._separate_y_axes = bool(enabled)

    @property
    def other_channels(self) -> List[str]:
        """ Recorded channels other than the count channel of the (last) scan """
        return [ch for ch in self.channel_counts if ch != self._scan_count_channel]

    def get_channel_plot_data(self, n_points: Optional[int] = None) -> Dict[str, Any]:
        """ Plot data of the other channels. Only the n_points most recent raw data points are
        returned (all if None); histograms are always complete.
        """
        length = min([len(self.wavelength)] + [len(v) for v in self.channel_counts.values()])
        start = 0 if n_points is None else max(0, length - n_points)
        channels = self.other_channels
        return {
            'channels': channels,
            'wavelength': np.asarray(self.wavelength[start:length], dtype=float),
            'frequency': np.asarray(self.frequency[start:length], dtype=float),
            'counts': {ch: np.asarray(self.channel_counts[ch][start:length], dtype=float)
                       for ch in channels},
            'histogram_axis': self.histogram_axis.copy(),
            'histogram': {ch: self.channel_histogram.get(ch, np.zeros(self._bins)).copy()
                          for ch in channels},
            'envelope': {ch: self.channel_envelope_histogram.get(ch, np.zeros(self._bins)).copy()
                         for ch in channels},
        }

    def clear_channel_data(self) -> None:
        """ Clear the recorded data of all channels and their histograms """
        self.channel_counts = dict()
        self._reset_channel_histograms()

    def _append_channel_counts(self, all_counts: np.ndarray) -> None:
        """ Append a block of time series raw data (samples x self._scan_channels) """
        previous_length = len(self.timings)
        for ch in self._scan_channels:
            if ch not in self.channel_counts:
                self.channel_counts[ch] = [np.nan] * previous_length
        for ch, values in self.channel_counts.items():
            if ch in self._scan_channels:
                values.extend(all_counts[:, self._scan_channels.index(ch)].tolist())
            else:
                values.extend([np.nan] * all_counts.shape[0])

    def _reset_channel_histograms(self) -> None:
        self.channel_histogram = dict()
        self.channel_envelope_histogram = dict()
        self._channel_rawhisto = dict()
        self._channel_sumhisto = dict()
        self._channel_envelope = dict()

    def _update_channel_histograms(self, indices: List[int], bins: List[int]) -> None:
        """ Add the data points at the given indices to the per channel histograms """
        for ch, values in self.channel_counts.items():
            if ch not in self._channel_rawhisto or len(self._channel_rawhisto[ch]) != self._bins:
                self._channel_rawhisto[ch] = np.zeros(self._bins)
                self._channel_sumhisto[ch] = np.ones(self._bins) * 1.0e-10
                self._channel_envelope[ch] = np.zeros(self._bins)
            if indices:
                idx = np.asarray(indices)
                new_bins = np.asarray(bins)
                vals = np.asarray(values[idx[0]:idx[-1] + 1], dtype=float)[idx - idx[0]]
                valid = np.isfinite(vals)
                np.add.at(self._channel_rawhisto[ch], new_bins[valid], vals[valid])
                np.add.at(self._channel_sumhisto[ch], new_bins[valid], 1.0)
                np.maximum.at(self._channel_envelope[ch], new_bins[valid], vals[valid])
            histogram = self._channel_rawhisto[ch] / self._channel_sumhisto[ch]
            envelope = self._channel_envelope[ch].copy()
            # Bins without valid data of this channel (e.g. paused) while the count channel has
            # data are no data (NaN, shown as gap) rather than 0
            no_data = (self._channel_sumhisto[ch] < 0.5) & (self.sumhisto >= 0.5)
            histogram[no_data] = np.nan
            envelope[no_data] = np.nan
            self.channel_histogram[ch] = histogram
            self.channel_envelope_histogram[ch] = envelope

    @QtCore.Slot(str)
    def set_count_channel(self, channel: str) -> None:
        """ Select the time series channel used as counts. Not possible while scanning. """
        if self.module_state() == 'locked':
            self.log.warning('Unable to change the count channel while laser scanning.')
        elif channel:
            self._selected_count_channel = channel
        self.sigCountChannelChanged.emit(self.count_channel_options, self.count_channel or '')

    @property
    def streamer_constraints(self) -> DataInStreamConstraints:
        """ Retrieve the hardware constrains from the counter device """
        # netobtain is required if streamer is a remote module
        return netobtain(self._streamer().constraints)

    @QtCore.Slot(object)
    def _counts_and_wavelength(self, new_count_data=None, new_count_timings=None) -> None:
        """
                This method synchronizes (interpolates) the available data from both the timeseries logic and the wavemeter hardware module.
                It runs repeatedly by being connected to a QTimer timeout signal from the time series (sigNewRawData).
                Note: new_count_timing is currently unused, but might be used for a more elaborate synchronization.
                #TODO Assure that the timing below is synchronized at an acceptable level and saving of raw data
                """
        with self.threadlock:
            if self.module_state() == 'locked':
                # Pick the count channel out of the interleaved time series raw data, but keep
                # all channels for the "all channels" display/save
                all_counts = None
                if new_count_data is not None:
                    all_counts = np.asarray(new_count_data, dtype=float).reshape(
                        [-1, self._count_channel_number]
                    )
                    new_count_data = all_counts[:, self._count_channel_index]
                # Determine samples to read according to new_count_data size
                if new_count_data is not None:
                    samples_to_read_counts = len(new_count_data)

                try:
                    n = self._streamer().available_samples if self._streamer().available_samples > 1 else 1

                    raw_data_wavelength, raw_timings = self._streamer().read_data(samples_per_channel=n)
                    raw_data_wavelength = netobtain(raw_data_wavelength)  # netobtain due to remote connection
                    raw_timings = netobtain(raw_timings)
                    # Above buffers as an option to save the raw wavemeter values
                    if self._delay_time:
                        raw_timings += self._delay_time
                    # Here the interpolation is performed to match the counts onto wavelength
                    if n == 1:
                        wavemeter_data, new_timings = np.ones(samples_to_read_counts) * raw_data_wavelength, np.ones(
                            samples_to_read_counts) * raw_timings
                    else:
                        arr_interp = interpolate.interp1d(raw_timings, raw_data_wavelength)
                        new_timings = np.linspace(raw_timings[0],
                                                  raw_timings[-1],
                                                  samples_to_read_counts) if samples_to_read_counts > 1 else np.ones(
                            1) * np.mean(raw_timings)
                        wavemeter_data = arr_interp(new_timings)

                    if len(wavemeter_data) != len(new_timings) != len(new_count_data) != samples_to_read_counts:
                        self.log.error('Reading data from streamers went wrong; '
                                       'stopping the stream.')
                        self.stop_scanning()
                        return

                    # Process data
                    if all_counts is not None:
                        self._append_channel_counts(all_counts)
                    self._process_data_for_histogram(wavemeter_data, new_count_data, new_timings)
                    self._update_histogram(self.complete_histogram)

                    # Emit update signal for Gui
                    self.sigNewWavelength2.emit(self.wavelength[-1], self.frequency[-1])
                    # only display self.number_of_displayed_points most recent values
                    start = len(self.wavelength) - self.number_of_displayed_points if len(
                        self.wavelength) > self.number_of_displayed_points else 0
                    self.sigDataChanged.emit(self.timings[start:], self.counts[start:],
                                             self.wavelength[start:], self.frequency[start:], self.histogram_axis,
                                             self.histogram, self.envelope_histogram)
                    if self._all_channels:
                        self.sigChannelDataChanged.emit(
                            self.get_channel_plot_data(self.number_of_displayed_points)
                        )

                except TimeoutError as err:
                    self.log.warning(f'Timeout error: {err}')
                    self.stop_scanning()
                    return

                except Exception as e:
                    self.log.warning(f'Reading data from streamer went wrong: {e}')
                    self._time_series_logic.sigNewRawData.disconnect()
                    self._stop_cleanup()
                    return

    def _process_data_for_histogram(self, data_wavelength, data_counts, data_wavelength_timings):
        """Method for appending to whole data set of wavelength and counts (already interpolated)"""
        data_freq = constants.speed_of_light / data_wavelength
        for i in range(len(data_wavelength)):
            self.wavelength.append(data_wavelength[i])
            self.counts.append(data_counts[i])
            self.timings.append(data_wavelength_timings[i])
            self.frequency.append(data_freq[i])
        return

    def _update_histogram(self, complete_histogram):
        """ Calculate new points for the histogram.
        @param bool complete_histogram: should the complete histogram be recalculated, or just the
                                                most recent data?
        @return:
        """
        # reset data index
        if complete_histogram:
            self._data_index = 0
            self.complete_histogram = False

        # n+1-dimensional binning axis, to avoid empty bin when using np.digitize
        offset = (self.histogram_axis[1] - self.histogram_axis[0]) / 2
        binning_axis = np.linspace(self.histogram_axis[0] - offset, self.histogram_axis[-1] + offset,
                                   len(self.histogram_axis) + 1)

        # data indices and bins of the new points, used for the per channel histograms
        new_indices = list()
        new_bins = list()
        for i in self.wavelength[self._data_index:]:
            self._data_index += 1  # before because of continue

            if i < self._xmin:
                self._xmin = i
            if i > self._xmax:
                self._xmax = i
            if i < self._xmin_histo or i > self._xmax_histo or np.isnan(i):
                continue

            # calculate the bin the new wavelength needs to go in
            newbin = np.digitize([i], binning_axis)[0]

            # sum the counts in rawhisto and count the occurence of the bin in sumhisto
            self.rawhisto[newbin - 1] += self.counts[self._data_index - 1]
            self.sumhisto[newbin - 1] += 1.0

            self.envelope_histogram[newbin - 1] = np.max(
                [self.counts[self._data_index - 1], self.envelope_histogram[newbin - 1]])
            new_indices.append(self._data_index - 1)
            new_bins.append(newbin - 1)

        # the plot data is the summed counts divided by the occurence of the respective bins
        self.histogram = self.rawhisto / self.sumhisto
        self._update_channel_histograms(new_indices, new_bins)
        return

    @QtCore.Slot()
    def start_scanning(self):
        """
                Start data acquisition loop.
                """

        if self.module_state() == 'locked':
            self.log.warning('Data acquisition already running. "start_scanning" call ignored.')
            self.sigStatusChanged.emit(True)
            return

        if not self._time_series_logic.module_state() == 'locked':
            self.log.warning('Time series data acquisition has to be running!')
            self.sigStatusChanged.emit(False)
            return

        time_series_channels = self.count_channel_options
        count_channel = self.count_channel
        if count_channel is None:
            self.log.warning('No active time series channel to use as counts!')
            self.sigStatusChanged.emit(False)
            return
        paused_channels = [ch for ch in self._paused_channel_names
                           if ch.lower() != count_channel.lower()]

        if len(self._streamer().active_channels) != 1:
            self.log.warning('Only a single wavemeter channel supported.')
            self.sigStatusChanged.emit(False)
            return

        constraints = self.streamer_constraints
        unit = constraints.channel_units[self._streamer().active_channels[0]]
        if unit != 'm':
            self.log.warning('Make sure acquisition unit is m!')
            self.sigStatusChanged.emit(False)
            return

        self.module_state.lock()

        self._count_channel_index = time_series_channels.index(count_channel)
        self._count_channel_number = len(time_series_channels)
        self._scan_channels = list(time_series_channels)
        self._scan_count_channel = count_channel
        if paused_channels:
            try:
                self._time_series_logic.pause_channels(self.module_name, paused_channels)
            except Exception:
                self.log.exception('Unable to pause time series channels:')
                self.module_state.unlock()
                self.sigStatusChanged.emit(False)
                return

        self.sigStatusChanged.emit(True)

        if self._is_wavelength_displaying:
            self.stop_displaying_current_wavelength()

        self._time_series_logic.sigNewRawData.connect(
            self._counts_and_wavelength, QtCore.Qt.QueuedConnection)

        if not len(self.timings) == 0:
            self._delay_time = self.timings[-1] + time.time() - self._start
        self._streamer().start_stream()
        return 0

    @QtCore.Slot()
    def stop_scanning(self):
        """
                Send a request to stop counting.
                """
        if self.module_state() == 'locked':
            try:
                # disconnect to time series signal
                self._time_series_logic.sigNewRawData.disconnect()

                # terminate the hardware streaming device #TODO test with remote module
                self._streamer().stop_stream()
            except:
                self.log.exception('Error while trying to stop stream reader:')
                raise
            finally:
                self._stop_cleanup()
        return 0

    def _stop_cleanup(self) -> None:
        # save start_time information of high finesse wavemeter
        self.module_state.unlock()
        if self._paused_channel_names:
            try:
                self._time_series_logic.resume_channels(self.module_name)
            except Exception:
                self.log.exception('Unable to resume paused time series channels:')
        self._start = time.time()
        self.sigStatusChanged.emit(False)
        self._trace_data = np.vstack(((self.timings, self.counts), (self.wavelength, self.frequency)))

    def get_max_wavelength(self):
        """ Current maximum wavelength of the scan.
            @return float: current maximum wavelength
        """
        return self._xmax

    def get_min_wavelength(self):
        """ Current minimum wavelength of the scan.
            @return float: current minimum wavelength
        """
        return self._xmin

    def get_bins(self):
        """ Current number of bins in the spectrum.
            @return int: current number of bins in the scan
        """
        return self._bins

    def recalculate_histogram(self, bins=None, xmin=None, xmax=None):
        """ Recalculate the current spectrum from raw data.
            @praram int bins: new number of bins
            @param float xmin: new minimum wavelength
            @param float xmax: new maximum wavelength
        """
        if bins is not None:
            self._bins = bins
        if xmin is not None:
            self._xmin_histo = xmin
        if xmax is not None:
            self._xmax_histo = xmax

        # create a new x axis from xmin to xmax with bins points
        self.rawhisto = np.zeros(self._bins)
        self.envelope_histogram = np.zeros(self._bins)
        self.sumhisto = np.ones(self._bins) * 1.0e-10
        self.histogram_axis = np.linspace(self._xmin_histo, self._xmax_histo, self._bins)
        self._reset_channel_histograms()
        self.complete_histogram = True
        if not self.module_state() == 'locked':
            self._update_histogram(self.complete_histogram)
        return

    def display_current_wavelength(self) -> None:
        try:
            current_wavelength, trash_time = self._streamer().read_single_point()
            # netobtain due to remote connection
            current_wavelength = netobtain(current_wavelength)
            if len(current_wavelength) > 0:
                current_freq = constants.speed_of_light / current_wavelength  # in Hz
                self.sigNewWavelength2.emit(current_wavelength[0], current_freq[0])
            # display data at a rate of 10Hz
            time.sleep(0.1)
            self._sigNextWavelength.emit()
        except Exception as e:
            self.log.warning(f'Reading data from streamer went wrong: {e}')
            self._stop_flag = True
            self.sigStatusChangedDisplaying.emit()
            return

    def start_displaying_current_wavelength(self):
        if len(self._streamer().active_channels) != 1:
            self.log.warning('Only a single wavemeter channel supported.')
            self.sigStatusChanged.emit(False)
            return -1

        constraints = self.streamer_constraints
        unit = constraints.channel_units[self._streamer().active_channels[0]]
        if unit != 'm':
            self.log.warning('Make sure acquisition unit is m!')
            self.sigStatusChanged.emit(False)
            return -1

        self._streamer().start_stream()
        self._sigNextWavelength.connect(self.display_current_wavelength, QtCore.Qt.QueuedConnection)
        self._is_wavelength_displaying = True
        self._sigNextWavelength.emit()
        return 0

    def stop_displaying_current_wavelength(self) -> None:
        self._sigNextWavelength.disconnect()
        self._is_wavelength_displaying = False
        self._streamer().stop_stream()
        # TODO

    def autoscale_histogram(self):
        self._xmax_histo = self._xmax
        self._xmin_histo = self._xmin
        self.recalculate_histogram(self._bins, self._xmin_histo, self._xmax_histo)
        return

    @staticmethod
    @_fit_config_model.representer
    def __repr_fit_configs(value: FitConfigurationsModel) -> List[Dict[str, Any]]:
        return value.dump_configs()

    @_fit_config_model.constructor
    def __constr_fit_configs(self, value: Sequence[Mapping[str, Any]]) -> FitConfigurationsModel:
        model = FitConfigurationsModel(parent=self)
        model.load_configs(value)
        return model

    @property
    def fit_config_model(self) -> FitConfigurationsModel:
        return self._fit_config_model

    def get_fit_container(self) -> FitContainer:
        # with self.threadlock:
        return self._get_fit_container()

    def _get_fit_container(self) -> FitContainer:
        return self._fit_container

    def do_fit(self, fit_config: str) -> Dict[str, Union[None, _ModelResult]]:
        """ Perform desired fit

        @param str fit_config: name of the fit. Must match a fit configuration in fit_config_model.
        """
        with self.threadlock:
            valid_fit_configs = self._fit_config_model.configuration_names
            if (fit_config != 'No Fit') and (fit_config not in valid_fit_configs):
                raise ValueError(f'Unknown fit configuration "{fit_config}" encountered. '
                                 f'Options are: {valid_fit_configs}')
            return self._do_fit(fit_config)

    def _do_fit(self, fit_config: str) -> Dict[str, Union[None, _ModelResult]]:

        fit_container = self._get_fit_container()

        # fit the histogram
        if not self.x_axis_hz_bool:
            fit_results = fit_container.fit_data(fit_config=fit_config, x=self.histogram_axis,
                                                 data=self.histogram if self.fit_histogram else self.envelope_histogram)[
                1]
        elif self.x_axis_hz_bool:
            fit_results = \
                fit_container.fit_data(fit_config=fit_config, x=constants.speed_of_light / self.histogram_axis,
                                       data=self.histogram if self.fit_histogram else self.envelope_histogram)[1]
        fit_config = fit_container._last_fit_config
        self._last_fit_result = fit_results

        fit_container.sigLastFitResultChanged.emit(fit_config, fit_results)
        self.sigFitChanged.emit(fit_config, fit_results)
        return fit_results

    def get_fit_results(self) -> Tuple[str, Dict[str, Union[None, _ModelResult]]]:
        # with self.threadlock:
        return self._get_fit_results()

    def _get_fit_results(self) -> Tuple[str, Dict[str, Union[None, _ModelResult]]]:
        fit_container = self._get_fit_container()
        return fit_container._last_fit_config, self._last_fit_result

    def save_data(self, postfix: Optional[str] = None, root_dir: Optional[str] = None) -> str:
        """ Save data of a single plot to file.

        @param str postfix: optional, an additional tag added to the generic filename
        @param str root_dir: optional, define a deviating folder for the data to be saved into
        @return str: file path the data was saved to
        """
        self._trace_data = np.vstack(((self.timings, self.counts), (self.wavelength, self.frequency)))
        with self.threadlock:
            return self._save_data(postfix, root_dir)

    def _save_data(self, postfix: Optional[str] = None, root_dir: Optional[str] = None) -> str:
        """ Save data of a single plot to file.

        @param str postfix: optional, an additional tag added to the generic filename
        @param str root_dir: optional, define a deviating folder for the data to be saved into
        @return str: file path the data was saved to
        """
        fit_container = self._get_fit_container()
        if len(self._trace_data[0]) < 1:
            self.log.warning(f'No data found in plot. Save aborted.')
            return ''

        data_set = self._trace_data

        data_set_histogram = np.vstack((self.histogram_axis, self.histogram))
        data_set_histogram = np.vstack((data_set_histogram, self.envelope_histogram))

        parameters_histogram = {'Number of Bins': self.get_bins(),
                                'Min Wavelength Of Histogram (m)': self._xmin_histo,
                                'Max Wavelength Of Histogram (m)': self._xmax_histo,
                                'FitResults': fit_container.formatted_result(self._last_fit_result)}
        parameters = {'Count channel (Flourescence column)': self._scan_count_channel}

        file_label = postfix if postfix else 'qdLaserScanning'

        header = ['Timings (s)', 'Flourescence (counts/s)', 'Wavelength (m)', 'Frequency (Hz)']
        header_histogram = ['HistogramX', 'HistogramY', 'HistogramEnvelope']

        # Append one column per time series channel (raw data) and a histogram + envelope column
        # per channel (histogram data)
        channel_plot_data = None
        if self._all_channels and self.channel_counts:
            channels = list(self.channel_counts)
            length = min([data_set.shape[1]] + [len(v) for v in self.channel_counts.values()])
            data_set = np.vstack(
                [data_set[:, :length]] +
                [np.asarray(self.channel_counts[ch][:length], dtype=float) for ch in channels]
            )
            header += [f'{ch} (counts/s)' for ch in channels]
            for ch in channels:
                data_set_histogram = np.vstack((
                    data_set_histogram,
                    self.channel_histogram.get(ch, np.zeros(self._bins)),
                    self.channel_envelope_histogram.get(ch, np.zeros(self._bins))
                ))
                header_histogram += [f'HistogramY {ch}', f'HistogramEnvelope {ch}']
            parameters['Channels'] = ', '.join(channels)
            channel_plot_data = self.get_channel_plot_data()

        ds = TextDataStorage(
            root_dir=self.module_default_data_dir if root_dir is None else root_dir,
            column_formats='.15e',
            include_global_metadata=True)
        file_path, _, _ = ds.save_data(data_set.T,
                                       metadata=parameters,
                                       column_headers=header,
                                       column_dtypes=[float] * len(header),
                                       nametag=file_label)

        file_path, _, _ = ds.save_data(data_set_histogram.T,
                                       metadata=parameters_histogram,
                                       column_headers=header_histogram,
                                       column_dtypes=[float] * len(header_histogram),
                                       nametag=file_label + '_histogram')

        # plot graph and save as image alongside data file
        fig = self._plot_figure(self.x_axis_hz_bool, self.get_fit_results(), data_set, data_set_histogram,
                                fit_container, channel_plot_data, self.separate_y_axes)
        ds.save_thumbnail(fig, file_path=file_path.rsplit('.', 1)[0])

        self.log.debug(f'Data saved to: {file_path}')
        return file_path

    @staticmethod
    def _plot_figure(x_axis_bool, fitting, data_set, data_set_histogram,
                     fit_container: FitContainer,
                     channel_plot_data: Optional[Dict[str, Any]] = None,
                     separate_y_axes: bool = False) -> plt.Figure:

        fit_config, fit_results = fitting

        # High-resolution fit data and formatted result string
        if fit_results is not None:
            fit_data = fit_results.high_res_best_fit
            fit_result_str = fit_container.formatted_result(fit_results)
        else:
            fit_data = None
            fit_result_str = False

        fig, ax1 = plt.subplots()

        if not x_axis_bool:
            ax1.plot(data_set[2],
                     data_set[1],
                     linestyle=':',
                     linewidth=1,
                     label='RawData')
            ax1.plot(data_set_histogram[0],
                     data_set_histogram[1],
                     color='y',
                     label='Histogram')
            ax1.plot(data_set_histogram[0],
                     data_set_histogram[2],
                     color='g',
                     label='Envelope')
            if fit_data is not None:
                ax1.plot(fit_data[0],
                         fit_data[1],
                         color='r',
                         marker='None',
                         linewidth=1.5,
                         label='Fit')
        elif x_axis_bool:
            ax1.plot(data_set[3],
                     data_set[1],
                     linestyle=':',
                     linewidth=1,
                     label='RawData')
            ax1.plot(constants.speed_of_light / data_set_histogram[0],
                     data_set_histogram[1],
                     color='y',
                     label='Histogram')
            ax1.plot(constants.speed_of_light / data_set_histogram[0],
                     data_set_histogram[2],
                     color='g',
                     label='Envelope')
            if fit_data is not None:
                ax1.plot(fit_data[0],
                         fit_data[1],
                         color='r',
                         marker='None',
                         linewidth=1.5,
                         label='Fit')

        # Other time series channels ("all channels"), optionally on their own y-axis
        ax2 = None
        if channel_plot_data and channel_plot_data['channels']:
            ax2 = ax1.twinx() if separate_y_axes else None
            ax_ch = ax1 if ax2 is None else ax2
            x_raw = channel_plot_data['frequency' if x_axis_bool else 'wavelength']
            x_hist = channel_plot_data['histogram_axis']
            if x_axis_bool:
                x_hist = constants.speed_of_light / x_hist
            colors = ['tab:purple', 'tab:cyan', 'tab:brown', 'tab:pink']
            for i, ch in enumerate(channel_plot_data['channels']):
                color = colors[i % len(colors)]
                ax_ch.plot(x_raw, channel_plot_data['counts'][ch], linestyle=':', linewidth=1,
                           color=color, alpha=0.6, label=f'RawData {ch}')
                ax_ch.plot(x_hist, channel_plot_data['histogram'][ch], color=color,
                           label=f'Histogram {ch}')
                ax_ch.plot(x_hist, channel_plot_data['envelope'][ch], color=color,
                           linestyle='--', label=f'Envelope {ch}')
            if ax2 is not None:
                ax2.set_ylabel(f'{", ".join(channel_plot_data["channels"])} (counts/s)')

        # Do not include fit parameter if there is no fit calculated.
        if fit_result_str:
            # Parameters for the text plot:
            # The position of the text annotation is controlled with the
            # relative offset in x direction and the relative length factor
            # rel_len_fac of the longest entry in one column
            rel_offset = 0.02 if ax2 is None else 0.15
            rel_len_fac = 0.011
            entries_per_col = 24

            # do reverse processing to get each entry in a list
            entry_list = fit_result_str.split('\n')
            # slice the entry_list in entries_per_col
            chunks = [entry_list[x:x + entries_per_col] for x in
                      range(0, len(entry_list), entries_per_col)]

            is_first_column = True  # first entry should contain header or \n

            for column in chunks:
                max_length = max(column, key=len)  # get the longest entry
                column_text = ''

                for entry in column:
                    column_text += entry.rstrip() + '\n'

                column_text = column_text[:-1]  # remove the last new line

                heading = f'Fit results for "{fit_config}":' if is_first_column else ''
                column_text = f'{heading}\n{column_text}'

                ax1.text(1.00 + rel_offset,
                         0.99,
                         column_text,
                         verticalalignment='top',
                         horizontalalignment='left',
                         transform=ax1.transAxes,
                         fontsize=12)

                # the rel_offset in position of the text is a linear function
                # which depends on the longest entry in the column
                rel_offset += rel_len_fac * len(max_length)

                is_first_column = False

        # set labels, units and limits
        if not x_axis_bool:
            ax1.set_xlabel('Wavelength (m)')
        elif x_axis_bool:
            ax1.set_xlabel('Frequency (Hz)')

        ax1.set_ylabel('Flourescence (counts/s)')

        handles, labels = ax1.get_legend_handles_labels()
        if ax2 is not None:
            handles2, labels2 = ax2.get_legend_handles_labels()
            handles += handles2
            labels += labels2
        ax1.legend(handles, labels)

        fig.tight_layout()
        return fig
