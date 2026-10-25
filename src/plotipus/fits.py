"""Fit model functions and the lookup used to evaluate stored fits.

A DataFrame row describing a fit names its model (``FitFunction`` /
``FitFunctionLabel``) and carries the fitted ``Params``; :func:`get_function`
resolves that name here first and then in every module added with
:func:`register_module` (e.g. a project's own physics models).
"""

import importlib
import types

import numpy as np
from scipy.special import erfc

_EXTRA_MODULES = []


def gaussian(x, a, b, c):
    return a * np.exp(-0.5 * ((x - b) / c) ** 2)


def gauss(x, coefficients, debug=False):
    """Gaussian with (amplitude, mean, sigma) packed in ``coefficients``."""
    a, x0, sigma = coefficients[0], coefficients[1], coefficients[2]
    return a * np.exp(-0.5 * np.power((x - x0) / sigma, 2))


def double_gaussian(x, a_core, mu, sigma_core, a_tail, sigma_tail):
    """Narrow core plus broad tail sharing one mean."""
    return (
        a_core * np.exp(-0.5 * ((x - mu) / abs(sigma_core)) ** 2)
        + a_tail * np.exp(-0.5 * ((x - mu) / abs(sigma_tail)) ** 2)
    )


def gaussian_train(x, *params):
    """Sum of Gaussians, one (amplitude, mean, sigma) triplet each."""
    total = np.zeros_like(np.asarray(x, dtype=float))
    for a, b, c in zip(params[0::3], params[1::3], params[2::3]):
        total = total + gaussian(x, a, b, c)
    return total


def exp_gauss_component(t, sig, amp, tau, phi):
    """Exponential decay (time constant ``tau``, onset ``phi``) convolved with
    a Gaussian of width ``sig``."""
    return (
        amp
        * np.exp(-(t - phi) / tau)
        * np.exp(-(sig**2) / (2 * tau**2))
        * erfc((phi - t) / (np.sqrt(2) * sig) + sig / (np.sqrt(2) * tau))
    )


def exp_gauss_component_left_tail(x, sig, amp, tau, mu):
    """Mirror image of :func:`exp_gauss_component`: the exponential tail sits
    below the peak."""
    return (
        amp
        * np.exp((x - mu) / tau + (sig**2) / (2 * tau**2))
        * erfc((x - mu) / (np.sqrt(2) * sig) + sig / (np.sqrt(2) * tau))
    )


def exponential(x, a, tau):
    return a * np.exp(-x / tau)


def gaussian_plus_exponential(x, a, mu, sigma, b, tau):
    """A Gaussian peak over an exponentially falling background."""
    return gaussian(x, a, mu, sigma) + exponential(x, b, tau)


def exponential_decay(x, a, b, c):
    return a * np.exp(-abs(x) / abs(c)) - b


def correction_func(x, a, b, c, d):
    return a * np.exp(-b * x) + c / (1 + np.exp(-d * x))


def quadratic_cut(x, a, b, c):
    y = a - a * b * x / x[-1] + c * (x / x[-1]) ** 2
    return 10**y


def quadratic_function(x, a, b, c):
    return a * x**2 + b * x + c


def linear_function(x, a, b):
    return a * x + b


def register_module(module):
    """Make the functions of ``module`` (a module or its import path)
    available to :func:`get_function`."""
    if isinstance(module, str):
        module = importlib.import_module(module)
    if module not in _EXTRA_MODULES:
        _EXTRA_MODULES.append(module)


def get_function(name):
    """Return the model called ``name`` (a bare or dotted name), or None."""
    if callable(name):
        return name
    if not isinstance(name, str) or not name:
        return None
    short = name.rsplit(".", 1)[-1]
    for module in [globals()] + _EXTRA_MODULES:
        namespace = module if isinstance(module, dict) else vars(module)
        candidate = namespace.get(short)
        if isinstance(candidate, types.FunctionType):
            return candidate
    if "." in name:
        module_name, _, attr = name.rpartition(".")
        try:
            return getattr(importlib.import_module(module_name), attr, None)
        except ImportError:
            return None
    return None
