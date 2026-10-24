"""Helpers shared by the generators: seeded generators and stored fits."""

import zlib

import numpy as np
from scipy.optimize import curve_fit


def rng_for(figure):
    """A generator seeded by the figure id, so each dataset is reproducible
    on its own and does not change when another generator draws more."""
    return np.random.default_rng(zlib.crc32(figure.encode()))


def stored_fit(function, x, y, error, p0, labels, label, units=None, formats=None, formula=None, fixed=(),
               **kwargs):
    """Fit ``function`` with errors ``error`` and return the plotipus fit
    columns (``FitFunction``, ``Params``, ``ParamsError``, ...). Parameters
    whose index is in ``fixed`` keep their ``p0`` value (error 0)."""
    free = [i for i in range(len(p0)) if i not in fixed]

    def model(x, *values):
        params = np.array(p0, dtype=float)
        params[free] = values
        return function(x, *params)

    values, covariance = curve_fit(model, x, y, p0=[p0[i] for i in free], sigma=error, absolute_sigma=True,
                                   **kwargs)
    params, errors = np.array(p0, dtype=float), np.zeros(len(p0))
    params[free], errors[free] = values, np.sqrt(np.diag(covariance))
    chi2 = float(np.sum(((y - function(x, *params)) / error) ** 2))
    columns = {
        "FitFunction": function.__name__,
        "FitFunctionLabel": label,
        "Params": list(params),
        "ParamsError": list(errors),
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
