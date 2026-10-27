import numpy as np
import pandas as pd
import pytest
from matplotlib.container import ErrorbarContainer

from plotipus import intervals
from plotipus.kinds import hist, line


def _capture():
    from plotipus import registry

    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    return figures


# --- intervals.py ------------------------------------------------------------------------


@pytest.mark.parametrize("n, low, high", [
    # Gehrels (1986), ApJ 303, 336, Tables 1 and 2 (S = 1, i.e. 84.13% one-sided limits,
    # together the central 68.27% interval): the exact Poisson (Garwood) bounds.
    (0, 0.0, 1.841),
    (1, 0.173, 3.300),
    (10, 6.891, 14.27),
])
def test_garwood_matches_published_values(n, low, high):
    lo, hi = intervals.garwood(n)
    assert np.isclose(lo, low, atol=1e-3) and np.isclose(hi, high, atol=1e-2)


def test_garwood_arrays_and_cl():
    lo, hi = intervals.garwood([0, 1, 10], cl=0.95)
    assert lo[0] == 0 and np.all(lo <= [0, 1, 10]) and np.all(hi >= [0, 1, 10])
    assert np.isclose(hi[0], 3.689, atol=1e-3)  # the 97.5% upper limit for n = 0


def test_clopper_pearson_bounded_at_0_and_1():
    assert intervals.clopper_pearson(0, 10) == (0.0, pytest.approx(0.1682, abs=1e-4))
    low, high = intervals.clopper_pearson(10, 10)
    assert high == 1.0 and 0 < low < 1
    lows, highs = intervals.clopper_pearson(np.array([0, 5, 10]), np.array([10, 10, 10]))
    assert np.all(lows >= 0) and np.all(highs <= 1) and lows[0] == 0 and highs[-1] == 1


def test_sumw2():
    assert np.isclose(intervals.sumw2([0.5, 0.5, 1.0]), np.sqrt(1.5))


def test_table_still_imports_clopper_pearson():
    from plotipus.format import clopper_pearson
    from plotipus.kinds import table

    assert clopper_pearson is intervals.clopper_pearson and table.clopper_pearson is intervals.clopper_pearson


def test_label():
    assert intervals.label("clopper_pearson") == "68% CL (Clopper–Pearson)"
    assert intervals.label("poisson", 0.95) == "95% CL (Poisson)"


# --- hist ---------------------------------------------------------------------------------


def test_hist_poisson_errors_are_garwood(make_project):
    x = np.random.default_rng(5).normal(0, 1, 300)
    make_project({"Ev": pd.DataFrame({"X": [x]})})
    figures = _capture()
    hist.main(["--datafile", "Ev", "-x", "X", "--bins", "12", "--rangex", "-3", "3", "--errory_type", "poisson"])
    ax = figures[-1].axes[0]
    (container,) = [c for c in ax.containers if isinstance(c, ErrorbarContainer)]
    counts, _ = np.histogram(x, bins=12, range=(-3, 3))
    low, high = intervals.garwood(counts)
    segments = container.lines[2][0].get_segments()
    assert np.allclose([s[0][1] for s in segments], low) and np.allclose([s[1][1] for s in segments], high)
    below, above = counts - low, high - counts
    assert np.all(above > below)  # asymmetric: longer above


def test_hist_weighted_overlay_keeps_sumw2(make_project):
    x = np.array([0.1, 0.2, 0.6, 0.7, 0.8])
    w = np.array([0.5, 0.5, 2.0, 1.0, 1.0])
    make_project({"Ev": pd.DataFrame({"X": [x], "W": [w], "S": ["data"]})})
    figures = _capture()
    hist.main(["--datafile", "Ev", "-x", "X", "--weight", "W", "--hue", "S", "--overlay", "data", "--bins", "2",
               "--rangex", "0", "1"])
    (container,) = [c for c in figures[-1].axes[0].containers if isinstance(c, ErrorbarContainer)]
    segments = container.lines[2][0].get_segments()
    half = np.array([(s[1][1] - s[0][1]) / 2 for s in segments])
    assert np.allclose(half, [np.sqrt(0.5), np.sqrt(6.0)])


# --- line ---------------------------------------------------------------------------------


