"""Write the example data of input/plots/example_scripts.txt (and of the
figures of docs/options.md): Distributions.pkl, and two files derived from
it, the per-config files of the --configs example and Moments.pkl for the
table example.

    python make_data.py          # into input/data
    python make_data.py DIR      # into DIR (the gallery's data)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(1)
out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "input" / "data"
out.mkdir(parents=True, exist_ok=True)


# Distributions: the common distributions of physics, as per-event samples
# (Value, Smeared, Weight) and as prebinned histograms (Bin, Counts) of the
# same events, with the true expectation (Expected) and its pull. One row per
# (distribution, sample); `line --variable_column Distribution --variables ...`
# draws one panel each. "Simulation" has 10x the events of "Data", weighted
# down to the same normalisation. The Gaussian rows also store a Gaussian fit
# and a chi2 scan of its mean and width (MeanScan, SigmaScan, Chi2Scan). The
# "Resonance" rows are a Higgs-like search instead: Data and its two simulated
# components, Background and Signal, each weighted to its expected yield.
def _distributions():
    from scipy import optimize, stats

    landau = getattr(stats, "landau", stats.moyal)
    integer = lambda lo, hi: np.arange(lo, hi + 1.5) - 0.5  # noqa: E731
    positive = np.linspace(0, 12, 49)  # one binning for the positive, skewed shapes, so they overlay bin by bin
    return {
        "Gaussian": (stats.norm(0, 1), np.linspace(-4, 4, 41)),
        "Poisson": (stats.poisson(4), integer(0, 14)),
        "Binomial": (stats.binom(20, 0.3), integer(0, 14)),
        "Exponential": (stats.expon(scale=2), positive),
        "Uniform": (stats.uniform(0, 1), np.linspace(-0.25, 1.25, 31)),
        "Breit-Wigner": (stats.cauchy(91.19, 2.50 / 2), np.linspace(81, 101, 41)),
        "Landau": (landau(2, 0.5), positive),
        "Log-normal": (stats.lognorm(0.5, scale=1.5), positive),
        "Chi-squared": (stats.chi2(3), positive),
    }, stats, optimize


def _chi2_scan(centres, counts, errors, total, width):
    means = np.linspace(-0.12, 0.12, 61)
    sigmas = np.linspace(0.85, 1.10, 61)
    mm, ss = np.meshgrid(means, sigmas)
    keep = errors > 0
    x, c, e = centres[keep], counts[keep], errors[keep]
    model = total * width * np.exp(-0.5 * ((x - mm[..., None]) / ss[..., None]) ** 2) / (ss[..., None] * np.sqrt(2 * np.pi))
    chi2 = (((c - model) / e) ** 2).sum(axis=-1)
    return means, sigmas, chi2 - chi2.min()


distributions, stats, optimize = _distributions()
rows = []
for name, (dist, edges) in distributions.items():
    centres, width = 0.5 * (edges[1:] + edges[:-1]), np.diff(edges)
    spread = min(dist.std(), np.diff(dist.ppf([0.16, 0.84]))[0] / 2)
    for sample, n in (("Data", 2000), ("Simulation", 20000)):
        value = dist.rvs(n, random_state=rng).astype(float)
        smeared = value * rng.normal(1, 0.05, n) + rng.normal(0, 0.1 * spread, n)
        weight = np.full(n, 2000 / n)
        counts = np.histogram(value, edges, weights=weight)[0]
        errors = np.sqrt(np.histogram(value, edges, weights=weight**2)[0])
        if isinstance(dist.dist, stats.rv_discrete):
            expected = 2000 * dist.pmf(np.round(centres))
        else:
            expected = 2000 * np.diff(dist.cdf(edges))
        row = {"Distribution": name, "Sample": sample,
               "Value": value, "Smeared": smeared, "Residual": smeared - value, "Weight": weight,
               "Bin": centres, "Counts": counts, "CountsError": errors, "Expected": expected,
               "Pull": np.divide(counts - expected, errors, out=np.zeros_like(counts), where=errors > 0)}
        if name == "Gaussian":
            keep = errors > 0
            params, cov = optimize.curve_fit(lambda x, a, b, c: a * np.exp(-0.5 * ((x - b) / c) ** 2),
                                             centres[keep], counts[keep], p0=(counts.max(), 0, 1),
                                             sigma=errors[keep], absolute_sigma=True)
            row |= {"FitFunctionLabel": "Gaussian", "Params": params, "ParamsError": np.sqrt(np.diag(cov)),
                    "ParamsLabel": ["A", r"$\mu$", r"$\sigma$"]}
            row["MeanScan"], row["SigmaScan"], row["Chi2Scan"] = _chi2_scan(centres, counts, errors, 2000, width[0])
        rows.append(row)

edges = np.linspace(100, 160, 31)
centres = 0.5 * (edges[1:] + edges[:-1])
components = {"Background": (stats.truncexpon(60 / 30, loc=100, scale=30), 5000),
              "Signal": (stats.norm(125, 2), 300)}
truth = {name: n * np.diff(dist.cdf(edges)) for name, (dist, n) in components.items()}
samples = {"Data": (np.concatenate([dist.rvs(rng.poisson(n), random_state=rng) for dist, n in components.values()]),
                    None, sum(truth.values()))}
for name, (dist, n) in components.items():
    samples[name] = (dist.rvs(10 * n, random_state=rng), 0.1, truth[name])
for sample, (value, w, expected) in samples.items():
    weight = np.full(value.size, 1.0 if w is None else w)
    smeared = value + rng.normal(0, 1.5, value.size)
    counts = np.histogram(value, edges, weights=weight)[0]
    errors = np.sqrt(np.histogram(value, edges, weights=weight**2)[0])
    row = {"Distribution": "Resonance", "Sample": sample, "Value": value, "Smeared": smeared,
           "Residual": smeared - value, "Weight": weight, "Bin": centres, "Counts": counts,
           "CountsError": errors, "Expected": expected,
           "Pull": np.divide(counts - expected, errors, out=np.zeros_like(counts), where=errors > 0)}
    if sample == "Data":
        # A signal + background fit of the data, drawn with its two components.
        model = lambda x, a, mu, sigma, b, tau: (a * np.exp(-0.5 * ((x - mu) / sigma) ** 2)  # noqa: E731
                                                 + b * np.exp(-x / tau))
        params, cov = optimize.curve_fit(model, centres, counts, p0=(100, 125, 2, 5000 * np.exp(100 / 30) / 15, 30),
                                         sigma=np.maximum(errors, 1), absolute_sigma=True)
        row |= {"FitFunction": "gaussian_plus_exponential", "FitFunctionLabel": "Signal + background", "Params": params,
                "ParamsError": np.sqrt(np.diag(cov)),
                "ParamsLabel": ["$A_s$", r"$m$", r"$\sigma$", "$A_b$", r"$\tau$"],
                "ParamsUnit": ["", "GeV", "GeV", "", "GeV"],
                "FitComponents": {"Signal": ["gaussian", [0, 1, 2]], "Background": ["exponential", [3, 4]]}}
    rows.append(row)

# Bivariate Gaussian: correlated (X, Y) samples for 2D histograms and their sigma regions.
cov = [[1.0, 0.9], [0.9, 2.25]]  # sigma_x = 1, sigma_y = 1.5, rho = 0.6
for sample, n in (("Data", 2000), ("Simulation", 20000)):
    xy = rng.multivariate_normal([0, 0], cov, n)
    rows.append({"Distribution": "Bivariate Gaussian", "Sample": sample, "X": xy[:, 0], "Y": xy[:, 1],
                 "Weight": np.full(n, 2000 / n)})
frame = pd.DataFrame(rows)
frame.to_pickle(out / "Distributions.pkl")

# Per-config files ({config}_{name}_{datafile}.pkl) for --configs/--names: the
# prebinned Landau histograms of each sample.
for sample in ("Data", "Simulation"):
    row = frame[(frame.Distribution == "Landau") & (frame.Sample == sample)].iloc[0]
    config = sample.lower()
    pd.DataFrame([{"Bin": row.Bin, "Counts": row.Counts, "CountsError": row.CountsError, "Config": config,
                   "Name": "landau"}]).to_pickle(out / f"{config}_landau_Histogram.pkl")

# Moments: mean and standard deviation of every 1D sample with their errors,
# one row per (distribution, sample, moment), for the table example.
moments = []
for row in frame[frame.Value.notna()].itertuples():
    value = np.asarray(row.Value, dtype=float)
    n, mean, std = value.size, value.mean(), value.std(ddof=1)
    for name, v, e in (("Mean", mean, std / np.sqrt(n)), ("Std", std, std / np.sqrt(2 * (n - 1)))):
        moments.append({"Config": row.Distribution, "Sample": row.Sample, "Variable": name, "Value": v,
                        "ValueError": e})
pd.DataFrame(moments).to_pickle(out / "Moments.pkl")
print(f"Example data written to {out}")
