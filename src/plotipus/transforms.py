"""DataFrame and array transforms applied before drawing.

Rows usually hold a whole series per cell (``x`` and ``y`` arrays); the
helpers here explode those cells into points, rebin, rescale, merge rows and
reshape series. They are pure functions of their inputs.
"""

import numpy as np
import pandas as pd
from rich import print as rprint

ARRAY_TYPES = (list, tuple, np.ndarray, pd.Series)


def is_array(value):
    return isinstance(value, ARRAY_TYPES)


def expand_singletons(frame, columns):
    """Broadcast one-value cells to the length of the longest array cell of
    the same row, so the columns can be exploded together."""
    frame = frame.copy()
    for row_index, row in frame.iterrows():
        lengths = [len(row[c]) if is_array(row[c]) else 1 for c in columns]
        target_length = max(lengths, default=1)
        if target_length <= 1:
            continue
        for column, length in zip(columns, lengths):
            if length == 1:
                value = row[column]
                if is_array(value):
                    value = value[0]
                frame.at[row_index, column] = [value] * target_length
    return frame


def align_error_column(frame, value_column, error_column):
    """Give rows whose error cell is missing/mismatched a NaN array of the
    value cell's length, so both columns explode together."""

    def _normalize(row):
        value = row[value_column]
        error = row[error_column]
        n = len(value) if is_array(value) else None
        if is_array(error) and n is not None and len(error) == n:
            return list(error)
        if n is not None:
            return [np.nan] * n
        return error

    frame = frame.copy()
    frame[error_column] = frame.apply(_normalize, axis=1)
    return frame


def explode(frame, columns):
    """One row per point of the array cells in ``columns``."""
    frame = expand_singletons(frame, columns)
    return frame.explode(column=list(columns))


def edges_from_centers(x):
    """Bin edges around sorted centres: uniform bins when the spacing is
    constant, midpoints otherwise (end bins extrapolated)."""
    x = np.asarray(x, dtype=float)
    if len(x) == 0:
        return np.array([])
    if len(x) == 1:
        return np.array([x[0] - 0.5, x[0] + 0.5])
    steps = np.diff(x)
    if np.allclose(steps, steps[0]):
        return np.linspace(x[0] - steps[0] / 2, x[-1] + steps[0] / 2, len(x) + 1)
    return np.concatenate([[x[0] - steps[0] / 2], x[:-1] + steps / 2, [x[-1] + steps[-1] / 2]])


def y_error_of(points, prefix="Error"):
    """Errors of exploded points: ``ErrorLow``/``ErrorHigh`` stacked (2, N),
    else ``Error`` (N,), else None (also when not castable to floats, and
    when every error is NaN: a row without an error cell in a frame where
    other rows have one has no error, so the default intervals apply).
    ``prefix`` names other error columns the same way."""
    error = None
    try:
        if f"{prefix}Low" in points.columns and f"{prefix}High" in points.columns:
            error = np.vstack([
                points[f"{prefix}Low"].astype(float).to_numpy(),
                points[f"{prefix}High"].astype(float).to_numpy(),
            ])
        elif prefix in points.columns:
            error = points[prefix].astype(float).to_numpy()
    except (ValueError, TypeError):
        return None
    if error is None or error.size == 0 or np.all(np.isnan(error)):
        return None
    return error


def pick_row(value, row):
    """Row ``row`` of a 2D cell (NaN-filled when the cell has fewer rows)."""
    value = np.asarray(value)
    if value.ndim != 2:
        return value
    return value[row] if row < len(value) else np.full(value.shape[1], np.nan)


def scale_cells(frame, columns, factor):
    """Multiply array/scalar cells of ``columns`` by ``factor``."""
    frame = frame.copy()
    for column in columns:
        if column in frame.columns:
            frame[column] = frame[column].apply(lambda v: np.asarray(v) * factor if v is not None else v)
    return frame


