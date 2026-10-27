# -*- coding: utf-8 -*-
"""
GUI module for a g(2) correlation measurement, driven by CorrelationLogic.

Example configuration::

    correlation_gui:
        module.Class: 'correlation.correlation_gui.CorrelationGui'
        connect:
            correlation_logic: 'correlation_logic'

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

__all__ = ['CorrelationGui']

import pyqtgraph as pg
from PySide6 import QtCore

from qudi.core.connector import Connector
from qudi.core.module import GuiBase
from qudi.util.colordefs import QudiPalettePale as palette
from qudi.util.widgets.fitting import FitConfigurationDialog
from qudi.gui.correlation.correlation_main_window import CorrelationMainWindow
from qudi.logic.correlation_logic import CorrelationLogic


class CorrelationGui(GuiBase):
    """ GUI module to be used in conjunction with CorrelationLogic. """

    # declare connectors
    _logic = Connector(name='correlation_logic', interface=CorrelationLogic)

    # GUI -> logic signals, queued so they execute on the logic module's own thread
    sigStart = QtCore.Signal(object)  # acquisition_time_s or None
    sigStop = QtCore.Signal()
    sigConfigure = QtCore.Signal(dict)
    sigSetChannelTrigger = QtCore.Signal(int, int, int)  # channel, level_mv, edge
    sigSetFitT0 = QtCore.Signal(float, bool)  # t0_s, fixed
    sigSetLiveFit = QtCore.Signal(str)  # fit config name, '' = off

    sigDoFit = QtCore.Signal(str)  # fit config name ('No Fit' clears the fit)

    _default_fit_config = 'No Fit'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mw = None
        self._g2_curve = None
        self._fit_curve = None
        self._fcd = None
        self._fitted_t0 = None

    def on_activate(self):
        self._mw = CorrelationMainWindow()
        logic = self._logic()

        # Plot curve with peak-preserving downsampling -- learned the hard way elsewhere in this
        # session that an un-downsampled pyqtgraph curve redrawn every poll tick can freeze the UI
        # once the array gets large (here: driven by window_size_s / bin_width_s).
        self._g2_curve = pg.PlotDataItem(pen=palette.c1)
        self._g2_curve.setDownsampling(auto=True, method='peak')
        self._g2_curve.setClipToView(True)
        self._mw.g2_plot_widget.addItem(self._g2_curve)

        # Populate settings fields from the logic's current configuration
        settings = logic.settings
        sw = self._mw.settings_dockwidget
        sw.start_channel_combobox.setCurrentIndex(sw.start_channel_combobox.findData(settings['start_channel']))
        sw.stop_channel_combobox.setCurrentIndex(sw.stop_channel_combobox.findData(settings['stop_channel']))
        sw.window_size_spinbox.setValue(settings['window_size_s'])
        sw.set_bin_width_choices(logic.bin_width_choices)
        bin_width_index = sw.bin_width_combobox.findData(settings['bin_width_s'])
        sw.bin_width_combobox.setCurrentIndex(bin_width_index if bin_width_index >= 0 else 0)
        sw.normalization_checkbox.setChecked(settings['normalization'])
        sw.acquisition_time_spinbox.setValue(settings['acquisition_time_s'])

        # Populate the per-channel trigger table with the real values currently on the device,
        # not placeholder defaults -- same reasoning as reading back fast_counter_settings earlier
        # this session rather than assuming the GUI state matches the hardware.
        tw = self._mw.trigger_dockwidget
        for channel, level_spinbox in tw.level_spinboxes.items():
            try:
                level_mv, edge = logic.get_channel_trigger(channel)
            except Exception:
                self.log.exception('Could not read back trigger settings for channel %s.', channel)
                continue
            level_spinbox.blockSignals(True)
            level_spinbox.setValue(level_mv)
            level_spinbox.blockSignals(False)
            edge_combobox = tw.edge_comboboxes[channel]
            edge_combobox.blockSignals(True)
            edge_combobox.setCurrentIndex(edge_combobox.findData(edge))
            edge_combobox.blockSignals(False)

        # User interactions -> this module's own slots
        self._mw.start_stop_action.triggered[bool].connect(self._start_stop_toggled)
        self._mw.save_action.triggered.connect(logic.save_data, QtCore.Qt.ConnectionType.QueuedConnection)
        sw.start_channel_combobox.currentIndexChanged.connect(self._settings_changed)
        sw.stop_channel_combobox.currentIndexChanged.connect(self._settings_changed)
        sw.window_size_spinbox.editingFinished.connect(self._settings_changed)
        sw.bin_width_combobox.currentIndexChanged.connect(self._settings_changed)
        sw.normalization_checkbox.toggled.connect(self._settings_changed)
        for channel in tw.level_spinboxes:
            tw.level_spinboxes[channel].editingFinished.connect(self._make_trigger_changed(channel))
            tw.edge_comboboxes[channel].currentIndexChanged.connect(self._make_trigger_changed(channel))

        # This module's signals -> logic, queued (logic runs on its own thread)
        self.sigStart.connect(logic.start_measurement, QtCore.Qt.ConnectionType.QueuedConnection)
        self.sigStop.connect(logic.stop_measurement, QtCore.Qt.ConnectionType.QueuedConnection)
        self.sigConfigure.connect(
            lambda kwargs: logic.configure(**kwargs), QtCore.Qt.ConnectionType.QueuedConnection
        )
        self.sigSetChannelTrigger.connect(
            logic.set_channel_trigger, QtCore.Qt.ConnectionType.QueuedConnection
        )

        # Logic's signals -> this module's update slots, queued (cross-thread)
        logic.sigDataUpdated.connect(self.update_data, QtCore.Qt.ConnectionType.QueuedConnection)
        logic.sigStatusChanged.connect(self.update_status, QtCore.Qt.ConnectionType.QueuedConnection)

        self._activate_fit_ui(logic)

        self.update_status(logic.is_running)
        self.show()

    def _activate_fit_ui(self, logic):
        # The fit curve stays on the plot permanently, drawn above the data; "no fit" = empty data.
        # Only downsampled (it has 10x the data points), not clipped to the view, so it can never
        # end up hidden by a stale clip range.
        self._fit_curve = pg.PlotDataItem(pen=pg.mkPen(palette.c2, width=2))
        self._fit_curve.setDownsampling(auto=True, method='mean')
        self._fit_curve.setZValue(10)
        self._mw.g2_plot_widget.addItem(self._fit_curve)

        fw = self._mw.fit_dockwidget
        fw.fit_widget.link_fit_container(logic.fc)
        # Show the logic's current fit (e.g. after reopening the window), otherwise "No Fit"
        start_config = logic.fit_config if logic.fit_result is not None else self._default_fit_config
        start_index = fw.fit_widget.selection_combobox.findText(start_config)
        fw.fit_widget.selection_combobox.setCurrentIndex(max(start_index, 0))
        self._fcd = FitConfigurationDialog(parent=self._mw, fit_config_model=logic.fit_config_model)

        t0_s, t0_fixed = logic.fit_t0
        fw.t0_spinbox.setValue(t0_s)
        fw.t0_fixed_checkbox.setChecked(t0_fixed)

        self._mw.fit_settings_action.triggered.connect(self._fcd.show)
        fw.fit_widget.sigDoFit.connect(self.sigDoFit)
        self.sigDoFit.connect(logic.do_fit, QtCore.Qt.ConnectionType.QueuedConnection)
        fw.t0_spinbox.editingFinished.connect(self._fit_t0_changed)
        fw.t0_fixed_checkbox.toggled.connect(self._fit_t0_changed)
        fw.use_fitted_t0_button.clicked.connect(self._use_fitted_t0)
        fw.live_fit_checkbox.toggled.connect(self._live_fit_changed)
        fw.fit_widget.selection_combobox.currentTextChanged.connect(self._fit_selection_changed)
        self.sigSetFitT0.connect(logic.set_fit_t0, QtCore.Qt.ConnectionType.QueuedConnection)
        self.sigSetLiveFit.connect(logic.set_live_fit, QtCore.Qt.ConnectionType.QueuedConnection)
        logic.sigFitUpdated.connect(self.update_fit, QtCore.Qt.ConnectionType.QueuedConnection)

        self.update_fit(logic.fit_config, logic.fit_result)

    def _deactivate_fit_ui(self, logic):
        fw = self._mw.fit_dockwidget
        self.sigSetLiveFit.emit('')
        self._mw.fit_settings_action.triggered.disconnect()
        fw.fit_widget.sigDoFit.disconnect()
        self.sigDoFit.disconnect()
        fw.t0_spinbox.editingFinished.disconnect()
        fw.t0_fixed_checkbox.toggled.disconnect()
        fw.use_fitted_t0_button.clicked.disconnect()
        fw.live_fit_checkbox.toggled.disconnect()
        fw.fit_widget.selection_combobox.currentTextChanged.disconnect(self._fit_selection_changed)
        self.sigSetFitT0.disconnect()
        self.sigSetLiveFit.disconnect()
        logic.sigFitUpdated.disconnect(self.update_fit)
        fw.fit_widget.link_fit_container(None)
        self._fcd.close()
        self._fcd = None
        self._fit_curve = None

    def on_deactivate(self):
        logic = self._logic()

        self._deactivate_fit_ui(logic)
        self._mw.start_stop_action.triggered[bool].disconnect()
        self._mw.save_action.triggered.disconnect()
        sw = self._mw.settings_dockwidget
        sw.start_channel_combobox.currentIndexChanged.disconnect()
        sw.stop_channel_combobox.currentIndexChanged.disconnect()
        sw.window_size_spinbox.editingFinished.disconnect()
        sw.bin_width_combobox.currentIndexChanged.disconnect()
        sw.normalization_checkbox.toggled.disconnect()
        tw = self._mw.trigger_dockwidget
        for channel in tw.level_spinboxes:
            tw.level_spinboxes[channel].editingFinished.disconnect()
            tw.edge_comboboxes[channel].currentIndexChanged.disconnect()

        self.sigStart.disconnect()
        self.sigStop.disconnect()
        self.sigConfigure.disconnect()
        self.sigSetChannelTrigger.disconnect()
        logic.sigDataUpdated.disconnect(self.update_data)
        logic.sigStatusChanged.disconnect(self.update_status)

        self._mw.close()
        self._mw = None
        self._g2_curve = None

    def show(self):
        self._mw.show()
        self._mw.activateWindow()
        self._mw.raise_()

    def _start_stop_toggled(self, checked: bool):
        if checked:
            acquisition_time_s = self._mw.settings_dockwidget.acquisition_time_spinbox.value()
            self.sigStart.emit(acquisition_time_s)
        else:
            self.sigStop.emit()

    def _settings_changed(self):
        sw = self._mw.settings_dockwidget
        self.sigConfigure.emit({
            'start_channel': sw.start_channel_combobox.currentData(),
            'stop_channel': sw.stop_channel_combobox.currentData(),
            'window_size_s': sw.window_size_spinbox.value(),
            'bin_width_s': sw.bin_width_combobox.currentData(),
            'normalization': sw.normalization_checkbox.isChecked(),
        })

    def _make_trigger_changed(self, channel: int):
        """ Returns a slot that pushes the current level/edge for one fixed channel. """
        def _slot(*_args):
            tw = self._mw.trigger_dockwidget
            level_mv = tw.level_spinboxes[channel].value()
            edge = tw.edge_comboboxes[channel].currentData()
            self.sigSetChannelTrigger.emit(channel, level_mv, edge)
        return _slot

    def _fit_t0_changed(self, *_args):
        fw = self._mw.fit_dockwidget
        self.sigSetFitT0.emit(fw.t0_spinbox.value(), fw.t0_fixed_checkbox.isChecked())

    def _use_fitted_t0(self):
        if self._fitted_t0 is not None:
            self._mw.fit_dockwidget.t0_spinbox.setValue(self._fitted_t0)
            self._fit_t0_changed()

    def _live_fit_changed(self, *_args):
        fw = self._mw.fit_dockwidget
        config = fw.fit_widget.selection_combobox.currentText()
        live = fw.live_fit_checkbox.isChecked() and config != 'No Fit'
        self.sigSetLiveFit.emit(config if live else '')
        if live:
            # Fit right away instead of waiting for the next data update (also when idle)
            self.sigDoFit.emit(config)

    def _fit_selection_changed(self, config):
        if config == 'No Fit':
            # Selecting "No Fit" removes the fit (curve, result, saved fit metadata) immediately
            self.sigDoFit.emit('No Fit')
        self._live_fit_changed()

    def update_fit(self, fit_config, result):
        if not fit_config or fit_config == 'No Fit' or result is None:
            self._fit_curve.setData([], [])
            self._fitted_t0 = None
        else:
            fit_x, fit_y = result.high_res_best_fit
            self._fit_curve.setData(x=fit_x, y=fit_y)
            t0_param = result.params.get('t0')
            self._fitted_t0 = None if t0_param is None else float(t0_param.value)
        self._mw.fit_dockwidget.use_fitted_t0_button.setEnabled(self._fitted_t0 is not None)

    def update_data(self, tau, g2):
        self._g2_curve.setData(x=tau, y=g2)

    def update_status(self, running: bool):
        self._mw.start_stop_action.blockSignals(True)
        self._mw.start_stop_action.setChecked(running)
        self._mw.start_stop_action.setText('Stop' if running else 'Start')
        self._mw.start_stop_action.blockSignals(False)
        self._mw.status_label.setText('Running' if running else 'Idle')
        self._mw.settings_dockwidget.setEnabled(not running)
        self._mw.trigger_dockwidget.setEnabled(not running)
