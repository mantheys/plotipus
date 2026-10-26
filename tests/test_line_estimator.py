import matplotlib.pyplot as plt
import numpy as np
import pytest
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



def test_binned_hues_share_bins(make_project):
    """Hues with different x ranges are binned over the same edges."""
    from plotipus import registry

    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    rng = np.random.default_rng(3)
    frame = pd.DataFrame([{"X": rng.uniform(0, top, 400), "Y": rng.normal(0, 1, 400), "Sample": sample}
                          for sample, top in (("short", 6.0), ("long", 10.0))])
    make_project({"Events": frame})
    line.main(["--datafile", "Events", "-x", "X", "-y", "Y", "--hue", "Sample", "--binned", "--bins", "11",
               "--plot_type", "line"])
    short, long = (np.asarray(l.get_xdata()) for l in figures[-1].axes[0].lines[:2])
    assert long.size == 10 and short.size < long.size
    assert np.isin(short.round(9), long.round(9)).all()

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


# --- Uncertainties (T03) -------------------------------------------------------------


def _capture():
    from plotipus import registry

    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    return figures


def _drawn(ax):
    """(x, y, yerr) of the first errorbar container on ``ax``."""
    container = ax.containers[0]
    line, _, (bars,) = container.lines[0], container.lines[1], container.lines[2]
    x, y = line.get_data()
    yerr = np.array([abs(segment[1, 1] - segment[0, 1]) / 2 for segment in bars.get_segments()])
    return np.asarray(x), np.asarray(y), yerr


def _sample(n_per_bin=(40, 60, 3, 80), seed=2):
    rng = np.random.default_rng(seed)
    x = np.concatenate([np.full(n, i) for i, n in enumerate(n_per_bin)])
    y = rng.normal(10.0, 2.0, x.size)
    return x, y


def _frame(x, y, error=None):
    row = {"Bin": x, "Value": y, "Config": "a", "Name": "b"}
    if error is not None:
        row["ValueError"] = error
    return pd.DataFrame([row])


def test_estimate_formulas():
    from plotipus.transforms import estimate

    y = np.random.default_rng(3).normal(0, 1.5, 50)
    sigma = np.std(y, ddof=1)
    assert estimate(y, "mean")[1] == pytest.approx(sigma / np.sqrt(50), abs=1e-12)
    assert estimate(y, "median")[1] == pytest.approx(1.2533 * sigma / np.sqrt(50), rel=1e-4)
    assert estimate(y, "std")[1] == pytest.approx(sigma / np.sqrt(2 * 49), abs=1e-12)
    rms = np.sqrt(np.mean(y**2))
    assert estimate(y, "rms")[1] == pytest.approx(np.std(y**2, ddof=1) / (2 * rms * np.sqrt(50)), abs=1e-12)
    assert estimate(np.ones(16), "sum") == (16, 4)
    assert estimate(np.array([0.5, 2.0]), "sum")[1] == pytest.approx(np.sqrt(4.25))
    assert np.isnan(estimate(y, "max")[1]) and np.isnan(estimate(y, "min")[1])
    assert estimate(y, "mean", error_mode="std")[1] == pytest.approx(sigma)
    assert np.isnan(estimate(y, "mean", error_mode="none")[1])
    # The plain-value API is unchanged.
    edges, _ = reduction_bins(np.array([0, 1]))
    assert list(bin_reduce(np.array([0, 1]), np.array([2.0, 3.0]), edges, "mean")) == [2, 3]


def test_binned_mean_error_is_sem(make_project):
    x, y = _sample()
    make_project({"Sample": _frame(x, y)})
    figures = _capture()
    line.main(["--datafile", "Sample", "-x", "Bin", "-y", "Value", "--binned", "--estimator", "mean"])
    ax = figures[0].axes[0]
    centres, values, errors = _drawn(ax)
    assert list(centres) == [0, 1, 3]  # the 3-entry bin is dropped
    for c, value, error in zip(centres, values, errors):
        sample = y[x == c]
        assert value == pytest.approx(sample.mean(), abs=1e-12)
        assert error == pytest.approx(np.std(sample, ddof=1) / np.sqrt(sample.size), abs=1e-12)
    # Markers, not joined.
    assert ax.containers[0].lines[0].get_linestyle() == "None"
    assert ax.get_ylabel() == r"Value (mean $\pm$ s.e.m.)"


def test_binned_std_error(make_project):
    x, y = _sample()
    make_project({"Sample": _frame(x, y)})
    figures = _capture()
    line.main(["--datafile", "Sample", "-x", "Bin", "-y", "Value", "--binned", "--estimator", "std"])
    centres, _, errors = _drawn(figures[0].axes[0])
    for c, error in zip(centres, errors):
        sample = y[x == c]
        assert error == pytest.approx(np.std(sample, ddof=1) / np.sqrt(2 * (sample.size - 1)), abs=1e-12)
    assert figures[0].axes[0].get_ylabel() == r"Value (std $\pm$ s.e.)"


def test_min_count(make_project, capsys):
    x, y = _sample()
    make_project({"Sample": _frame(x, y)})
    figures = _capture()
    line.main(["--datafile", "Sample", "-x", "Bin", "-y", "Value", "--binned", "--min_count", "1"])
    assert list(_drawn(figures[0].axes[0])[0]) == [0, 1, 2, 3]
    line.main(["--datafile", "Sample", "-x", "Bin", "-y", "Value", "--binned"])
    assert list(_drawn(figures[1].axes[0])[0]) == [0, 1, 3]
    assert "dropped 1 of 4 bins" in capsys.readouterr().out


