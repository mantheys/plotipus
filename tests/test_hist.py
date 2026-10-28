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


# --- Edges, range, overflow and legend (T04) ---------------------------------------------


def _capture():
    from plotipus import registry

    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    return figures


def _stairs(ax):
    """The step outlines (the filled step patches are error bands)."""
    from matplotlib.patches import StepPatch

    return [p for p in ax.patches if isinstance(p, StepPatch) and not p.get_fill()]


def _bands(ax):
    from matplotlib.patches import StepPatch

    return [p for p in ax.patches if isinstance(p, StepPatch) and p.get_fill()]


def test_hist_flat_outline_spans_all_edges(make_project):
    x = np.random.default_rng(2).uniform(0, 10, 20000)
    make_project({"Flat": pd.DataFrame({"E": [x]})})
    figures = _capture()
    hist.main(["--datafile", "Flat", "-x", "E", "--bins", "10"])
    ax = figures[0].axes[0]
    (step,) = _stairs(ax)
    edges = step.get_data().edges
    assert len(edges) == 11
    assert edges[0] == x.min() and edges[-1] == x.max()
    assert np.allclose(np.diff(edges), np.diff(edges)[0])  # outer bins at full width
    assert ax.get_xlim() == (edges[0], edges[-1])
    assert step.get_data().values.sum() == len(x)
    assert ax.get_legend() is None  # no legend for a single series without --hue
    assert ax.get_legend_handles_labels()[1] == []  # and no "None" label


def test_hist_range_spans_every_hue(make_project):
    make_project({"Ev": pd.DataFrame({"Group": ["A", "B"], "X": [np.linspace(0, 1, 100), np.linspace(5, 9, 100)]})})
    figures = _capture()
    hist.main(["--datafile", "Ev", "-x", "X", "--hue", "Group", "--bins", "9"])
    ax = figures[0].axes[0]
    steps = _stairs(ax)
    assert [s.get_label() for s in steps] == ["A", "B"]
    for step in steps:
        assert np.array_equal(step.get_data().edges, steps[0].get_data().edges)  # same edges for every hue
        assert step.get_data().values.sum() == 100  # nothing clipped
    assert steps[0].get_data().edges[[0, -1]].tolist() == [0.0, 9.0]
    assert ax.get_legend() is not None
    assert [t.get_text() for t in ax.get_legend().get_texts()] == ["A", "B"]


def test_hist_flow_show_and_hint(make_project, capsys):
    x = np.array([-5.0, -1.0, 0.5, 1.5, 2.5, 3.5, 7.0, 8.0, 9.0])
    make_project({"D": pd.DataFrame({"X": [x]})})
    figures = _capture()
    hist.main(["--datafile", "D", "-x", "X", "--bins", "4", "--rangex", "0", "4"])
    hist.main(["--datafile", "D", "-x", "X", "--bins", "4", "--rangex", "0", "4", "--flow", "show"])
    hist.main(["--datafile", "D", "-x", "X", "--bins", "4", "--rangex", "0", "4", "--flow", "hint"])
    assert _stairs(figures[0].axes[0])[0].get_data().values.tolist() == [1, 1, 1, 1]
    assert _stairs(figures[1].axes[0])[0].get_data().values.tolist() == [3, 1, 1, 4]  # 2 under, 3 over
    hints = figures[2].axes[0].get_lines()
    assert sorted(line.get_marker() for line in hints) == ["<", ">"]
    assert "5 of 9 entries" in capsys.readouterr().out


def test_hist_flow_show_density_normalises_drawn_counts():
    counts, under, over = hist.histogram(np.array([-1.0, 0.5, 1.5, 3.0]), np.array([0.0, 1.0, 2.0]),
                                         density=True, flow="show")
    assert (under, over) == (1.0, 1.0)
    assert np.isclose(np.sum(counts * 1.0), 1.0) and np.allclose(counts, [0.5, 0.5])


