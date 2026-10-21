"""Lower panels: what they show and how.

A lower panel is described by ``--lower SPEC`` (repeatable, one panel each):

* an operation between the drawn series, against a reference series:
  ``ratio``, ``subtract``, ``add``, ``multiply``, ``relative_difference``,
  ``absolute_relative_difference``, ``asymmetry``, ``excess``,
  ``excess_probability``; or across all series: ``sum``, ``mean``, ``rms``;
* ``group``: two weighted sums of series (``--reference_group`` against
  ``--other_group``), their difference or significance;
* ``residual`` / ``pull``: data against a fit/model curve,
  (y - model) / model and (y - model) / error;
* ``column:NAME``: a series stored in the DataFrame (with ``NAMEError``);
* ``events:PREFIX``: event markers read from ``PREFIX*`` columns.

Every panel is styled with the same options as the upper panel, prefixed
with ``lower_`` (``--lower_plot_type``, ``--lower_labely``, ...).
"""

from dataclasses import dataclass

import numpy as np
from scipy.special import erf

PAIRWISE_OPERATIONS = (
    "relative_difference",
    "absolute_relative_difference",
    "asymmetry",
    "excess",
    "excess_probability",
    "subtract",
    "ratio",
    "add",
    "multiply",
)
AGGREGATE_OPERATIONS = ("sum", "mean", "rms")
MODEL_OPERATIONS = ("residual", "pull")
# "group": two weighted sums of series compared (--reference_group/--other_group).
OPERATIONS = PAIRWISE_OPERATIONS + AGGREGATE_OPERATIONS + MODEL_OPERATIONS + ("group",)

DEFAULT_LABELS = {
    "subtract": "Difference",
    "add": "Sum",
    "multiply": "Product",
    "sum": "Sum",
    "mean": "Mean",
    "rms": "RMS",
    "ratio": "Ratio",
    "asymmetry": "Asymmetry",
    "excess": "Excess Significance",
    "excess_probability": "Excess Probability",
    "relative_difference": "Relative Difference (%)",
    "absolute_relative_difference": "Absolute Relative Difference (%)",
    "residual": "Residual",
    "pull": "Pull",
    "group": "Difference",
}

# Reference line drawn by default on a lower panel of each operation.
REFERENCE_LINES = {"ratio": 1.0, "subtract": 0.0, "relative_difference": 0.0, "residual": 0.0, "pull": 0.0}


@dataclass
class LowerSpec:
    kind: str  # "operation", "column" or "events"
    name: str

    @property
    def label(self):
        return DEFAULT_LABELS.get(self.name, self.name)


def parse_lower(spec):
    """``ratio`` -> operation, ``column:X`` -> column, ``events:P`` -> events."""
    text = str(spec).strip()
    if ":" in text:
        kind, _, name = text.partition(":")
        if kind in ("column", "events"):
            return LowerSpec(kind, name)
    if text in OPERATIONS:
        return LowerSpec("operation", text)
    return LowerSpec("column", text)


