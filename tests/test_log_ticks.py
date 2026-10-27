"""Log-axis tick labels (T12 follow-up): plain numbers on short ranges, 10^n
on long ones, and never "2x10^2" on minor ticks."""

import numpy as np
import pandas as pd
import pytest

from plotipus import registry
from plotipus.kinds import line
from plotipus.plot import LogTickFormatter, log_label_modes


def _figures():
    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    return figures


def _labels(axis):
    """The tick labels drawn inside the view, majors then minors."""
    low, high = sorted(axis.get_view_interval())
    found = []
    for ticker in (axis.major, axis.minor):
        locs = [v for v in ticker.locator() if low * (1 - 1e-9) <= v <= high * (1 + 1e-9)]
        found += [text for text in ticker.formatter.format_ticks(locs) if text]
    return found


def _plain(texts):
    return [t.replace(r"$\mathdefault{", "").replace("}$", "") for t in texts]


@pytest.fixture
def curve(make_project):
    x = np.geomspace(1e-3, 1e3, 40)
    make_project({"Curve": pd.DataFrame([{"X": x, "Y": x**2, "Sample": "a"}])})


def _line(*argv):
    figures = _figures()
    line.main(["--datafile", "Curve", "-x", "X", "-y", "Y", *argv])
    return figures[-1].axes[0]


def test_short_range_reads_as_plain_numbers(curve):
    ax = _line("--logx", "--rangex", "110", "600")
    assert isinstance(ax.xaxis.get_major_formatter(), LogTickFormatter)
    assert _plain(_labels(ax.xaxis)) == ["200", "300", "400", "600"]


def test_decades_within_the_plain_range(curve):
    ax = _line("--logx", "--rangex", "0.008", "1.6")
    assert _plain(_labels(ax.xaxis)) == ["0.01", "0.1", "1"]


def test_long_range_keeps_powers_of_ten(curve):
    ax = _line("--logx", "--logy")
    texts = _labels(ax.yaxis)
    assert texts and all("10^{" in t for t in texts)  # 1e-6 .. 1e6: sci
    assert len(_labels(ax.xaxis)) == len(set(_labels(ax.xaxis)))


def test_sci_mode_never_writes_a_minor_tick_as_a_power(curve):
    ax = _line("--logx", "--rangex", "110", "600", "--log_labels", "sci")
    texts = _labels(ax.xaxis)
    assert texts and not any(r"\times" in t for t in texts)
    ax = _line("--logx", "--rangex", "5", "300", "--log_labels", "sci")  # two labelled decades
    assert _plain(_labels(ax.xaxis)) == ["10^{1}", "10^{2}"]


def test_per_axis_modes_and_the_style_setting(curve, make_project, tmp_path):
    ax = _line("--logx", "--logy", "--rangex", "0.1", "100", "--rangey", "0.01", "1e4", "--log_labels", "x=sci")
    assert _plain(_labels(ax.xaxis)) == ["10^{-1}", "10^{0}", "10^{1}", "10^{2}"]
    assert _plain(_labels(ax.yaxis))[:2] == ["0.01", "0.1"]
    assert log_label_modes(["plain", "z=sci"]) == {"x": "plain", "y": "plain", "z": "sci"}
    (tmp_path / "style.json").write_text('{"plot_settings": {"log_labels": "sci"}}')
    x = np.geomspace(1e-3, 1e3, 40)
    make_project({"Curve": pd.DataFrame([{"X": x, "Y": x, "Sample": "a"}])}, 'style = ["style.json"]\n')
    ax = _line("--logx", "--rangex", "0.1", "100")
    assert _plain(_labels(ax.xaxis))[0] == "10^{-1}"


def test_bad_mode_is_an_error(curve):
    with pytest.raises(SystemExit):
        _line("--logx", "--log_labels", "x=fancy")


def test_lower_panel_axes(curve):
    figures = _figures()
    line.main(["--datafile", "Curve", "-x", "X", "-y", "Y", "--logx", "--rangex", "110", "600",
               "--lower", "column:Y"])
    lower = figures[-1].axes[1]
    assert _plain(_labels(lower.xaxis)) == ["200", "300", "400", "600"]


def test_colorbar_axis(make_project):
    from plotipus.kinds import map as map_kind

    grid = np.linspace(0, 1, 6)
    for (low, high), argv, expected in [((1, 1e4), [], ["1", "10", "100", "1000", "10000"]),
                                        ((10, 1e6), [], None),
                                        ((1, 1e4), ["--log_labels", "z=sci"], ["10^{0}", "10^{1}"])]:
        z = np.geomspace(low, high, 36).reshape(6, 6)
        make_project({"Grid": pd.DataFrame([{"X": grid, "Y": grid, "Z": z}])})
        figures = _figures()
        map_kind.main(["--datafile", "Grid", "-x", "X", "-y", "Y", "-z", "Z", "--logz", *argv])
        bar = next(ax for ax in figures[-1].axes if hasattr(ax, "_colorbar"))
        texts = _plain(_labels(bar.yaxis))
        if expected is None:
            assert texts and all("10^{" in t for t in texts)
        else:
            assert texts[:len(expected)] == expected


def test_hist_log_axis_and_scatter_colorbar(make_project):
    from plotipus.kinds import hist, scatter

    rng = np.random.default_rng(2)
    values = rng.uniform(120, 580, 500)
    make_project({"Ev": pd.DataFrame([{"E": values, "F": values[::-1], "C": rng.uniform(1, 1e3, 500), "Sample": "a"}])})
    figures = _figures()
    hist.main(["--datafile", "Ev", "-x", "E", "--logx"])
    ax = figures[-1].axes[0]
    assert isinstance(ax.xaxis.get_major_formatter(), LogTickFormatter)
    texts = _labels(ax.xaxis)
    assert texts and not any(r"\times" in t for t in texts)
    scatter.main(["--datafile", "Ev", "-x", "E", "-y", "F", "--colorby", "C", "--logz"])
    bar = next(ax for ax in figures[-1].axes if hasattr(ax, "_colorbar"))
    assert _plain(_labels(bar.yaxis))[:2] == ["10", "100"]


def test_classic_keeps_powers_of_ten(curve, make_project):
    x = np.geomspace(1e-3, 1e3, 40)
    make_project({"Curve": pd.DataFrame([{"X": x, "Y": x, "Sample": "a"}])}, 'style = ["classic"]\n')
    ax = _line("--logx", "--rangex", "0.1", "100")
    assert _plain(_labels(ax.xaxis)) == ["10^{-1}", "10^{0}", "10^{1}", "10^{2}"]