def test_variable_column_panels_hues_of_the_selection(make_project, capsys):
    """Panels from --variable_column; hue values missing from every panel are not looked for."""
    rng = np.random.default_rng(2)
    frame = pd.DataFrame([{"Shape": shape, "Sample": sample, "E": rng.normal(size=200)}
                          for shape, sample in (("A", "data"), ("A", "mc"), ("B", "data"), ("B", "mc"), ("C", "extra"))])
    make_project({"Shapes": frame})
    figures = _capture()
    hist.main(["--datafile", "Shapes", "-x", "E", "--hue", "Sample", "--variable_column", "Shape",
               "--variables", "A", "B"])
    assert len([ax for ax in figures[-1].axes if ax.has_data()]) == 2
    assert "extra" not in capsys.readouterr().out


def test_hist_data_hue_points(tmp_path, monkeypatch):
    from matplotlib.container import ErrorbarContainer

    from plotipus import registry

    out = make_project(tmp_path, monkeypatch, {"Energies": _frame()})
    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    try:
        hist.main(["--datafile", "Energies", "-x", "True", "--hue", "Sample", "--data_hue", "a", "--bins", "20"])
    finally:
        registry.figure_hooks.clear()
    ax = figures[0].axes[0]
    points = [c for c in ax.containers if isinstance(c, ErrorbarContainer)]
    assert len(points) == 1 and len(_stairs(ax)) == 1
    errors = points[0].lines[2][0].get_segments()
    counts = points[0].lines[0].get_ydata()
    from plotipus.intervals import garwood

    low, high = garwood(counts)  # unweighted data: the Poisson (Garwood) interval (T19)
    assert np.allclose([seg[0][1] for seg in errors], low) and np.allclose([seg[1][1] for seg in errors], high)
    assert [t.get_text() for t in ax.get_legend().get_texts()] == ["a", "b"]


def test_histogram_errors_scale_with_density():
    counts, _, _, errors = hist.histogram_with_errors(np.array([0.5, 0.5, 1.5, 1.5]), np.array([0.0, 1.0, 2.0]),
                                                      density=True)
    assert np.allclose(counts, [0.5, 0.5]) and np.allclose(errors, np.sqrt(2) / 4)


def test_hist_hue_cmap_colorbar(make_project):
    import matplotlib
    from matplotlib.colors import to_hex

    rng = np.random.default_rng(3)
    frame = pd.DataFrame({"Run": [1, 2, 4], "X": [rng.normal(m, 1, 200) for m in (0, 1, 2)]})
    make_project({"Runs": frame})
    figures = _capture()
    hist.main(["--datafile", "Runs", "-x", "X", "--hue", "Run", "--hue_cmap", "viridis"])
    fig = figures[0]
    ax = fig.axes[0]
    colors = [to_hex(p.get_edgecolor()) for p in _stairs(ax)]
    cmap = matplotlib.colormaps["viridis"]
    assert colors == [to_hex(cmap(v)) for v in (0.0, 1 / 3, 1.0)]  # numeric runs on a 1-4 scale
    assert ax.get_legend() is None
    assert any(hasattr(a, "_colorbar") for a in fig.axes)


def test_overlay_gaussian_scaled_to_entries(make_project):
    from scipy.stats import norm

    pulls = np.random.default_rng(5).normal(0, 1, 4000)
    make_project({"Pulls": pd.DataFrame([{"Pull": pulls}])})
    figures = _capture()
    hist.main(["--datafile", "Pulls", "-x", "Pull", "--bins", "40", "--overlay_gaussian"])
    ax = figures[0].axes[0]
    (curve,) = [l for l in ax.lines if l.get_label().startswith("$\\mathcal{N}")]
    edges = _stairs(ax)[0].get_data().edges
    peak = norm.pdf(0) * len(pulls) * np.diff(edges).mean()
    assert np.isclose(curve.get_ydata().max(), peak, rtol=0.01)
    assert [t.get_text() for t in ax.get_legend().get_texts()] == ["$\\mathcal{N}(0, 1)$"]
    figures.clear()
    hist.main(["--datafile", "Pulls", "-x", "Pull", "--density", "--overlay_gaussian", "0.5", "2"])
    (curve,) = [l for l in figures[0].axes[0].lines if l.get_label().startswith("$\\mathcal{N}")]
    assert np.isclose(curve.get_ydata().max(), norm.pdf(0, 0, 2), rtol=0.01)
    assert curve.get_label() == "$\\mathcal{N}(0.5, 2)$"


