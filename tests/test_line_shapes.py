"""line --plot_type fill and per-series styling from data columns (the mascot tutorial)."""

import numpy as np
import pandas as pd
import pytest
from matplotlib.colors import to_hex
from matplotlib.patches import Polygon

from plotipus import registry, style
from plotipus.kinds import line


@pytest.fixture
def shapes():
    t = np.linspace(0, 2 * np.pi, 50)
    return pd.DataFrame([
        {"X": 2 * np.cos(t), "Y": 2 * np.sin(t), "Part": "disc", "Mode": "fill", "Face": "#2fc4ee", "Edge": "none",
         "Width": 0.0, "Layer": "water"},
        {"X": np.cos(t), "Y": 0.5 * np.sin(t), "Part": "body", "Mode": "fill", "Face": "#9a6650", "Edge": "#2b1d18",
         "Width": 3.0, "Layer": "base"},
        {"X": np.array([-0.5, 0.5]), "Y": np.array([0.0, 0.1]), "Part": "stroke", "Mode": "line", "Face": "#633d31",
         "Edge": "none", "Width": 1.5, "Layer": "detail"},
    ])


def draw(make_project, frame, *argv):
    make_project({"Shapes": frame})
    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    line.main(["--datafile", "Shapes", "-x", "X", "-y", "Y", "--hue", "Part", "--no_legend", *argv])
    return figures[-1].axes[0]


def polygons(ax):
    return [p for p in ax.patches if isinstance(p, Polygon)]


def test_fill_with_colours_from_the_data(make_project, shapes):
    ax = draw(make_project, shapes, "--plot_type", "fill", "--plot_type_column", "Mode", "--color_column", "Face",
              "--edgecolor_column", "Edge", "--linewidth_column", "Width")
    disc, body = polygons(ax)
    assert to_hex(disc.get_facecolor()) == "#2fc4ee" and disc.get_linewidth() == 0
    assert to_hex(body.get_facecolor()) == "#9a6650" and to_hex(body.get_edgecolor()) == "#2b1d18"
    assert body.get_linewidth() == 3.0
    (stroke,) = ax.get_lines()  # the Mode=line row stays a line
    assert to_hex(stroke.get_color()) == "#633d31" and stroke.get_linewidth() == 1.5


def test_constant_face_and_edge_override_the_data(make_project, shapes):
    style.configure(roles={"paper": "#ffffff", "ink": "#111111"})
    ax = draw(make_project, shapes, "--plot_type", "fill", "--plot_type_column", "Mode", "--color_column", "Face",
              "--facecolor", "role:paper", "--edgecolor", "role:ink")
    assert all(to_hex(p.get_facecolor()) == "#ffffff" for p in polygons(ax))
    assert all(to_hex(p.get_edgecolor()) == "#111111" for p in polygons(ax))
    assert to_hex(ax.get_lines()[0].get_color()) == "#111111"  # strokes take the edge colour


def test_shapes_are_drawn_in_row_order(make_project, shapes):
    ax = draw(make_project, shapes, "--plot_type", "fill", "--color_column", "Face")
    assert [to_hex(p.get_facecolor()) for p in polygons(ax)] == ["#2fc4ee", "#9a6650", "#633d31"]


def test_axis_equal_and_off(make_project, shapes):
    ax = draw(make_project, shapes, "--plot_type", "fill", "--axis", "equal", "off")
    assert ax.get_aspect() == 1.0
    assert not ax.axison


def test_no_palette_warning_for_many_coloured_shapes(make_project, capsys):
    t = np.linspace(0, 2 * np.pi, 20)
    frame = pd.DataFrame([{"X": np.cos(t) + i, "Y": np.sin(t), "Part": f"p{i}", "Face": "#808080"} for i in range(15)])
    draw(make_project, frame, "--plot_type", "fill", "--color_column", "Face")
    assert "More categories" not in capsys.readouterr().out


def test_mapping_wins_over_the_data(make_project, shapes):
    style.configure(mappings={"recolour": {"disc": "#1f6fb2"}})
    ax = draw(make_project, shapes, "--plot_type", "fill", "--plot_type_column", "Mode", "--color_column", "Face",
              "--iterable_color_mapping", "recolour")
    disc, body = polygons(ax)
    assert to_hex(disc.get_facecolor()) == "#1f6fb2" and to_hex(body.get_facecolor()) == "#9a6650"
