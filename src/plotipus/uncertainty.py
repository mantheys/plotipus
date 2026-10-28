"""The style guide's uncertainty rules for drawn and tabulated values.

U1: stored errors are drawn by default; a series without them gets the
standard interval of its quantity (Garwood for counts, Clopper-Pearson for
efficiencies with their trials) and a warning naming it, or a warning that
it has none. U4: stored errors that cross a physical bound (below 0, above
100% for efficiencies) are drawn as given, with a warning naming the bound.
Each warning is printed once per series and command.
"""

import numpy as np
from rich import print as rprint

from . import intervals


def is_counts(values):
    """Whether ``values`` read as event counts: finite, non-negative
    integers (a measurement such as a magnitude or a ratio is not)."""
    try:
        values = np.asarray(values, dtype=float)
    except (TypeError, ValueError):
        return False
    values = values[np.isfinite(values)]
    return values.size > 0 and bool(np.all(values >= 0)) and bool(np.all(values == np.round(values)))


def is_exact(args, hue):
    """Whether hue value ``hue`` is exact (--exact): a model, fit or theory
    curve, drawn without errors and without a warning."""
    exact = getattr(args, "exact", None)
    return bool(exact) and hue is not None and str(hue) in {str(v) for v in exact}


def warn_once(args, key, message):
    """Print ``message`` the first time ``key`` comes up in this command."""
    warned = args.__dict__.setdefault("_uncertainty_warned", set())
    if key in warned:
        return
    warned.add(key)
    rprint(f"[yellow]Warning:[/yellow] {message}")


def warn_interval(args, name, column, kind, trials=None):
    """U1: the series ``name`` has no error column; ``kind`` is drawn instead."""
    what = {"poisson": "Garwood (Poisson)", "clopper_pearson": "Clopper–Pearson"}.get(kind, kind)
    cl = 100 * getattr(args, "confidence_level", intervals.ONE_SIGMA)
    of = f" of the {trials} trials" if trials else ""
    warn_once(args, ("interval", name), f"{name}: {column} has no error column; drawing {what} {cl:.0f}% intervals{of}.")


def warn_none(args, name, column):
    """U1: the series ``name`` has no error column and no standard interval."""
    warn_once(args, ("none", name),
              f"{name}: {column} has no error column and no standard interval applies; drawn with no "
              "uncertainty (--exact VALUE marks a model curve, --no_error draws none).")


def check_bounds(args, name, column, values, low, high, scale=1.0, efficiency=None):
    """U4: warn once when stored errors (``low``/``high`` distances below and
    above ``values``) cross 0 for a quantity that is never negative, or
    ``scale`` (100%) for an efficiency. ``efficiency`` None reads every
    value inside [0, scale] as an efficiency."""
    try:
        values = np.asarray(values, dtype=float)
        low = np.broadcast_to(np.asarray(low, dtype=float), values.shape)
        high = np.broadcast_to(np.asarray(high, dtype=float), values.shape)
    except (TypeError, ValueError):
        return
    finite = np.isfinite(values) & np.isfinite(low) & np.isfinite(high)
    if not finite.any():
        return
    values, low, high = values[finite], low[finite], high[finite]
    if not np.all(values >= 0):
        return
    below = int(np.sum(values - low < 0))
    if below:
        warn_once(args, ("below", name),
                  f"{name}: the stored {column} errors go below 0 at {below} point{'s' if below > 1 else ''}, "
                  "but the quantity is never negative; drawn as given.")
    if efficiency is None:
        efficiency = bool(np.all(values <= scale))
    above = int(np.sum(values + high > scale)) if efficiency else 0
    if above:
        bound = "100%" if scale == 100 else f"{scale:g}"
        warn_once(args, ("above", name),
                  f"{name}: the stored {column} errors go above {bound} at {above} point{'s' if above > 1 else ''}, "
                  "but an efficiency cannot; drawn as given.")