# --- KDE, ECDF, cumulative histograms, rugs and ridgelines (T22.4) ------------------------


def test_kde_curve_unit_area_and_error():
    """A7: the KDE has unit area, and its band is sqrt(f R(K) / (n h)) for a Gaussian kernel."""
    x = np.random.default_rng(2).normal(0, 1, 2000)
    grid = np.linspace(-6, 6, 2001)
    density, error = hist.kde_curve(x, None, grid)
    assert np.isclose(np.trapezoid(density, grid), 1.0, atol=1e-3)
    h = 1.0 * len(x) ** (-1 / 5) * np.std(x, ddof=1)  # Scott's rule in one dimension
    assert np.allclose(error, np.sqrt(density / (2 * np.sqrt(np.pi)) / (len(x) * h)), rtol=1e-2)
    narrow, _ = hist.kde_curve(x, None, grid, bw="0.05")
    assert narrow.max() > density.max()  # --bw in x units: a narrower kernel, a rougher curve


def test_kde_weights_use_the_effective_count():
    x = np.random.default_rng(3).normal(0, 1, 1000)
    grid = np.linspace(-3, 3, 7)
    _, plain = hist.kde_curve(x, None, grid)
    _, weighted = hist.kde_curve(x, np.r_[np.full(500, 3.0), np.ones(500)], grid)
    assert np.all(weighted > plain)  # unequal weights: fewer effective entries, a wider band


def test_ecdf_curve_and_binomial_error():
    points, fraction, error = hist.ecdf_curve(np.array([3.0, 1.0, 2.0, 2.0]), None)
    assert np.allclose(points, [1, 2, 2, 3]) and np.allclose(fraction, [0.25, 0.5, 0.75, 1.0])
    assert np.allclose(error, np.sqrt(fraction * (1 - fraction) / 4))
    _, on_grid, _ = hist.ecdf_curve(np.array([3.0, 1.0, 2.0, 2.0]), None, grid=np.array([0.0, 2.0, 5.0]))
    assert np.allclose(on_grid, [0.0, 0.75, 1.0])


def test_cumulate_forward_reverse_and_errors():
    from plotipus.intervals import garwood

    counts = np.array([1.0, 2.0, 3.0])
    values, errors = hist.cumulate(counts, counts, weighted=False, density=False)
    low, high = garwood([1, 3, 6])
    assert np.allclose(values, [1, 3, 6]) and np.allclose(errors, [[1, 3, 6] - low, high - [1, 3, 6]])
    values, errors = hist.cumulate(counts, np.array([1.0, 4.0, 9.0]), weighted=True, density=True, reverse=True)
    assert np.allclose(values, [1.0, 5 / 6, 0.5]) and np.allclose(errors[0], np.sqrt([14, 13, 9]) / 6)


def test_hist_type_kde_draws_a_density_with_a_band_and_data_points(make_project):
    from matplotlib.collections import FillBetweenPolyCollection
    from matplotlib.container import ErrorbarContainer

    make_project({"Energies": _frame()})
    figures = _capture()
    hist.main(["--datafile", "Energies", "-x", "True", "--hue", "Sample", "--hist_type", "kde"])
    hist.main(["--datafile", "Energies", "-x", "True", "--hue", "Sample", "--hist_type", "kde", "--data_hue", "a",
               "--bins", "20", "--output_suffix", "data.png"])
    density_ax, data_ax = (fig.axes[0] for fig in figures)
    lines = [l for l in density_ax.lines if l.get_label() in ("a", "b")]
    assert len(lines) == 2 and density_ax.get_ylabel() == "Density"
    for line in lines:
        assert np.isclose(np.trapezoid(line.get_ydata(), line.get_xdata()), 1.0, atol=0.05)  # most of the area
    assert len([c for c in density_ax.collections if isinstance(c, FillBetweenPolyCollection)]) == 2
    assert not _stairs(density_ax)
    # With data points: the data stay a histogram with Poisson errors; the KDE is scaled to counts per bin.
    assert len([c for c in data_ax.containers if isinstance(c, ErrorbarContainer)]) == 1
    (curve,) = [l for l in data_ax.lines if l.get_label() == "b"]
    width = (12 + 4 - (10 - 4)) / 20  # roughly: the edges span both samples
    assert curve.get_ydata().max() > 50 * width
    assert data_ax.get_ylabel().startswith("Counts") and "Poisson" in data_ax.get_ylabel()
    assert [t.get_text() for t in data_ax.get_legend().get_texts()] == ["a", "b"]  # data first


