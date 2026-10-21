import numpy as np
import pandas as pd

from plotipus.kinds import line
from plotipus.legacy import translate
from plotipus.transforms import bin_reduce, reduction_bins


def _events():
    rng = np.random.default_rng(1)
    hits = rng.integers(1, 12, 500)
    energy = 2.0 * hits + rng.normal(0, 1, 500)
    return pd.DataFrame([{"Hits": hits, "Charge": energy * 3.0, "Energy": energy, "Config": "a", "Name": "b"}])


def test_bin_reduce():
    x = np.array([0, 0, 1, 1, 2])
    edges, centres = reduction_bins(x)
    assert list(centres) == [0, 1, 2]
    assert list(bin_reduce(x, np.array([1, 3, 5, 7, 9]), edges, "mean")) == [2, 6, 9]
    assert list(bin_reduce(x, np.array([1, 3, 5, 7, 9]), edges, "sum", cumulative=True)) == [25, 21, 9]


def test_binned_estimator(make_project):
    out = make_project({"Events": _events()})
    outputs = line.main(["--datafile", "Events", "-x", "Hits", "-y", "Energy", "--binned", "--estimator", "mean"])
    assert outputs == ["events_hits_energy_mean_scatter.png"]
    assert (out / outputs[0]).exists()


def test_binned_box(make_project):
    out = make_project({"Events": _events()})
    outputs = line.main(["--datafile", "Events", "-x", "Hits", "-y", "Energy", "--binned", "--plot_type", "box"])
    assert outputs[0].endswith("_box.png") and (out / outputs[0]).exists()


def test_panels_compact(make_project):
    out = make_project({"Events": _events()})
    outputs = line.main(["--datafile", "Events", "-y", "Energy", "--binned", "--panels", "Hits", "Charge",
                         "--panel_rangex", "0", "12", "0", "80", "--compact", "--panel_vertical", "5", "none",
                         "--plot_type", "step"])
    assert (out / outputs[0]).exists()


def test_legacy_reduction_translation():
    kind, args = translate(["scripts/script_compare_reduction.py", "--datafile", "E", "-x", "Hits", "-y", "Energy",
                            "--boxplot", "--operation", "sum"])
    assert kind == "line" and "--binned" in args
    assert args[args.index("--plot_type") + 1] == "box"
    assert args[args.index("--estimator") + 1] == "sum"
