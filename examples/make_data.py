"""Write the toy pickles used by input/plots/example_scripts.txt."""

from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(1)
out = Path(__file__).parent / "input" / "data"
out.mkdir(parents=True, exist_ok=True)
energy = np.arange(0.5, 30, 1.0)

# Spectra: one row per (sample, stage) holding a whole binned series.
rows = []
for sample, (norm, slope) in {"signal": (1e3, 6.0), "background": (5e3, 2.5), "calibration": (2e2, 10.0)}.items():
    for stage, keep in (("Raw", 1.0), ("Selected", 0.6)):
        counts = keep * norm * np.exp(-energy / slope)
        rows.append({"Energy": energy, "Counts": counts, "CountsError": np.sqrt(counts), "Sample": sample,
                     "Stage": stage, "Variable": "Energy", "CountsUnit": "events / MeV",
                     "Significance": counts / np.sqrt(5e3 * np.exp(-energy / 2.5))})
pd.DataFrame(rows).to_pickle(out / "Spectra.pkl")

# Per-config efficiency curves (files named {config}_{name}_{datafile}.pkl).
for config, scale in (("small", 0.8), ("large", 0.95)):
    eff = 100 * scale * (1 - np.exp(-energy / 4))
    pd.DataFrame([{"Values": energy, "Efficiency": eff, "EfficiencyError": np.full_like(energy, 2.0),
                   "Config": config, "Name": "signal", "Variable": "Efficiency"}]).to_pickle(
        out / f"{config}_signal_Efficiency.pkl")

# Events: raw per-event arrays (for hist, map and the binned estimator).
events = []
for sample, (mu, sigma) in {"signal": (10, 3), "background": (5, 4)}.items():
    true = rng.uniform(1, 30, 4000)
    reco = true * rng.normal(1, 0.1, true.size) + rng.normal(0, 0.5, true.size)
    events.append({"TrueEnergy": true, "RecoEnergy": reco, "Resolution": (reco - true) / true,
                   "Hits": rng.poisson(true * 3), "Sample": sample, "Variable": "Energy"})
pd.DataFrame(events).to_pickle(out / "Events.pkl")

# Grid: a chi2 map for contours.
x = np.linspace(0, 1, 60)
y = np.linspace(0, 2, 80)
xx, yy = np.meshgrid(x, y)
chi2 = ((xx - 0.4) / 0.08) ** 2 + ((yy - 1.1) / 0.2) ** 2 + (xx - 0.4) * (yy - 1.1) * 20
pd.DataFrame([{"XGrid": x, "YGrid": y, "ZGrid": chi2, "Config": "small", "Name": "signal",
               "Variable": "Map"}]).to_pickle(out / "Contour.pkl")

# Summary table input: one scalar per (config, variable).
pd.DataFrame([{"Config": c, "Variable": v, "Value": val, "ValueError": 0.05 * val}
              for c, s in (("small", 1.0), ("large", 1.3))
              for v, val in (("Efficiency", 82.0 * s), ("Purity", 61.0 * s), ("Rate", 1.2e3 * s))]).to_pickle(
    out / "Summary.pkl")
print(f"Example data written to {out}")