def test_hist_type_ecdf_steps_from_zero_to_one(make_project):
    make_project({"Energies": _frame()})
    figures = _capture()
    hist.main(["--datafile", "Energies", "-x", "True", "--hue", "Sample", "--hist_type", "ecdf"])
    ax = figures[0].axes[0]
    steps = [l for l in ax.lines if l.get_label() in ("a", "b")]
    assert len(steps) == 2 and ax.get_ylabel() == "Cumulative fraction"
    for line in steps:
        y = line.get_ydata()
        assert y[0] == 0.0 and np.isclose(y[-1], 1.0) and np.all(np.diff(y) >= 0)
        assert line.get_drawstyle() == "steps-post"


def test_cumulative_histogram_with_density_ends_at_one(make_project):
    make_project({"Energies": _frame()})
    figures = _capture()
    hist.main(["--datafile", "Energies", "-x", "True", "--hue", "Sample", "--cumulative", "--density"])
    hist.main(["--datafile", "Energies", "-x", "True", "--hue", "Sample", "--cumulative", "reverse",
               "--output_suffix", "reverse.png"])
    forward, reverse = (fig.axes[0] for fig in figures)
    for step in _stairs(forward):
        values = step.get_data().values
        assert np.isclose(values[-1], 1.0) and np.all(np.diff(values) >= 0)
    assert forward.get_ylabel() == "Cumulative fraction"
    for step in _stairs(reverse):
        values = step.get_data().values
        assert np.isclose(values[0], 500) and np.all(np.diff(values) <= 0)
    assert reverse.get_ylabel() == "Cumulative counts"


def test_rug_marks_every_value(make_project):
    from matplotlib.collections import LineCollection

    rng = np.random.default_rng(4)
    make_project({"Small": pd.DataFrame([{"X": rng.normal(0, 1, 30)}])})
    figures = _capture()
    hist.main(["--datafile", "Small", "-x", "X", "--hist_type", "kde", "--rug"])
    ax = figures[0].axes[0]
    (rug,) = [c for c in ax.collections if isinstance(c, LineCollection)]
    segments = rug.get_segments()
    assert len(segments) == 30
    assert all(s[0][1] == 0 and np.isclose(s[1][1], 0.04) for s in segments)  # axes fraction, at the bottom


def test_ridge_stacks_hues_first_on_top(make_project):
    """A11: --ridge puts each hue on its own baseline (the first on top), names them on the y axis
    and draws no legend; the tallest curve reaches OVERLAP into the row above."""
    from matplotlib.collections import FillBetweenPolyCollection

    rng = np.random.default_rng(6)
    frame = pd.DataFrame({"Run": ["r1", "r2", "r3"], "X": [rng.normal(m, 1, 400) for m in (0, 1, 2)]})
    make_project({"Runs": frame})
    figures = _capture()
    hist.main(["--datafile", "Runs", "-x", "X", "--hue", "Run", "--hist_type", "kde", "--ridge", "0.8"])
    ax = figures[0].axes[0]
    assert [t.get_text() for t in ax.get_yticklabels()] == ["r1", "r2", "r3"]
    assert list(ax.get_yticks()) == [2.0, 1.0, 0.0]
    assert ax.get_legend() is None
    bodies = [c for c in ax.collections if isinstance(c, FillBetweenPolyCollection) and c.get_facecolor()[0][3] > 0.5]
    assert len(bodies) == 3
    tops = [b.get_paths()[0].vertices[:, 1].max() for b in bodies]
    bases = [2.0, 1.0, 0.0]
    assert np.isclose(max(t - b for t, b in zip(tops, bases)), 1.8, atol=0.05)


