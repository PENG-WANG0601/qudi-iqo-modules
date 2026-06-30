# -*- coding: utf-8 -*-

"""
This module controls a spectrometer through the Princeton Instruments LightField
software using its .NET automation API (accessed from Python via pythonnet/clr).

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

import os
import sys
import threading

import numpy as np

from qudi.core.configoption import ConfigOption
from qudi.interface.spectrometer_interface import SpectrometerInterface

# .NET / pythonnet imports. These are only available on a machine with LightField
# installed and the PrincetonInstruments assemblies on the path.
import clr
import System
from System import EventHandler
from System.Collections.Generic import List as NetList


class Lightfield(SpectrometerInterface):
    """ Control a Princeton Instruments LightField spectrometer from qudi.

    This module drives LightField through its .NET AutomationV4 API. An
    experiment must already be configured (and selected) in LightField; this
    module reuses the currently loaded experiment, sets its exposure time and
    triggers acquisitions.

    Example config for copy-paste:

    lightfield_spectrometer:
        module.Class: 'spectrometer.lightfield_spectrometer.Lightfield'
        options:
            # maximum time in seconds to wait for an acquisition to finish,
            # on top of the exposure time. Optional.
            acquisition_timeout_margin: 30
    """

    _timeout_margin = ConfigOption(name='acquisition_timeout_margin', default=30)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.au = None
        self.app = None
        self.exp = None
        self._ai = None
        # synchronisation between the LightField callbacks (which run in a
        # .NET thread) and record_spectrum()
        self._acquisition_done = threading.Event()
        self._last_frame = None
        self._frame_lock = threading.Lock()

    def on_activate(self):
        """ Activate module: set up the CLR-to-Python bindings and start LightField. """
        lfpath = os.environ['LIGHTFIELD_ROOT']
        lfaddinpath = os.path.join(lfpath, 'AddInViews')

        if lfpath not in sys.path:
            sys.path.append(lfpath)
        if lfaddinpath not in sys.path:
            sys.path.append(lfaddinpath)

        clr.AddReference('PrincetonInstruments.LightFieldViewV4')
        clr.AddReference('PrincetonInstruments.LightField.AutomationV4')
        clr.AddReference('PrincetonInstruments.LightField.AddInViews')

        from PrincetonInstruments.LightField.Automation import Automation
        import PrincetonInstruments.LightField.AddIns as ai
        self._ai = ai

        # Start a LightField instance. The second argument is the (empty) list
        # of command line options to pass to LightField.
        self.au = Automation(True, NetList[System.String]())
        self.app = self.au.LightFieldApplication
        self.exp = self.app.Experiment

        # Register callbacks. ImageDataSetReceived delivers the acquired frame,
        # ExperimentCompleted signals that the acquisition has finished.
        self.exp.ImageDataSetReceived += EventHandler(self._frame_callback)
        self.exp.ExperimentCompleted += EventHandler(self._acquisition_complete_callback)

        # Avoid blocking dialogs popping up during automated acquisitions.
        self.app.UserInteractionManager.SuppressUserInteraction = True

        self.log.info(f'LightField started, using experiment "{self.exp.Name}".')

    def on_deactivate(self):
        """ Deactivate module and shut down the LightField instance. """
        if self.exp is not None:
            try:
                self.exp.ImageDataSetReceived -= EventHandler(self._frame_callback)
                self.exp.ExperimentCompleted -= EventHandler(self._acquisition_complete_callback)
            except Exception:
                pass
        if self.au is not None:
            try:
                self.au.Dispose()
            except Exception:
                pass
        self.au = None
        self.app = None
        self.exp = None

    # ---------------------------------------------------------------------
    # LightField callbacks (executed in a .NET thread)
    # ---------------------------------------------------------------------
    def _frame_callback(self, sender, args):
        """ Called when an image/spectrum data set has been received. """
        try:
            data_set = args.ImageDataSet
            frame = data_set.GetFrame(0, 0)
            intensities = np.fromiter(frame.GetData(), dtype=np.double)
            with self._frame_lock:
                self._last_frame = intensities
        except Exception as exc:
            self.log.exception(f'Error while reading LightField frame: {exc}')

    def _acquisition_complete_callback(self, sender, args):
        """ Called when an acquisition has finished. Unblocks record_spectrum(). """
        self._acquisition_done.set()

    # ---------------------------------------------------------------------
    # SpectrometerInterface
    # ---------------------------------------------------------------------
    def record_spectrum(self):
        """ Trigger an acquisition and wait for the resulting spectrum.

        @return (2, N) float numpy array: wavelength in meter in the first row,
                                          measured intensity in the second row.
        """
        if self.exp is None:
            raise RuntimeError('LightField is not active.')
        if not self.exp.IsReadyToRun:
            raise RuntimeError('LightField experiment is not ready to run.')

        with self._frame_lock:
            self._last_frame = None
        self._acquisition_done.clear()

        self.exp.Acquire()

        # Wait until the ExperimentCompleted callback fires. The timeout
        # generously covers the configured exposure time plus a margin.
        timeout = self.exposure_time + float(self._timeout_margin)
        if not self._acquisition_done.wait(timeout=timeout):
            raise TimeoutError(
                f'LightField acquisition did not complete within {timeout} seconds.')

        with self._frame_lock:
            intensities = self._last_frame
        if intensities is None:
            raise RuntimeError('Acquisition completed but no frame was received.')

        wavelengths = np.fromiter(self.exp.SystemColumnCalibration, dtype=np.double)

        length = min(len(wavelengths), len(intensities))
        spectrum = np.empty((2, length), dtype=np.double)
        # SystemColumnCalibration is given in nanometer, convert to meter.
        spectrum[0] = wavelengths[:length] * 1e-9
        spectrum[1] = intensities[:length]
        return spectrum

    @property
    def exposure_time(self):
        """ Get the acquisition exposure time.

        @return float: exposure time in seconds.
        """
        # ShutterTimingExposureTime is expressed in milliseconds.
        exposure_ms = self.exp.GetValue(self._ai.CameraSettings.ShutterTimingExposureTime)
        return float(exposure_ms) / 1e3

    @exposure_time.setter
    def exposure_time(self, value):
        """ Set the acquisition exposure time.

        @param float value: exposure time to set in seconds.
        """
        assert isinstance(value, (float, int)), \
            f'exposure_time needs to be a float in seconds, but was {value}'
        # ShutterTimingExposureTime is expressed in milliseconds.
        exposure_ms = float(value) * 1e3
        self.exp.SetValue(self._ai.CameraSettings.ShutterTimingExposureTime, exposure_ms)
