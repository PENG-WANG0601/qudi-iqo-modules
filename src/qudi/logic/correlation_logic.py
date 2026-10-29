# -*- coding: utf-8 -*-
"""
Logic module driving a g(2) correlation measurement on a PicoQuant snAPI fast counter
(qudi.hardware.picoquant.snapi_fast_counter.SnapiFastCounter).

This connects directly to that concrete hardware class rather than through a formal qudi
interface: snAPI's Correlation API (setG2Parameters/measure/getG2Data) is specific to this one
hardware family, and there is no other implementation to abstract against. The fast counter and
a g(2) measurement share a single underlying snAPI device instance, so they cannot run at the
same time -- the hardware module itself enforces that; this logic just surfaces it.

Example configuration::

    correlation_logic:
        module.Class: 'correlation_logic.CorrelationLogic'
        options:
            start_channel: 1        # snAPI numbering: 0 = sync, 1..N = inputs
            stop_channel: 1         # same as start_channel -> autocorrelation
            window_size_s: 1.0e-6
            bin_width_s: null       # optional, defaults to device base resolution
            normalization: True
            poll_interval_s: 0.2
            live_fit_interval_s: 1.0  # optional, minimum time between live refits (0 = every poll)
            fit_curve_decimation: 10  # optional, fit curve has (data points / this) points
        connect:
            counter: 'fast_counter'

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

from __future__ import annotations

import re
import time
import datetime
from typing import Optional

import numpy as np
from matplotlib.figure import Figure
from PySide6 import QtCore

from qudi.core.connector import Connector
from qudi.core.configoption import ConfigOption
from qudi.core.statusvariable import StatusVar
from qudi.core.module import LogicBase
from qudi.util.datastorage import TextDataStorage, ImageFormat
from qudi.util.datafitting import FitContainer, FitConfigurationsModel, get_all_fit_models
from qudi.hardware.picoquant.snapi_fast_counter import SnapiFastCounter


class CorrelationFitContainer(FitContainer):
    """ FitContainer that applies global parameter overrides (e.g. a GUI-set t0) on top of the
    estimator and fit-configuration parameters, so they hold for every fit model that has a
    parameter of that name.
    """

    def __init__(self, *args, curve_decimation=10, **kwargs):
        super().__init__(*args, **kwargs)
        self.parameter_overrides = dict()  # parameter name -> kwargs for lmfit Parameter.set()
        self.curve_decimation = curve_decimation

    @staticmethod
    def _curve_points(x, y, n_points):
        """ Indices of n_points samples spread evenly along the curve's length (in axis-normalized
        units) instead of evenly in x: sparse where the curve is flat, dense in a narrow dip/peak,
        so a sharp antibunching dip keeps its shape with few points.
        """
        if x.size <= n_points:
            return np.arange(x.size)
        x_span = np.ptp(x) or 1.
        y_span = np.ptp(y) or 1.
        seg = np.hypot(np.diff(x) / x_span, np.diff(y) / y_span)
        arc = np.concatenate(([0.], np.cumsum(seg)))
        idx = np.searchsorted(arc, np.linspace(0., arc[-1], n_points))
        return np.unique(np.clip(np.concatenate((idx, [0, x.size - 1, np.argmin(y)])),
                                 0, x.size - 1))

    @QtCore.Slot(str, object, object)
    def fit_data(self, fit_config, x, data):
        # Same as FitContainer.fit_data, plus parameter_overrides applied last.
        with self._access_lock:
            if not fit_config:
                return '', None
            if fit_config == 'No Fit':
                self._last_fit_result = None
                self._last_fit_config = 'No Fit'
            else:
                config = self._configuration_model.get_configuration_by_name(fit_config)
                model = get_all_fit_models()[config.model]()
                if config.estimator is None:
                    parameters = model.make_params()
                else:
                    parameters = model.estimators[config.estimator](data, x)
                if config.custom_parameters is not None:
                    for name, param in config.custom_parameters.items():
                        parameters[name] = param
                for name, settings in self.parameter_overrides.items():
                    if name in parameters:
                        parameters[name].set(**settings)
                result = model.fit(data, parameters, x=x)
                # Displayed/saved fit curve: 1/curve_decimation of the data points (drawing a
                # dense curve on every live fit made the GUI lag), placed along the curve length.
                x_arr = np.asarray(x, dtype=float)
                y_fit = model.eval(**result.best_values, x=x_arr)
                n_points = max(50, x_arr.size // max(1, int(self.curve_decimation)))
                idx = self._curve_points(x_arr, y_fit, n_points)
                result.high_res_best_fit = (x_arr[idx], y_fit[idx])
                self._last_fit_result = result
                self._last_fit_config = fit_config
            self.sigLastFitResultChanged.emit(self._last_fit_config, self._last_fit_result)
            return self._last_fit_config, self._last_fit_result


class CorrelationLogic(LogicBase):
    """ Drives a g(2) correlation measurement on the snAPI fast counter and polls live data. """

    # declare signals
    sigDataUpdated = QtCore.Signal(object, object)  # tau_s (1D array), g2 (1D array)
    sigStatusChanged = QtCore.Signal(bool)  # True while a measurement is running
    sigSettingsChanged = QtCore.Signal(dict)
    sigFitUpdated = QtCore.Signal(str, object)  # fit config name, lmfit.ModelResult or None
    _sigStartTimer = QtCore.Signal()  # internal, used to (re)start __poll_timer on its own thread
    _sigStopTimer = QtCore.Signal()

    # declare connectors
    _counter = Connector(name='counter', interface=SnapiFastCounter)

    # config options
    _start_channel = ConfigOption('start_channel', 1, missing='nothing')
    _stop_channel = ConfigOption('stop_channel', 1, missing='nothing')
    _window_size_s = ConfigOption('window_size_s', 1.0e-6, missing='nothing')
    _bin_width_s = ConfigOption('bin_width_s', None, missing='nothing')
    _normalization = ConfigOption('normalization', True, missing='nothing')
    _poll_interval_s = ConfigOption('poll_interval_s', 0.2, missing='nothing')
    # Live fit reruns the fit on new data at most this often; 0 = with every data update
    # (poll_interval_s). It runs on this module's thread and delays data polling while it fits.
    _live_fit_interval_s = ConfigOption('live_fit_interval_s', 1.0, missing='nothing')
    # The fit curve is shown/saved with (number of data points / fit_curve_decimation) points
    _fit_curve_decimation = ConfigOption('fit_curve_decimation', 10, missing='nothing')

    # status vars -- last-used settings, offered back as defaults on the next activation
    acquisition_time_s = StatusVar('acquisition_time_s', default=0.0)
    _fit_configs = StatusVar(name='fit_configs', default=None)
    _fit_t0_s = StatusVar(name='fit_t0_s', default=0.0)
    _fit_t0_fixed = StatusVar(name='fit_t0_fixed', default=False)

    _default_fit_configs = (
        {'name': 'Antibunching (full)', 'model': 'G2Antibunching',
         'estimator': 'Full', 'custom_parameters': None},
        {'name': 'Antibunching (no bunching)', 'model': 'G2Antibunching',
         'estimator': 'No bunching', 'custom_parameters': None},
        {'name': 'Antibunching (no SNR factor)', 'model': 'G2Antibunching',
         'estimator': 'No SNR factor', 'custom_parameters': None},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__poll_timer: Optional[QtCore.QTimer] = None
        self._running = False
        self.tau = np.zeros(0, dtype=np.float64)
        self.g2 = np.zeros(0, dtype=np.float64)
        self.fit_config_model = None
        self.fc = None
        self._fit_result = None
        self._fit_config = ''
        self._live_fit_config = ''
        self._last_live_fit_time = 0.0

    @_fit_configs.representer
    def __repr_fit_configs(self, value):
        configs = self.fit_config_model.dump_configs()
        return configs if configs else None

    @_fit_configs.constructor
    def __constr_fit_configs(self, value):
        return value if value else list(self._default_fit_configs)

    def on_activate(self):
        if self._poll_interval_s <= 0:
            raise ValueError('poll_interval_s must be greater than zero.')
        if self._window_size_s <= 0:
            raise ValueError('window_size_s must be greater than zero.')

        self._running = False
        self.tau = np.zeros(0, dtype=np.float64)
        self.g2 = np.zeros(0, dtype=np.float64)

        self.fit_config_model = FitConfigurationsModel(parent=self)
        self.fit_config_model.load_configs(self._fit_configs)
        self.fc = CorrelationFitContainer(parent=self, config_model=self.fit_config_model,
                                          curve_decimation=self._fit_curve_decimation)
        self._fit_result = None
        self._fit_config = ''
        self._live_fit_config = ''
        self._apply_t0_override()

        # QTimer must be created here rather than __init__, same reasoning as elsewhere in qudi:
        # it needs to live on this module's own worker thread, which only exists once activated.
        self.__poll_timer = QtCore.QTimer()
        self.__poll_timer.setSingleShot(False)
        self.__poll_timer.setInterval(round(1000. * self._poll_interval_s))
        self.__poll_timer.timeout.connect(self._poll_loop, QtCore.Qt.ConnectionType.QueuedConnection)
        self._sigStartTimer.connect(self.__poll_timer.start, QtCore.Qt.ConnectionType.QueuedConnection)
        self._sigStopTimer.connect(self.__poll_timer.stop, QtCore.Qt.ConnectionType.QueuedConnection)

    def on_deactivate(self):
        if self._running:
            self.stop_measurement()
        self._sigStartTimer.disconnect()
        self._sigStopTimer.disconnect()
        self.__poll_timer.timeout.disconnect()
        self.__poll_timer = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def settings(self) -> dict:
        return {
            'start_channel': self._start_channel,
            'stop_channel': self._stop_channel,
            'window_size_s': self._window_size_s,
            'bin_width_s': self._bin_width_s,
            'normalization': self._normalization,
            'acquisition_time_s': self.acquisition_time_s,
        }

    @property
    def bin_width_choices(self):
        """ Achievable bin widths (seconds), same list/floor the fast counter itself advertises
        (hardware_binwidth_list, already filtered by its own min_binwidth_s config option).
        """
        return list(self._counter().get_constraints()['hardware_binwidth_list'])

    def configure(self, start_channel=None, stop_channel=None, window_size_s=None,
                  bin_width_s=None, normalization=None):
        """ Update g(2) settings. Any argument left as None keeps its current value. """
        if self._running:
            raise RuntimeError('Cannot change settings while a measurement is running.')

        if start_channel is not None:
            self._start_channel = int(start_channel)
        if stop_channel is not None:
            self._stop_channel = int(stop_channel)
        if window_size_s is not None:
            if window_size_s <= 0:
                raise ValueError('window_size_s must be greater than zero.')
            self._window_size_s = float(window_size_s)
        if bin_width_s is not None:
            self._bin_width_s = float(bin_width_s)
        if normalization is not None:
            self._normalization = bool(normalization)

        self.sigSettingsChanged.emit(self.settings)

    def start_measurement(self, acquisition_time_s: Optional[float] = None):
        """ Configure and start a g(2) measurement. acquisition_time_s=0 runs until stopped. """
        if self._running:
            return

        if acquisition_time_s is not None:
            self.acquisition_time_s = float(acquisition_time_s)

        self.tau = np.zeros(0, dtype=np.float64)
        self.g2 = np.zeros(0, dtype=np.float64)

        self._counter().configure_g2(
            self._start_channel, self._stop_channel, self._window_size_s, self._bin_width_s,
            self._normalization,
        )
        self._counter().start_g2_measurement(self.acquisition_time_s)

        self._running = True
        self.sigStatusChanged.emit(True)
        self._sigStartTimer.emit()

    def stop_measurement(self):
        """ Stop a running g(2) measurement, keeping the last data received. """
        if not self._running:
            return

        self._sigStopTimer.emit()
        try:
            self._counter().stop_g2_measurement()
        finally:
            self._running = False
            self.sigStatusChanged.emit(False)

    def set_channel_trigger(self, channel: int, level_mv: int, edge: int):
        """ Set a discriminator trigger level/edge. channel: 0 = sync, 1..N = inputs. """
        self._counter().set_channel_trigger(channel, level_mv, edge)

    def get_channel_trigger(self, channel: int):
        """ Read back a discriminator trigger level/edge. channel: 0 = sync, 1..N = inputs.

        @return tuple(int, int): (level_mv, edge) -- edge: 0 = falling, 1 = rising
        """
        return self._counter().get_channel_trigger(channel)

    @property
    def fit_t0(self):
        """ (t0_s, fixed): global detuning applied to every fit model with a "t0" parameter.
        fixed=True pins t0 to t0_s; fixed=False lets each fit estimate and vary t0 itself.
        """
        return float(self._fit_t0_s), bool(self._fit_t0_fixed)

    @QtCore.Slot(float, bool)
    def set_fit_t0(self, t0_s: float, fixed: bool):
        self._fit_t0_s = float(t0_s)
        self._fit_t0_fixed = bool(fixed)
        self._apply_t0_override()

    def _apply_t0_override(self):
        if self._fit_t0_fixed:
            self.fc.parameter_overrides['t0'] = {'value': float(self._fit_t0_s), 'vary': False}
        else:
            self.fc.parameter_overrides.pop('t0', None)

    @property
    def fit_result(self):
        return self._fit_result

    @property
    def fit_config(self) -> str:
        """ Name of the fit configuration that produced fit_result ('' if there is none). """
        return self._fit_config

    @QtCore.Slot(str)
    def do_fit(self, fit_config: str):
        """ Fit the current g(2) data with the named fit configuration ('No Fit' clears it). """
        if self.tau.size == 0 and fit_config != 'No Fit':
            self.log.warning('No g(2) data to fit yet.')
            return None
        try:
            config, result = self.fc.fit_data(fit_config, self.tau.copy(), self.g2.copy())
        except Exception:
            config, result = '', None
            self.log.exception('g(2) fit "%s" failed.', fit_config)
        self._fit_result = result
        self._fit_config = config if result is not None else ''
        self.sigFitUpdated.emit(config, result)
        return result

    @QtCore.Slot(str)
    def set_live_fit(self, fit_config: str):
        """ Refit with <fit_config> as new data arrives during a measurement; '' turns it off. """
        self._live_fit_config = '' if fit_config in ('', 'No Fit') else fit_config
        self._last_live_fit_time = 0.0

    def save_data(self, tag: Optional[str] = None, notes: Optional[str] = None) -> str:
        """ Save the currently held tau/g(2) data to a text file, plus a PNG plot of it next to the
        file (same name, .png), including the fit curve if a fit is active.

        @param str tag: optional measurement name; files are named
                        <timestamp>_g2_correlation_<tag> and the name is stored in the header
        @param str notes: optional free-text note stored as-is in the file header
        @return str: the path the data was saved to
        """
        if self.tau.size == 0:
            raise RuntimeError('No g(2) data to save yet -- run a measurement first.')

        name = tag.strip() if isinstance(tag, str) else ''
        # Windows-safe file name part: characters not allowed in file names -> '_'
        safe_name = re.sub(r'[<>:"/\\|?*\s]+', '_', name).strip('._')
        nametag = f'g2_correlation_{safe_name}' if safe_name else 'g2_correlation'

        data_storage = TextDataStorage(root_dir=self.module_default_data_dir,
                                       image_format=ImageFormat.PNG)
        metadata = {
            'measurement_name': name,
            'start_channel': self._start_channel,
            'stop_channel': self._stop_channel,
            'window_size_s': self._window_size_s,
            'bin_width_s': self._bin_width_s if self._bin_width_s is not None else 'auto (device base resolution)',
            'normalization': self._normalization,
            'acquisition_time_s': self.acquisition_time_s,
        }
        fit_result = self._fit_result
        if fit_result is not None:
            metadata['fit_config'] = self._fit_config
            metadata['fit'] = self.fc.dict_result(fit_result)
            metadata['fit_t0_fixed'] = self._fit_t0_fixed
        data = np.vstack((self.tau, self.g2)).transpose()
        file_path, _, _ = data_storage.save_data(
            data,
            metadata=metadata,
            nametag=nametag,
            timestamp=datetime.datetime.now(),
            notes=notes,
            column_headers=('tau (s)', 'g(2)'),
        )
        self.log.info('g(2) data saved to %s', file_path)

        try:
            fig = self._draw_figure(self.tau, self.g2, fit_result, name)
            image_path = data_storage.save_thumbnail(fig, file_path=file_path.rsplit('.', 1)[0])
            self.log.info('g(2) plot saved to %s', image_path)
        except Exception:
            self.log.exception('Could not save the g(2) plot image (data file was saved).')
        return file_path

    def _draw_figure(self, tau, g2, fit_result=None, name='') -> Figure:
        """ Plot of the g(2) data (and fit curve, if given) for the saved PNG. """
        # Figure instead of pyplot: this runs on the logic thread, pyplot is not thread-safe.
        fig = Figure(figsize=(8, 5), dpi=150)
        ax = fig.add_subplot(111)
        ax.plot(tau * 1e9, g2, color='tab:blue', linewidth=0.8, label='data')
        if fit_result is not None:
            fit_x, fit_y = fit_result.high_res_best_fit
            ax.plot(np.asarray(fit_x) * 1e9, fit_y, color='tab:red', linewidth=1.5,
                    label=f'fit: {self._fit_config}')
            lines = []
            for param_name, param in fit_result.params.items():
                is_time = param_name in ('t0', 'tau1', 'tau2')
                value = param.value * 1e9 if is_time else param.value
                unit = ' ns' if is_time else ''
                error = '' if param.stderr is None or not param.vary else (
                    f' ± {param.stderr * 1e9 if unit else param.stderr:.3g}')
                fixed = '' if param.vary else ' (fixed)'
                lines.append(f'{param_name} = {value:.4g}{error}{unit}{fixed}')
            ax.text(0.99, 0.02, '\n'.join(lines), transform=ax.transAxes, ha='right',
                    va='bottom', fontsize=8, family='monospace',
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            ax.legend(loc='upper right', fontsize=8)
        ax.set_xlabel('τ (ns)')
        ax.set_ylabel('g(2)(τ)' if self._normalization else 'coincidences')
        ax.set_xlim(tau[0] * 1e9, tau[-1] * 1e9)
        title = f'g(2): channel {self._start_channel} → channel {self._stop_channel}'
        ax.set_title(f'{name}\n{title}' if name else title)
        ax.grid(alpha=0.3)
        return fig

    def _poll_loop(self):
        try:
            self.tau, self.g2 = self._counter().get_g2_data()
            self.sigDataUpdated.emit(self.tau, self.g2)

            # acquisition_time_s == 0 means "run until stop_measurement() is called" -- checking
            # is_g2_finished() in that case makes no sense (there is no time-based completion to
            # detect) and is what caused the measurement to appear to stop almost immediately:
            # snAPI's "finished" flag is a single ctypes value reused across every measure() call
            # on the same Correlation object, so it could still read stale from the previous run
            # for the first poll or two. Bounded (> 0) measurements still auto-stop normally.
            if self._live_fit_config and self.tau.size > 0:
                now = time.monotonic()
                if now - self._last_live_fit_time >= self._live_fit_interval_s:
                    self._last_live_fit_time = now
                    self.do_fit(self._live_fit_config)

            if self.acquisition_time_s > 0 and self._counter().is_g2_finished():
                self.stop_measurement()
        except Exception:
            self.log.exception('Error while polling g(2) data; stopping measurement.')
            self.stop_measurement()
