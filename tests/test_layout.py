"""Measured layout (T13): every example command, drawn at a paper column and
at the default 8 in width, keeps its text inside the figure and its panels
aligned."""

import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg

import plotipus.project as project
from plotipus import registry, style
from plotipus.legacy import kind_module

REPO = Path(__file__).resolve().parents[1]
EXAMPLES = REPO / "examples"
PAPER = REPO / "docs" / "design" / "styles" / "paper"
COMMANDS = [line for line in (EXAMPLES / "input" / "plots" / "example_scripts.txt").read_text().splitlines()
            if line.strip() and not line.startswith("#")]


@pytest.fixture(scope="module")
def example_data(tmp_path_factory):
    """The example project's data, generated once into a scratch folder."""
    root = tmp_path_factory.mktemp("examples")
    shutil.copy(EXAMPLES / "make_data.py", root / "make_data.py")
    subprocess.run([sys.executable, "make_data.py"], cwd=root, check=True, capture_output=True)
    return root / "input" / "data"


def _project(tmp_path, monkeypatch, data, style_json):
    (tmp_path / "style.json").write_text(json.dumps(style_json))
    (tmp_path / "plotipus.toml").write_text(
        f'[project]\ndata_root = "{data.as_posix()}"\noutput = "output"\nstyle = ["style.json"]\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(project, "_PROJECT", None)


def _draw(command):
    """The saved figures of one example command."""
    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    try:
        kind, *argv = shlex.split(command)
        kind_module(kind).main(argv)
    finally:
        registry.figure_hooks.clear()
    save_dpi = plt.rcParams["savefig.dpi"]
    for fig in figures:
        FigureCanvasAgg(fig)  # closed figures lose their canvas
        if save_dpi != "figure":
            fig.set_dpi(float(save_dpi))  # text widths depend on the resolution
        fig.draw_without_rendering()
    return figures


def _outside(fig, tolerance=1.0):
    """Drawn boxes (panels with all their text, figure texts) that leave the figure."""
    renderer = fig.canvas.get_renderer()
    width, height = fig.bbox.width, fig.bbox.height
    boxes = [(ax.get_ylabel() or ax.get_xlabel() or "axes", ax.get_tightbbox(renderer))
             for ax in fig.axes if ax.get_visible()]
    boxes += [(t.get_text(), t.get_window_extent(renderer)) for t in [fig._suptitle, *fig.texts]
              if t is not None and t.get_visible() and t.get_text()]
    return [name for name, b in boxes if b is not None and (
        b.x0 < -tolerance or b.y0 < -tolerance or b.x1 > width + tolerance or b.y1 > height + tolerance)]


def _paper_style():
    paper = json.loads((PAPER / "style.json").read_text())
    paper["mplstyle"] = str(PAPER / "plotipus-paper.mplstyle")
    paper["plot_settings"]["figure_layout"].update(base_width=3.4, height=2.6)
    paper["mappings"] = json.loads((EXAMPLES / "style.json").read_text()).get("mappings", {})
    return paper


@pytest.mark.parametrize("command", COMMANDS, ids=[c.split("--output_suffix ")[-1] for c in COMMANDS])
def test_paper_column_keeps_text_inside_and_panels_aligned(command, example_data, tmp_path, monkeypatch):
    _project(tmp_path, monkeypatch, example_data, _paper_style())
    try:
        for fig in _draw(command):
            assert tuple(fig.get_size_inches())[1] == pytest.approx(2.6)
            assert _outside(fig) == []
            for ax in fig.axes:
                for other in ax.get_shared_x_axes().get_siblings(ax):
                    if other is not ax and other.get_visible():
                        assert other.get_position().x0 == pytest.approx(ax.get_position().x0)
    finally:
        style.reset()


def _title_crowded(fig, gap_px=2.0):
    """The figure title touches (or nearly touches) a panel's drawn box."""
    title = fig._suptitle
    if title is None or not title.get_text():
        return False
    renderer = fig.canvas.get_renderer()
    box = title.get_window_extent(renderer)
    return any(box.y0 - gap_px < b.y1 and box.x0 < b.x1 and b.x0 < box.x1
               for b in (ax.get_tightbbox(renderer) for ax in fig.axes if ax.get_visible()) if b is not None)


@pytest.mark.parametrize("command", COMMANDS, ids=[c.split("--output_suffix ")[-1] for c in COMMANDS])
def test_default_size_never_shrinks_the_panels(command, example_data, tmp_path, monkeypatch):
    """At the default 8x6 in the figure keeps its size, and the panels only
    shrink below the old fixed margins where the old layout left something
    outside the figure or crowded the title against the panels."""
    runs = {}
    for fixed in (True, False):
        _project(tmp_path, monkeypatch, example_data,
                 {"plot_settings": {"figure_layout": {"fixed_margins": fixed}}})
        try:
            runs[fixed] = [(tuple(fig.get_size_inches()),
                            sum(ax.get_position().width * ax.get_position().height for ax in fig.axes
                                if ax.get_visible() and not hasattr(ax, "_colorbar")),
                            bool(_outside(fig)) or _title_crowded(fig))
                           for fig in _draw(command)]
        finally:
            style.reset()
    for (old_size, old, old_broken), (new_size, new, _) in zip(runs[True], runs[False]):
        assert new_size == pytest.approx(old_size)
        if not old_broken:
            assert new >= old - 1e-9


def test_measured_layout_keeps_text_inside_at_default_size(example_data, tmp_path, monkeypatch):
    _project(tmp_path, monkeypatch, example_data, {})
    try:
        for command in COMMANDS:
            for fig in _draw(command):
                assert _outside(fig) == [] and not _title_crowded(fig), command
    finally:
        style.reset()


def test_fixed_margins_keep_the_old_geometry(example_data, tmp_path, monkeypatch):
    _project(tmp_path, monkeypatch, example_data, {"plot_settings": {"figure_layout": {"fixed_margins": True}}})
    try:
        fig = _draw(next(c for c in COMMANDS if c.endswith("--output_suffix errors")))[0]
        margins = style.figure_margins_inches
        assert fig.subplotpars.left == pytest.approx(margins["left"] / fig.get_figwidth())
        assert fig.subplotpars.bottom == pytest.approx(margins["bottom"] / fig.get_figheight())
    finally:
        style.reset()


def test_pointer_tick_labels_fit_without_growing_the_figure(example_data, tmp_path, monkeypatch):
    _project(tmp_path, monkeypatch, example_data, {})
    try:
        fig = _draw("line --datafile Distributions -x Bin -y Counts --hue Sample --select Distribution -s Gaussian "
                    "--plot_type step --ytick 100 --ytick_label threshold --xtick 1.5 --xtick_label '$x_0$'")[0]
        assert tuple(fig.get_size_inches()) == pytest.approx((8, 6))
        assert _outside(fig) == []
    finally:
        style.reset()


def test_font_sizes_write_axis_label_size():
    import matplotlib.pyplot as plt

    try:
        style.configure(font_sizes={"xlabelfontsize": "small"})
        assert plt.rcParams["axes.labelsize"] == "small"
    finally:
        style.reset()
    assert plt.rcParams["axes.labelsize"] == "x-large"


def test_title_sits_above_the_panels(example_data, tmp_path, monkeypatch):
    _project(tmp_path, monkeypatch, example_data, _paper_style() | {"plot_settings": {
        **_paper_style()["plot_settings"], "auto_title": True}})
    try:
        fig = _draw(COMMANDS[0])[0]
        renderer = fig.canvas.get_renderer()
        title = fig._suptitle.get_window_extent(renderer)
        panels = [ax.get_tightbbox(renderer) for ax in fig.axes if ax.get_visible()]
        assert title.y0 >= max(b.y1 for b in panels) - 0.5
        assert title.y1 <= fig.bbox.height
        centre = np.mean([min(ax.get_position().x0 for ax in fig.axes), max(ax.get_position().x1 for ax in fig.axes)])
        assert fig._suptitle.get_position()[0] == pytest.approx(centre)
    finally:
        style.reset()
