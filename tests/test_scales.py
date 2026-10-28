"""--secondary_x/y (catalogue H6) and --xscale/--yscale (H7)."""

import numpy as np
import pandas as pd
import pytest

from plotipus import registry, scales
from plotipus.kinds import line


def _frame():
    x = np.linspace(2, 2500, 200)
    return pd.DataFrame([{"Series": "a", "X": x, "Y": np.sqrt(x)}])


def _figure(make_project, *argv, frame=None):
    make_project({"Curve": frame if frame is not None else _frame()})
    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    line.main(["--datafile", "Curve", "-x", "X", "-y", "Y", "--plot_type", "line", *argv])
    return figures[-1]


def _secondary(ax, which="x"):
    return [c for c in ax.child_axes if getattr(c, "_plotipus_secondary", False)]


def test_builtin_conversion_on_top_with_its_label(make_project):
    fig = _figure(make_project, "--secondary_x", "cm-1->GHz", "--rangex", "1", "20")
    ax = fig.axes[0]
    (top,) = _secondary(ax)
    assert top.get_xlabel() == "Frequency (GHz)"
    lo, hi = top.get_xlim()
    assert np.isclose(lo, 29.9792458) and np.isclose(hi, 20 * 29.9792458)


def test_inline_conversion_and_label(make_project):
    fig = _figure(make_project, "--secondary_y", "x*2;x/2", "--secondary_labely", "Twice")
    (right,) = _secondary(fig.axes[0])
    assert right.get_ylabel() == "Twice"
    assert np.allclose(right.get_ylim(), 2 * np.asarray(fig.axes[0].get_ylim()))


def test_style_and_plugin_conversions():
    from plotipus import style

    style.configure(mappings={"conversions": {"km": {"forward": "x/1000", "inverse": "x*1000", "label": "km"}}})
    try:
        forward, inverse, label = scales.conversion("km")
        assert forward(2000.0) == 2.0 and inverse(2.0) == 2000.0 and label == "km"
    finally:
        style.reset()
    registry.add_conversion("double", lambda x: 2 * x, lambda x: x / 2, "2x")
    try:
        assert scales.conversion("double")[2] == "2x"
    finally:
        registry.conversions.clear()


def test_conversion_expressions_are_restricted():
    with pytest.raises(ValueError, match="unknown name"):
        scales.conversion("__import__('os').getcwd();x")
    with pytest.raises(ValueError, match="no conversion name"):
        scales.conversion("nope")


def test_secondary_x_only_on_the_top_row(make_project):
    fig = _figure(make_project, "--secondary_x", "C->F", "--lower", "ratio")
    upper, lower = fig.axes[:2]
    assert len(_secondary(upper)) == 1 and _secondary(lower) == []


def test_hybrid_scale_log_below_the_break_linear_above(make_project):
    """H7: log<30<linear puts the decade 3..30 and the range 30..2500 on fixed shares of the axis."""
    fig = _figure(make_project, "--xscale", "log<30<linear", "--rangex", "2", "2500", "--scale_split", "0.3")
    ax = fig.axes[0]
    assert ax.get_xscale() == "function"
    to_axes = lambda v: ax.transAxes.inverted().transform(ax.transData.transform((v, 1)))[0]  # noqa: E731
    assert np.isclose(to_axes(2), 0) and np.isclose(to_axes(30), 0.3) and np.isclose(to_axes(2500), 1)
    assert np.isclose(to_axes(1265), 0.3 + 0.7 * 0.5)  # linear above the break
    assert np.isclose(to_axes(np.sqrt(2 * 30)), 0.15)  # logarithmic below it
    ticks = list(ax.get_xticks())
    assert 2 in ticks and 10 in ticks and 30 in ticks and 1000 in ticks


def test_hybrid_scale_needs_a_positive_range(make_project, capsys):
    frame = pd.DataFrame([{"Series": "a", "X": np.linspace(-5, 50, 20), "Y": np.ones(20)}])
    fig = _figure(make_project, "--xscale", "log<30<linear", frame=frame)
    assert fig.axes[0].get_xscale() == "linear"
    assert "needs 0 <" in capsys.readouterr().out


def test_symlog_and_lower_panels_keep_their_y(make_project):
    fig = _figure(make_project, "--yscale", "symlog:10", "--lower", "ratio")
    upper, lower = fig.axes[:2]
    assert upper.get_yscale() == "symlog" and lower.get_yscale() == "linear"


def test_unknown_scale_warns(make_project, capsys):
    fig = _figure(make_project, "--xscale", "cubic")
    assert fig.axes[0].get_xscale() == "linear"
    assert "unknown scale 'cubic'" in capsys.readouterr().out
