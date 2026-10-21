import numpy as np
import pandas as pd

from plotipus.kinds import hist
from plotipus.legacy import translate

from _hcs_project import make_project


def _frame():
    rng = np.random.default_rng(1)
    return pd.DataFrame({
        "Sample": ["a", "b"],
        "Variable": ["E", "E"],
        "True": [rng.normal(10, 1, 500), rng.normal(12, 1, 500)],
        "Reco": [rng.normal(10, 1, 500), rng.normal(12, 1, 500)],
    })


def test_hist_single_and_combined(tmp_path, monkeypatch):
    out = make_project(tmp_path, monkeypatch, {"Energies": _frame()})
    hist.main(["--datafile", "Energies", "-x", "True", "--hue", "Sample", "--bins", "20"])
    hist.main(["--datafile", "Energies", "-x", "True", "Reco", "--hist_combine", "relative",
               "--hue", "Sample", "--density", "-v", "E", "--panel_vertical", "0"])
    names = sorted(p.name for p in out.glob("*.png"))
    assert names == ["energies_e_sample_relative_hist.png", "energies_sample_hist.png"], names


def test_hist_combine_values():
    class Args:
        x = ["a", "b"]
        hist_combine = "subtract"

    frame = pd.DataFrame({"a": [np.array([3.0, 5.0])], "b": [np.array([1.0, 1.0])]})
    assert np.allclose(hist.combined_values(frame, Args), [2.0, 4.0])


def test_hist_legacy_translation():
    kind, args = translate(["scripts/script_compare_hist1d.py", "--datafile", "D", "-x", "A", "-i", "C", "--labely", "Counts"])
    assert kind == "hist"
    assert "--hist_combine" in args and args[args.index("--output_suffix") + 1] == "hist1d.png"


def test_plugin_argument_and_figure_hook(tmp_path, monkeypatch):
    from plotipus import registry

    seen = []
    registry.add_argument("--stamp", type=str, default=None)
    registry.add_figure_hook(lambda fig, args: seen.append((len(fig.axes), args.stamp)))
    try:
        out = make_project(tmp_path, monkeypatch, {"Energies": _frame()})
        hist.main(["--datafile", "Energies", "-x", "True", "--hue", "Sample", "--stamp", "Preliminary"])
    finally:
        registry.arguments.clear()
        registry.figure_hooks.clear()
    assert seen == [(1, "Preliminary")]
    assert (out / "energies_sample_hist.png").is_file()
