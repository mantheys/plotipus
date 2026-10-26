"""Experiment header and watermark (T17)."""

import json

import numpy as np
import pandas as pd
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import to_hex
from matplotlib.offsetbox import TextArea

from plotipus import header, registry, style
from plotipus.kinds import line


@pytest.fixture
def spectra():
    x = np.arange(0.5, 10, 1.0)
    return pd.DataFrame([{"Energy": x, "Counts": s * np.exp(-x / 3), "Sample": sample}
                         for sample, s in (("A", 1.0), ("B", 2.0))])


def _draw(*argv):
    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    line.main(["--datafile", "Spectra", "-x", "Energy", "-y", "Counts", "--hue", "Sample", *argv])
    fig = figures[-1]
    FigureCanvasAgg(fig)  # the saved figure was closed
    fig.draw_without_rendering()
    return fig


def _texts(box):
    """The TextAreas of a header box, depth first."""
    found, stack = [], [box]
    while stack:
        item = stack.pop()
        if isinstance(item, TextArea):
            found.append(item._text)
        stack.extend(reversed(item.get_children()))
    return found


def test_atlas_label_in_its_font_above_the_axes(make_project, spectra):
    make_project({"Spectra": spectra})
    fig = _draw("--experiment", "atlas", "--label_status", "Internal")
    ax = fig.axes[0]
    boxes = header.header_artists(ax, "above")
    assert len(boxes) == 1
    label, status = _texts(boxes[0])
    assert (label.get_text(), label.get_fontweight(), label.get_fontstyle()) == ("ATLAS", "bold", "italic")
    assert (status.get_text(), status.get_fontstyle()) == ("Internal", "normal")
    assert label.get_fontsize() > status.get_fontsize()
    renderer = fig.canvas.get_renderer()
    box = boxes[0].get_window_extent(renderer)
    assert box.y0 >= ax.bbox.y1 - 1  # above the axes
    assert box.x0 >= 0 and box.y1 <= fig.bbox.height and box.x1 <= fig.bbox.width  # inside the figure
    # The label and the status share a baseline.
    assert abs(label.get_window_extent(renderer).y0 - status.get_window_extent(renderer).y0) < 0.35 * label.get_fontsize()


def test_header_options_and_right_text(make_project, spectra):
    make_project({"Spectra": spectra})
    fig = _draw("--label", "plotipus", "--label_status", "Preliminary", "--label_right", "13.6 TeV")
    ax = fig.axes[0]
    left, right = header.header_artists(ax, "above")
    assert [t.get_text() for t in _texts(left)] == ["plotipus", "Preliminary"]
    assert [t.get_text() for t in _texts(right)] == ["13.6 TeV"]
    renderer = fig.canvas.get_renderer()
    assert right.get_window_extent(renderer).x1 == pytest.approx(ax.bbox.x1, abs=1.5)
    assert to_hex(_texts(left)[0].get_color()) == to_hex(style.role("ink"))


def test_inside_header_gets_headroom(make_project, spectra):
    make_project({"Spectra": spectra})
    fig = _draw("--experiment", "dune", "--label_status", "Preliminary")
    ax = fig.axes[0]
    box, = header.header_artists(ax, "inside")
    renderer = fig.canvas.get_renderer()
    from plotipus.plot import _Occupancy, axes_occupancy

    occupancy = _Occupancy(*axes_occupancy(ax, renderer, exclude=header.header_artists(ax)))
    assert occupancy.fraction(box.get_window_extent(renderer), pad=0) == 0


def test_diagonal_watermark_behind_the_data(make_project, spectra):
    make_project({"Spectra": spectra})
    fig = _draw("--watermark", "wip", "--watermark_style", "diagonal")
    ax = fig.axes[0]
    mark = next(t for t in ax.texts if t.get_text() == "Work In Progress")
    data = [a.get_zorder() for a in [*ax.lines, *ax.patches, *ax.collections]]
    assert data and mark.get_zorder() < min(data)
    assert 0 < mark.get_rotation() < 90


