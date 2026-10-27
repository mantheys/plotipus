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


def test_data_hue_points_over_bars(make_project):
    """--data_hue: data as ink points with errors (first in the legend), the rest as bars."""
    from matplotlib.colors import to_hex
    from matplotlib.container import BarContainer, ErrorbarContainer

    from plotipus import registry, style

    frame = _frame().replace({"Component": {"signal": "data"}})
    make_project({"Cutflow": frame})
    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    cat.main(["--datafile", "Cutflow", "-x", "Stage", "-y", "Counts", "--hue", "Component", "--integrate_over",
              "Energy", "--kind", "bar", "--data_hue", "data"])
    ax = figures[0].axes[0]
    bars = [c for c in ax.containers if isinstance(c, BarContainer)]
    points = [c for c in ax.containers if isinstance(c, ErrorbarContainer)]
    assert len(bars) == 1 and len(points) == 1
    assert [p.get_x() + p.get_width() / 2 for p in bars[0]] == [0.0, 1.0, 2.0]  # one model: bars centred
    assert to_hex(points[0].lines[0].get_color()) == to_hex(style.role("ink"))
    assert points[0].has_yerr  # data shows its errors without --errory
    assert [t.get_text() for t in ax.get_legend().get_texts()] == ["data", "background"]


def _yields():
    rows = []
    for region, (data, background, signal) in {"low": (105, 100, 1), "peak": (60, 40, 15), "high": (52, 50, 1)}.items():
        for sample, value in (("Data", data), ("Background", background), ("Signal", signal)):
            rows.append({"Region": region, "Sample": sample, "Counts": float(value),
                         "CountsError": float(np.sqrt(value))})
    return pd.DataFrame(rows)


def test_stacked_bars_with_data_and_error_band(make_project):
    """--stacked: one stack per category, data points on top, a hatched band of the total's error."""
    from matplotlib.container import BarContainer, ErrorbarContainer
    from matplotlib.patches import Rectangle

    from plotipus import style

    figures = _capture()
    make_project({"Yields": _yields()})
    cat.main(["--datafile", "Yields", "-x", "Region", "-y", "Counts", "--hue", "Sample", "--kind", "bar",
              "--stacked", "--data_hue", "Data", "--errory"])
    ax = figures[0].axes[0]
    background, signal = [c for c in ax.containers if isinstance(c, BarContainer)]
    assert [p.get_y() for p in signal] == [p.get_height() for p in background]  # signal on the background
    assert all(p.get_width() == 0.8 for p in signal)
    totals = [b.get_height() + s.get_height() for b, s in zip(background, signal)]
    bands = [p for p in ax.patches if isinstance(p, Rectangle) and p.get_hatch()]
    assert len(bands) == 3
    expected = [np.hypot(np.sqrt(b), np.sqrt(s)) for b, s in ((100, 1), (40, 15), (50, 1))]
    assert np.allclose([p.get_height() / 2 for p in bands], expected)
    assert np.allclose([p.get_y() + p.get_height() / 2 for p in bands], totals)
    assert len([c for c in ax.containers if isinstance(c, ErrorbarContainer)]) == 1
    assert [t.get_text() for t in ax.get_legend().get_texts()] == ["Data", "Signal", "Background",
                                                                    style.stack_error["label"]]


def test_bar_errors_are_bands_not_error_bars(make_project):
    from matplotlib.container import ErrorbarContainer
    from matplotlib.patches import Rectangle

    figures = _capture()
    make_project({"Cutflow": _frame()})
    cat.main(["--datafile", "Cutflow", "-x", "Stage", "-y", "Counts", "--hue", "Component", "--integrate_over",
              "Energy", "--kind", "bar", "--errory"])
    ax = figures[0].axes[0]
    assert not [c for c in ax.containers if isinstance(c, ErrorbarContainer)]
    assert len([p for p in ax.patches if isinstance(p, Rectangle) and p.get_hatch()]) == 6


def test_points_dodge_side_by_side(make_project):
    """--kind point: data and each hue value get their own slot within a category."""
    from matplotlib.container import ErrorbarContainer

    figures = _capture()
    make_project({"Yields": _yields()})
    cat.main(["--datafile", "Yields", "-x", "Region", "-y", "Counts", "--hue", "Sample", "--kind", "point",
              "--data_hue", "Data", "--errory"])
    ax = figures[0].axes[0]
    first = sorted(c.lines[0].get_xdata()[0] for c in ax.containers if isinstance(c, ErrorbarContainer))
    assert len(first) == 3 and first[0] < first[1] < first[2] and np.isclose(np.mean(first), 0.0)
    assert first[2] - first[0] < 0.8  # all within the category


# --- Orientation, sorting and lollipops (T22.1) ------------------------------------------


def test_orient_h_puts_categories_on_y_first_on_top(make_project):
    """D5: --orient h draws horizontal bars, the categories down the y axis with the first on top and
    the value label on x."""
    figures = _capture()
    frame = _importance(["pt", "eta", "phi"])
    make_project({"Importance": frame})
    cat.main(["--datafile", "Importance", "-x", "Feature", "-y", "Importance", "--hue", "Model", "--kind", "bar",
              "--orient", "h"])
    ax = figures[-1].axes[0]
    assert np.allclose([p.get_width() for p in ax.patches], frame["Importance"])
    assert [round(p.get_y() + p.get_height() / 2, 6) for p in ax.patches] == [0.0, 1.0, 2.0]
    assert [t.get_text() for t in ax.get_yticklabels()] == ["pt", "eta", "phi"]
    bottom, top = ax.get_ylim()
    assert bottom > top  # position 0 (the first category) at the top
    assert ax.get_xlabel() == "Importance" and ax.get_ylabel() == "Feature"


