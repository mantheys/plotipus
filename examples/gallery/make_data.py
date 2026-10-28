"""Write the gallery data into input/data:

- the example data (``../make_data.py``: Distributions and the files
  derived from it);
- the famous-plot data (``../famous``, T24), with the colour and label
  mappings of its style file copied to ``input/famous_mappings.json`` (the
  gallery keeps the default style otherwise);
- the gallery's own themes: ``detector.py`` and ``ml.py``.

    python make_data.py
"""

import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parent
FAMOUS = EXAMPLES / "famous"
sys.path.insert(0, str(HERE))

import detector  # noqa: E402
import ml  # noqa: E402

THEMES = {"detector": detector.GENERATORS, "ml": ml.GENERATORS}


def main(out=None):
    out = Path(out) if out is not None else HERE / "input" / "data"
    out.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    subprocess.run([sys.executable, str(EXAMPLES / "make_data.py"), str(out)], check=True)

    spec = importlib.util.spec_from_file_location("famous_make_data", FAMOUS / "make_data.py")
    famous = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(famous)
    famous.main(out=out)
    mappings = json.loads((FAMOUS / "style.json").read_text()).get("mappings", {})
    (HERE / "input" / "famous_mappings.json").write_text(json.dumps({"mappings": mappings}, indent=1) + "\n")

    written = ["Probes", "PowerSpectrum"]
    _probes(out)
    _power_spectrum(out, np.random.default_rng(2018))
    for theme, generators in THEMES.items():
        rng = np.random.default_rng(sum(map(ord, theme)))
        for generator in generators.values():
            for name, frame in generator(rng).items():
                frame.to_pickle(out / f"{name}.pkl")
                written.append(name)
    print(f"Gallery data written to {out} ({len(written)} gallery datasets) in {time.perf_counter() - start:.1f} s")


def _probes(out):
    """G8: several datasets in one file, told apart by the ``Probe`` column.
    The SN and CMB Delta chi^2 maps of the famous F10 (``SN``/``CMB``
    ``_Riess1998_OmegaContours``), and a synthetic BAO map: an illustrative
    ellipse tight in Omega_M (0.3 +- 0.03), loose along Omega_Lambda."""
    import pandas as pd

    frames = [pd.read_pickle(out / f"{probe}_Riess1998_OmegaContours.pkl").assign(Probe=probe)
              for probe in ("SN", "CMB")]
    omega_m, omega_lambda = frames[0]["OmegaM"].iloc[0], frames[0]["OmegaLambda"].iloc[0]
    om, ol = np.meshgrid(omega_m, omega_lambda)
    bao = ((om - 0.3 - 0.05 * (ol - 0.7)) / 0.03) ** 2 + ((ol - 0.7) / 0.6) ** 2
    frames.append(frames[0].assign(Probe="BAO", DeltaChi2=[bao.astype(np.float32)]))
    pd.concat(frames, ignore_index=True).assign(Config="Probes").to_pickle(out / "Probes.pkl")


def _power_spectrum(out, rng):
    """H7: a synthetic CMB temperature power spectrum D_l (muK^2) over
    l = 2..2500, shaped like Planck's (a plateau, then acoustic peaks near
    l = 220, 540, 810, ... damped at high l) but not fitted to it: the
    points scatter by cosmic variance, sqrt(2/(2l+1)) D_l, unbinned below
    l = 30 and in bins of 30 above (errors / sqrt(30)). Rows: ``Series``
    (Data, Model)."""
    import pandas as pd

    def model(ell):
        peaks = sum(a * np.exp(-0.5 * ((ell - c) / w) ** 2)
                    for a, c, w in ((4700, 220, 75), (1900, 540, 90), (1850, 810, 95), (900, 1130, 110),
                                    (650, 1430, 120), (300, 1740, 130)))
        return (1000 * np.exp(-ell / 400) + 600 + peaks) * np.exp(-(ell / 2100) ** 2)

    low = np.arange(2, 30, dtype=float)
    high = np.arange(30, 2500, 30, dtype=float) + 15
    ell = np.concatenate([low, high])
    sigma = model(ell) * np.sqrt(2 / (2 * ell + 1)) / np.where(ell < 30, 1, np.sqrt(30))
    data = model(ell) + rng.normal(0, sigma)
    curve = np.unique(np.concatenate([np.geomspace(2, 30, 60), np.linspace(30, 2500, 500)]))
    pd.DataFrame([{"Series": "Data", "Multipole": ell, "Dl": data, "DlError": sigma},
                  {"Series": "Model", "Multipole": curve, "Dl": model(curve)}]).to_pickle(out / "PowerSpectrum.pkl")


if __name__ == "__main__":
    main()
