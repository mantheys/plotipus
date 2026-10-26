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


# --- Scalar cells, handles and tick labels (T08) -----------------------------------------


def _capture():
    from plotipus import registry

    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    return figures


def _importance(features):
    rng = np.random.default_rng(4)
    return pd.DataFrame({"Feature": features, "Importance": rng.uniform(0.1, 0.4, len(features)),
                         "Model": "BDT"})


def test_scalar_cells_render_one_bar_each(make_project):
    """B07b: one scalar per row is taken as already integrated (no crash, no --integrate_over)."""
    figures = _capture()
    frame = _importance(["pt", "eta", "phi", "mass", "nhits", "chi2"])
    make_project({"Importance": frame})
    cat.main(["--datafile", "Importance", "-x", "Feature", "-y", "Importance", "--hue", "Model", "--kind", "bar"])
    ax = figures[-1].axes[0]
    heights = [p.get_height() for p in ax.patches]
    assert np.allclose(heights, frame["Importance"])
    assert ax.get_ylabel() == "Importance"


def test_scalar_cell_error():
    class Args:
        y = "Counts"
        integrate_over = None
        integral_mode = "integrate"
        integration_range = None
        errory = True
        multiply = 2.0

    assert cat.integrate_row(pd.Series({"Counts": 3.0, "CountsError": 0.5}), Args) == (6.0, 1.0)


def test_point_and_line_legend_handles(make_project):
    figures = _capture()
    make_project({"Cutflow": _frame()})
    for kind in ("point", "line"):
        cat.main(["--datafile", "Cutflow", "-x", "Stage", "-y", "Counts", "--hue", "Component",
                  "--integrate_over", "Energy", "--kind", kind])
    point, line = (fig.axes[0].get_legend().legend_handles for fig in figures)
    assert all(h.get_linestyle() == "None" and h.get_marker() not in (None, "None", "") for h in point)
    assert all(h.get_linestyle() == "-" and h.get_marker() not in (None, "None", "") for h in line)


def test_tick_labels_rotate_only_when_they_overlap(make_project):
    figures = _capture()
    long = [f"a rather long feature name {i}" for i in range(12)]
    make_project({"Short": _importance(["pt", "eta"]), "Long": _importance(long)})
    cat.main(["--datafile", "Short", "-x", "Feature", "-y", "Importance", "--hue", "Model", "--kind", "bar"])
    cat.main(["--datafile", "Long", "-x", "Feature", "-y", "Importance", "--hue", "Model", "--kind", "bar"])
    cat.main(["--datafile", "Short", "-x", "Feature", "-y", "Importance", "--hue", "Model", "--kind", "bar",
              "--xtick_rotation", "20", "--output_suffix", "forced.png"])
    rotations = [{t.get_rotation() for t in fig.axes[0].get_xticklabels() if t.get_text()} for fig in figures]
    # Long labels: 30 degrees, or 90 when the font is too large for 30 to clear the tick spacing.
    assert rotations[0] == {0.0} and rotations[1] in ({30.0}, {90.0}) and rotations[2] == {20.0}
    assert not any(gl.get_visible() for gl in figures[0].axes[0].get_ygridlines())  # no kind-specific grid
