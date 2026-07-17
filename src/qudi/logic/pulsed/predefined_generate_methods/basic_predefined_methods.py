# -*- coding: utf-8 -*-

"""
This file contains the Qudi Predefined Methods for sequence generator

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
from qudi.logic.pulsed.pulse_objects import PulseBlock, PulseBlockEnsemble, PulseSequence
from qudi.logic.pulsed.pulse_objects import PredefinedGeneratorBase
from qudi.logic.pulsed.sampling_functions import SamplingFunctions
from qudi.util.helpers import csv_2_list

"""
General Pulse Creation Procedure:
=================================
- Create at first each PulseBlockElement object
- add all PulseBlockElement object to a list and combine them to a
  PulseBlock object.
- Create all needed PulseBlock object with that idea, that means
  PulseBlockElement objects which are grouped to PulseBlock objects.
- Create from the PulseBlock objects a PulseBlockEnsemble object.
- If needed and if possible, combine the created PulseBlockEnsemble objects
  to the highest instance together in a PulseSequence object.
"""


class BasicPredefinedGenerator(PredefinedGeneratorBase):
    """
    A collection of basic pulse sequences.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    ################################################################################################
    #                             Generation methods for waveforms                                 #
    ################################################################################################
    def generate_laser_on(self, name='laser_on', length=3.0e-6):
        """Generates a laser pulse block ensemble.

        Parameters
        ----------
        name : str
            Name of the PulseBlockEnsemble to be generated.
        length : float
            Laser pulse duration in seconds.

        Returns
        -------
        created_blocks : list
            List of PulseBlock objects created.
        created_ensembles : list
            List of PulseBlockEnsemble objects created.
        created_sequences : list
            List of PulseSequence objects created.
        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # create the laser element
        laser_element = self._get_laser_element(length=length, increment=0)
        # Create block and append to created_blocks list
        laser_block = PulseBlock(name=name)
        laser_block.append(laser_element)
        created_blocks.append(laser_block)
        # Create block ensemble and append to created_ensembles list
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
        block_ensemble.append((laser_block.name, 0))
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_laser_mw_on(self, name='laser_mw_on', length=3.0e-6):
        """Generates a laser and microwave pulse block ensemble.

        Parameters
        ----------
        name : str
            Name of the PulseBlockEnsemble to be generated.
        length : float
            Laser and microwave pulse duration in seconds.

        Returns
        -------
        created_blocks : list
            List of PulseBlock objects created.
        created_ensembles : list
            List of PulseBlockEnsemble objects created.
        created_sequences : list
            List of PulseSequence objects created.
        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # create the laser_mw element
        laser_mw_element = self._get_mw_laser_element(length=length,
                                                      increment=0,
                                                      amp=self.microwave_amplitude,
                                                      freq=self.microwave_frequency,
                                                      phase=0)
        # Create block and append to created_blocks list
        laser_mw_block = PulseBlock(name=name)
        laser_mw_block.append(laser_mw_element)
        created_blocks.append(laser_mw_block)
        # Create block ensemble and append to created_ensembles list
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
        block_ensemble.append((laser_mw_block.name, 0))
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_two_digital_high(self, name='digital_high', length=3.0e-6, digital_channel1='d_ch1',
                                  digital_channel2='d_ch1'):
        """Generates a digital high pulse block ensemble on two digital channels.

        Parameters
        ----------
        name : str
            Name of the PulseBlockEnsemble to be generated.
        length : float
            Length of the digital high pulse in seconds.
        digital_channel1 : str
            Name of the first digital channel.
        digital_channel2 : str
            Name of the second digital channel.

        Returns
        -------
        created_blocks : list
            List of PulseBlock objects created.
        created_ensembles : list
            List of PulseBlockEnsemble objects created.
        created_sequences : list
            List of PulseSequence objects created.
        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        digital_channels = list([digital_channel1, digital_channel2])
        # create the laser_mw element
        trigger_element = self._get_trigger_element(length=length,
                                                    increment=0,
                                                    channels=list(digital_channels))

        # Create block and append to created_blocks list
        laser_mw_block = PulseBlock(name=name)
        laser_mw_block.append(trigger_element)
        created_blocks.append(laser_mw_block)
        # Create block ensemble and append to created_ensembles list
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
        block_ensemble.append((laser_mw_block.name, 0))
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_n_digital_high(self, name='digital_high', length=3.0e-6, digital_channels="1,2,3,4"):
        """Generates a digital high pulse block ensemble on n digital channels.

        Parameters
        ----------
        name : str
            Name of the PulseBlockEnsemble to be generated.
        length : float
            Length of the digital high pulse in seconds.
        digital_channels : str
            Comma-separated channel numbers.

        Returns
        -------
        created_blocks : list
            List of PulseBlock objects created.
        created_ensembles : list
            List of PulseBlockEnsemble objects created.
        created_sequences : list
            List of PulseSequence objects created.
        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        d_ch_nums = csv_2_list(digital_channels)
        digital_channels = ["d_ch{}".format(int(i)) for i in d_ch_nums]
        # create the laser_mw element
        trigger_element = self._get_trigger_element(length=length,
                                                    increment=0,
                                                    channels=list(digital_channels))

        # Create block and append to created_blocks list
        laser_mw_block = PulseBlock(name=name)
        laser_mw_block.append(trigger_element)
        created_blocks.append(laser_mw_block)
        # Create block ensemble and append to created_ensembles list
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
        block_ensemble.append((laser_mw_block.name, 0))
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences


    def generate_idle(self, name='idle', length=3.0e-6):
        """Generates an idle pulse block ensemble.

        Parameters
        ----------
        name : str
            Name of the PulseBlockEnsemble to be generated.
        length : float
            Length of the idle pulse in seconds.

        Returns
        -------
        created_blocks : list
            List of PulseBlock objects created.
        created_ensembles : list
            List of PulseBlockEnsemble objects created.
        created_sequences : list
            List of PulseSequence objects created.
        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # create the laser_mw element
        idle_element = self._get_idle_element(length=length, increment=0)
        # Create block and append to created_blocks list
        idle_block = PulseBlock(name=name)
        idle_block.append(idle_element)
        created_blocks.append(idle_block)
        # Create block ensemble and append to created_ensembles list
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
        block_ensemble.append((idle_block.name, 0))
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_rabi(self, name='rabi', tau_start=10.0e-9, tau_step=10.0e-9, num_of_points=50):
        """Generates a Rabi pulse block ensemble where the pulse length is varied linearly.

        Parameters
        ----------
        name : str
            Name of the PulseBlockEnsemble to be generated.
        tau_start : float
            Length of the first pulse in seconds.
        tau_step : float
            Increment of the pulse length in seconds.
        num_of_points : int
            Number of tau steps to be generated.

        Returns
        -------
        created_blocks : list
            List of PulseBlock objects created.
        created_ensembles : list
            List of PulseBlockEnsemble objects created.
        created_sequences : list
            List of PulseSequence objects created.
        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # get tau array for measurement ticks
        tau_array = tau_start + np.arange(num_of_points) * tau_step

        # create the laser_mw element
        mw_element = self._get_mw_element(length=tau_start,
                                          increment=tau_step,
                                          amp=self.microwave_amplitude,
                                          freq=self.microwave_frequency,
                                          phase=0)
        waiting_element = self._get_idle_element(length=self.wait_time,
                                                 increment=0)
        laser_element = self._get_laser_gate_element(length=self.laser_length,
                                                     increment=0)
        delay_element = self._get_delay_gate_element()

        # Create block and append to created_blocks list
        rabi_block = PulseBlock(name=name)
        rabi_block.append(mw_element)
        rabi_block.append(laser_element)
        rabi_block.append(delay_element)
        rabi_block.append(waiting_element)
        created_blocks.append(rabi_block)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
        block_ensemble.append((rabi_block.name, num_of_points - 1))

        # Create and append sync trigger block if needed
        self._add_trigger(created_blocks=created_blocks, block_ensemble=block_ensemble)

        # add metadata to invoke settings later on
        block_ensemble.measurement_information['alternating'] = False
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = tau_array
        block_ensemble.measurement_information['units'] = ('s', '')
        block_ensemble.measurement_information['labels'] = ('Tau<sub>pulse spacing</sub>', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = num_of_points
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks)

        # Append ensemble to created_ensembles list
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_pulsedodmr(self, name='pulsedODMR', freq_start=2870.0e6, freq_step=0.2e6, num_of_points=50):
        """Generates a pulsed ODMR pulse block ensemble where the microwave frequency is varied linearly.

        Parameters
        ----------
        name : str
            Name of the PulseBlockEnsemble to be generated.
        freq_start : float
            Start frequency in Hz.
        freq_step : float
            Frequency step in Hz.
        num_of_points : int
            Number of frequency steps to be generated.

        Returns
        -------
        created_blocks : list
            List of PulseBlock objects created.
        created_ensembles : list
            List of PulseBlockEnsemble objects created.
        created_sequences : list
            List of PulseSequence objects created.
        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # Create frequency array
        freq_array = freq_start + np.arange(num_of_points) * freq_step

        # create the elements
        waiting_element = self._get_idle_element(length=self.wait_time,
                                                 increment=0)
        laser_element = self._get_laser_gate_element(length=self.laser_length,
                                                     increment=0)
        delay_element = self._get_delay_gate_element()

        # Create block and append to created_blocks list
        pulsedodmr_block = PulseBlock(name=name)
        for mw_freq in freq_array:
            mw_element = self._get_mw_element(length=self.rabi_period / 2,
                                              increment=0,
                                              amp=self.microwave_amplitude,
                                              freq=mw_freq,
                                              phase=0)
            pulsedodmr_block.append(mw_element)
            pulsedodmr_block.append(laser_element)
            pulsedodmr_block.append(delay_element)
            pulsedodmr_block.append(waiting_element)
        created_blocks.append(pulsedodmr_block)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
        block_ensemble.append((pulsedodmr_block.name, 0))

        # Create and append sync trigger block if needed
        self._add_trigger(created_blocks=created_blocks, block_ensemble=block_ensemble)

        # add metadata to invoke settings later on
        block_ensemble.measurement_information['alternating'] = False
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = freq_array
        block_ensemble.measurement_information['units'] = ('Hz', '')
        block_ensemble.measurement_information['labels'] = ('Frequency', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = num_of_points
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks)

        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_ramsey(self, name='ramsey', tau_start=1.0e-6, tau_step=1.0e-6, num_of_points=50, alternating=True):
        """Generates a Ramsey pulse block ensemble where the free evolution time tau is varied linearly.

        Parameters
        ----------
        name : str
            Name of the PulseBlockEnsemble to be generated.
        tau_start : float
            Start tau in seconds.
        tau_step : float
            Tau step in seconds.
        num_of_points : int
            Number of tau points to be generated.
        alternating : bool
            If True, the final pi/2 pulse is alternated with either a -pi/2 pulse or 3pi/2 pulse depending on whether an
            analog or digital channel is used for microwave generation respectively. Default is True.

        Returns
        -------
        created_blocks : list
            List of PulseBlock objects created.
        created_ensembles : list
            List of PulseBlockEnsemble objects created.
        created_sequences : list
            List of PulseSequence objects created.
        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # get tau array for measurement ticks
        tau_array = tau_start + np.arange(num_of_points) * tau_step
        tau_pspacing_start = self.tau_2_pulse_spacing(tau_start)

        # create the elements
        waiting_element = self._get_idle_element(length=self.wait_time,
                                                 increment=0)
        laser_element = self._get_laser_gate_element(length=self.laser_length,
                                                     increment=0)
        delay_element = self._get_delay_gate_element()
        pihalf_element = self._get_mw_element(length=self.rabi_period / 4,
                                              increment=0,
                                              amp=self.microwave_amplitude,
                                              freq=self.microwave_frequency,
                                              phase=0)
        # Use a 180 deg phase shiftet pulse as 3pihalf pulse if microwave channel is analog
        if self.microwave_channel.startswith('a'):
            pi3half_element = self._get_mw_element(length=self.rabi_period / 4,
                                                   increment=0,
                                                   amp=self.microwave_amplitude,
                                                   freq=self.microwave_frequency,
                                                   phase=180)
        else:
            pi3half_element = self._get_mw_element(length=3 * self.rabi_period / 4,
                                                   increment=0,
                                                   amp=self.microwave_amplitude,
                                                   freq=self.microwave_frequency,
                                                   phase=0)
        tau_element = self._get_idle_element(length=tau_pspacing_start, increment=tau_step)

        # Create block and append to created_blocks list
        ramsey_block = PulseBlock(name=name)
        ramsey_block.append(pihalf_element)
        ramsey_block.append(tau_element)
        ramsey_block.append(pihalf_element)
        ramsey_block.append(laser_element)
        ramsey_block.append(delay_element)
        ramsey_block.append(waiting_element)
        if alternating:
            ramsey_block.append(pihalf_element)
            ramsey_block.append(tau_element)
            ramsey_block.append(pi3half_element)
            ramsey_block.append(laser_element)
            ramsey_block.append(delay_element)
            ramsey_block.append(waiting_element)
        created_blocks.append(ramsey_block)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=True)
        block_ensemble.append((ramsey_block.name, num_of_points - 1))

        # Create and append sync trigger block if needed
        self._add_trigger(created_blocks=created_blocks, block_ensemble=block_ensemble)

        # add metadata to invoke settings later on
        number_of_lasers = 2 * num_of_points if alternating else num_of_points
        block_ensemble.measurement_information['alternating'] = alternating
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = tau_array
        block_ensemble.measurement_information['units'] = ('s', '')
        block_ensemble.measurement_information['labels'] = ('Tau', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = number_of_lasers
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks)

        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_ramsey_from_list(self, name='ramsey', tau_list='[1e-6, 2e-6]', alternating=True):
        """Generates a Ramsey pulse block ensemble where the free evolution time tau is passed as a list.

        Parameters
        ----------
        name : str
            Name of the PulseBlockEnsemble to be generated.
        tau_list : str
            List of tau values in seconds as a string e.g. '[1e-6, 2e-6]'.
        alternating : bool
            If True, the final pi/2 pulse is alternated with either a -pi/2 pulse or 3pi/2 pulse depending on whether an
            analog or digital channel is used for microwave generation respectively. Default is True.

        Returns
        -------
        created_blocks : list
            List of PulseBlock objects created.
        created_ensembles : list
            List of PulseBlockEnsemble objects created.
        created_sequences : list
            List of PulseSequence objects created.
        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # get tau array for measurement ticks
        try:
            tau_array = csv_2_list(tau_list)
        except TypeError:
            tau_array = tau_list
        tau_pspacing_array = self.tau_2_pulse_spacing(tau_array)

        waiting_element = self._get_idle_element(length=self.wait_time,
                                                 increment=0)
        laser_element = self._get_laser_gate_element(length=self.laser_length,
                                                     increment=0)
        delay_element = self._get_delay_gate_element()
        # get pihalf element
        pihalf_element = self._get_mw_element(length=self.rabi_period / 4,
                                              increment=0,
                                              amp=self.microwave_amplitude,
                                              freq=self.microwave_frequency,
                                              phase=0)

        if alternating:
            if self.microwave_channel.startswith('a'):
                pi3half_element = self._get_mw_element(length=self.rabi_period / 4,
                                                       increment=0,
                                                       amp=self.microwave_amplitude,
                                                       freq=self.microwave_frequency,
                                                       phase=180)
            else:
                pi3half_element = self._get_mw_element(length=3 * self.rabi_period / 4,
                                                       increment=0,
                                                       amp=self.microwave_amplitude,
                                                       freq=self.microwave_frequency,
                                                       phase=0)

        # Create block and append to created_blocks list
        ramsey_block = PulseBlock(name=name)
        for tau_pspacing in tau_pspacing_array:
            tau_element = self._get_idle_element(length=tau_pspacing, increment=0)
            ramsey_block.append(pihalf_element)
            ramsey_block.append(tau_element)
            ramsey_block.append(tau_element)
            ramsey_block.append(pihalf_element)
            ramsey_block.append(laser_element)
            ramsey_block.append(delay_element)
            ramsey_block.append(waiting_element)

            if alternating:
                ramsey_block.append(pihalf_element)
                ramsey_block.append(tau_element)
                ramsey_block.append(pi3half_element)
                ramsey_block.append(laser_element)
                ramsey_block.append(delay_element)
                ramsey_block.append(waiting_element)

        created_blocks.append(ramsey_block)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=True)
        block_ensemble.append((ramsey_block.name, 0))

        # Create and append sync trigger block if needed
        self._add_trigger(created_blocks=created_blocks, block_ensemble=block_ensemble)

        # add metadata to invoke settings later on
        number_of_lasers = 2 * len(tau_array) if alternating else len(tau_array)
        block_ensemble.measurement_information['alternating'] = alternating
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = tau_array
        block_ensemble.measurement_information['units'] = ('s', '')
        block_ensemble.measurement_information['labels'] = ('Tau', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = number_of_lasers
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks)
        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_hahnecho(self, name='hahn_echo', tau_start=0.0e-6, tau_step=1.0e-6, num_of_points=50,
                          alternating=True):
        """Generates a Hahn echo pulse block ensemble where the free evolution time tau is varied linearly.

        Parameters
        ----------
        name : str
            Name of the PulseBlockEnsemble to be generated.
        tau_start : float
            Start tau in seconds.
        tau_step : float
            Tau step in seconds.
        num_of_points : int
            Number of tau points to be generated.
        alternating : bool
            If True, the final pi/2 pulse is alternated with either a -pi/2 pulse or 3pi/2 pulse depending on whether an
            analog or digital channel is used for microwave generation respectively. Default is True.

        Returns
        -------
        created_blocks : list
            List of PulseBlock objects created.
        created_ensembles : list
            List of PulseBlockEnsemble objects created.
        created_sequences : list
            List of PulseSequence objects created.
        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # get tau array for measurement ticks
        tau_array = tau_start + np.arange(num_of_points) * tau_step
        tau_pspacing_start = self.tau_2_pulse_spacing(tau_start)

        # create the elements
        waiting_element = self._get_idle_element(length=self.wait_time,
                                                 increment=0)
        laser_element = self._get_laser_gate_element(length=self.laser_length,
                                                     increment=0)
        delay_element = self._get_delay_gate_element()
        pihalf_element = self._get_mw_element(length=self.rabi_period / 4,
                                              increment=0,
                                              amp=self.microwave_amplitude,
                                              freq=self.microwave_frequency,
                                              phase=0)
        pi_element = self._get_mw_element(length=self.rabi_period / 2,
                                          increment=0,
                                          amp=self.microwave_amplitude,
                                          freq=self.microwave_frequency,
                                          phase=0)
        # Use a 180 deg phase shiftet pulse as 3pihalf pulse if microwave channel is analog
        if self.microwave_channel.startswith('a'):
            pi3half_element = self._get_mw_element(length=self.rabi_period / 4,
                                                   increment=0,
                                                   amp=self.microwave_amplitude,
                                                   freq=self.microwave_frequency,
                                                   phase=180)
        else:
            pi3half_element = self._get_mw_element(length=3 * self.rabi_period / 4,
                                                   increment=0,
                                                   amp=self.microwave_amplitude,
                                                   freq=self.microwave_frequency,
                                                   phase=0)
        tau_element = self._get_idle_element(length=tau_pspacing_start, increment=tau_step)

        # Create block and append to created_blocks list
        hahn_block = PulseBlock(name=name)
        hahn_block.append(pihalf_element)
        hahn_block.append(tau_element)
        hahn_block.append(pi_element)
        hahn_block.append(tau_element)
        hahn_block.append(pihalf_element)
        hahn_block.append(laser_element)
        hahn_block.append(delay_element)
        hahn_block.append(waiting_element)
        if alternating:
            hahn_block.append(pihalf_element)
            hahn_block.append(tau_element)
            hahn_block.append(pi_element)
            hahn_block.append(tau_element)
            hahn_block.append(pi3half_element)
            hahn_block.append(laser_element)
            hahn_block.append(delay_element)
            hahn_block.append(waiting_element)
        created_blocks.append(hahn_block)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=True)
        block_ensemble.append((hahn_block.name, num_of_points - 1))

        # Create and append sync trigger block if needed
        self._add_trigger(created_blocks=created_blocks, block_ensemble=block_ensemble)

        # add metadata to invoke settings later on
        number_of_lasers = 2 * num_of_points if alternating else num_of_points
        block_ensemble.measurement_information['alternating'] = alternating
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = tau_array
        block_ensemble.measurement_information['units'] = ('s', '')
        block_ensemble.measurement_information['labels'] = ('Tau', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = number_of_lasers
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks)

        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_hahnecho_exp(self, name='hahn_echo', tau_start=1.0e-6, tau_end=1.0e-6, num_of_points=50,
                              alternating=True):
        """Generates a Hahn echo pulse block ensemble where the free evolution time tau is varied exponentially.

        Parameters
        ----------
        name : str
            Name of the PulseBlockEnsemble to be generated.
        tau_start : float
            Start tau in seconds.
        tau_end : float
            End tau in seconds.
        num_of_points : int
            Number of tau points to be generated.
        alternating : bool
            If True, the final pi/2 pulse is alternated with either a -pi/2 pulse or 3pi/2 pulse depending on whether an
            analog or digital channel is used for microwave generation respectively. Default is True.

        Returns
        -------
        created_blocks : list
            List of PulseBlock objects created.
        created_ensembles : list
            List of PulseBlockEnsemble objects created.
        created_sequences : list
            List of PulseSequence objects created.
        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # get tau array for measurement ticks
        if tau_start == 0.0:
            tau_array = np.geomspace(1e-9, tau_end, num_of_points - 1)
            tau_array = np.insert(tau_array, 0, 0.0)
        else:
            tau_array = np.geomspace(tau_start, tau_end, num_of_points)

        tau_pspacing_array = self.tau_2_pulse_spacing(tau_array)

        # create the elements
        waiting_element = self._get_idle_element(length=self.wait_time,
                                                 increment=0)
        laser_element = self._get_laser_gate_element(length=self.laser_length,
                                                     increment=0)
        delay_element = self._get_delay_gate_element()
        pihalf_element = self._get_mw_element(length=self.rabi_period / 4,
                                              increment=0,
                                              amp=self.microwave_amplitude,
                                              freq=self.microwave_frequency,
                                              phase=0)
        pi_element = self._get_mw_element(length=self.rabi_period / 2,
                                          increment=0,
                                          amp=self.microwave_amplitude,
                                          freq=self.microwave_frequency,
                                          phase=0)
        # Use a 180 deg phase shiftet pulse as 3pihalf pulse if microwave channel is analog
        if self.microwave_channel.startswith('a'):
            pi3half_element = self._get_mw_element(length=self.rabi_period / 4,
                                                   increment=0,
                                                   amp=self.microwave_amplitude,
                                                   freq=self.microwave_frequency,
                                                   phase=180)
        else:
            pi3half_element = self._get_mw_element(length=3 * self.rabi_period / 4,
                                                   increment=0,
                                                   amp=self.microwave_amplitude,
                                                   freq=self.microwave_frequency,
                                                   phase=0)

        # Create block and append to created_blocks list
        hahn_block = PulseBlock(name=name)
        for tau_pspacing in tau_pspacing_array:
            tau_element = self._get_idle_element(length=tau_pspacing, increment=0.0)
            hahn_block.append(pihalf_element)
            hahn_block.append(tau_element)
            hahn_block.append(pi_element)
            hahn_block.append(tau_element)
            hahn_block.append(pihalf_element)
            hahn_block.append(laser_element)
            hahn_block.append(delay_element)
            hahn_block.append(waiting_element)
            if alternating:
                hahn_block.append(pihalf_element)
                hahn_block.append(tau_element)
                hahn_block.append(pi_element)
                hahn_block.append(tau_element)
                hahn_block.append(pi3half_element)
                hahn_block.append(laser_element)
                hahn_block.append(delay_element)
                hahn_block.append(waiting_element)
        created_blocks.append(hahn_block)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=True)
        block_ensemble.append((hahn_block.name, 0))

        # Create and append sync trigger block if needed
        self._add_trigger(created_blocks=created_blocks, block_ensemble=block_ensemble)

        # add metadata to invoke settings later on
        number_of_lasers = 2 * num_of_points if alternating else num_of_points
        block_ensemble.measurement_information['alternating'] = alternating
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = tau_array
        block_ensemble.measurement_information['units'] = ('s', '')
        block_ensemble.measurement_information['labels'] = ('Tau', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = number_of_lasers
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks)
        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_t1(self, name='T1', tau_start=1.0e-6, tau_step=1.0e-6, num_of_points=50, alternating=False):
        """Generates a T1 pulse block ensemble where the free evolution time tau is varied linearly.

        Parameters
        ----------
        name : str
            Name of the PulseBlockEnsemble to be generated.
        tau_start: float
            Start tau in seconds.
        tau_step: float
            Tau step in seconds.
        num_of_points: int
            Number of tau points.
        alternating: bool
            If True, the final pi/2 pulse is alternated with either a -pi/2 pulse or 3pi/2 pulse depending on whether an
            analog or digital channel is used for microwave generation respectively. Default is False.

        Returns
        -------
        created_blocks : list
            List of PulseBlock objects created.
        created_ensembles : list
            List of PulseBlockEnsemble objects created.
        created_sequences : list
            List of PulseSequence objects created.
        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # get tau array for measurement ticks
        tau_array = tau_start + np.arange(num_of_points) * tau_step

        # create the elements
        waiting_element = self._get_idle_element(length=self.wait_time,
                                                 increment=0)
        laser_element = self._get_laser_gate_element(length=self.laser_length,
                                                     increment=0)
        delay_element = self._get_delay_gate_element()
        if alternating:  # get pi element
            pi_element = self._get_mw_element(length=self.rabi_period / 2,
                                              increment=0,
                                              amp=self.microwave_amplitude,
                                              freq=self.microwave_frequency,
                                              phase=0)

        tau_element = self._get_idle_element(length=tau_start, increment=tau_step)
        t1_block = PulseBlock(name=name)
        t1_block.append(tau_element)
        t1_block.append(laser_element)
        t1_block.append(delay_element)
        t1_block.append(waiting_element)
        if alternating:
            t1_block.append(pi_element)
            t1_block.append(tau_element)
            t1_block.append(laser_element)
            t1_block.append(delay_element)
            t1_block.append(waiting_element)
        created_blocks.append(t1_block)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
        block_ensemble.append((t1_block.name, num_of_points - 1))

        # Create and append sync trigger block if needed
        self._add_trigger(created_blocks=created_blocks, block_ensemble=block_ensemble)

        # add metadata to invoke settings later on
        number_of_lasers = 2 * num_of_points if alternating else num_of_points
        block_ensemble.measurement_information['alternating'] = alternating
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = tau_array
        block_ensemble.measurement_information['units'] = ('s', '')
        block_ensemble.measurement_information['labels'] = ('Tau<sub>pulse spacing</sub>', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = number_of_lasers
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks)
        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_t1_exponential(self, name='T1_exp', tau_start=1.0e-6, tau_end=1.0e-6, num_of_points=50,
                                alternating=False):
        """Generates a T1 pulse block ensemble where the free evolution time tau is varied exponentially.

        Parameters
        ----------
        name : str
            Name of the PulseBlockEnsemble to be generated.
        tau_start : float
            Start tau in seconds.
        tau_end : float
            End tau in seconds.
        num_of_points : int
            Number of tau points.
        alternating : bool
            If True, the final pi/2 pulse is alternated with either a -pi/2 pulse or 3pi/2 pulse depending on whether an
            analog or digital channel is used for microwave generation respectively. Default is False.

        Returns
        -------
        created_blocks : list
            List of PulseBlock objects created.
        created_ensembles : list
            List of PulseBlockEnsemble objects created.
        created_sequences : list
            List of PulseSequence objects created.
        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # get tau array for measurement ticks
        if tau_start == 0.0:
            tau_array = np.geomspace(1e-9, tau_end, num_of_points - 1)
            tau_array = np.insert(tau_array, 0, 0.0)
        else:
            tau_array = np.geomspace(tau_start, tau_end, num_of_points)

        # create the elements
        waiting_element = self._get_idle_element(length=self.wait_time,
                                                 increment=0)
        laser_element = self._get_laser_gate_element(length=self.laser_length,
                                                     increment=0)
        delay_element = self._get_delay_gate_element()
        if alternating:  # get pi element
            pi_element = self._get_mw_element(length=self.rabi_period / 2,
                                              increment=0,
                                              amp=self.microwave_amplitude,
                                              freq=self.microwave_frequency,
                                              phase=0)
        t1_block = PulseBlock(name=name)
        for tau in tau_array:
            tau_element = self._get_idle_element(length=tau, increment=0.0)
            t1_block.append(tau_element)
            t1_block.append(laser_element)
            t1_block.append(delay_element)
            t1_block.append(waiting_element)
            if alternating:
                t1_block.append(pi_element)
                t1_block.append(tau_element)
                t1_block.append(laser_element)
                t1_block.append(delay_element)
                t1_block.append(waiting_element)
        created_blocks.append(t1_block)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
        block_ensemble.append((t1_block.name, 0))

        # Create and append sync trigger block if needed
        self._add_trigger(created_blocks=created_blocks, block_ensemble=block_ensemble)

        # add metadata to invoke settings later on
        number_of_lasers = 2 * num_of_points if alternating else num_of_points
        block_ensemble.measurement_information['alternating'] = alternating
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = tau_array
        block_ensemble.measurement_information['units'] = ('s', '')
        block_ensemble.measurement_information['labels'] = ('Tau<sub>pulse spacing</sub>', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = number_of_lasers
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks)
        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_HHamp(self, name='hh_amp', spinlock_length=20e-6, amp_start=0.05, amp_step=0.01,
                       num_of_points=50):
        """

        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # get amplitude array for measurement ticks
        amp_array = amp_start + np.arange(num_of_points) * amp_step

        # create the elements
        waiting_element = self._get_idle_element(length=self.wait_time, increment=0)
        laser_element = self._get_laser_gate_element(length=self.laser_length, increment=0)
        delay_element = self._get_delay_gate_element()
        pihalf_element = self._get_mw_element(length=self.rabi_period / 4,
                                              increment=0,
                                              amp=self.microwave_amplitude,
                                              freq=self.microwave_frequency,
                                              phase=0)
        # Use a 180 deg phase shiftet pulse as 3pihalf pulse if microwave channel is analog
        if self.microwave_channel.startswith('a'):
            pi3half_element = self._get_mw_element(length=self.rabi_period / 4,
                                                   increment=0,
                                                   amp=self.microwave_amplitude,
                                                   freq=self.microwave_frequency,
                                                   phase=180)
        else:
            pi3half_element = self._get_mw_element(length=3 * self.rabi_period / 4,
                                                   increment=0,
                                                   amp=self.microwave_amplitude,
                                                   freq=self.microwave_frequency,
                                                   phase=0)

        # Create block and append to created_blocks list
        hhamp_block = PulseBlock(name=name)
        for sl_amp in amp_array:
            sl_element = self._get_mw_element(length=spinlock_length,
                                              increment=0,
                                              amp=sl_amp,
                                              freq=self.microwave_frequency,
                                              phase=90)
            hhamp_block.append(pihalf_element)
            hhamp_block.append(sl_element)
            hhamp_block.append(pihalf_element)
            hhamp_block.append(laser_element)
            hhamp_block.append(delay_element)
            hhamp_block.append(waiting_element)

            hhamp_block.append(pi3half_element)
            hhamp_block.append(sl_element)
            hhamp_block.append(pihalf_element)
            hhamp_block.append(laser_element)
            hhamp_block.append(delay_element)
            hhamp_block.append(waiting_element)
        created_blocks.append(hhamp_block)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=True)
        block_ensemble.append((hhamp_block.name, 0))

        # Create and append sync trigger block if needed
        self._add_trigger(created_blocks=created_blocks, block_ensemble=block_ensemble)

        # add metadata to invoke settings later on
        block_ensemble.measurement_information['alternating'] = True
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = amp_array
        block_ensemble.measurement_information['units'] = ('V', '')
        block_ensemble.measurement_information['labels'] = ('MW amplitude', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = 2 * num_of_points
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks)

        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_HHtau(self, name='hh_tau', spinlock_amp=0.1, tau_start=1e-6, tau_step=1e-6,
                       num_of_points=50):
        """

        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # get tau array for measurement ticks
        tau_array = tau_start + np.arange(num_of_points) * tau_step

        # create the elements
        waiting_element = self._get_idle_element(length=self.wait_time, increment=0)
        laser_element = self._get_laser_gate_element(length=self.laser_length, increment=0)
        delay_element = self._get_delay_gate_element()
        pihalf_element = self._get_mw_element(length=self.rabi_period / 4,
                                              increment=0,
                                              amp=self.microwave_amplitude,
                                              freq=self.microwave_frequency,
                                              phase=0)
        # Use a 180 deg phase shiftet pulse as 3pihalf pulse if microwave channel is analog
        if self.microwave_channel.startswith('a'):
            pi3half_element = self._get_mw_element(length=self.rabi_period / 4,
                                                   increment=0,
                                                   amp=self.microwave_amplitude,
                                                   freq=self.microwave_frequency,
                                                   phase=180)
        else:
            pi3half_element = self._get_mw_element(length=3 * self.rabi_period / 4,
                                                   increment=0,
                                                   amp=self.microwave_amplitude,
                                                   freq=self.microwave_frequency,
                                                   phase=0)
        sl_element = self._get_mw_element(length=tau_start,
                                          increment=tau_step,
                                          amp=spinlock_amp,
                                          freq=self.microwave_frequency,
                                          phase=90)

        # Create block and append to created_blocks list
        hhtau_block = PulseBlock(name=name)
        hhtau_block.append(pihalf_element)
        hhtau_block.append(sl_element)
        hhtau_block.append(pihalf_element)
        hhtau_block.append(laser_element)
        hhtau_block.append(delay_element)
        hhtau_block.append(waiting_element)

        hhtau_block.append(pi3half_element)
        hhtau_block.append(sl_element)
        hhtau_block.append(pihalf_element)
        hhtau_block.append(laser_element)
        hhtau_block.append(delay_element)
        hhtau_block.append(waiting_element)
        created_blocks.append(hhtau_block)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=True)
        block_ensemble.append((hhtau_block.name, num_of_points - 1))

        # Create and append sync trigger block if needed
        self._add_trigger(created_blocks=created_blocks, block_ensemble=block_ensemble)

        # add metadata to invoke settings later on
        block_ensemble.measurement_information['alternating'] = True
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = tau_array
        block_ensemble.measurement_information['units'] = ('s', '')
        block_ensemble.measurement_information['labels'] = ('Spinlock time', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = 2 * num_of_points
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks)

        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_HHpol(self, name='hh_pol', spinlock_length=20.0e-6, spinlock_amp=0.1,
                       polarization_steps=50):
        """

        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # get steps array for measurement ticks
        steps_array = np.arange(2 * polarization_steps)

        # create the elements
        waiting_element = self._get_idle_element(length=self.wait_time, increment=0)
        laser_element = self._get_laser_gate_element(length=self.laser_length, increment=0)
        delay_element = self._get_delay_gate_element()
        pihalf_element = self._get_mw_element(length=self.rabi_period / 4,
                                              increment=0,
                                              amp=self.microwave_amplitude,
                                              freq=self.microwave_frequency,
                                              phase=0)
        # Use a 180 deg phase shiftet pulse as 3pihalf pulse if microwave channel is analog
        if self.microwave_channel.startswith('a'):
            pi3half_element = self._get_mw_element(length=self.rabi_period / 4,
                                                   increment=0,
                                                   amp=self.microwave_amplitude,
                                                   freq=self.microwave_frequency,
                                                   phase=180)
        else:
            pi3half_element = self._get_mw_element(length=3 * self.rabi_period / 4,
                                                   increment=0,
                                                   amp=self.microwave_amplitude,
                                                   freq=self.microwave_frequency,
                                                   phase=0)
        sl_element = self._get_mw_element(length=spinlock_length,
                                          increment=0,
                                          amp=spinlock_amp,
                                          freq=self.microwave_frequency,
                                          phase=90)

        # Create block for "up"-polarization and append to created_blocks list
        up_block = PulseBlock(name=name + '_up')
        up_block.append(pihalf_element)
        up_block.append(sl_element)
        up_block.append(pihalf_element)
        up_block.append(laser_element)
        up_block.append(delay_element)
        up_block.append(waiting_element)
        created_blocks.append(up_block)

        # Create block for "down"-polarization and append to created_blocks list
        down_block = PulseBlock(name=name + '_down')
        down_block.append(pi3half_element)
        down_block.append(sl_element)
        down_block.append(pi3half_element)
        down_block.append(laser_element)
        down_block.append(delay_element)
        down_block.append(waiting_element)
        created_blocks.append(down_block)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=True)
        block_ensemble.append((up_block.name, polarization_steps - 1))
        block_ensemble.append((down_block.name, polarization_steps - 1))

        # Create and append sync trigger block if needed
        self._add_trigger(created_blocks=created_blocks, block_ensemble=block_ensemble)

        # add metadata to invoke settings later on
        block_ensemble.measurement_information['alternating'] = False
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = steps_array
        block_ensemble.measurement_information['units'] = ('#', '')
        block_ensemble.measurement_information['labels'] = ('Polarization Steps', 'Signal')
        block_ensemble.measurement_information['number_of_lasers'] = 2 * polarization_steps
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks)

        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_chirpedodmr(self, name='LinearChirpedODMR', mw_freq_center=2870.0e6, freq_range=500.0e6,
                             freq_overlap=20.0e6, num_of_points=50, pulse_length=500e-9, expected_rabi_frequency=30e6,
                             expected_t2=5e-6):
        """Generates a chirped ODMR pulse block ensemble where the microwave frequency is chirped linearly.

        Parameters
        ----------
        name : str
            Name of the PulseBlockEnsemble to be generated.
        mw_freq_center : float
            Central frequency of the chirped ODMR in Hz.
        freq_range : float
            Target frequency range of the whole ODMR scan in Hz.
        freq_overlap : float
            Additional 'overlap' frequency range for each chirped pulse, i.e. the frequency range of each single chirped
            pulse is (freq_range / num_points) + freq_overlap.
        num_of_points : float
            Number of chirped pulses used in the scan.
        pulse_length : float
            Length of the mw pulse.
        expected_rabi_frequency : float
            Expected value of the Rabi frequency - used to calculate adiabaticity.
        expected_t2 : float
            Expected T2 time - used to check if the chirped pulse is shorter than T2.

        Returns
        -------
        created_blocks : list
            List of PulseBlock objects created.
        created_ensembles : list
            List of PulseBlockEnsemble objects created.
        created_sequences : list
            List of PulseSequence objects created.
        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # create the elements
        waiting_element = self._get_idle_element(length=self.wait_time, increment=0)
        laser_element = self._get_laser_gate_element(length=self.laser_length, increment=0)
        delay_element = self._get_delay_gate_element()

        # Create block and append to created_blocks list
        chirpedodmr_block = PulseBlock(name=name)

        # Create frequency array
        mw_freq_start = mw_freq_center - freq_range / 2.
        mw_freq_incr = freq_range / num_of_points
        freq_array = mw_freq_start + np.arange(num_of_points) * mw_freq_incr + mw_freq_incr / 2.

        if pulse_length > expected_t2:
            self.log.error('The duration of the chirped pulse exceeds expected the T2 time')

        for mw_freq in freq_array:
            mw_element = self._get_mw_element_linearchirp(length=pulse_length,
                                                          increment=0,
                                                          amplitude=self.microwave_amplitude,
                                                          start_freq=(mw_freq - mw_freq_incr / 2.
                                                                      - freq_overlap),
                                                          stop_freq=(mw_freq + mw_freq_incr / 2.
                                                                     + freq_overlap),
                                                          phase=0)
            chirpedodmr_block.append(mw_element)
            chirpedodmr_block.append(laser_element)
            chirpedodmr_block.append(delay_element)
            chirpedodmr_block.append(waiting_element)
        created_blocks.append(chirpedodmr_block)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
        block_ensemble.append((chirpedodmr_block.name, 0))

        # Create and append sync trigger block if needed
        self._add_trigger(created_blocks=created_blocks, block_ensemble=block_ensemble)

        # chirp range
        pulse_freq_range = mw_freq + mw_freq_incr / 2. + freq_overlap - (
                mw_freq - mw_freq_incr / 2. - freq_overlap)

        # chirp rate
        chirp_rate = pulse_freq_range / pulse_length

        # adiabaticity condition
        adiab = 2 * np.pi * expected_rabi_frequency ** 2 / chirp_rate
        # adiab >> 1 is needed for adiabatic evolution. Simulations show that adiab > 5 works very
        # well,
        # adiab > 2 will work but is on the edge, so we impose a check if adiab < 2.5 to give a
        # warning.

        if adiab < 2.5:
            self.log.error(
                'Adiabadicity conditions not matched. Rabi**2/(pulse_freq_range/pulse_length)>>1 is'
                ' not fulfilled,  Rabi**2/(pulse_freq_range/pulse_length) = {}'.format(adiab))
        else:
            self.log.info(
                'Adiabadicity conditions is Rabi**2/(pulse_freq_range/pulse_length) = '
                '{} >> 1'.format(adiab))

        # Approximate expected transfer efficiency in case of perfect adiabaticity for a linear
        # chirp this formula works very well for adiab = 5 and overestimates the efficiency by
        # 5-10% for adiab = 2.5
        approx_transfer_eff_perfect_adiab = 1 - 2 / (
                4 + (pulse_freq_range / expected_rabi_frequency) ** 2)

        self.log.info(
            'Expected transfer efficiency in case of perfect adiabaticity = ' + str(
                approx_transfer_eff_perfect_adiab))

        # add metadata to invoke settings later on
        block_ensemble.measurement_information['alternating'] = False
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = freq_array
        block_ensemble.measurement_information['labels'] = ('Frequency', '')
        block_ensemble.measurement_information['units'] = ('Hz', '')
        block_ensemble.measurement_information['number_of_lasers'] = num_of_points
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks)

        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    def generate_AEchirpedodmr(self, name='AllenEberlyChirpODMR', mw_freq_center=2870.0e6, freq_range=500.0e6,
                               freq_overlap=20.0e6, num_of_points=50, pulse_length=500e-9, truncation_ratio=0.1,
                               expected_rabi_frequency=30e6, expected_t2=5e-6, peak_mw_amplitude=0.25):
        """Generates a chirped ODMR pulse block ensemble where the microwave frequency is chirped using the Allen-Eberly
        model.

        Additional information about the Allen-Eberly chirped ODMR
        Chirped ODMR with a pulse, following the Allen-Eberly model: a sech amplitude shape and a
        tanh shaped detuning. The AE pulse has very good properties in terms of adiabaticity and is
        often preferable to the standard Landau-Zener-Stueckelberg-Majorana model with a constant
        amplitude and a linear chirp (see class Chirp). More information about the Allen-Eberly
        model can be found in:
        L. Allen and J. H. Eberly, Optical Resonance and Two-Level Atoms Dover, New York, 1987,
        Analytical solution is given in: F. T. Hioe, Phys. Rev. A 30, 2100 (1984).

        Parameters
        ----------
        name : str
            Name of the PulseBlockEnsemble to be generated.
        mw_freq_center : float
            Central frequency of the chirped ODMR in Hz.
        freq_range : float
            Target frequency range of the whole ODMR scan in Hz.
        freq_overlap : float
            Additional 'overlap' frequency range for each chirped pulse, i.e. the frequency range of each single chirped
            pulse is (freq_range / num_points) + freq_overlap. Truncation is usually negligible for values <0.2.
        num_of_points : float
            Number of chirped pulses used in the scan.
        pulse_length : float
            Length of the mw pulse.
        truncation_ratio : float
            Ratio that characterizes the truncation of the chirped pulse. Specifically, the pulse shape is given by
            sech(t/ truncation ratio /pulse length). truncation_ratio = 0.1 is excellent; the scheme will work for 0.2.
            Higher values truncate the sech pulse and reduce the frequency range of ODMR as the transfer efficiency in
            the wings of the pulse range drops.
        expected_rabi_frequency : float
            Expected value of the Rabi frequency - used to calculate adiabaticity.
        expected_t2 : float
            Expected T2 time - used to check if the chirped pulse is shorter than T2.
        peak_mw_amplitude : float
            Peak amplitude of the Allen-Eberly Chirp pulse.

        Returns
        -------
        created_blocks : list
            List of PulseBlock objects created.
        created_ensembles : list
            List of PulseBlockEnsemble objects created.
        created_sequences : list
            List of PulseSequence objects created.
        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # create the elements
        waiting_element = self._get_idle_element(length=self.wait_time, increment=0)
        laser_element = self._get_laser_gate_element(length=self.laser_length, increment=0)
        delay_element = self._get_delay_gate_element()

        # Create block and append to created_blocks list
        chirpedodmr_block = PulseBlock(name=name)

        # Create frequency array
        mw_freq_start = mw_freq_center - freq_range / 2.
        mw_freq_incr = freq_range / num_of_points
        freq_array = mw_freq_start + np.arange(num_of_points) * mw_freq_incr + mw_freq_incr / 2.

        if pulse_length > expected_t2:
            self.log.error('The duration of the chirped pulse exceeds the expected T2 time')

        for mw_freq in freq_array:
            mw_element = self._get_mw_element_AEchirp(length=pulse_length,
                                                      increment=0,
                                                      amp=peak_mw_amplitude,
                                                      start_freq=(mw_freq - mw_freq_incr / 2.
                                                                  - freq_overlap),
                                                      stop_freq=(mw_freq + mw_freq_incr / 2.
                                                                 + freq_overlap),
                                                      phase=0,
                                                      truncation_ratio=truncation_ratio)
            chirpedodmr_block.append(mw_element)
            chirpedodmr_block.append(laser_element)
            chirpedodmr_block.append(delay_element)
            chirpedodmr_block.append(waiting_element)
        created_blocks.append(chirpedodmr_block)

        # Create block ensemble
        block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
        block_ensemble.append((chirpedodmr_block.name, 0))

        # Create and append sync trigger block if needed
        self._add_trigger(created_blocks=created_blocks, block_ensemble=block_ensemble)

        # chirp range
        pulse_freq_range = mw_freq + mw_freq_incr / 2. + freq_overlap - (
                mw_freq - mw_freq_incr / 2. - freq_overlap)

        # chirp rate for the AE model at the moment of level crossing
        chirp_rate_ae = pulse_freq_range / pulse_length / truncation_ratio
        # In comparison to linear chirp, the chirp rate is divided by the truncation_ratio

        # adiabaticity condition for the AE model
        adiab_ae = 2 * np.pi * expected_rabi_frequency ** 2 / chirp_rate_ae
        # adiab_ae >> 1 is needed for adiabatic evolution. Simulations show adiab_ae > 2 will work
        # but is on the edge, so we impose a check if adiab_ae < 2.5 to give a warning.

        if adiab_ae < 2.5:
            self.log.error(
                'Adiabadicity conditions not matched. Rabi**2/(pulse_freq_range/'
                'pulse_length/truncation_ratio)>>1 is not fulfilled,  Rabi**2/(pulse_freq_range / '
                'pulse_length / truncation_ratio) = {}'.format(adiab_ae))
        else:
            self.log.info(
                'Adiabadicity conditions is Rabi**2/'
                '(pulse_freq_range / pulse_length / truncation_ratio) = {} >> 1'.format(adiab_ae))

        # Approximate expected transfer efficiency in case of perfect adiabaticity for a AE pulse
        # this formula works very well for adiab > 2.5
        approx_transfer_eff_perfect_adiab_ae = 1 - 2 / (
                4 + (pulse_freq_range * np.sinh(1 / 2 / truncation_ratio)
                     / expected_rabi_frequency) ** 2)

        self.log.info(
            'Expected transfer efficiency in case of perfect adiabaticity = ' + str(
                approx_transfer_eff_perfect_adiab_ae))

        # add metadata to invoke settings later on
        block_ensemble.measurement_information['alternating'] = False
        block_ensemble.measurement_information['laser_ignore_list'] = list()
        block_ensemble.measurement_information['controlled_variable'] = freq_array
        block_ensemble.measurement_information['labels'] = ('Frequency', '')
        block_ensemble.measurement_information['units'] = ('Hz', '')
        block_ensemble.measurement_information['number_of_lasers'] = num_of_points
        block_ensemble.measurement_information['counting_length'] = self._get_ensemble_count_length(
            ensemble=block_ensemble, created_blocks=created_blocks)

        # append ensemble to created ensembles
        created_ensembles.append(block_ensemble)
        return created_blocks, created_ensembles, created_sequences

    ################################################################################################
    #                             Generation methods for sequences                                 #
    ################################################################################################
    def generate_t1_sequencing(self, name='t1_seq', tau_start=1.0e-6, tau_max=1.0e-3, num_of_points=10):
        """Generates a T1 pulse sequence where the free evolution time tau is varied exponentially.

        Parameters
        ----------
        name : str
            Name of the PulseSequence to be generated.
        tau_start : float
            Start tau in seconds.
        tau_max : float
            Maximum tau in seconds.
        num_of_points : int
            Number of tau points.

        Returns
        -------
        created_blocks : list
            List of PulseBlock objects created.
        created_ensembles : list
            List of PulseBlockEnsemble objects created.
        created_sequences : list
            List of PulseSequence objects created.
        """
        created_blocks = list()
        created_ensembles = list()
        created_sequences = list()

        # Get logarithmically spaced steps in multiples of tau_start.
        # Note that the number of points and the position of the last point can change here.
        k_array = np.unique(
            np.rint(np.logspace(0., np.log10(tau_max / tau_start), num_of_points)).astype(int))
        # get tau array for measurement ticks
        tau_array = k_array * tau_start

        # Create the readout PulseBlockEnsemble
        # Get necessary PulseBlockElements
        laser_element = self._get_laser_gate_element(length=self.laser_length, increment=0)
        delay_element = self._get_delay_gate_element()
        waiting_element = self._get_idle_element(length=self.wait_time, increment=0)
        # Create PulseBlock and append PulseBlockElements
        readout_block = PulseBlock(name='{0}_readout'.format(name))
        readout_block.append(laser_element)
        readout_block.append(delay_element)
        readout_block.append(waiting_element)
        created_blocks.append(readout_block)
        # Create PulseBlockEnsemble and append block to it
        readout_ensemble = PulseBlockEnsemble(name='{0}_readout'.format(name), rotating_frame=False)
        readout_ensemble.append((readout_block.name, 0))
        created_ensembles.append(readout_ensemble)

        if self.sync_channel:
            # Create the last readout PulseBlockEnsemble including a sync trigger
            # Get necessary PulseBlockElements
            sync_element = self._get_sync_element()
            # Create PulseBlock and append PulseBlockElements
            sync_readout_block = PulseBlock(name='{0}_readout_sync'.format(name))
            sync_readout_block.append(laser_element)
            sync_readout_block.append(delay_element)
            sync_readout_block.append(waiting_element)
            sync_readout_block.append(sync_element)
            created_blocks.append(sync_readout_block)
            # Create PulseBlockEnsemble and append block to it
            sync_readout_ensemble = PulseBlockEnsemble(name='{0}_readout_sync'.format(name),
                                                       rotating_frame=False)
            sync_readout_ensemble.append((sync_readout_block.name, 0))
            created_ensembles.append(sync_readout_ensemble)

        # Create the tau/waiting PulseBlockEnsemble
        # Get tau PulseBlockElement
        tau_element = self._get_idle_element(length=tau_start, increment=0)
        # Create PulseBlock and append PulseBlockElements
        tau_block = PulseBlock(name='{0}_tau'.format(name))
        tau_block.append(tau_element)
        created_blocks.append(tau_block)
        # Create PulseBlockEnsemble and append block to it
        tau_ensemble = PulseBlockEnsemble(name='{0}_tau'.format(name), rotating_frame=False)
        tau_ensemble.append((tau_block.name, 0))
        created_ensembles.append(tau_ensemble)

        # Create the PulseSequence and append the PulseBlockEnsemble names as sequence steps
        # together with the necessary parameters.
        t1_sequence = PulseSequence(name=name, rotating_frame=False)
        for k in k_array:
            t1_sequence.append(tau_ensemble.name)
            t1_sequence[-1].repetitions = int(k) - 1

            if self.sync_channel and k == k_array[-1]:
                t1_sequence.append(sync_readout_ensemble.name)
            else:
                t1_sequence.append(readout_ensemble.name)

        # Make the sequence loop infinitely by setting the go_to parameter of the last sequence
        # step to the first step.
        t1_sequence[-1].go_to = 1

        # Trigger the calculation of parameters in the PulseSequence instance
        t1_sequence.refresh_parameters()

        # add metadata to invoke settings later on
        t1_sequence.measurement_information['alternating'] = False
        t1_sequence.measurement_information['laser_ignore_list'] = list()
        t1_sequence.measurement_information['controlled_variable'] = tau_array
        t1_sequence.measurement_information['units'] = ('s', '')
        t1_sequence.measurement_information['labels'] = ('Tau<sub>pulse spacing</sub>', 'Signal')
        t1_sequence.measurement_information['number_of_lasers'] = len(tau_array)
        t1_sequence.measurement_information['counting_length'] = self._get_sequence_count_length(t1_sequence, created_ensembles, created_blocks)

        # Append PulseSequence to created_sequences list
        created_sequences.append(t1_sequence)
        return created_blocks, created_ensembles, created_sequences

    # def generate_resonant_decay_sequence(self, name='resonant_decay', repump_total=1.0e-3,
    #                                     repump_length=1.0e-6, waiting_length=1.0e-7,
    #                                     decay_length=1.0e-6, record_length=1.0e-1):
    #     """ Charge initialization and resonant decay using a PulseSequence for AWG8195 compatibility.
    #     Operates in UNGATED mode: d_ch2 fires only during the repump block; its rising edge
    #     triggers the MCS8A to start a time trace. Waiting and decay blocks have no d_ch2.

    #     All AWG blocks are short (≤ repump_length, ≤ decay_length). Long durations are achieved
    #     by repeating blocks in the AWG sequence table — no large waveform is ever transferred.
    #     Block lengths are snapped to exact AWG granularity multiples to prevent idle_extension.

    #       Block 1 — green_repump   (a_ch2 DC + d_ch2 trigger rising edge → MCS8A start)
    #                 repeated repump_reps = round(repump_total / repump_length) times
    #       Block 2 — waiting        (all idle, d_ch2 LOW)         [once]
    #       Block 3 — resonant_decay (d_ch1 only, no d_ch2)
    #                 repeated decay_reps = round(record_length / decay_length) times
    #       Block 4 — end idle       (all low)                     [once, then loop to step 1]

    #     @param str   name:           Name of the PulseSequence
    #     @param float repump_total:   Total green repump duration per cycle [s]
    #     @param float repump_length:  Single repump AWG block duration [s]; snapped to AWG bins (≤1 µs)
    #     @param float waiting_length: Idle block duration [s]; snapped to AWG bins
    #     @param float decay_length:   Single decay AWG block duration [s]; snapped to AWG bins (≤1 µs)
    #     @param float record_length:  Total decay recording time [s]

    #     @return: created_blocks, created_ensembles, created_sequences
    #     """
    #     created_blocks = list()
    #     created_ensembles = list()
    #     created_sequences = list()

    #     gran_s = int(self.pulse_generator_constraints.waveform_length.step)
    #     min_s  = int(self.pulse_generator_constraints.waveform_length.min)
    #     sr     = self.sample_rate

    #     def _bins(length_s):
    #         return max(min_s, int(round(length_s * sr / gran_s)) * gran_s)

    #     repump_bins  = _bins(repump_length)
    #     waiting_bins = _bins(waiting_length)
    #     decay_bins   = _bins(decay_length)

    #     repump_s  = repump_bins  / sr
    #     waiting_s = waiting_bins / sr
    #     decay_s   = decay_bins   / sr

    #     # The M8195A sequence table supports 32-bit repetition counts (~4.3 billion).
    #     # Keep block lengths short (≤1 µs) so waveform data transferred is small;
    #     # large rep counts are handled in hardware at no extra cost.
    #     repump_reps = max(1, int(round(repump_total / repump_s)))
    #     decay_reps  = max(1, int(round(record_length / decay_s)))

    #     # --- Block 1: Green repump (a_ch2 DC + d_ch2 gate) ---
    #     repump_element = self._get_green_laser_element(length=repump_s, increment=0,
    #                                                    channels=['d_ch2'])
    #     repump_block = PulseBlock(name='{0}_repump'.format(name))
    #     repump_block.append(repump_element)
    #     created_blocks.append(repump_block)
    #     repump_ensemble = PulseBlockEnsemble(name='{0}_repump'.format(name), rotating_frame=False)
    #     repump_ensemble.append((repump_block.name, 0))
    #     created_ensembles.append(repump_ensemble)

    #     # --- Block 2: Waiting (all idle — d_ch2 goes LOW after repump, MCS8A keeps recording) ---
    #     waiting_element = self._get_idle_element(length=waiting_s, increment=0)
    #     waiting_block = PulseBlock(name='{0}_waiting'.format(name))
    #     waiting_block.append(waiting_element)
    #     created_blocks.append(waiting_block)
    #     waiting_ensemble = PulseBlockEnsemble(name='{0}_waiting'.format(name), rotating_frame=False)
    #     waiting_ensemble.append((waiting_block.name, 0))
    #     created_ensembles.append(waiting_ensemble)

    #     # --- Block 3: Resonant decay (d_ch1 only — ungated, no d_ch2) ---
    #     decay_element = self._get_trigger_element(length=decay_s, increment=0,
    #                                               channels=['d_ch1'])
    #     decay_block = PulseBlock(name='{0}_decay'.format(name))
    #     decay_block.append(decay_element)
    #     created_blocks.append(decay_block)
    #     decay_ensemble = PulseBlockEnsemble(name='{0}_decay'.format(name), rotating_frame=False)
    #     decay_ensemble.append((decay_block.name, 0))
    #     created_ensembles.append(decay_ensemble)

    #     # --- Block 4: End-of-cycle idle (all low — d_ch2 falling edge) ---
    #     end_element = self._get_idle_element(length=waiting_s, increment=0)
    #     end_block = PulseBlock(name='{0}_end'.format(name))
    #     end_block.append(end_element)
    #     created_blocks.append(end_block)
    #     end_ensemble = PulseBlockEnsemble(name='{0}_end'.format(name), rotating_frame=False)
    #     end_ensemble.append((end_block.name, 0))
    #     created_ensembles.append(end_ensemble)

    #     # --- Build PulseSequence ---
    #     decay_sequence = PulseSequence(name=name, rotating_frame=False)

    #     decay_sequence.append(repump_ensemble.name)
    #     decay_sequence[-1].repetitions = repump_reps - 1

    #     decay_sequence.append(waiting_ensemble.name)
    #     decay_sequence[-1].repetitions = 0

    #     decay_sequence.append(decay_ensemble.name)
    #     decay_sequence[-1].repetitions = decay_reps - 1

    #     decay_sequence.append(end_ensemble.name)
    #     decay_sequence[-1].repetitions = 0
    #     decay_sequence[-1].go_to = 1

    #     decay_sequence.refresh_parameters()

    #     total_counting_length = repump_reps * repump_s + waiting_s + decay_reps * decay_s
    #     decay_sequence.measurement_information['alternating'] = False
    #     decay_sequence.measurement_information['laser_ignore_list'] = list()
    #     decay_sequence.measurement_information['controlled_variable'] = [0]
    #     decay_sequence.measurement_information['units'] = ('', '')
    #     decay_sequence.measurement_information['labels'] = ('Repetition', 'Signal')
    #     decay_sequence.measurement_information['number_of_lasers'] = 1
    #     decay_sequence.measurement_information['counting_length'] = total_counting_length

    #     created_sequences.append(decay_sequence)
    #     return created_blocks, created_ensembles, created_sequences

    # def generate_resonant_decay_rest_sequence(self, name='resonant_decay_rest', repump_total=1.0e-3,
    #                                           repump_length=1.0e-6, waiting_length=1.0e-7,
    #                                           decay_length=1.0e-6, record_length_1=1.0e-3,
    #                                           rest_total=100.0e-3, rest_length=1.0e-3,
    #                                           record_length_2=1.0e-3):
    #     """ Resonant decay sequence with an idle rest inserted between two decay phases.

    #     Operates in UNGATED mode: d_ch2 fires only during the repump block; its rising edge
    #     triggers the MCS8A to start a time trace.

    #     Structure (loops continuously via go_to=1):
    #       Block 1 — repump:   (a_ch2 DC + d_ch2 trigger)  × repump_reps
    #       Block 2 — waiting:  (idle)                       × 1
    #       Block 3 — decay_1:  (d_ch1 only)                 × decay_reps_1
    #       Block 4 — rest:     (idle)                       × rest_reps
    #       Block 5 — decay_2:  (d_ch1 only)                 × decay_reps_2
    #       Block 6 — end:      (idle)                       × 1  → go_to=1

    #       repump_reps  = round(repump_total  / repump_s)
    #       decay_reps_1 = round(record_length_1 / decay_s)
    #       rest_reps    = round(rest_total    / rest_s)
    #       decay_reps_2 = round(record_length_2 / decay_s)

    #     MCS8A time trace (from d_ch2 trigger at t=0):
    #       [repump_total] [waiting] [record_length_1] [rest_total] [record_length_2]

    #     @param str   name:            Name of the PulseSequence
    #     @param float repump_total:    Total green repump duration per cycle [s]
    #     @param float repump_length:   Single repump AWG block duration [s]; snapped to AWG bins
    #     @param float waiting_length:  Idle waiting block duration [s]; snapped to AWG bins
    #     @param float decay_length:    Single decay AWG block duration [s]; snapped to AWG bins (shared by both phases)
    #     @param float record_length_1: Total resonant decay duration before rest [s]
    #     @param float rest_total:      Total idle rest duration [s]
    #     @param float rest_length:     Single rest AWG block duration [s]; snapped to AWG bins
    #     @param float record_length_2: Total resonant decay duration after rest [s]

    #     @return: created_blocks, created_ensembles, created_sequences
    #     """
    #     created_blocks = list()
    #     created_ensembles = list()
    #     created_sequences = list()

    #     gran_s = int(self.pulse_generator_constraints.waveform_length.step)
    #     min_s  = int(self.pulse_generator_constraints.waveform_length.min)
    #     sr     = self.sample_rate

    #     def _bins(length_s):
    #         return max(min_s, int(round(length_s * sr / gran_s)) * gran_s)

    #     repump_s  = _bins(repump_length)  / sr
    #     waiting_s = _bins(waiting_length) / sr
    #     decay_s   = _bins(decay_length)   / sr
    #     rest_s    = _bins(rest_length)    / sr

    #     repump_reps  = max(1, int(round(repump_total    / repump_s)))
    #     decay_reps_1 = max(1, int(round(record_length_1 / decay_s)))
    #     rest_reps    = max(1, int(round(rest_total      / rest_s)))
    #     decay_reps_2 = max(1, int(round(record_length_2 / decay_s)))

    #     # --- Block 1: Green repump (a_ch2 DC + d_ch2 trigger) ---
    #     repump_element = self._get_green_laser_element(length=repump_s, increment=0,
    #                                                    channels=['d_ch2'])
    #     repump_block = PulseBlock(name='{0}_repump'.format(name))
    #     repump_block.append(repump_element)
    #     created_blocks.append(repump_block)
    #     repump_ensemble = PulseBlockEnsemble(name='{0}_repump'.format(name), rotating_frame=False)
    #     repump_ensemble.append((repump_block.name, 0))
    #     created_ensembles.append(repump_ensemble)

    #     # --- Block 2: Waiting (idle) ---
    #     waiting_element = self._get_idle_element(length=waiting_s, increment=0)
    #     waiting_block = PulseBlock(name='{0}_waiting'.format(name))
    #     waiting_block.append(waiting_element)
    #     created_blocks.append(waiting_block)
    #     waiting_ensemble = PulseBlockEnsemble(name='{0}_waiting'.format(name), rotating_frame=False)
    #     waiting_ensemble.append((waiting_block.name, 0))
    #     created_ensembles.append(waiting_ensemble)

    #     # --- Block 3: Decay phase 1 (d_ch1 only) ---
    #     decay1_element = self._get_trigger_element(length=decay_s, increment=0,
    #                                                channels=['d_ch1'])
    #     decay1_block = PulseBlock(name='{0}_decay1'.format(name))
    #     decay1_block.append(decay1_element)
    #     created_blocks.append(decay1_block)
    #     decay1_ensemble = PulseBlockEnsemble(name='{0}_decay1'.format(name), rotating_frame=False)
    #     decay1_ensemble.append((decay1_block.name, 0))
    #     created_ensembles.append(decay1_ensemble)

    #     # --- Block 4: Idle rest (all low) ---
    #     rest_element = self._get_idle_element(length=rest_s, increment=0)
    #     rest_block = PulseBlock(name='{0}_rest'.format(name))
    #     rest_block.append(rest_element)
    #     created_blocks.append(rest_block)
    #     rest_ensemble = PulseBlockEnsemble(name='{0}_rest'.format(name), rotating_frame=False)
    #     rest_ensemble.append((rest_block.name, 0))
    #     created_ensembles.append(rest_ensemble)

    #     # --- Block 5: Decay phase 2 (d_ch1 only) ---
    #     decay2_element = self._get_trigger_element(length=decay_s, increment=0,
    #                                                channels=['d_ch1'])
    #     decay2_block = PulseBlock(name='{0}_decay2'.format(name))
    #     decay2_block.append(decay2_element)
    #     created_blocks.append(decay2_block)
    #     decay2_ensemble = PulseBlockEnsemble(name='{0}_decay2'.format(name), rotating_frame=False)
    #     decay2_ensemble.append((decay2_block.name, 0))
    #     created_ensembles.append(decay2_ensemble)

    #     # --- Block 6: End idle ---
    #     end_element = self._get_idle_element(length=waiting_s, increment=0)
    #     end_block = PulseBlock(name='{0}_end'.format(name))
    #     end_block.append(end_element)
    #     created_blocks.append(end_block)
    #     end_ensemble = PulseBlockEnsemble(name='{0}_end'.format(name), rotating_frame=False)
    #     end_ensemble.append((end_block.name, 0))
    #     created_ensembles.append(end_ensemble)

    #     # --- Build PulseSequence ---
    #     decay_sequence = PulseSequence(name=name, rotating_frame=False)

    #     decay_sequence.append(repump_ensemble.name)
    #     decay_sequence[-1].repetitions = repump_reps - 1

    #     decay_sequence.append(waiting_ensemble.name)
    #     decay_sequence[-1].repetitions = 0

    #     decay_sequence.append(decay1_ensemble.name)
    #     decay_sequence[-1].repetitions = decay_reps_1 - 1

    #     decay_sequence.append(rest_ensemble.name)
    #     decay_sequence[-1].repetitions = rest_reps - 1

    #     decay_sequence.append(decay2_ensemble.name)
    #     decay_sequence[-1].repetitions = decay_reps_2 - 1

    #     decay_sequence.append(end_ensemble.name)
    #     decay_sequence[-1].repetitions = 0
    #     decay_sequence[-1].go_to = 1

    #     decay_sequence.refresh_parameters()

    #     total_counting_length = (repump_reps * repump_s + waiting_s
    #                              + decay_reps_1 * decay_s
    #                              + rest_reps * rest_s
    #                              + decay_reps_2 * decay_s)
    #     decay_sequence.measurement_information['alternating'] = False
    #     decay_sequence.measurement_information['laser_ignore_list'] = list()
    #     decay_sequence.measurement_information['controlled_variable'] = [0]
    #     decay_sequence.measurement_information['units'] = ('', '')
    #     decay_sequence.measurement_information['labels'] = ('Repetition', 'Signal')
    #     decay_sequence.measurement_information['number_of_lasers'] = 1
    #     decay_sequence.measurement_information['counting_length'] = total_counting_length

    #     created_sequences.append(decay_sequence)
    #     return created_blocks, created_ensembles, created_sequences

    # def generate_dual_decay_sequence(self, name='dual_decay', repump_total=1.0e-3,
    #                                 repump_length=1.0e-6, waiting_length=1.0e-7,
    #                                 decay_length=1.0e-6, record_length=1.0e-1):
    #     """ Charge initialization and dual-laser decay using a PulseSequence for AWG8195 compatibility.
    #     Operates in UNGATED mode: d_ch2 fires only during the repump block; its rising edge
    #     triggers the MCS8A to start a time trace. Waiting and decay blocks have no d_ch2.

    #     Same structure as generate_resonant_decay_sequence but phase 3 uses both
    #     green (a_ch2 DC) and resonant (d_ch1) lasers simultaneously.

    #       Block 1 — green_repump (a_ch2 DC + d_ch2 trigger rising edge → MCS8A start)
    #                 repeated repump_reps = round(repump_total / repump_length) times
    #       Block 2 — waiting      (all idle, d_ch2 LOW)            [once]
    #       Block 3 — dual_decay   (a_ch2 DC + d_ch1 only, no d_ch2)
    #                 repeated decay_reps = round(record_length / decay_length) times
    #       Block 4 — end idle     (all low)                        [once, then loop to step 1]

    #     @param str   name:           Name of the PulseSequence
    #     @param float repump_total:   Total green repump duration per cycle [s]
    #     @param float repump_length:  Single repump AWG block duration [s]; snapped to AWG bins (≤1 µs)
    #     @param float waiting_length: Idle block duration [s]; snapped to AWG bins
    #     @param float decay_length:   Single dual-decay AWG block duration [s]; snapped to AWG bins (≤1 µs)
    #     @param float record_length:  Total decay recording time [s]

    #     @return: created_blocks, created_ensembles, created_sequences
    #     """
    #     created_blocks = list()
    #     created_ensembles = list()
    #     created_sequences = list()

    #     gran_s = int(self.pulse_generator_constraints.waveform_length.step)
    #     min_s  = int(self.pulse_generator_constraints.waveform_length.min)
    #     sr     = self.sample_rate

    #     def _bins(length_s):
    #         return max(min_s, int(round(length_s * sr / gran_s)) * gran_s)

    #     repump_bins  = _bins(repump_length)
    #     waiting_bins = _bins(waiting_length)
    #     decay_bins   = _bins(decay_length)

    #     repump_s  = repump_bins  / sr
    #     waiting_s = waiting_bins / sr
    #     decay_s   = decay_bins   / sr

    #     repump_reps = max(1, int(round(repump_total / repump_s)))
    #     decay_reps  = max(1, int(round(record_length / decay_s)))

    #     # --- Block 1: Green repump (a_ch2 DC + d_ch2 gate) ---
    #     repump_element = self._get_green_laser_element(length=repump_s, increment=0,
    #                                                    channels=['d_ch2'])
    #     repump_block = PulseBlock(name='{0}_repump'.format(name))
    #     repump_block.append(repump_element)
    #     created_blocks.append(repump_block)
    #     repump_ensemble = PulseBlockEnsemble(name='{0}_repump'.format(name), rotating_frame=False)
    #     repump_ensemble.append((repump_block.name, 0))
    #     created_ensembles.append(repump_ensemble)

    #     # --- Block 2: Waiting (all idle — d_ch2 goes LOW after repump, MCS8A keeps recording) ---
    #     waiting_element = self._get_idle_element(length=waiting_s, increment=0)
    #     waiting_block = PulseBlock(name='{0}_waiting'.format(name))
    #     waiting_block.append(waiting_element)
    #     created_blocks.append(waiting_block)
    #     waiting_ensemble = PulseBlockEnsemble(name='{0}_waiting'.format(name), rotating_frame=False)
    #     waiting_ensemble.append((waiting_block.name, 0))
    #     created_ensembles.append(waiting_ensemble)

    #     # --- Block 3: Dual decay (a_ch2 DC + d_ch1 only — ungated, no d_ch2) ---
    #     decay_element = self._get_green_laser_element(length=decay_s, increment=0,
    #                                                   channels=['d_ch1'])
    #     decay_block = PulseBlock(name='{0}_decay'.format(name))
    #     decay_block.append(decay_element)
    #     created_blocks.append(decay_block)
    #     decay_ensemble = PulseBlockEnsemble(name='{0}_decay'.format(name), rotating_frame=False)
    #     decay_ensemble.append((decay_block.name, 0))
    #     created_ensembles.append(decay_ensemble)

    #     # --- Block 4: End-of-cycle idle (all low — d_ch2 falling edge) ---
    #     end_element = self._get_idle_element(length=waiting_s, increment=0)
    #     end_block = PulseBlock(name='{0}_end'.format(name))
    #     end_block.append(end_element)
    #     created_blocks.append(end_block)
    #     end_ensemble = PulseBlockEnsemble(name='{0}_end'.format(name), rotating_frame=False)
    #     end_ensemble.append((end_block.name, 0))
    #     created_ensembles.append(end_ensemble)

    #     # --- Build PulseSequence ---
    #     decay_sequence = PulseSequence(name=name, rotating_frame=False)

    #     decay_sequence.append(repump_ensemble.name)
    #     decay_sequence[-1].repetitions = repump_reps - 1

    #     decay_sequence.append(waiting_ensemble.name)
    #     decay_sequence[-1].repetitions = 0

    #     decay_sequence.append(decay_ensemble.name)
    #     decay_sequence[-1].repetitions = decay_reps - 1

    #     decay_sequence.append(end_ensemble.name)
    #     decay_sequence[-1].repetitions = 0
    #     decay_sequence[-1].go_to = 1

    #     decay_sequence.refresh_parameters()

    #     total_counting_length = repump_reps * repump_s + waiting_s + decay_reps * decay_s
    #     decay_sequence.measurement_information['alternating'] = False
    #     decay_sequence.measurement_information['laser_ignore_list'] = list()
    #     decay_sequence.measurement_information['controlled_variable'] = [0]
    #     decay_sequence.measurement_information['units'] = ('', '')
    #     decay_sequence.measurement_information['labels'] = ('Repetition', 'Signal')
    #     decay_sequence.measurement_information['number_of_lasers'] = 1
    #     decay_sequence.measurement_information['counting_length'] = total_counting_length

    #     created_sequences.append(decay_sequence)
    #     return created_blocks, created_ensembles, created_sequences

    # def generate_charge_repump_sequence(self, name='charge_repump', killing_time=1.0e-2,
    #                                     killing_block=1.0e-6, tau=1.0e-3,
    #                                     tau_block=1.0e-6, readout_window=1.0e-6,
    #                                     wait_length=1.0e-6):
    #     """ Charge state killing + repeated (green repump + readout) units as a PulseSequence.

    #     Operates in UNGATED mode: d_ch2 fires only in Block 1 (kill); its rising edge
    #     triggers the MCS8A to start a time trace. Unit and end blocks have no d_ch2.

    #     Each unit block contains TWO sequential elements played back-to-back:
    #       [tau_block: a_ch2 green] + [readout_window: d_ch1 resonant]
    #     This unit is repeated repump_reps = round(tau / tau_block) times.
    #     The MCS8A time trace therefore contains repump_reps evenly spaced readout peaks.

    #     Structure (loops continuously via go_to=1):
    #       Block 1 — kill:  [d_ch1 + d_ch2 trigger] × killing_reps   (d_ch2 rising edge → MCS8A start)
    #       Block 2 — unit:  [green(tau_block) + readout(readout_window)] × repump_reps
    #       Block 3 — end:   [idle] × 1 → go_to=1

    #     killing_reps = round(killing_time / killing_block)
    #     repump_reps  = round(tau / tau_block)

    #     @param str   name:           Name of the PulseSequence
    #     @param float killing_time:   Total resonant kill duration [s]
    #     @param float killing_block:  Single kill AWG block duration [s]; snapped to AWG bins
    #     @param float tau:            Total green repump duration per cycle [s]
    #     @param float tau_block:      Single green repump element duration [s]; snapped to AWG bins
    #     @param float readout_window: Resonant readout element duration [s]; snapped to AWG bins
    #     @param float wait_length:    End idle block duration [s]; snapped to AWG bins

    #     @return: created_blocks, created_ensembles, created_sequences
    #     """
    #     created_blocks = list()
    #     created_ensembles = list()
    #     created_sequences = list()

    #     gran_s = int(self.pulse_generator_constraints.waveform_length.step)
    #     min_s  = int(self.pulse_generator_constraints.waveform_length.min)
    #     sr     = self.sample_rate

    #     def _bins(length_s):
    #         return max(min_s, int(round(length_s * sr / gran_s)) * gran_s)

    #     kill_s    = _bins(killing_block) / sr
    #     tau_s     = _bins(tau_block)     / sr
    #     readout_s = _bins(readout_window) / sr
    #     wait_s    = _bins(wait_length)   / sr

    #     kill_reps   = max(1, int(round(killing_time / kill_s)))
    #     repump_reps = max(1, int(round(tau / tau_s)))

    #     # --- Block 1: Kill (d_ch1 resonant + d_ch2 trigger → MCS8A start) ---
    #     kill_element = self._get_trigger_element(length=kill_s, increment=0,
    #                                              channels=['d_ch1', 'd_ch2'])
    #     kill_block = PulseBlock(name='{0}_kill'.format(name))
    #     kill_block.append(kill_element)
    #     created_blocks.append(kill_block)
    #     kill_ensemble = PulseBlockEnsemble(name='{0}_kill'.format(name), rotating_frame=False)
    #     kill_ensemble.append((kill_block.name, 0))
    #     created_ensembles.append(kill_ensemble)

    #     # --- Block 2: Unit = [green tau_block] + [resonant readout] played sequentially ---
    #     # Both elements are in a single PulseBlock so they play back-to-back on each repetition.
    #     green_element   = self._get_green_laser_element(length=tau_s, increment=0)
    #     readout_element = self._get_trigger_element(length=readout_s, increment=0,
    #                                                 channels=['d_ch1'])
    #     unit_block = PulseBlock(name='{0}_unit'.format(name))
    #     unit_block.append(green_element)
    #     unit_block.append(readout_element)
    #     created_blocks.append(unit_block)
    #     unit_ensemble = PulseBlockEnsemble(name='{0}_unit'.format(name), rotating_frame=False)
    #     unit_ensemble.append((unit_block.name, 0))
    #     created_ensembles.append(unit_ensemble)

    #     # --- Block 3: End idle ---
    #     end_element = self._get_idle_element(length=wait_s, increment=0)
    #     end_block = PulseBlock(name='{0}_end'.format(name))
    #     end_block.append(end_element)
    #     created_blocks.append(end_block)
    #     end_ensemble = PulseBlockEnsemble(name='{0}_end'.format(name), rotating_frame=False)
    #     end_ensemble.append((end_block.name, 0))
    #     created_ensembles.append(end_ensemble)

    #     # --- Build PulseSequence ---
    #     charge_sequence = PulseSequence(name=name, rotating_frame=False)

    #     charge_sequence.append(kill_ensemble.name)
    #     charge_sequence[-1].repetitions = kill_reps - 1

    #     charge_sequence.append(unit_ensemble.name)
    #     charge_sequence[-1].repetitions = repump_reps - 1

    #     charge_sequence.append(end_ensemble.name)
    #     charge_sequence[-1].repetitions = 0
    #     charge_sequence[-1].go_to = 1

    #     charge_sequence.refresh_parameters()

    #     total_counting_length = kill_reps * kill_s + repump_reps * (tau_s + readout_s) + wait_s
    #     charge_sequence.measurement_information['alternating'] = False
    #     charge_sequence.measurement_information['laser_ignore_list'] = list()
    #     charge_sequence.measurement_information['controlled_variable'] = [0]
    #     charge_sequence.measurement_information['units'] = ('', '')
    #     charge_sequence.measurement_information['labels'] = ('Repetition', 'Signal')
    #     charge_sequence.measurement_information['number_of_lasers'] = 1
    #     charge_sequence.measurement_information['counting_length'] = total_counting_length

    #     created_sequences.append(charge_sequence)
    #     return created_blocks, created_ensembles, created_sequences

    # def generate_extra_repump_sequence(self, name='extra_repump', repump_total=1.0e-3,
    #                                    repump_length=1.0e-6, killing_time=1.0e-2,
    #                                    killing_block=1.0e-6, tau=1.0e-3,
    #                                    tau_block=1.0e-6, readout_window=1.0e-6,
    #                                    wait_length=1.0e-6):
    #     """ Green repump → kill → repeated (extra-repump + readout) units.

    #     Operates in UNGATED mode: d_ch2 fires only during Block 1 (green repump); its rising
    #     edge triggers the MCS8A to start a time trace. Kill and unit blocks have no d_ch2.

    #     Block 1 — green repump:  a_ch2 DC + d_ch2 trigger,     × repump_reps
    #     Block 2 — kill:          d_ch1 only (resonant),         × kill_reps
    #     Block 3 — unit:          [a_ch1 DC (extra repump, tau_block) +
    #                               d_ch1 (readout, readout_window)] × unit_reps
    #     Block 4 — end:           idle × 1  → go_to=1

    #     The extra repump element drives a_ch1 as DC at green_laser_voltage.

    #     repump_reps = round(repump_total  / repump_s)
    #     kill_reps   = round(killing_time  / kill_s)
    #     unit_reps   = round(tau           / tau_s)

    #     @param str   name:           Name of the PulseSequence
    #     @param float repump_total:   Total green repump duration per cycle [s]
    #     @param float repump_length:  Single green repump AWG block duration [s]; snapped to AWG bins
    #     @param float killing_time:   Total resonant kill duration [s]
    #     @param float killing_block:  Single kill AWG block duration [s]; snapped to AWG bins
    #     @param float tau:            Total extra-repump duration per cycle [s]
    #     @param float tau_block:      Single extra-repump element duration [s]; snapped to AWG bins
    #     @param float readout_window: Readout element duration [s]; snapped to AWG bins
    #     @param float wait_length:    End idle block duration [s]; snapped to AWG bins

    #     @return: created_blocks, created_ensembles, created_sequences
    #     """
    #     created_blocks = list()
    #     created_ensembles = list()
    #     created_sequences = list()

    #     gran_s = int(self.pulse_generator_constraints.waveform_length.step)
    #     min_s  = int(self.pulse_generator_constraints.waveform_length.min)
    #     sr     = self.sample_rate

    #     def _bins(length_s):
    #         return max(min_s, int(round(length_s * sr / gran_s)) * gran_s)

    #     repump_s  = _bins(repump_length)  / sr
    #     kill_s    = _bins(killing_block)  / sr
    #     tau_s     = _bins(tau_block)      / sr
    #     readout_s = _bins(readout_window) / sr
    #     wait_s    = _bins(wait_length)    / sr

    #     repump_reps = max(1, int(round(repump_total   / repump_s)))
    #     kill_reps   = max(1, int(round(killing_time   / kill_s)))
    #     unit_reps   = max(1, int(round(tau            / tau_s)))

    #     # --- Block 1: Green repump (a_ch2 DC + d_ch2 trigger → MCS8A start) ---
    #     repump_element = self._get_green_laser_element(length=repump_s, increment=0,
    #                                                    channels=['d_ch2'])
    #     repump_block = PulseBlock(name='{0}_repump'.format(name))
    #     repump_block.append(repump_element)
    #     created_blocks.append(repump_block)
    #     repump_ensemble = PulseBlockEnsemble(name='{0}_repump'.format(name), rotating_frame=False)
    #     repump_ensemble.append((repump_block.name, 0))
    #     created_ensembles.append(repump_ensemble)

    #     # --- Block 2: Kill (d_ch1 resonant only, no d_ch2) ---
    #     kill_element = self._get_trigger_element(length=kill_s, increment=0,
    #                                              channels=['d_ch1'])
    #     kill_block = PulseBlock(name='{0}_kill'.format(name))
    #     kill_block.append(kill_element)
    #     created_blocks.append(kill_block)
    #     kill_ensemble = PulseBlockEnsemble(name='{0}_kill'.format(name), rotating_frame=False)
    #     kill_ensemble.append((kill_block.name, 0))
    #     created_ensembles.append(kill_ensemble)

    #     # --- Block 3: Unit = [a_ch1 extra repump (tau_block)] + [d_ch1 readout] ---
    #     extra_repump_element = self._get_extra_repump_element(length=tau_s, increment=0)
    #     readout_element      = self._get_trigger_element(length=readout_s, increment=0,
    #                                                      channels=['d_ch1'])
    #     unit_block = PulseBlock(name='{0}_unit'.format(name))
    #     unit_block.append(extra_repump_element)
    #     unit_block.append(readout_element)
    #     created_blocks.append(unit_block)
    #     unit_ensemble = PulseBlockEnsemble(name='{0}_unit'.format(name), rotating_frame=False)
    #     unit_ensemble.append((unit_block.name, 0))
    #     created_ensembles.append(unit_ensemble)

    #     # --- Block 4: End idle ---
    #     end_element = self._get_idle_element(length=wait_s, increment=0)
    #     end_block = PulseBlock(name='{0}_end'.format(name))
    #     end_block.append(end_element)
    #     created_blocks.append(end_block)
    #     end_ensemble = PulseBlockEnsemble(name='{0}_end'.format(name), rotating_frame=False)
    #     end_ensemble.append((end_block.name, 0))
    #     created_ensembles.append(end_ensemble)

    #     # --- Build PulseSequence ---
    #     extra_sequence = PulseSequence(name=name, rotating_frame=False)

    #     extra_sequence.append(repump_ensemble.name)
    #     extra_sequence[-1].repetitions = repump_reps - 1

    #     extra_sequence.append(kill_ensemble.name)
    #     extra_sequence[-1].repetitions = kill_reps - 1

    #     extra_sequence.append(unit_ensemble.name)
    #     extra_sequence[-1].repetitions = unit_reps - 1

    #     extra_sequence.append(end_ensemble.name)
    #     extra_sequence[-1].repetitions = 0
    #     extra_sequence[-1].go_to = 1

    #     extra_sequence.refresh_parameters()

    #     total_counting_length = (repump_reps * repump_s + kill_reps * kill_s
    #                              + unit_reps * (tau_s + readout_s) + wait_s)
    #     extra_sequence.measurement_information['alternating'] = False
    #     extra_sequence.measurement_information['laser_ignore_list'] = list()
    #     extra_sequence.measurement_information['controlled_variable'] = [0]
    #     extra_sequence.measurement_information['units'] = ('', '')
    #     extra_sequence.measurement_information['labels'] = ('Repetition', 'Signal')
    #     extra_sequence.measurement_information['number_of_lasers'] = 1
    #     extra_sequence.measurement_information['counting_length'] = total_counting_length

    #     created_sequences.append(extra_sequence)
    #     return created_blocks, created_ensembles, created_sequences

    # def generate_green_laser_on(self, name='green_on', length=3.0e-6):
    #     """ Generates green laser on by driving a_ch2 as DC high.

    #     @param str name: Name of the PulseBlockEnsemble
    #     @param float length: green laser duration in seconds

    #     @return object: the generated PulseBlockEnsemble object.
    #     """
    #     created_blocks = list()
    #     created_ensembles = list()
    #     created_sequences = list()

    #     # create the green laser element (a_ch2 driven as DC at green_laser_voltage, all others idle/low)
    #     green_laser_element = self._get_green_laser_element(length=length, increment=0)
    #     # Create block and append to created_blocks list
    #     green_laser_block = PulseBlock(name=name)
    #     green_laser_block.append(green_laser_element)
    #     created_blocks.append(green_laser_block)
    #     # Create block ensemble and append to created_ensembles list
    #     block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
    #     block_ensemble.append((green_laser_block.name, 0))
    #     created_ensembles.append(block_ensemble)
    #     return created_blocks, created_ensembles, created_sequences
    
    # def generate_resonant_laser_on(self, name='resonant_on', length=3.0e-6):
    #     """ Generates resonant laser on by driving d_ch1 digital high.

    #     @param str name: Name of the PulseBlockEnsemble
    #     @param float length: resonant laser duration in seconds

    #     @return object: the generated PulseBlockEnsemble object.
    #     """
    #     created_blocks = list()
    #     created_ensembles = list()
    #     created_sequences = list()

    #     # create the resonant laser element (d_ch1 digital high, all others idle/low)
    #     resonant_laser_element = self._get_trigger_element(length=length, increment=0, channels='d_ch1')
    #     # Create block and append to created_blocks list
    #     resonant_laser_block = PulseBlock(name=name)
    #     resonant_laser_block.append(resonant_laser_element)
    #     created_blocks.append(resonant_laser_block)
    #     # Create block ensemble and append to created_ensembles list
    #     block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
    #     block_ensemble.append((resonant_laser_block.name, 0))
    #     created_ensembles.append(block_ensemble)
    #     return created_blocks, created_ensembles, created_sequences    
    
    # def generate_all_laser_on(self, name='all_laser_on', length=3.0e-6):
    #     """ Generates both green (a_ch2 DC) and resonant (d_ch1 digital high) lasers on simultaneously.

    #     @param str name: Name of the PulseBlockEnsemble
    #     @param float length: duration in seconds

    #     @return object: the generated PulseBlockEnsemble object.
    #     """
    #     created_blocks = list()
    #     created_ensembles = list()
    #     created_sequences = list()

    #     # a_ch2 DC at green_laser_voltage + d_ch1 digital high simultaneously
    #     all_laser_element = self._get_green_laser_element(length=length, increment=0, channels='d_ch1')
    #     # Create block and append to created_blocks list
    #     all_laser_block = PulseBlock(name=name)
    #     all_laser_block.append(all_laser_element)
    #     created_blocks.append(all_laser_block)
    #     # Create block ensemble and append to created_ensembles list
    #     block_ensemble = PulseBlockEnsemble(name=name, rotating_frame=False)
    #     block_ensemble.append((all_laser_block.name, 0))
    #     created_ensembles.append(block_ensemble)
    #     return created_blocks, created_ensembles, created_sequences
