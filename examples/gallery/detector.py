"""Detector theme of the gallery: a toy calorimeter test beam (synthetic,
seeded).

- ``Showers``: per-event arrays for electrons, pions and muons fired at
  5-100 GeV: true and reconstructed energy, the response reco/true and the
  relative residual, the number of hits and a trigger prescale weight.
  Electrons have a stochastic term of 10%/sqrt(E) and a constant term of 1%,
  pions 50%/sqrt(E) and 3% at a response of 0.85 (non-compensation, rising
  slowly with energy); muons leave a minimum-ionising deposit (Landau-like,
  near 2 GeV) whatever their energy. Below 20 GeV, electrons and pions come
  from a trigger prescaled by 5: four in five are dropped and the rest carry
  weight 5.
- ``TriggerEfficiency``: the turn-on curves of two trigger levels per
  particle, as pass/total counts per energy bin with the efficiency in
  percent and its Clopper-Pearson interval (``EfficiencyError+/-``).
- ``Yields``: the reconstructed-energy spectra of each particle after
  preselection and after the final selection (for a before/after chart).
- ``Summary``: efficiency, purity and rate of two detector layouts, with
  errors (for the result tables).
"""

import numpy as np
import pandas as pd
from scipy import stats

PARTICLES = ("electron", "pion", "muon")


def _response(particle, true, rng):
    if particle == "electron":
        resolution = np.hypot(0.10 / np.sqrt(true), 0.01)
        return rng.normal(1.0, resolution)
    if particle == "pion":
        resolution = np.hypot(0.50 / np.sqrt(true), 0.03)
        return rng.normal(0.85 + 0.03 * np.log10(true / 5), resolution)
    deposit = stats.moyal.rvs(loc=2.0, scale=0.15, size=true.size, random_state=rng)
    return deposit / true


def showers(rng):
    rows = []
    for particle, n in (("electron", 20000), ("pion", 20000), ("muon", 8000)):
        true = np.exp(rng.uniform(np.log(5), np.log(100), n))
        if particle != "muon":
            prescaled = true < 20
            true = true[~prescaled | (rng.random(n) < 0.2)]
        response = _response(particle, true, rng)
        reco = true * response
        hits = rng.poisson((3.0 if particle != "muon" else 0.4) * reco + 5)
        weight = np.where(true < 20, 5.0, 1.0) if particle != "muon" else np.ones(true.size)
        rows.append({"Particle": particle, "TrueEnergy": true, "RecoEnergy": reco, "Response": response,
                     "Residual": response - 1, "Hits": hits, "Weight": weight})
    return {"Showers": pd.DataFrame(rows)}


def _clopper_pearson(passed, total, level=0.6827):
    alpha = 1 - level
    low = np.where(passed > 0, stats.beta.ppf(alpha / 2, passed, total - passed + 1), 0.0)
    high = np.where(passed < total, stats.beta.ppf(1 - alpha / 2, passed + 1, total - passed), 1.0)
    return low, high


def trigger_efficiency(rng):
    edges = np.array([2, 4, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 70, 100], dtype=float)
    centres = 0.5 * (edges[1:] + edges[:-1])
    rows = []
    for level, (threshold, width, plateau) in {"L1": (10, 2.0, 0.99), "HLT": (18, 3.5, 0.97)}.items():
        for particle, shift in (("electron", 0.0), ("pion", 4.0)):
            total = rng.poisson(300 * np.exp(-centres / 30)) + 8
            probability = plateau * stats.norm.cdf(centres, threshold + shift, width + shift / 2)
            passed = rng.binomial(total, probability)
            efficiency = passed / total
            low, high = _clopper_pearson(passed, total)
            rows.append({"Config": level, "Name": "trigger", "Particle": particle, "Energy": centres,
                         "Passed": passed, "Total": total, "Efficiency": 100 * efficiency,
                         "EfficiencyError+": 100 * (high - efficiency), "EfficiencyError-": 100 * (efficiency - low)})
    return {"TriggerEfficiency": pd.DataFrame(rows)}


def yields(rng):
    edges = np.linspace(0, 100, 21)
    centres = 0.5 * (edges[1:] + edges[:-1])
    rows = []
    for particle, total, kept in (("electron", 52000, 0.82), ("pion", 61000, 0.35), ("muon", 9000, 0.12)):
        shape = np.exp(-centres / (35 if particle != "muon" else 8))
        shape /= shape.sum()
        for stage, fraction in (("Preselection", 1.0), ("Final selection", kept)):
            rows.append({"Particle": particle, "Stage": stage, "Energy": centres,
                         "Counts": rng.poisson(total * fraction * shape).astype(float)})
    return {"Yields": pd.DataFrame(rows)}


def summary(rng):
    rows = []
    for layout, scale in (("Baseline", 1.0), ("Upgrade", 1.06)):
        for variable, value, error in (("Efficiency", 0.874, 0.004), ("Purity", 0.912, 0.006),
                                       ("Rate", 1.32e3, 40.0)):
            if variable == "Rate":
                measured = value / scale + rng.normal(0, error / 3)
            else:
                measured = min(value * scale + rng.normal(0, error / 3), 0.999)
            rows.append({"Config": layout, "Variable": variable, "Value": measured, "ValueError": error})
    return {"Summary": pd.DataFrame(rows)}


GENERATORS = {"showers": showers, "trigger_efficiency": trigger_efficiency, "yields": yields, "summary": summary}