def test_propagated_stored_errors(make_project):
    x, y = _sample()
    error = np.random.default_rng(4).uniform(0.1, 0.5, x.size)
    make_project({"Sample": _frame(x, y, error)})
    figures = _capture()
    line.main(["--datafile", "Sample", "-x", "Bin", "-y", "Value", "--binned", "--errory"])
    ax = figures[0].axes[0]
    centres, _, errors = _drawn(ax)
    for c, drawn in zip(centres, errors):
        stored = error[x == c]
        assert drawn == pytest.approx(np.sqrt(np.sum(stored**2)) / stored.size, abs=1e-12)
    assert ax.get_ylabel() == r"Value (mean $\pm$ propagated error)"


def test_error_modes_and_label_switches(make_project):
    x, y = _sample()
    make_project({"Sample": _frame(x, y)})
    figures = _capture()
    line.main(["--datafile", "Sample", "-x", "Bin", "-y", "Value", "--binned", "--estimator_error", "std"])
    _, _, errors = _drawn(figures[0].axes[0])
    assert errors[0] == pytest.approx(np.std(y[x == 0], ddof=1), abs=1e-12)
    assert figures[0].axes[0].get_ylabel() == r"Value (mean $\pm$ $\sigma$)"
    line.main(["--datafile", "Sample", "-x", "Bin", "-y", "Value", "--binned", "--estimator_error", "none"])
    assert not figures[1].axes[0].containers and figures[1].axes[0].get_ylabel() == "Value"
    line.main(["--datafile", "Sample", "-x", "Bin", "-y", "Value", "--binned", "--no_error_label"])
    assert figures[2].axes[0].get_ylabel() == "Value"
    line.main(["--datafile", "Sample", "-x", "Bin", "-y", "Value", "--binned", "--note", "mean ± s.e.m."])
    assert figures[3].axes[0].get_ylabel() == "Value"


# --- Box plots (T10) -----------------------------------------------------------------


def _three_groups():
    rng = np.random.default_rng(4)
    return pd.DataFrame([{"X": rng.uniform(0, 12, 1200), "Y": rng.normal(k, 1, 1200), "Group": g}
                         for k, g in enumerate("ABC")])


def _box_figure(make_project, *argv):
    make_project({"Groups": _three_groups()})
    figures = _capture()
    line.main(["--datafile", "Groups", "-x", "X", "-y", "Y", "--hue", "Group", "--binned", "--bins", "13",
               "--rangex", "0", "12", "--plot_type", "box", *argv])
    figures[0].canvas.draw()
    return figures[0].axes[0]


def _boxes(ax):
    from matplotlib.patches import PathPatch

    return [p for p in ax.patches if isinstance(p, PathPatch)]


def test_box_hues_dodged_per_bin(make_project):
    ax = _box_figure(make_project)
    boxes = _boxes(ax)
    assert len(boxes) == 36
    xs = [p.get_path().vertices[:, 0] for p in boxes]
    centres = np.array([(x.min() + x.max()) / 2 for x in xs])
    offsets = np.round(centres - (np.floor(centres) + 0.5), 6)
    assert sorted(set(offsets)) == pytest.approx([-0.8 / 3, 0.0, 0.8 / 3], abs=1e-6)
    widths = {round(np.ptp(p.get_path().vertices[:, 0]), 6) for p in boxes}
    assert widths == {round(0.8 / 3, 6)}


def test_box_colours_and_legend(make_project):
    from matplotlib.colors import to_hex

    ax = _box_figure(make_project)
    legend = ax.get_legend()
    assert [t.get_text() for t in legend.get_texts()] == ["A", "B", "C"]
    handles = legend.legend_handles
    edges = [to_hex(h.get_edgecolor()) for h in handles]
    assert len(set(edges)) == 3
    assert all(h.get_facecolor()[3] == pytest.approx(0.25) for h in handles)
    # Median lines in the box colour; fliers hollow.
    medians = [l for l in ax.lines if len(l.get_xdata()) == 2 and l.get_xdata()[0] != l.get_xdata()[1]]
    assert {to_hex(l.get_color()) for l in medians} <= set(edges)
    fliers = [l for l in ax.lines if l.get_marker() == "o"]
    assert fliers and all(l.get_markerfacecolor() == "none" for l in fliers)


def test_box_tick_labels(make_project):
    ax = _box_figure(make_project)
    labels = [t.get_text() for t in ax.get_xticklabels()]
    assert labels == [f"{c + 0.5:.1f}" for c in range(12)]
    plt.close("all")
    ax = _box_figure(make_project, "--box_tick_labels", "ranges")
    labels = [t.get_text() for t in ax.get_xticklabels()]
    assert labels == ["[0, 1)", "[2, 3)", "[4, 5)", "[6, 7)", "[8, 9)", "[10, 11)"]


def test_box_whis_and_fliers(make_project):
    ax = _box_figure(make_project, "--whis", "0", "100")
    assert not any(len(l.get_xdata()) for l in ax.lines if l.get_marker() == "o")
    plt.close("all")
    ax = _box_figure(make_project, "--no_fliers")
    assert not [l for l in ax.lines if l.get_marker() == "o"]


def test_box_categorical_x(make_project):
    rng = np.random.default_rng(5)
    frame = pd.DataFrame([{"Det": rng.choice(["Muon", "ECAL", "HCAL"], 300), "Y": rng.normal(0, 1, 300), "Run": r}
                          for r in ("2023", "2024")])
    make_project({"Cat": frame})
    figures = _capture()
    line.main(["--datafile", "Cat", "-x", "Det", "-y", "Y", "--hue", "Run", "--binned", "--plot_type", "box"])
    ax = figures[0].axes[0]
    figures[0].canvas.draw()
    assert [t.get_text() for t in ax.get_xticklabels()] == ["ECAL", "HCAL", "Muon"]
    assert len(_boxes(ax)) == 6