def pairwise(reference, other, operation):
    """``other`` compared with ``reference``; undefined points are NaN."""
    reference = np.asarray(reference, dtype=float)
    other = np.asarray(other, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        if operation == "subtract":
            return other - reference
        if operation == "add":
            return other + reference
        if operation == "multiply":
            return other * reference
        if operation == "ratio":
            result = np.divide(other, reference)
        elif operation == "relative_difference":
            result = 100.0 * np.divide(other - reference, reference)
        elif operation == "absolute_relative_difference":
            result = 100.0 * np.abs(np.divide(other - reference, reference))
        elif operation == "asymmetry":
            result = np.divide(reference - other, 0.5 * (reference + other))
        elif operation == "excess":
            # Floored S/sqrt(B)-style significance of reference over other.
            result = np.maximum(0.0, reference - other) / np.sqrt(other)
        elif operation == "excess_probability":
            # The same significance as two-sided Gaussian coverage: bounded in
            # [0, 1) and saturating instead of diverging when other -> 0.
            z = np.maximum(0.0, reference - other) / np.sqrt(other)
            result = erf(z / np.sqrt(2.0))
        else:
            raise ValueError(f"Unsupported pairwise operation: {operation}")
    result[~np.isfinite(result)] = np.nan
    return result


def operation_series(labels, arrays, operation, reference_index=0, reference_sum=None, reference_sum_label=None):
    """Lower-panel series ``[(label, values)]`` of ``operation`` over the
    upper series ``arrays`` (named ``labels``).

    Aggregates (sum/mean/rms) give one series. Pairwise operations compare
    every series with the one at ``reference_index``; the series named in
    ``reference_sum`` are first summed into one (labelled
    ``reference_sum_label``).
    """
    if len(labels) != len(arrays):
        raise ValueError("labels and arrays must have the same length")
    if not arrays:
        return []

    op = operation.lower()
    if op in AGGREGATE_OPERATIONS:
        stacked = np.vstack(arrays)
        if op == "sum":
            return [("sum", np.sum(stacked, axis=0))]
        if op == "mean":
            return [("mean", np.mean(stacked, axis=0))]
        return [("rms", np.sqrt(np.mean(stacked**2, axis=0)))]

    if len(arrays) < 2:
        return []

    ref_idx = max(0, min(reference_index, len(arrays) - 1))
    ref_array = arrays[ref_idx]
    sum_set = {str(s) for s in reference_sum} if reference_sum else set()
    summed = None
    summed_label = reference_sum_label or (" + ".join(str(s) for s in reference_sum) if reference_sum else None)

    output = []
    for idx, (label, values) in enumerate(zip(labels, arrays)):
        if idx == ref_idx:
            continue
        if str(label) in sum_set:
            summed = values if summed is None else summed + values
            continue
        output.append((str(label), pairwise(ref_array, values, op)))
    if summed is not None:
        output.append((str(summed_label), pairwise(ref_array, summed, op)))
    return output


def _group_weights(values, weights):
    weights = list(weights) if weights is not None else [1.0] * len(values)
    if len(weights) != len(values):
        raise ValueError(f"Got {len(values)} group values but {len(weights)} weights; they must match 1:1.")
    return weights


def weighted_group_sum(labels, arrays, errors, group, weights=None):
    """Weighted sum of the series named in ``group`` and its error (each
    series' error times its weight, in quadrature)."""
    index = {str(l): i for i, l in enumerate(labels)}
    total, variance = None, None
    for value, weight in zip(group, _group_weights(group, weights)):
        i = index.get(str(value))
        if i is None:
            raise ValueError(f"Value '{value}' not found among plotted labels: {list(index)}")
        scaled = arrays[i] * weight
        total = scaled if total is None else total + scaled
        error = errors[i] if i < len(errors) else None
        err_sq = (error * weight) ** 2 if error is not None else np.zeros_like(scaled)
        variance = err_sq if variance is None else variance + err_sq
    return total, np.sqrt(variance)


def group_difference(
    labels,
    arrays,
    errors,
    reference_group,
    reference_group_weights,
    reference_group_label,
    other_group,
    other_group_weights,
    other_group_label,
    correlated=True,
    relative=False,
    significance=False,
    significance_min_background=0.0,
):
    """``[(label, values, errors)]`` comparing two weighted sums of series.

    * default: reference sum minus other sum. With ``correlated`` a series in
      both groups at equal weight cancels from value and error (the same
      quantity counted on both sides); otherwise the two sums are combined as
      independent.
    * ``relative``: the difference in percent of the other sum (points where
      that sum is below 1e-6 of its peak are left out).
    * ``significance``: S/sqrt(B) per point, S and B the two sums; points
      with B <= 0 or below ``significance_min_background`` are left out.
    """
    ref_label = reference_group_label or " + ".join(str(v) for v in reference_group)
    other_label = other_group_label or " + ".join(str(v) for v in other_group)
    out_label = f"{ref_label} - {other_label}"

    if significance:
        # Empty bins of a component are NaN; they count as zero in the sums.
        arrays_0 = [np.nan_to_num(np.asarray(a, dtype=float), nan=0.0) for a in arrays]
        errors_0 = [None if e is None else np.nan_to_num(np.asarray(e, dtype=float), nan=0.0) for e in errors]
        s, s_err = weighted_group_sum(labels, arrays_0, errors_0, reference_group, reference_group_weights)
        b, b_err = weighted_group_sum(labels, arrays_0, errors_0, other_group, other_group_weights)
        with np.errstate(divide="ignore", invalid="ignore"):
            sig = s / np.sqrt(b)
            sig_err = np.sqrt((s_err / np.sqrt(b)) ** 2 + (s * b_err / (2.0 * b**1.5)) ** 2)
        empty = ~((b > 0) & (b >= significance_min_background))
        sig[empty] = np.nan
        sig_err[empty] = np.nan
        sig[~np.isfinite(sig)] = np.nan
        sig_err[~np.isfinite(sig_err)] = np.nan
        return [(f"{ref_label}/sqrt({other_label})", sig, sig_err)]

    if correlated:
        index = {str(l): i for i, l in enumerate(labels)}
        net = {}
        for value, weight in zip(reference_group, _group_weights(reference_group, reference_group_weights)):
            net[str(value)] = net.get(str(value), 0.0) + weight
        for value, weight in zip(other_group, _group_weights(other_group, other_group_weights)):
            net[str(value)] = net.get(str(value), 0.0) - weight

        diff, variance = None, None
        for label, weight in net.items():
            if weight == 0:
                continue
            i = index.get(label)
            if i is None:
                raise ValueError(f"Value '{label}' not found among plotted labels: {list(index)}")
            contribution = arrays[i] * weight
            diff = contribution if diff is None else diff + contribution
            error = errors[i] if i < len(errors) else None
            err_sq = (error * weight) ** 2 if error is not None else np.zeros_like(contribution)
            variance = err_sq if variance is None else variance + err_sq
        if diff is None:
            raise ValueError("reference_group and other_group fully cancel -- nothing left to plot.")
        diff_err = np.sqrt(variance)
    else:
        ref_sum, ref_err = weighted_group_sum(labels, arrays, errors, reference_group, reference_group_weights)
        other_sum, other_err = weighted_group_sum(labels, arrays, errors, other_group, other_group_weights)
        diff = ref_sum - other_sum
        diff_err = np.sqrt(ref_err**2 + other_err**2)

    if not relative:
        return [(out_label, diff, diff_err)]

    other_sum, other_err = weighted_group_sum(labels, arrays, errors, other_group, other_group_weights)
    with np.errstate(divide="ignore", invalid="ignore"):
        rel = 100.0 * diff / other_sum
        rel_err = 100.0 * np.sqrt((diff_err / other_sum) ** 2 + (diff * other_err / other_sum**2) ** 2)
    # A merely tiny denominator still gives a finite but meaningless ratio.
    tiny = np.abs(other_sum) < 1e-6 * np.nanmax(np.abs(other_sum))
    rel[tiny] = np.nan
    rel_err[tiny] = np.nan
    rel[~np.isfinite(rel)] = np.nan
    rel_err[~np.isfinite(rel_err)] = np.nan
    return [(f"({out_label})/{other_label} [%]", rel, rel_err)]


def model_series(y, model, error=None, operation="residual"):
    """``residual`` = (y - model) / model, ``pull`` = (y - model) / error."""
    y = np.asarray(y, dtype=float)
    model = np.asarray(model, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        if operation == "pull":
            if error is None:
                return np.full_like(y, np.nan)
            result = (y - model) / np.asarray(error, dtype=float)
        else:
            result = (y - model) / model
    result[~np.isfinite(result)] = np.nan
    return result
