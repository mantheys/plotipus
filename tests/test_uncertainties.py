"""The style guide's uncertainty rules: U1 (errors drawn by default, the
standard interval or a warning when there are none), U4 (stored errors that
cross a physical bound warn) and U10 (tables pick the interval)."""

import numpy as np
import pandas as pd
from matplotlib.collections import PolyCollection
from matplotlib.container import ErrorbarContainer

from plotipus import intervals, registry
from plotipus.kinds import cat, line, table


def _capture():
    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    return figures


def _said(capsys):
    """Everything printed so far, with rich's line wrapping undone."""
    return " ".join(capsys.readouterr().out.split())


def _bands(ax):
    return [c for c in ax.collections if isinstance(c, PolyCollection)]


def _curves(error=True):
    x = np.linspace(0.5, 9.5, 10)
    rows = [{"X": x, "Y": 2.0 + 0.1 * x, "Sample": "measured"}, {"X": x, "Y": 1.0 + 0.1 * x, "Sample": "model"}]
    if error:
        for row in rows:
            row["YError"] = 0.2 * np.ones_like(x)
    return pd.DataFrame(rows)


# --- U1: line ------------------------------------------------------------------------------


def test_stored_errors_are_drawn_without_errory(make_project):
    figures = _capture()
    out = make_project({"Curves": _curves()})
    line.main(["--datafile", "Curves", "-x", "X", "-y", "Y", "--hue", "Sample", "--plot_type", "line"])
    assert len(_bands(figures[-1].axes[0])) == 2
    # The default does not rename the figure: only a typed --errory adds 'error'.
    assert [p.name for p in out.iterdir()] == ["curves_x_y_sample_line.png"]


def test_errory_still_names_the_file(make_project):
    out = make_project({"Curves": _curves()})
    line.main(["--datafile", "Curves", "-x", "X", "-y", "Y", "--hue", "Sample", "--plot_type", "line", "--errory"])
    assert [p.name for p in out.iterdir()] == ["curves_x_y_error_sample_line.png"]


def test_no_error_draws_none_and_says_nothing(make_project, capsys):
    figures = _capture()
    make_project({"Curves": _curves(error=False)})
    capsys.readouterr()
    line.main(["--datafile", "Curves", "-x", "X", "-y", "Y", "--hue", "Sample", "--plot_type", "line", "--no_error"])
    assert not _bands(figures[-1].axes[0])
    assert "uncertainty" not in _said(capsys)


def test_exact_series_skip_their_errors(make_project):
    figures = _capture()
    make_project({"Curves": _curves()})
    line.main(["--datafile", "Curves", "-x", "X", "-y", "Y", "--hue", "Sample", "--plot_type", "line",
               "--exact", "model"])
    assert len(_bands(figures[-1].axes[0])) == 1


def test_counts_without_errors_get_garwood_and_a_warning(make_project, capsys):
    counts = np.array([0, 1, 4, 9, 3, 0], dtype=float)
    frame = pd.DataFrame([{"Bin": np.arange(6) + 0.5, "Counts": counts, "Sample": "mc"}])
    figures = _capture()
    make_project({"Spectrum": frame})
    capsys.readouterr()
    line.main(["--datafile", "Spectrum", "-x", "Bin", "-y", "Counts", "--hue", "Sample", "--plot_type", "errorbar"])
    said = _said(capsys)
    assert "mc: Counts has no error column; drawing Garwood (Poisson) 68% intervals." in said
    (points,) = [c for c in figures[-1].axes[0].containers if isinstance(c, ErrorbarContainer)]
    low, high = intervals.garwood(counts)
    segments = points.lines[2][0].get_segments()
    assert np.allclose([s[0][1] for s in segments], low) and np.allclose([s[1][1] for s in segments], high)