def test_line_poisson_and_label(make_project):
    counts = np.array([0.0, 1.0, 4.0, 10.0])
    make_project({"Spec": pd.DataFrame([{"X": np.arange(4.0), "Counts": counts, "S": "data"}])})
    figures = _capture()
    line.main(["--datafile", "Spec", "-x", "X", "-y", "Counts", "--hue", "S", "--plot_type", "errorbar",
               "--errory_type", "poisson", "--error_label"])
    ax = figures[-1].axes[0]
    (container,) = [c for c in ax.containers if isinstance(c, ErrorbarContainer)]
    low, high = intervals.garwood(counts)
    segments = container.lines[2][0].get_segments()
    assert np.allclose([s[0][1] for s in segments], low) and np.allclose([s[1][1] for s in segments], high)
    assert ax.get_ylabel().endswith("68% CL (Poisson)")


def test_line_overlay_without_error_column_defaults_to_poisson(make_project):
    x = np.arange(4.0)
    frame = pd.DataFrame([{"X": x, "Counts": np.array([0.0, 2.0, 5.0, 3.0]), "S": "data"},
                          {"X": x, "Counts": np.array([1.0, 2.0, 4.0, 3.0]), "S": "mc"}])
    make_project({"Spec": frame})
    figures = _capture()
    line.main(["--datafile", "Spec", "-x", "X", "-y", "Counts", "--hue", "S", "--overlay", "data"])
    (container,) = [c for c in figures[-1].axes[0].containers if isinstance(c, ErrorbarContainer)]
    low, high = intervals.garwood(frame["Counts"].iloc[0])
    segments = container.lines[2][0].get_segments()
    assert np.allclose([s[1][1] for s in segments], high)


def test_line_overlay_without_its_own_error_cell_defaults_to_poisson(make_project):
    # The error column exists for the simulation only: the data row's NaN cell is no error.
    x = np.arange(4.0)
    counts = np.array([0.0, 2.0, 5.0, 3.0])
    frame = pd.DataFrame([{"X": x, "Counts": counts, "S": "data"},
                          {"X": x, "Counts": np.array([1.0, 2.0, 4.0, 3.0]), "CountsError": np.full(4, 0.5), "S": "mc"}])
    make_project({"Spec": frame})
    figures = _capture()
    line.main(["--datafile", "Spec", "-x", "X", "-y", "Counts", "--hue", "S", "--overlay", "data", "--errory"])
    (container,) = [c for c in figures[-1].axes[0].containers if isinstance(c, ErrorbarContainer)]
    segments = container.lines[2][0].get_segments()
    assert np.allclose([s[1][1] for s in segments], intervals.garwood(counts)[1])


def test_line_overlay_of_measurements_gets_no_poisson_default(make_project):
    # Overlay data whose y are not counts (negative or fractional values) keeps no errors.
    x = np.arange(4.0)
    frame = pd.DataFrame([{"X": x, "Y": np.array([4.3, 5.7, -1.2, 9.0]), "S": "data"},
                          {"X": x, "Y": np.array([4.0, 5.5, -1.0, 9.1]), "S": "model"}])
    make_project({"Meas": frame})
    figures = _capture()
    line.main(["--datafile", "Meas", "-x", "X", "-y", "Y", "--hue", "S", "--overlay", "data", "--error_label"])
    ax = figures[-1].axes[0]
    for container in (c for c in ax.containers if isinstance(c, ErrorbarContainer)):
        assert not container.has_yerr
    assert "Poisson" not in ax.get_ylabel()


def test_line_clopper_pearson_never_crosses_the_bounds(make_project):
    trials = np.full(5, 20.0)
    efficiency = np.array([0.0, 5.0, 50.0, 95.0, 100.0])  # percent
    make_project({"Eff": pd.DataFrame([{"X": np.arange(5.0), "Efficiency": efficiency, "N": trials, "S": "trig"}])})
    figures = _capture()
    line.main(["--datafile", "Eff", "-x", "X", "-y", "Efficiency", "--hue", "S", "--plot_type", "errorbar",
               "--errory_type", "clopper_pearson", "--count_column", "N", "--efficiency_scale", "100"])
    (container,) = [c for c in figures[-1].axes[0].containers if isinstance(c, ErrorbarContainer)]
    segments = container.lines[2][0].get_segments()
    lows, highs = np.array([s[0][1] for s in segments]), np.array([s[1][1] for s in segments])
    expected_low, expected_high = intervals.clopper_pearson(efficiency / 100 * trials, trials)
    assert np.allclose(lows, 100 * expected_low) and np.allclose(highs, 100 * expected_high)
    assert lows.min() >= 0 and highs.max() <= 100 and lows[0] == 0 and highs[-1] == 100
