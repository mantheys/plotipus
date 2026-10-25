import numpy as np
import pandas as pd

from plotipus.kinds import cat
from plotipus.legacy import translate

from _hcs_project import make_project


def _frame():
    rows = []
    for stage in ["raw", "cut1", "cut2"]:
        for component, scale in (("signal", 1.0), ("background", 5.0)):
            rows.append({"Stage": stage, "Component": component, "Energy": np.arange(10.0),
                         "Counts": np.full(10, scale), "CountsError": np.full(10, 0.1)})
    return pd.DataFrame(rows)


def test_cat_kinds(tmp_path, monkeypatch):
    out = make_project(tmp_path, monkeypatch, {"Cutflow": _frame()})
    for kind in ("line", "point", "bar"):
        cat.main(["--datafile", "Cutflow", "-x", "Stage", "-y", "Counts", "--hue", "Component",
                  "--integrate_over", "Energy", "--kind", kind, "--errory", "--output_suffix", f"{kind}.png"])
    assert len(list(out.glob("*.png"))) == 3


def test_integrate_row():
    class Args:
        y = "Counts"
        integrate_over = "Energy"
        integral_mode = "integrate"
        integration_range = (2, 5)
        errory = True
        multiply = None

    row = _frame().iloc[0]
    value, error = cat.integrate_row(row, Args)
    assert value == 4.0 and np.isclose(error, 0.2)


def test_cat_legacy_translation():
    kind, args = translate(["scripts/script_compare_integral.py", "--datafile", "D", "-x", "S", "-y", "C", "-i", "K",
                            "--plot_type", "scatter"])
    assert kind == "cat" and args[args.index("--kind") + 1] == "point"


def test_bar_legend_shows_patches(make_project):
    """--kind bar: the legend shows filled patches, not line-and-marker handles."""
    from matplotlib.patches import Patch

    from plotipus import registry

    x = np.arange(0.5, 5, 1.0)
    frame = pd.DataFrame([{"Stage": stage, "Sample": sample, "Counts": k * np.ones_like(x), "Energy": x}
                          for stage in ("Raw", "Cut") for k, sample in ((1, "A"), (2, "B"))])
    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    make_project({"Spectra": frame})
    cat.main(["--datafile", "Spectra", "-x", "Stage", "-y", "Counts", "--hue", "Sample", "--kind", "bar"])
    handles = figures[-1].axes[0].get_legend().legend_handles
    assert len(handles) == 2 and all(isinstance(h, Patch) for h in handles)