def test_corner_watermark_and_none(make_project, spectra):
    make_project({"Spectra": spectra}, '[header]\nwatermark = "preliminary"\n')
    fig = _draw()
    marks = header.header_artists(fig.axes[0], "inside")
    assert [t.get_text() for t in _texts(marks[0])] == ["Preliminary"]
    assert to_hex(_texts(marks[0])[0].get_color()) == to_hex(style.role("muted"))
    fig = _draw("--watermark", "none")
    assert not header.header_artists(fig.axes[0])


def test_paper_reminds_about_a_watermark(make_project, spectra, capsys, monkeypatch):
    monkeypatch.setattr(header, "_PAPER_REMINDED", False)
    make_project({"Spectra": spectra})
    _draw("--medium", "paper", "--watermark", "draft")
    assert "watermark 'Draft' is on in a paper figure" in capsys.readouterr().out


def test_project_header_and_experiment_in_the_style_list(make_project, spectra):
    make_project({"Spectra": spectra}, 'style = ["experiment-cms"]\n[header]\nlabel_status = "Simulation"\n')
    fig = _draw()
    left, = header.header_artists(fig.axes[0], "above")
    label, status = _texts(left)
    assert (label.get_text(), status.get_text(), status.get_fontstyle()) == ("CMS", "Simulation", "italic")
    from plotipus import palettes

    assert palettes.active == "petroff6"


def test_header_follows_the_medium(make_project, spectra):
    make_project({"Spectra": spectra})
    sizes = {}
    for medium in ("slides", "paper"):
        fig = _draw("--medium", medium, "--label", "X")
        sizes[medium] = _texts(header.header_artists(fig.axes[0])[0])[0].get_fontsize()
    assert sizes["slides"] == pytest.approx(14 * 1.3) and sizes["paper"] == pytest.approx(8 * 1.3)


def unverified_entries():
    """{preset: [notes]} of the "_unverified" entries of the experiment presets."""
    return {path.stem: json.loads(path.read_text()).get("_unverified", [])
            for path in sorted(style.EXPERIMENTS_DIR.glob("*.json"))}


@pytest.mark.parametrize("name", style.experiments())
def test_every_preset_loads(make_project, spectra, name):
    preset = json.loads((style.EXPERIMENTS_DIR / f"{name}.json").read_text())
    assert preset["_source"] and preset["header"]["label"]
    make_project({"Spectra": spectra})
    fig = _draw("--experiment", name, "--theme", "dark")
    assert header.header_artists(fig.axes[0])


def test_unverified_entries_are_listed():
    notes = unverified_entries()
    assert set(notes) == set(style.experiments())
    assert notes["dune"] == []  # from DUNE's own plot-style repository
    assert any("SSO" in note for note in notes["cms"])


def test_several_right_lines(make_project, spectra):
    make_project({"Spectra": spectra})
    fig = _draw("--experiment", "atlas", "--label_position", "inside", "--label_status", "2011 - 2012",
                "--label_right", "$\\sqrt{s}$ = 7 TeV", "$\\sqrt{s}$ = 8 TeV")
    box, = header.header_artists(fig.axes[0], "inside")
    texts = [t.get_text() for t in _texts(box)]
    assert texts == ["ATLAS", "2011 - 2012", "$\\sqrt{s}$ = 7 TeV", "$\\sqrt{s}$ = 8 TeV"]
    renderer = fig.canvas.get_renderer()
    lines = [t.get_window_extent(renderer) for t in _texts(box)]
    assert lines[0].y0 > lines[2].y1 - 1 and lines[2].y0 > lines[3].y1 - 1  # one line under another
    fig = _draw("--experiment", "cms", "--label_right", "line one", "line two")
    right = header.header_artists(fig.axes[0], "above")[1]
    a, b = [t.get_window_extent(renderer) for t in _texts(right)]
    assert a.x1 == pytest.approx(b.x1, abs=1.5)  # right-aligned above the axes