def test_hist_draws_a_garwood_band_by_default(make_project):
    """Rule U1: a step histogram carries its statistical error as a band (U7),
    the Garwood interval of unweighted counts, named in the y label (U6)."""
    from plotipus.intervals import garwood

    x = np.random.default_rng(3).exponential(1.0, 300)
    make_project({"Ev": pd.DataFrame({"E": [x]})})
    figures = _capture()
    hist.main(["--datafile", "Ev", "-x", "E", "--bins", "12"])
    ax = figures[0].axes[0]
    (step,), (band,) = _stairs(ax), _bands(ax)
    counts = step.get_data().values
    low, high = garwood(counts)
    assert np.allclose(band.get_data().values, high) and np.allclose(band.get_data().baseline, low)
    assert band not in ax.get_legend_handles_labels()[0]
    assert "68% CL (Poisson)" in ax.get_ylabel()


def test_hist_weighted_band_is_sqrt_sum_of_squared_weights(make_project):
    rng = np.random.default_rng(4)
    x, w = rng.uniform(0, 1, 500), rng.uniform(0.5, 2.0, 500)
    make_project({"Ev": pd.DataFrame({"E": [x], "W": [w]})})
    figures = _capture()
    hist.main(["--datafile", "Ev", "-x", "E", "--weight", "W", "--bins", "5", "--rangex", "0", "1"])
    ax = figures[0].axes[0]
    (step,), (band,) = _stairs(ax), _bands(ax)
    sumw2 = np.sqrt(np.histogram(x, bins=step.get_data().edges, weights=w**2)[0])
    assert np.allclose(band.get_data().values - step.get_data().values, sumw2)
    assert "CL" not in ax.get_ylabel()


def test_hist_no_error_draws_no_band_and_no_bars(tmp_path, monkeypatch):
    from matplotlib.container import ErrorbarContainer

    from plotipus import registry

    make_project(tmp_path, monkeypatch, {"Energies": _frame()})
    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    try:
        hist.main(["--datafile", "Energies", "-x", "True", "--hue", "Sample", "--data_hue", "a", "--bins", "20",
                   "--no_error"])
    finally:
        registry.figure_hooks.clear()
    ax = figures[0].axes[0]
    assert _bands(ax) == []
    (points,) = [c for c in ax.containers if isinstance(c, ErrorbarContainer)]
    assert not points.has_yerr
    assert "CL" not in ax.get_ylabel()


def test_hist_errory_type_poisson_keeps_bars_instead_of_the_band(make_project):
    from matplotlib.container import ErrorbarContainer

    make_project({"Ev": pd.DataFrame({"E": [np.random.default_rng(5).normal(0, 1, 200)]})})
    figures = _capture()
    hist.main(["--datafile", "Ev", "-x", "E", "--bins", "8", "--errory_type", "poisson"])
    ax = figures[0].axes[0]
    assert _bands(ax) == []
    assert len([c for c in ax.containers if isinstance(c, ErrorbarContainer)]) == 1


def test_hist_band_spans_the_filled_bins_only(make_project):
    """No band over the empty bins beyond a sample (the upper limit of seeing
    nothing); an empty bin inside it keeps its band."""
    x = np.concatenate([np.full(5, 2.5), np.full(3, 4.5)])
    make_project({"Ev": pd.DataFrame({"E": [x]})})
    figures = _capture()
    hist.main(["--datafile", "Ev", "-x", "E", "--bins", "8", "--rangex", "0", "8"])
    (band,) = _bands(figures[0].axes[0])
    assert band.get_data().edges.tolist() == [2.0, 3.0, 4.0, 5.0]
    assert band.get_data().values[1] > 1.8  # the empty bin between: up to Garwood's 1.84
