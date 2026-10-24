"""Helpers shared by the generators: seeded generators and stored fits."""

import zlib

import numpy as np
from scipy.optimize import curve_fit


def rng_for(figure):
    """A generator seeded by the figure id, so each dataset is reproducible
    on its own and does not change when another generator draws more."""
    return np.random.default_rng(zlib.crc32(figure.encode()))


def stored_fit(function, x, y, error, p0, labels, label, units=None, formats=None, formula=None, **kwargs):
    """Fit ``function`` with errors ``error`` and return the plotipus fit
    columns (``FitFunction``, ``Params``, ``ParamsError``, ...)."""
    params, covariance = curve_fit(function, x, y, p0=p0, sigma=error, absolute_sigma=True, **kwargs)
    chi2 = float(np.sum(((y - function(x, *params)) / error) ** 2))
    columns = {
        "FitFunction": function.__name__,
        "FitFunctionLabel": label,
        "Params": list(params),
        "ParamsError": list(np.sqrt(np.diag(covariance))),
        "ParamsLabel": list(labels),
        "Chi2": chi2,
    }
    if units is not None:
        columns["ParamsUnit"] = list(units)
    if formats is not None:
        columns["ParamsFormat"] = list(formats)
    if formula is not None:
        columns["FitFunctionFormula"] = formula
    return columns
