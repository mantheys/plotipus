"""Confidence intervals for counts and efficiencies.

``garwood`` is the exact (central) Poisson interval of a count, as in mplhep
and ROOT's kPoisson; ``clopper_pearson`` the exact binomial interval of an
efficiency; ``sumw2`` the error of a weighted count. ``--errory_type
poisson`` and ``--errory_type clopper_pearson`` draw them, ``table
--clopper_pearson`` prints them.
"""

import numpy as np

ONE_SIGMA = 0.6827


def garwood(n, cl=ONE_SIGMA):
    """(low, high) central Poisson interval of the count(s) ``n`` at
    confidence ``cl``, from the chi-squared quantiles; low is 0 for n = 0."""
    from scipy.stats import chi2

    n = np.asarray(n, dtype=float)
    alpha = 1 - cl
    with np.errstate(invalid="ignore"):
        low = np.where(n > 0, chi2.ppf(alpha / 2, 2 * n) / 2, 0.0)
        high = chi2.ppf(1 - alpha / 2, 2 * (n + 1)) / 2
    return low, high


def clopper_pearson(passed, total, confidence=ONE_SIGMA):
    """Central Clopper-Pearson interval (low, high) of the fraction
    passed/total at the given confidence level. Exact for binomial counts and
    always inside [0, 1]: at 0 or 100% efficiency the interval is one-sided
    instead of a symmetric error crossing the bound (100.0 ± 0.9). Scalars
    give floats, arrays give arrays."""
    from scipy.stats import beta

    passed, total = np.asarray(passed, dtype=float), np.asarray(total, dtype=float)
    alpha = 1 - confidence
    with np.errstate(invalid="ignore", divide="ignore"):
        low = np.where(passed > 0, beta.ppf(alpha / 2, passed, total - passed + 1), 0.0)
        high = np.where(passed < total, beta.ppf(1 - alpha / 2, passed + 1, total - passed), 1.0)
    if low.ndim == 0:
        return float(low), float(high)
    return low, high


def sumw2(weights):
    """Error of a weighted count: the square root of the summed squared weights."""
    return float(np.sqrt(np.sum(np.square(np.asarray(weights, dtype=float)))))


def label(kind, cl=ONE_SIGMA):
    """Name of an interval for a legend or axis label, e.g. "68% CL (Clopper-Pearson)"."""
    name = {"poisson": "Poisson", "clopper_pearson": "Clopper–Pearson"}.get(kind, kind)
    return f"{100 * cl:.0f}% CL ({name})"