def test_sort_orders_categories_by_total(make_project):
    """--sort desc: largest total first (on top with --orient h); asc the reverse."""
    figures = _capture()
    frame = pd.DataFrame({"Feature": ["a", "b", "c"], "Importance": [0.1, 0.5, 0.3], "Model": "BDT"})
    make_project({"Importance": frame})
    for order in ("desc", "asc"):
        cat.main(["--datafile", "Importance", "-x", "Feature", "-y", "Importance", "--hue", "Model", "--kind", "bar",
                  "--orient", "h", "--sort", order, "--output_suffix", f"{order}.png"])
    desc, asc = ([t.get_text() for t in fig.axes[0].get_yticklabels()] for fig in figures)
    assert desc == ["b", "c", "a"] and asc == ["a", "c", "b"]
    widths = [p.get_width() for p in figures[0].axes[0].patches]
    assert widths == sorted(widths, reverse=True)


def test_sort_sums_every_series(make_project):
    """The sort key is the category's total over every hue value, not the first series."""
    figures = _capture()
    make_project({"Yields": _yields()})
    cat.main(["--datafile", "Yields", "-x", "Region", "-y", "Counts", "--hue", "Sample", "--kind", "bar",
              "--sort", "asc"])
    # Totals: low 206, peak 115, high 103.
    assert [t.get_text() for t in figures[0].axes[0].get_xticklabels()] == ["high", "peak", "low"]


def test_lollipop_stems_end_at_the_values_with_errors(make_project):
    """D7: --kind lollipop draws a stem from zero to each value and the value as a marker with its
    error bar; the legend shows markers only."""
    from matplotlib.collections import LineCollection
    from matplotlib.container import ErrorbarContainer

    figures = _capture()
    make_project({"Yields": _yields()})
    cat.main(["--datafile", "Yields", "-x", "Region", "-y", "Counts", "--hue", "Sample", "--kind", "lollipop",
              "--select", "Sample", "-s", "Background", "--errory"])
    ax = figures[0].axes[0]
    # Stems start at zero; the error bars (also line collections) at value - error.
    stems = [c for c in ax.collections if isinstance(c, LineCollection)
             and all(s[0][1] == 0.0 for s in c.get_segments())]
    assert len(stems) == 1
    segments = stems[0].get_segments()
    assert [s[1][1] for s in segments] == [100.0, 40.0, 50.0]
    points = [c for c in ax.containers if isinstance(c, ErrorbarContainer)]
    assert len(points) == 1 and points[0].has_yerr
    assert np.allclose(points[0].lines[0].get_ydata(), [100.0, 40.0, 50.0])
    handle = ax.get_legend().legend_handles[0] if ax.get_legend() else None
    assert handle is None or handle.get_linestyle() == "None"


def test_lollipop_orient_h_and_dodged_series(make_project):
    """Horizontal lollipops: stems along x; several series dodge within the category."""
    from matplotlib.collections import LineCollection

    figures = _capture()
    make_project({"Yields": _yields()})
    cat.main(["--datafile", "Yields", "-x", "Region", "-y", "Counts", "--hue", "Sample", "--kind", "lollipop",
              "--orient", "h"])
    ax = figures[0].axes[0]
    stems = [c for c in ax.collections if isinstance(c, LineCollection) and len(c.get_segments()) == 3]
    assert len(stems) == 3
    for collection in stems:
        for (x0, y0), (x1, y1) in collection.get_segments():
            assert x0 == 0.0 and y0 == y1  # horizontal stems from zero
    first = sorted(c.get_segments()[0][0][1] for c in stems)
    assert first[0] < first[1] < first[2] and np.isclose(np.mean(first), 0.0)


def test_stacked_horizontal_bars_and_band(make_project):
    """--stacked with --orient h: stacks grow along x; the total's error band is horizontal."""
    from matplotlib.container import BarContainer
    from matplotlib.patches import Rectangle

    figures = _capture()
    make_project({"Yields": _yields()})
    cat.main(["--datafile", "Yields", "-x", "Region", "-y", "Counts", "--hue", "Sample", "--kind", "bar",
              "--stacked", "--data_hue", "Data", "--errory", "--orient", "h"])
    ax = figures[0].axes[0]
    background, signal = [c for c in ax.containers if isinstance(c, BarContainer)]
    assert [p.get_x() for p in signal] == [p.get_width() for p in background]
    bands = [p for p in ax.patches if isinstance(p, Rectangle) and p.get_hatch()]
    totals = [b.get_width() + s.get_width() for b, s in zip(background, signal)]
    assert np.allclose([p.get_x() + p.get_width() / 2 for p in bands], totals)
    assert all(np.isclose(p.get_height(), 0.8) for p in bands)


def test_orient_h_reference_lines_are_vertical(make_project):
    figures = _capture()
    make_project({"Importance": _importance(["pt", "eta"])})
    cat.main(["--datafile", "Importance", "-x", "Feature", "-y", "Importance", "--hue", "Model", "--kind", "point",
              "--orient", "h", "--horizontal", "0.2"])
    ax = figures[0].axes[0]
    assert any(np.allclose(line.get_xdata(), [0.2, 0.2]) for line in ax.get_lines())
