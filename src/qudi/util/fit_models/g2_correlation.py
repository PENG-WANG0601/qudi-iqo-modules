# -*- coding: utf-8 -*-

"""
Fit models for second-order photon correlation g(2)(tau) measurements.

Add further g(2) models to this file (or another module in this namespace package): every
FitModelBase subclass found here is offered automatically in every qudi fit configuration dialog,
including the correlation GUI's. Give a model a parameter named "t0" to have it follow the
correlation GUI's global detuning (t0) setting.

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

__all__ = ('G2Antibunching',)

import numpy as np
from scipy.ndimage import gaussian_filter1d

from qudi.util.fit_models.model import FitModelBase, estimator


class G2Antibunching(FitModelBase):
    """ Antibunching dip with optional bunching shoulders and background (SNR) reduction:

        g2(tau) = norm * (1 + snr_factor * (a * exp(-|tau - t0| / tau1)
                                            - (1 + a) * exp(-|tau - t0| / tau2)))

    norm:       normalization (baseline at large |tau|)
    t0:         detuning / delay offset of the dip centre
    snr_factor: rho^2 = (S / (S + B))^2, background reduction of the contrast (1 = no background)
    a, tau1:    bunching amplitude and time constant (a = 0 -> pure antibunching)
    tau2:       antibunching time constant
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_param_hint('norm', value=1., min=0., max=np.inf)
        self.set_param_hint('t0', value=0., min=-np.inf, max=np.inf)
        self.set_param_hint('snr_factor', value=1., min=0., max=1.)
        self.set_param_hint('a', value=0.1, min=0., max=np.inf)
        self.set_param_hint('tau1', value=1e-7, min=0., max=np.inf)
        self.set_param_hint('tau2', value=1e-8, min=0., max=np.inf)

    @staticmethod
    def _model_function(x, norm, t0, snr_factor, a, tau1, tau2):
        dt = np.abs(x - t0)
        return norm * (1 + snr_factor * (a * np.exp(-dt / tau1) - (1 + a) * np.exp(-dt / tau2)))

    @estimator('Full')
    def estimate_full(self, data, x):
        data = np.asarray(data, dtype=float)
        x = np.asarray(x, dtype=float)
        step = abs(x[1] - x[0]) if x.size > 1 else 1e-9

        edge = max(1, x.size // 10)
        norm = float(np.mean(np.concatenate((data[:edge], data[-edge:]))))
        if not norm > 0:
            norm = max(float(np.mean(data)), 1e-12)

        smooth = gaussian_filter1d(data, sigma=max(1, x.size // 200)) if x.size > 20 else data
        i_min = int(np.argmin(smooth))
        t0 = float(x[i_min])
        depth = float(np.clip(1 - smooth[i_min] / norm, 0.01, 1.))

        # time for the dip to recover half its depth ~ ln(2) * tau2
        half_level = norm * (1 - depth / 2)
        recovered = np.nonzero(smooth[i_min:] >= half_level)[0]
        tau2 = (x[i_min + recovered[0]] - t0) / np.log(2) if recovered.size and recovered[0] > 0 \
            else 5 * step
        tau2 = max(float(tau2), step)

        bunching = max(float(np.max(smooth)) / norm - 1, 0.)

        estimate = self.make_params()
        estimate['norm'].set(value=norm)
        estimate['t0'].set(value=t0)
        estimate['snr_factor'].set(value=depth, min=0., max=1., vary=True)
        estimate['a'].set(value=max(bunching / depth, 0.05), min=0., vary=True)
        estimate['tau1'].set(value=10 * tau2, min=step, vary=True)
        estimate['tau2'].set(value=tau2, min=step / 10)
        return estimate

    @estimator('No bunching')
    def estimate_no_bunching(self, data, x):
        estimate = self.estimate_full(data, x)
        estimate['a'].set(value=0., vary=False)
        estimate['tau1'].set(vary=False)
        return estimate

    @estimator('No SNR factor')
    def estimate_no_snr(self, data, x):
        estimate = self.estimate_full(data, x)
        estimate['snr_factor'].set(value=1., vary=False)
        return estimate

    @estimator('No bunching, no SNR factor')
    def estimate_no_bunching_no_snr(self, data, x):
        estimate = self.estimate_no_bunching(data, x)
        estimate['snr_factor'].set(value=1., vary=False)
        return estimate