def test_efficiency_with_trials_gets_clopper_pearson(make_project, capsys):
    total = np.array([10, 20, 40, 10], dtype=float)
    passed = np.array([10, 15, 20, 0], dtype=float)
    frame = pd.DataFrame([{"E": np.arange(4.0), "Eff": passed / total, "N": total, "Particle": "e"}])
    figures = _capture()
    make_project({"Trigger": frame})
    capsys.readouterr()
    line.main(["--datafile", "Trigger", "-x", "E", "-y", "Eff", "--hue", "Particle", "--plot_type", "errorbar",
               "--count_column", "N"])
    assert "e: Eff has no error column; drawing Clopper–Pearson 68% intervals of the N trials." in _said(capsys)
    (points,) = [c for c in figures[-1].axes[0].containers if isinstance(c, ErrorbarContainer)]
    tops = [s[1][1] for s in points.lines[2][0].get_segments()]
    assert np.isclose(tops[0], 1.0) and max(tops) <= 1.0  # inside [0, 1] even at 100%


def test_series_without_a_standard_interval_warn(make_project, capsys):
    make_project({"Curves": _curves(error=False)})
    capsys.readouterr()
    line.main(["--datafile", "Curves", "-x", "X", "-y", "Y", "--hue", "Sample", "--plot_type", "line",
               "--exact", "model"])
    said = _said(capsys)
    assert "measured: Y has no error column and no standard interval applies; drawn with no uncertainty" in said
    assert "model:" not in said  # exact: no warning


def test_fitted_counts_get_garwood(make_project, capsys):
    x = np.linspace(-5, 5, 21)
    frame = pd.DataFrame([{"Values": x, "Counts": np.round(10.0 * np.exp(-0.5 * (x / 1.2) ** 2)),
                           "FitFunctionLabel": "Gaussian", "Params": [10.0, 0.0, 1.2],
                           "ParamsError": [0.3, 0.05, 0.04], "ParamsLabel": ["A", r"$\mu$", r"$\sigma$"]}])
    figures = _capture()
    make_project({"Peak": frame})
    capsys.readouterr()
    line.main(["--datafile", "Peak", "-x", "Values", "-y", "Counts", "--fit"])
    assert "Data: Counts has no error column; drawing Garwood (Poisson) 68% intervals." in _said(capsys)
    (points,) = [c for c in figures[-1].axes[0].containers if isinstance(c, ErrorbarContainer)]
    assert points.has_yerr


# --- U4: bounds ----------------------------------------------------------------------------


def test_stored_errors_below_zero_warn_once_per_series(make_project, capsys):
    x = np.arange(4.0)
    frame = pd.DataFrame([{"X": x, "Y": np.array([0.5, 2.0, 3.0, 4.0]), "YError": np.ones(4), "Sample": s,
                           "Variable": v} for s in ("a", "b") for v in ("one", "two")])
    make_project({"Rates": frame})
    capsys.readouterr()
    line.main(["--datafile", "Rates", "-x", "X", "-y", "Y", "--hue", "Sample", "--variables", "one", "two"])
    said = _said(capsys)
    assert said.count("a: the stored YError errors go below 0 at 1 point") == 1  # two panels, one warning
    assert said.count("b: the stored YError errors go below 0") == 1


def test_efficiency_errors_above_one_warn(make_project, capsys):
    frame = pd.DataFrame([{"X": np.arange(3.0), "Eff": np.array([0.5, 0.9, 0.98]), "EffError": np.full(3, 0.05),
                           "Particle": "e"}])
    make_project({"Trigger": frame})
    capsys.readouterr()
    line.main(["--datafile", "Trigger", "-x", "X", "-y", "Eff", "--hue", "Particle"])
    assert "e: the stored EffError errors go above 1 at 1 point" in _said(capsys)


def test_signed_quantities_do_not_warn(make_project, capsys):
    frame = pd.DataFrame([{"X": np.arange(3.0), "Pull": np.array([-1.0, 0.2, 1.5]), "PullError": np.ones(3),
                           "Sample": "a"}])
    make_project({"Pulls": frame})
    capsys.readouterr()
    line.main(["--datafile", "Pulls", "-x", "X", "-y", "Pull", "--hue", "Sample"])
    assert "stored PullError" not in _said(capsys)


# --- U1: cat -------------------------------------------------------------------------------


