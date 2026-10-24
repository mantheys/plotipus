"""Toy pickles for the bug reproductions and the gap-analysis probes.

    cd docs/design/repro && python make_data.py && plotipus run repro

Writes input/data/*.pkl next to this file (plus the examples' own pickles,
which some reproductions use).
"""

from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
D = HERE / "input" / "data"
D.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(3)

# The examples' pickles (Spectra, Efficiency, Events, Contour, Summary).
examples = HERE.parents[2] / "examples" / "make_data.py"
exec(compile(examples.read_text(), str(examples), "exec"), {"__file__": str(HERE / "make_data.py"), "__name__": "__main__"})

# Twelve hue values (colour cycle wrap-around).
x = np.linspace(0, 10, 50)
pd.DataFrame([{"X": x, "Y": np.sin(x + 0.4 * i) + 0.3 * i, "Run": f"run{i:02d}", "Variable": "V"}
              for i in range(12)]).to_pickle(D / "ManyHue.pkl")
# A flat distribution (histogram edge bins).
pd.DataFrame([{"E": rng.uniform(0, 10, 20000), "Sample": "flat", "Variable": "V"}]).to_pickle(D / "Flat.pkl")

# Binned data/MC (one row per sample, Poisson data)
m = np.arange(100.5, 160, 1.0)
bkg = 3000*np.exp(-(m-100)/40); bkg2 = 400*np.exp(-(m-100)/25); sig = 120*np.exp(-0.5*((m-125)/1.6)**2)
data = rng.poisson(bkg+bkg2+sig).astype(float)
rows = [dict(Mass=m, Counts=c, CountsError=np.sqrt(c), Sample=s, Variable="Mass") for s, c in
        (("data", data), ("bkg_a", bkg), ("bkg_b", bkg2), ("signal", sig))]
pd.DataFrame(rows).to_pickle(D / "Spectrum.pkl")
# Stored gaussian fit
x = np.linspace(-5, 5, 41); y = rng.poisson(200*np.exp(-0.5*(x/1.2)**2)).astype(float)
pd.DataFrame([dict(X=x, Counts=y, CountsError=np.sqrt(np.maximum(y,1)), FitFunctionLabel="Gaussian", Params=[200,0,1.2],
    ParamsError=[5,0.02,0.03], ParamsLabel=["A","mu","sigma"], Sample="fit", Variable="Fit")]).to_pickle(D / "Fit.pkl")
# Brazil: median, +-1, +-2 as columns, observed
mh = np.linspace(110, 600, 60); med = 0.6 + 0.002*(mh-110)
pd.DataFrame([dict(Mass=mh, Limit=med, LimitError=0.3*med, Kind="expected", Variable="L"),
              dict(Mass=mh, Limit=med*(1+0.15*np.sin(mh/20)), Kind="observed", Variable="L")]).to_pickle(D / "Limits.pkl")
# Likelihood scan
mu = np.linspace(0, 2, 81)
pd.DataFrame([dict(Mu=mu, DeltaNLL=((mu-1.0)/0.3)**2, Kind="obs", Variable="Scan")]).to_pickle(D / "Scan.pkl")
# ROC / PR / calibration / learning curves as precomputed series
fpr = np.linspace(0,1,101)
pd.DataFrame([dict(FPR=fpr, TPR=fpr**(1/k), Model=n, Variable="ROC") for n, k in (("BDT",4),("DNN",6),("cut",2))]).to_pickle(D / "ROC.pkl")
n = np.array([100,300,1000,3000,10000,30000.])
pd.DataFrame([dict(TrainSize=n, Score=s0-0.3/np.sqrt(n/100), ScoreError=0.05/np.sqrt(n/100), Split=sp, Variable="LC") for sp, s0 in (("train",0.99),("validation",0.9))]).to_pickle(D / "Learning.pkl")
# Categorical scalars: feature importance (one scalar per row)
feats = ["pt","eta","phi","mass","nhits","chi2"]
pd.DataFrame([dict(Feature=f, Importance=float(v), Model="BDT", Variable="FI") for f, v in zip(feats, rng.uniform(0.02,0.4,6))]).to_pickle(D / "Importance.pkl")
# Per-event arrays for distributions & relations
ev = []
for s, mu0 in (("A",0.0),("B",1.0),("C",2.5)):
    xx = rng.normal(mu0, 1, 3000); ev.append(dict(Xv=xx, Yv=0.5*xx+rng.normal(0,0.7,3000), Group=s, Variable="Ev"))
pd.DataFrame(ev).to_pickle(D / "Ev.pkl")
# Confusion matrix as grid
cm = np.array([[90,7,3],[10,80,10],[2,8,90.]])
pd.DataFrame([dict(Pred=np.arange(3.), True_=np.arange(3.), Frac=cm, Variable="CM")]).to_pickle(D / "Confusion.pkl")
# Small multiples: 4 variables of curves
pd.DataFrame([dict(T=x, V=np.sin(x*(i+1)/3), Run=r, Variable=f"panel{i}") for i in range(4) for r, x in (("a", np.linspace(0,10,50)), ("b", np.linspace(0,10,50)+0.0))]).to_pickle(D / "Multi.pkl")
print(f"Repro data written to {D}")
