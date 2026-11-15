"""Statistics of posterior samples for the corner plot (``map --corner
--contour``): effective sample sizes, marginal densities and the intervals
read from them (highest density, in pieces, wrapped around a cyclic axis,
one-sided at a bound), the probabilities of the parts of a split sample, the
profile of a log-likelihood over the draws and the correlation of two
parameters. Plain numpy on arrays; nothing here draws.
"""

import numpy as np

# Fine bins per panel bin of the density an interval is read from.
FINE = 8
# A profile bin with fewer draws is not drawn: the maximum over them is too far below the true one.
PROFILE_MIN_DRAWS = 3
# Effective draws a region needs outside it: fewer, and its outline is mostly noise.
MIN_DRAWS_OUTSIDE = 25
# Smallest kernel of a smoothed marginal, in panel bins: below it the curve follows the noise of the fine bins.
KDE_MIN_SIGMA = 0.25


# --- Sample sizes ------------------------------------------------------------------


def kish_ess(weights):
    """Effective size of weighted draws: (sum w)^2 / sum w^2."""
    weights = np.asarray(weights, dtype=float)
    total = weights.sum()
    return float(total**2 / np.sum(weights**2)) if total > 0 else 0.0


def chain_ess(chain):
    """Effective size of one chain in draw order: N / (1 + 2 sum rho_t), the
    autocorrelations summed in pairs while the pairs stay positive (Geyer's
    initial positive sequence). N for independent draws, never more."""
    chain = np.asarray(chain, dtype=float)
    n = chain.size
    if n < 8 or np.ptp(chain) == 0:
        return float(n)
    centred = chain - chain.mean()
    size = 1 << int(np.ceil(np.log2(2 * n)))
    spectrum = np.fft.rfft(centred, size)
    rho = np.fft.irfft(spectrum * np.conj(spectrum), size)[:n]
    rho /= rho[0]
    pairs = rho[: 2 * (n // 2)].reshape(-1, 2).sum(axis=1)
    stop = np.argmax(pairs <= 0) if np.any(pairs <= 0) else len(pairs)
    tau = max(1.0, 2.0 * pairs[:stop].sum() - 1.0)
    return float(n / tau)


def sample_ess(columns, weights, lengths, cyclic=()):
    """Effective size of a sample: Kish's for weighted draws, else the
    smallest over the parameters of the summed chain sizes (``lengths``: the
    draws of each chain, in the order they are joined). ``cyclic`` gives
    (low, high) for the periodic columns (None for the others), which are
    taken through their sine and cosine."""
    if weights is not None and np.ptp(weights) > 0:
        return kish_ess(weights)
    bounds = np.r_[0, np.cumsum(lengths)]
    sizes = []
    for index, column in enumerate(columns):
        period = cyclic[index] if index < len(cyclic) else None
        if period is not None:
            phase = 2 * np.pi * (column - period[0]) / (period[1] - period[0])
            series = [np.sin(phase), np.cos(phase)]
        else:
            series = [column]
        for values in series:
            sizes.append(sum(chain_ess(values[a:b]) for a, b in zip(bounds[:-1], bounds[1:])))
    return float(min(sizes)) if sizes else 0.0


# --- Marginal densities and intervals ----------------------------------------------


def smooth1d(density, sigma, left="nearest", right="nearest"):
    """Gaussian smoothing of a 1D density by ``sigma`` bins. Each end is
    padded by its own rule: 'wrap' (cyclic), 'reflect' (a hard bound: nothing
    leaks across) or 'nearest'."""
    from scipy.ndimage import gaussian_filter1d

    density = np.asarray(density, dtype=float)
    if sigma <= 0:
        return density
    pad = min(len(density), int(np.ceil(4 * sigma)) + 1)
    sides = {"wrap": (density[-pad:], density[:pad]), "reflect": (density[:pad][::-1], density[-pad:][::-1]),
             "nearest": (np.full(pad, density[0]), np.full(pad, density[-1]))}
    padded = np.concatenate([sides[left][0], density, sides[right][1]])
    return gaussian_filter1d(padded, sigma, mode="nearest")[pad:-pad]


def fine_density(values, weights, edges, cyclic=False, bound=(np.nan, np.nan), sigma=0.75):
    """(fine edges, density) of a marginal: FINE bins per panel bin over the
    panel range, widened to hold the tails outside it (never past a bound,
    exactly one period for a cyclic variable), smoothed by ``sigma`` panel
    bins. The density integrates to the fraction of the draws inside."""
    values = np.asarray(values, dtype=float)
    width = (edges[-1] - edges[0]) / (len(edges) - 1) / FINE
    low, high = float(edges[0]), float(edges[-1])
    if not cyclic:
        tails = np.percentile(values, [0.05, 99.95])
        low = min(low, tails[0]) if not np.isfinite(bound[0]) else max(min(low, tails[0]), bound[0])
        high = max(high, tails[1]) if not np.isfinite(bound[1]) else min(max(high, tails[1]), bound[1])
    count = int(np.clip(np.ceil((high - low) / width), FINE, 20000))
    fine = np.linspace(low, high, count + 1)
    total = float(np.sum(weights)) if weights is not None else float(len(values))
    counts, _ = np.histogram(values, bins=fine, weights=weights)
    density = counts / (total * np.diff(fine))
    left = "wrap" if cyclic else "reflect" if np.isfinite(bound[0]) and np.isclose(low, bound[0]) else "nearest"
    right = "wrap" if cyclic else "reflect" if np.isfinite(bound[1]) and np.isclose(high, bound[1]) else "nearest"
    return fine, smooth1d(density, sigma * FINE, left, right)


def kde_sigma(values, weights, ess, width, bw="scott"):
    """Gaussian kernel width of a marginal in panel bins of ``width``: ``bw`` is a
    width in the units of the values, or 'scott' / 'silverman' (the rules of thumb
    at the effective sample size ``ess``, so that autocorrelated or heavily weighted
    draws are smoothed more). Never below KDE_MIN_SIGMA."""
    values = np.asarray(values, dtype=float)
    mean = np.average(values, weights=weights)
    spread = float(np.sqrt(np.average((values - mean) ** 2, weights=weights)))
    try:
        h = float(bw)
    except (TypeError, ValueError):
        n = max(float(ess or len(values)), 2.0)
        h = spread * ((0.75 * n) ** -0.2 if bw == "silverman" else n**-0.2)
    return max(h / width, KDE_MIN_SIGMA)


def marginal_curve(values, weights, edges, sigma, cyclic=False, bound=(np.nan, np.nan)):
    """(edges, density) of a smoothed marginal over the panel range ``edges``:
    :func:`fine_density` cut to the panel."""
    fine, density = fine_density(values, weights, edges, cyclic, bound, sigma=sigma)
    centres = 0.5 * (fine[1:] + fine[:-1])
    kept = np.flatnonzero((centres >= edges[0]) & (centres <= edges[-1]))
    if kept.size == 0:
        return np.asarray(edges, dtype=float), np.zeros(len(edges) - 1)
    return fine[kept[0]: kept[-1] + 2], density[kept[0]: kept[-1] + 1]


def density_pieces(fine, density, fraction, cyclic=False):
    """The highest-density region of a marginal holding ``fraction`` of it:
    ([(low, high), ...], mode). The bins are filled from the densest down and
    the ends interpolated where the density crosses the threshold. Pieces are
    never merged. A piece of a cyclic variable that crosses the end of the
    axis is one piece whose upper end lies past it (high > fine[-1])."""
    widths = np.diff(fine)
    centres = 0.5 * (fine[1:] + fine[:-1])
    mass = density * widths
    order = np.argsort(density)[::-1]
    reached = np.searchsorted(np.cumsum(mass[order]), fraction * mass.sum())
    threshold = density[order[min(reached, len(order) - 1)]]
    inside = density >= threshold
    mode = float(centres[np.argmax(density)])
    pieces, start = [], None
    for i, flag in enumerate(np.r_[inside, False]):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            pieces.append([_crossing(centres, density, start, threshold, fine[0], -1),
                           _crossing(centres, density, i - 1, threshold, fine[-1], +1)])
            start = None
    if cyclic and len(pieces) > 1 and inside[0] and inside[-1]:
        first = pieces.pop(0)
        pieces[-1][1] = first[1] + (fine[-1] - fine[0])
    elif cyclic and len(pieces) == 1 and inside.all():
        pieces = [[float(fine[0]), float(fine[-1])]]
    return [tuple(float(v) for v in piece) for piece in pieces], mode


def _crossing(centres, density, index, threshold, end, step):
    """Where the density crosses the threshold just outside bin ``index``
    (towards ``step``), or the end of the axis."""
    other = index + step
    if other < 0 or other >= len(centres):
        return end
    d_in, d_out = density[index], density[other]
    if d_in == d_out:
        return centres[index]
    return centres[index] + (centres[other] - centres[index]) * (d_in - threshold) / (d_in - d_out)


def weighted_quantiles(values, weights, quantiles):
    """Quantiles of weighted values (unit weights for None): the weighted
    ECDF taken at each value's mid-weight, interpolated."""
    order = np.argsort(values)
    values = np.asarray(values, dtype=float)[order]
    weights = np.ones(len(values)) if weights is None else np.asarray(weights, dtype=float)[order]
    cumulative = (np.cumsum(weights) - 0.5 * weights) / weights.sum()
    return np.interp(quantiles, cumulative, values)


def quantile_error(values, weights, quantile, ess):
    """Monte Carlo standard error of a quantile: half the distance between
    the quantiles one binomial standard deviation to each side."""
    if not ess or ess <= 1:
        return np.nan
    step = np.sqrt(quantile * (1 - quantile) / ess)
    low, high = weighted_quantiles(values, weights, [max(0.0, quantile - step), min(1.0, quantile + step)])
    return float(0.5 * (high - low))


# --- Splits --------------------------------------------------------------------------


def split_probabilities(masks, weights, ess):
    """[(probability, error)] of the parts of a sample (boolean masks): the
    weighted fraction of the draws, with its binomial error at the effective
    sample size."""
    weights = np.ones(len(masks[0])) if weights is None else np.asarray(weights, dtype=float)
    total = weights.sum()
    result = []
    for mask in masks:
        p = float(weights[mask].sum() / total)
        result.append((p, float(np.sqrt(max(p * (1 - p), 0.0) / ess)) if ess and ess > 0 else np.nan))
    return result


# --- Profile likelihood ------------------------------------------------------------


def profile_grid(chi2, bins, shape):
    """(-2 ln L minimised over the draws of each bin, draws per bin):
    ``bins`` is one array of bin indices per axis (-1: outside), ``shape``
    the number of bins per axis. Empty bins are +inf."""
    inside = np.logical_and.reduce([(b >= 0) & (b < s) for b, s in zip(bins, shape)])
    index = tuple(b[inside] for b in bins)
    best = np.full(shape, np.inf)
    np.minimum.at(best, index, chi2[inside])
    counts = np.zeros(shape, dtype=int)
    np.add.at(counts, index, 1)
    return best, counts


def bin_index(values, edges):
    """Bin of each value in ``edges`` (-1 outside)."""
    index = np.searchsorted(edges, values, side="right") - 1
    index[values == edges[-1]] = len(edges) - 2
    index[(index < 0) | (index >= len(edges) - 1)] = -1
    return index


# --- Correlations --------------------------------------------------------------------


def correlation(x, y, weights, ess):
    """(rho, error): the weighted Pearson coefficient of two columns and its
    large-sample error (1 - rho^2) / sqrt(ESS - 1)."""
    rho = float(np.cov(x, y, aweights=weights)[0, 1] / np.sqrt(np.cov(x, aweights=weights) * np.cov(y, aweights=weights)))
    error = (1 - rho**2) / np.sqrt(ess - 1) if ess and ess > 1 else np.nan
    return rho, float(error)


def resampled_counts(counts, total, ess, rng):
    """One resampling of a histogram of ``total`` (weighted) draws worth
    ``ess`` independent ones: each bin's effective count is redrawn from a
    Poisson law and scaled back. It costs the same whatever the number of
    draws, and widens with the autocorrelation or the spread of the weights."""
    factor = ess / total if total > 0 else 1.0
    return rng.poisson(np.clip(counts * factor, 0, None)) / factor