def test_cat_counts_get_garwood_totals(make_project, capsys):
    frame = pd.DataFrame([{"Stage": stage, "Particle": "e", "Counts": np.array([n, n], dtype=float)}
                          for stage, n in (("raw", 2), ("cut", 0))])
    figures = _capture()
    make_project({"Yields": frame})
    capsys.readouterr()
    cat.main(["--datafile", "Yields", "-x", "Stage", "-y", "Counts", "--hue", "Particle", "--kind", "point"])
    assert "e: Counts has no error column; drawing Garwood (Poisson) 68% intervals." in _said(capsys)
    (points,) = [c for c in figures[-1].axes[0].containers if isinstance(c, ErrorbarContainer)]
    low, high = intervals.garwood(np.array([4.0, 0.0]))
    segments = points.lines[2][0].get_segments()
    assert np.allclose([s[0][1] for s in segments], low) and np.allclose([s[1][1] for s in segments], high)


def test_cat_no_error(make_project):
    frame = pd.DataFrame([{"Stage": "raw", "Particle": "e", "Counts": np.array([2.0, 2.0])}])
    figures = _capture()
    make_project({"Yields": frame})
    cat.main(["--datafile", "Yields", "-x", "Stage", "-y", "Counts", "--hue", "Particle", "--kind", "point",
              "--no_error"])
    assert not any(c.has_yerr for c in figures[-1].axes[0].containers if isinstance(c, ErrorbarContainer))


# --- U10: tables ---------------------------------------------------------------------------


def _table(out, *argv):
    table.main(["-o", str(out), *argv])
    return next(p for p in out.iterdir() if p.suffix == ".tex").read_text()


def test_table_poisson_column(make_project, tmp_path):
    frame = pd.DataFrame([{"Config": "a", "Variable": "Events", "Value": 4.0, "Events": 4},
                          {"Config": "a", "Variable": "Events", "Value": 5.0, "Events": 5}])
    make_project({"Yields": frame})
    text = _table(tmp_path / "out", "--datafile", "Yields", "-y", "Value", "--variables", "Events",
                  "--poisson", "Events", "--agg", "sum")
    low, high = intervals.garwood(9)
    assert f"^{{+{high - 9:.0f}" in text and "9" in text


def test_table_counts_pick_garwood(make_project, tmp_path, capsys):
    frame = pd.DataFrame([{"Config": "a", "Variable": "Events", "Value": 3}])
    make_project({"Yields": frame})
    capsys.readouterr()
    text = _table(tmp_path / "out", "--datafile", "Yields", "-y", "Value", "--variables", "Events")
    assert "Value: Value has no error column; drawing Garwood (Poisson) 68% intervals." in _said(capsys)
    assert "3^{+" in text


def test_table_efficiency_picks_clopper_pearson(make_project, tmp_path, capsys):
    frame = pd.DataFrame([{"Config": "a", "Variable": "Eff", "Value": 1.0, "Passed": 20, "Total": 20}])
    make_project({"Trigger": frame})
    capsys.readouterr()
    text = _table(tmp_path / "out", "--datafile", "Trigger", "-y", "Value", "--variables", "Eff")
    assert "Clopper–Pearson 68% intervals of the Passed/Total trials" in _said(capsys)
    low, _ = intervals.clopper_pearson(20, 20)
    assert "1.00^{+0.00}" in text  # a fraction stays a fraction, never above 1


def test_table_spread_of_counts_warns(make_project, tmp_path, capsys):
    frame = pd.DataFrame([{"Config": "a", "Variable": "Events", "Value": n} for n in (3, 5, 4)])
    make_project({"Yields": frame})
    capsys.readouterr()
    _table(tmp_path / "out", "--datafile", "Yields", "-y", "Value", "--variables", "Events", "--error_mode", "std")
    assert "Value holds counts: --error_mode std gives their spread, not their uncertainty" in _said(capsys)


def test_table_stored_errors_crossing_one_warn(make_project, tmp_path, capsys):
    frame = pd.DataFrame([{"Config": "a", "Variable": "Efficiency", "Value": 0.98, "ValueError": 0.05}])
    make_project({"Summary": frame})
    capsys.readouterr()
    _table(tmp_path / "out", "--datafile", "Summary", "-y", "Value", "--variables", "Efficiency")
    assert "Efficiency: the stored ValueError errors go above 1" in _said(capsys)