def rebin_rows(frame, x, y, n, sum_y=False, error_columns=()):
    """Merge every ``n`` consecutive points of array-valued x/y rows: x is the
    mean of the merged centres, y their mean (or sum with ``sum_y``); errors
    are combined in quadrature (divided by n unless summing). Trailing points
    that do not fill a group are dropped."""
    if not n or n <= 1:
        return frame
    frame = frame.copy()

    def _group(values, how):
        values = np.asarray(values, dtype=float)
        if values.ndim != 1 or len(values) < n:
            return values
        grouped = values[: len(values) // n * n].reshape(-1, n)
        if how == "sum":
            return grouped.sum(axis=1)
        if how == "quad":
            return np.sqrt((grouped**2).sum(axis=1)) / (1 if sum_y else n)
        return grouped.mean(axis=1)

    for i in frame.index:
        xv, yv = frame.at[i, x], frame.at[i, y]
        if np.ndim(xv) != 1 or np.ndim(yv) != 1 or len(xv) != len(yv):
            continue
        frame.at[i, x] = _group(xv, "mean")
        frame.at[i, y] = _group(yv, "sum" if sum_y else "mean")
        for column in error_columns:
            if column in frame.columns and np.ndim(frame.at[i, column]) == 1 and len(frame.at[i, column]) == len(yv):
                frame.at[i, column] = _group(frame.at[i, column], "quad")
    return frame


def _matches(value, token):
    """Match a data value against a CLI token, so '1' matches 1.0."""
    if str(value) == token:
        return True
    try:
        return float(value) == float(token)
    except (ValueError, TypeError):
        return False


def parse_merge_specs(specs):
    """'v1,v2=Label' specs -> [(members, label)]."""
    parsed = []
    for spec in specs or []:
        if "=" not in spec:
            raise ValueError(f"Invalid merge spec '{spec}' (expected 'v1,v2,...=Label')")
        values, label = spec.rsplit("=", 1)
        members = [v.strip() for v in values.split(",") if v.strip()]
        if not members or not label.strip():
            raise ValueError(f"Invalid merge spec '{spec}' (expected 'v1,v2,...=Label')")
        parsed.append((members, label.strip()))
    return parsed


def merge_groups(frame, column, y, specs, error_columns=None):
    """Replace the rows of each merged group of ``column`` values by summed
    rows (point by point, aligned on every other hashable column; errors in
    quadrature). A merged label takes the position of its first member."""
    groups = parse_merge_specs(specs)
    if not groups or frame.empty:
        return frame

    if error_columns is None:
        error_columns = [c for c in ("Error", f"{y}Error") if c in frame.columns]
    value_columns = {column, y, *error_columns}

    def _hashable(name):
        try:
            frame[name].map(hash)
            return True
        except TypeError:
            return False

    key_columns = [c for c in frame.columns if c not in value_columns and _hashable(c)]

    order = {}
    for value in frame[column]:
        order.setdefault(value, len(order))

    merged_frames = []
    consumed = pd.Series(False, index=frame.index)
    for members, label in groups:
        mask = frame[column].map(lambda v: any(_matches(v, m) for m in members)) & ~consumed
        if not mask.any():
            rprint(f"[yellow]Warning:[/yellow] merge group '{label}' matched no {column} values.")
            continue
        consumed |= mask
        members_df = frame[mask]
        order[label] = min(order[v] for v in members_df[column].unique())

        grouped = members_df.groupby(key_columns, dropna=False, sort=False) if key_columns else [((), members_df)]
        rows = []
        for _, group in grouped:
            row = group.iloc[0].copy()
            row[column] = label
            row[y] = sum(np.asarray(v, dtype=float) for v in group[y])
            for error_column in error_columns:
                row[error_column] = np.sqrt(sum(np.asarray(v, dtype=float) ** 2 for v in group[error_column]))
            rows.append(row)
        merged_frames.append(pd.DataFrame(rows))
        rprint(f"Merged {column} values ({', '.join(map(str, members_df[column].unique()))}) into '{label}' ({len(rows)} rows)")

    out = pd.concat([frame[~consumed].astype({column: object}), *merged_frames], ignore_index=True)
    rank = out[column].map(order)
    return out.iloc[np.argsort(rank.to_numpy(), kind="stable")].reset_index(drop=True)


def extrapolated_segments(x, y, mask):
    """Split a series into its measured points and the extrapolated ones;
    each extrapolated run is padded with its neighbouring measured points
    and runs are separated by NaN, ready for one dashed ``plot`` call."""
    x_norm, y_norm = x[~mask], y[~mask]
    ext_indices = np.where(mask)[0]
    groups = np.split(ext_indices, np.where(np.diff(ext_indices) > 1)[0] + 1)

    parts_x, parts_y = [], []
    for group in groups:
        if len(group) == 0:
            continue
        xi, yi = list(x[group]), list(y[group])
        if group[0] > 0 and not mask[group[0] - 1]:
            xi, yi = [x[group[0] - 1]] + xi, [y[group[0] - 1]] + yi
        if group[-1] + 1 < len(x) and not mask[group[-1] + 1]:
            xi, yi = xi + [x[group[-1] + 1]], yi + [y[group[-1] + 1]]
        parts_x.append(np.array(xi))
        parts_y.append(np.array(yi))

    nan = np.array([np.nan])
    x_ext = np.concatenate([v for p in parts_x for v in (p, nan)][:-1]) if parts_x else np.array([])
    y_ext = np.concatenate([v for p in parts_y for v in (p, nan)][:-1]) if parts_y else np.array([])
    return x_norm, y_norm, x_ext, y_ext


def mirror(x, y, at_edge=False):
    """Extend a spectrum by its reflection: around the upper edge of the last
    bin (``at_edge``), or around the last bin centre without repeating it."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    width = x[1] - x[0] if len(x) > 1 else 1
    if at_edge:
        point = x[-1] + width / 2
        return np.concatenate((x, 2 * point - x[::-1])), np.concatenate((y, y[::-1]))
    return np.concatenate((x, x[:-1] + (x[-1] - x[0]) + width)), np.concatenate((y, y[-2::-1]))


def project(x, y, target_x, scale=1.0, offset=0.0, error=None):
    """Values of the series (x rescaled by ``scale`` and shifted by
    ``offset``) interpolated on ``target_x`` (0 below the range); errors
    (symmetric array or [low, high]) are interpolated alike (0 outside)."""
    source_x = np.asarray(x, dtype=float) * scale + offset
    values = np.interp(target_x, source_x, y, left=0)
    if error is None:
        return values, None
    if isinstance(error, list):
        return values, [np.interp(target_x, source_x, e if e is not None else np.zeros_like(source_x), left=0, right=0) for e in error]
    return values, np.interp(target_x, source_x, error, left=0, right=0)


def union_grid(xs):
    """Common grid spanning every series (spacing of the first one)."""
    width, lo, hi = None, None, None
    for x in xs:
        if x is None or len(x) < 2:
            continue
        if width is None:
            width = float(x[1] - x[0])
        lo = float(np.min(x)) if lo is None else min(lo, float(np.min(x)))
        hi = float(np.max(x)) if hi is None else max(hi, float(np.max(x)))
    if not width or lo is None:
        return None
    n = int(round((hi - lo) / width)) + 1
    return lo + width * np.arange(n)


def combine(series, grid, how="sum"):
    """Combine (x, y, error) series on ``grid``: ``sum``, ``mean`` or
    ``squared_sum`` (sqrt of the sum of squares). Series off the grid are
    interpolated (0 outside their range); errors add in quadrature."""
    total, variance, count = None, None, 0
    for x, y, error in series:
        if not np.array_equal(x, grid):
            y = np.interp(grid, x, y, left=0, right=0)
            if error is not None:
                error = (
                    [np.interp(grid, x, e, left=0, right=0) for e in error]
                    if isinstance(error, list)
                    else np.interp(grid, x, error, left=0, right=0)
                )
        term = np.power(y, 2) if how == "squared_sum" else np.asarray(y, dtype=float)
        total = term if total is None else total + term
        if error is not None:
            err_sq = np.power(error, 2)
            variance = err_sq if variance is None else variance + err_sq
        count += 1
    if total is None:
        return None, None
    if how == "squared_sum":
        total = np.sqrt(total)
    elif how == "mean":
        total = total / count
        variance = None if variance is None else variance / count**2
    return total, None if variance is None else np.sqrt(variance)


def reduction_bins(x, n_edges=51, reduce=False, span=None):
    """(edges, centres) for binning raw values: unit bins centred on the
    integers for integer x (every other bin when ``reduce`` and there are
    more than 8), else ``n_edges`` equally spaced edges over the range
    (``span`` = (min, max) when given, e.g. shared by every series)."""
    x = np.asarray(x)
    lo, hi = (x.min(), x.max()) if span is None else span
    if np.issubdtype(x.dtype, np.integer):
        lo, hi = int(np.floor(lo)), int(np.ceil(hi))
        edges = np.arange(lo, hi + 1.5) - 0.5
        centres = np.arange(lo, hi + 1)
        if reduce and len(edges) > 8:
            edges, centres = edges[::2], centres[::2]
        if edges[-1] < centres[-1]:
            centres = centres[:-1]
        return edges, centres
    edges = np.linspace(lo, hi, n_edges)
    return edges, (edges[:-1] + edges[1:]) / 2


_ESTIMATORS = {
    "mean": np.mean,
    "average": np.mean,
    "sum": np.sum,
    "max": np.max,
    "min": np.min,
    "median": np.median,
    "std": np.std,
    "rms": lambda values: np.sqrt(np.mean(np.square(values))),
}


def _sigma(values):
    """Sample standard deviation (ddof=1); NaN below two entries."""
    return np.std(values, ddof=1) if len(values) > 1 else np.nan


def _rms_error(values):
    rms = np.sqrt(np.mean(np.square(values)))
    # Delta method: var(mean(x²)) = var(x²)/n and d√m/dm = 1/(2√m).
    return _sigma(np.square(values)) / (2 * rms * np.sqrt(len(values))) if rms > 0 else np.nan


# Standard error of each estimator from the bin's own spread.
_ESTIMATOR_ERRORS = {
    "mean": lambda values: _sigma(values) / np.sqrt(len(values)),
    "average": lambda values: _sigma(values) / np.sqrt(len(values)),
    # √Σy²: √n for unit entries (counts), √Σw² when the entries are weights.
    "sum": lambda values: np.sqrt(np.sum(np.square(values))),
    "max": lambda values: np.nan,
    "min": lambda values: np.nan,
    # √(π/2) = 1.2533: asymptotic efficiency of the median for a normal sample.
    "median": lambda values: np.sqrt(np.pi / 2) * _sigma(values) / np.sqrt(len(values)),
    "std": lambda values: _sigma(values) / np.sqrt(2 * (len(values) - 1)) if len(values) > 1 else np.nan,
    "rms": _rms_error,
}


def _propagated_error(values, errors, estimator):
    """First-order propagation of stored per-event errors through the
    estimator, the events taken as independent: mean √Σe²/n, sum √Σe²,
    median 1.2533·√Σe²/n, std and rms through their derivatives, max/min the
    error of the selected event. NaN where the propagation is undefined
    (std of identical values, rms of zeros)."""
    values = np.asarray(values, dtype=float)
    errors = np.asarray(errors, dtype=float)
    n = len(values)
    if estimator in ("mean", "average"):
        return np.sqrt(np.sum(np.square(errors))) / n
    if estimator == "sum":
        return np.sqrt(np.sum(np.square(errors)))
    if estimator == "median":
        return np.sqrt(np.pi / 2) * np.sqrt(np.sum(np.square(errors))) / n
    if estimator == "max":
        return errors[np.argmax(values)]
    if estimator == "min":
        return errors[np.argmin(values)]
    if estimator == "std":
        sigma = _sigma(values)
        if not sigma > 0:
            return np.nan
        return np.sqrt(np.sum(np.square((values - values.mean()) * errors))) / ((n - 1) * sigma)
    if estimator == "rms":
        rms = np.sqrt(np.mean(np.square(values)))
        return np.sqrt(np.sum(np.square(values * errors))) / (n * rms) if rms > 0 else np.nan
    return np.nan


def estimate(values, estimator="mean", errors=None, error_mode="sem"):
    """(value, error) of ``estimator`` over ``values``.

    ``error_mode``: ``sem`` the standard error of the statistic, propagated
    from stored per-event ``errors`` when given (see
    :func:`_propagated_error`; the statistical error where that is
    undefined), else from the spread of the values; ``std`` the spread
    itself (sample σ); ``none`` no error (NaN)."""
    estimator = estimator.lower()
    values = np.asarray(values)
    if values.size == 0:
        return np.nan, np.nan
    value = _ESTIMATORS[estimator](values)
    if error_mode == "none":
        return value, np.nan
    if error_mode == "std":
        return value, _sigma(values)
    error = np.nan if errors is None else _propagated_error(values, errors, estimator)
    if not np.isfinite(error):
        error = _ESTIMATOR_ERRORS[estimator](values)
    return value, error


def _bin_masks(x, edges, cumulative):
    for i in range(len(edges) - 1):
        yield x >= edges[i] if cumulative else (x >= edges[i]) & (x < edges[i + 1])


def bin_reduce(x, y, edges, estimator="mean", cumulative=False):
    """``estimator`` of the y values falling in each bin of ``edges`` (bins
    are [lo, hi); with ``cumulative`` every value with x >= lo). Without an
    estimator, the list of per-bin y arrays (e.g. for box plots)."""
    x = np.asarray(x)
    y = np.asarray(y)
    groups = [y[mask] for mask in _bin_masks(x, edges, cumulative)]
    if estimator is None:
        return groups
    function = _ESTIMATORS[estimator.lower()]
    return np.array([function(group) for group in groups])


def bin_estimate(x, y, edges, estimator="mean", cumulative=False, errors=None, error_mode="sem"):
    """(values, errors, counts) per bin: :func:`bin_reduce` with each bin's
    error from :func:`estimate` and its number of entries. ``errors`` are
    optional stored per-event errors of ``y``."""
    x = np.asarray(x)
    y = np.asarray(y)
    errors = None if errors is None else np.asarray(errors)
    values, uncertainties, counts = [], [], []
    for mask in _bin_masks(x, edges, cumulative):
        value, error = estimate(y[mask], estimator, None if errors is None else errors[mask], error_mode)
        values.append(value)
        uncertainties.append(error)
        counts.append(int(np.count_nonzero(mask)))
    return np.array(values, dtype=float), np.array(uncertainties, dtype=float), np.array(counts)
