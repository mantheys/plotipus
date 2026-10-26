"""Legends that never cover data (T15): occupancy-mask placement, headroom,
legends above the axes, entry order and lower-panel legends."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.legend import Legend
from matplotlib.patches import Rectangle

from plotipus import registry
from plotipus.kinds import cat, line
from plotipus.plot import _Occupancy, apply_legend_style, axes_occupancy, place_legends


def _resonance():
    """Falling background, a peak and the data: the B06 shapes."""
    x = np.arange(101, 160, 2.0)
    background = 400 * np.exp(-(x - 100) / 30)
    signal = 120 * np.exp(-0.5 * ((x - 125) / 2) ** 2)
    rows = [{"Bin": x, "Counts": c, "CountsError": np.sqrt(c), "Sample": s}
            for s, c in (("Data", background + signal), ("Background", background), ("Signal", signal))]
    rows += [{"Bin": x, "Counts": (k + 1) * 10 * np.exp(-x / (20 + 5 * k)), "CountsError": np.ones_like(x),
              "Sample": f"Run {k:02d}"} for k in range(12)]
    return pd.DataFrame(rows)


def _figures():
    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    return figures


def _drawn(fig):
    FigureCanvasAgg(fig)  # the saved figure was closed
    fig.draw_without_rendering()
    return fig.canvas.get_renderer()


def _legends(ax):
    return [a for a in ax.get_children() if isinstance(a, Legend) and a.get_visible()]


def _covered(ax, legend, renderer):
    """Fraction of the legend box drawn over by data (other legends excluded)."""
    occupancy = _Occupancy(*axes_occupancy(ax, renderer))
    return occupancy.fraction(legend.get_window_extent(renderer), pad=0)


def test_stacked_legend_covers_no_bar(make_project):
    make_project({"Spectra": _resonance()})
    figures = _figures()
    line.main(["--datafile", "Spectra", "-x", "Bin", "-y", "Counts", "--hue", "Sample", "--select", "Sample",
               "-s", "Background", "Signal", "--stacked", "--logy"])
    ax = figures[0].axes[0]
    renderer = _drawn(figures[0])
    legend, = _legends(ax)
    assert _covered(ax, legend, renderer) == 0
    # A stack lists its top first.
    assert [t.get_text() for t in legend.get_texts()] == ["Signal", "Background"]


def test_bar_legend_covers_no_bar(make_project):
    make_project({"Spectra": _resonance()})
    figures = _figures()
    cat.main(["--datafile", "Spectra", "-x", "Sample", "--hue", "Sample", "-y", "Counts", "--integrate_over", "Bin",
              "--select", "Sample", "-s", "Data", "Background", "Signal", "--kind", "bar"])
    ax = figures[0].axes[0]
    renderer = _drawn(figures[0])
    box = _legends(ax)[0].get_window_extent(renderer)
    bars = [p.get_window_extent(renderer) for p in ax.patches if isinstance(p, Rectangle) and p.get_height()]
    assert bars and not any(box.overlaps(bar) for bar in bars)


def test_many_entries_go_above_the_axes(make_project):
    make_project({"Spectra": _resonance()})
    figures = _figures()
    line.main(["--datafile", "Spectra", "-x", "Bin", "-y", "Counts", "--hue", "Sample", "--select", "Sample",
               "-s", *[f"Run {k:02d}" for k in range(12)], "--plot_type", "line"])
    fig = figures[0]
    ax = fig.axes[0]
    renderer = _drawn(fig)
    legend, = _legends(ax)
    box = legend.get_window_extent(renderer)
    assert box.y0 >= ax.bbox.y1 - 1  # above the axes
    assert box.y1 <= fig.bbox.height + 1 and box.x0 >= -1 and box.x1 <= fig.bbox.width + 1
    assert legend._ncols > 1


def test_lower_ratio_in_upper_colours_has_no_legend(make_project):
    make_project({"Spectra": _resonance()})
    figures = _figures()
    line.main(["--datafile", "Spectra", "-x", "Bin", "-y", "Counts", "--hue", "Sample", "--select", "Sample",
               "-s", "Data", "Background", "Signal", "--plot_type", "step", "--lower", "ratio"])
    upper, lower = figures[0].axes[:2]
    assert not _legends(lower)
    assert lower.get_ylabel() == "Ratio"
    assert lower.get_legend_handles_labels()[1] == ["Background / Data", "Signal / Data"]


def test_lines_ordered_by_their_right_ends(make_project):
    make_project({"Spectra": _resonance()})
    figures = _figures()
    base = ["--datafile", "Spectra", "-x", "Bin", "-y", "Counts", "--hue", "Sample", "--select", "Sample",
            "-s", "Run 00", "Run 01", "Run 02", "--plot_type", "line"]
    line.main(base)
    line.main([*base, "--legend_order", "data"])
    by_value = [t.get_text() for t in figures[0].axes[0].get_legend().get_texts()]
    drawn = [t.get_text() for t in figures[1].axes[0].get_legend().get_texts()]
    assert by_value == ["Run 02", "Run 01", "Run 00"]  # highest right-hand end first
    assert drawn == ["Run 00", "Run 01", "Run 02"]


def test_headroom_when_no_corner_is_free():
    fig, ax = plt.subplots(figsize=(6, 4))
    x = np.linspace(0, 1, 50)
    ax.fill_between(x, 0, 1 - 0.02 * x, label="band")  # data fills the axes up to the top
    ax.plot(x, 0.5 + 0.0 * x, label="line")
    ax.set_xlim(0, 1)
    top = ax.get_ylim()[1]
    legend = apply_legend_style(ax)
    assert place_legends(fig)
    renderer = fig.canvas.get_renderer()
    assert ax.get_ylim()[1] > top
    assert _covered(ax, legend, renderer) <= 0.002
    plt.close(fig)


def test_fixed_range_goes_above_instead_of_headroom():
    fig, ax = plt.subplots(figsize=(6, 4))
    x = np.linspace(0, 1, 50)
    ax.fill_between(x, 0, 1, label="band")
    ax.set_ylim(0, 1)  # e.g. --rangey
    legend = apply_legend_style(ax)
    place_legends(fig)
    renderer = fig.canvas.get_renderer()
    assert ax.get_ylim() == (0, 1)
    legend = _legends(ax)[0]
    assert legend.get_window_extent(renderer).y0 >= ax.bbox.y1 - 1
    plt.close(fig)


@pytest.mark.parametrize("loc", ["outside", "none", "lower left"])
def test_legend_loc_values(make_project, loc):
    make_project({"Spectra": _resonance()})
    figures = _figures()
    line.main(["--datafile", "Spectra", "-x", "Bin", "-y", "Counts", "--hue", "Sample", "--select", "Sample",
               "-s", "Background", "Signal", "--legend_loc", loc])
    ax = figures[0].axes[0]
    renderer = _drawn(figures[0])
    legends = _legends(ax)
    if loc == "none":
        assert legends == []
    elif loc == "outside":
        assert legends[0].get_window_extent(renderer).y0 >= ax.bbox.y1 - 1
    else:
        assert legends[0]._loc == Legend.codes["lower left"]


def test_legend_loc_rejects_unknown_values(make_project, capsys):
    make_project({"Spectra": _resonance()})
    with pytest.raises(SystemExit):
        line.main(["--datafile", "Spectra", "-x", "Bin", "-y", "Counts", "--legend_loc", "somewhere"])
    assert "--legend_loc must be one of" in capsys.readouterr().err
