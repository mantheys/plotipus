import numpy as np
import pandas as pd
import pytest

from plotipus import style
from plotipus.intervals import garwood
from plotipus.kinds import map as map_kind
from plotipus.legacy import translate


def _points():
    rng = np.random.default_rng(0)
    x = rng.normal(size=500)
    return pd.DataFrame([{"Variable": "a", "X": x, "Y": x + rng.normal(scale=0.3, size=500)}])


def _maps():
    xs, ys = np.linspace(0, 1, 30), np.linspace(0, 2, 40)
    xx, yy = np.meshgrid(xs, ys)
    rows = []
    for config, (cx, cy) in {"one": (0.4, 1.0), "two": (0.6, 1.1)}.items():
        chi2 = ((xx - cx) / 0.1) ** 2 + ((yy - cy) / 0.2) ** 2
        rows.append({"Config": config, "Name": "s", "Variable": "p", "XGrid": xs, "YGrid": ys, "ZGrid": chi2})
    return pd.DataFrame(rows)


def test_hist2d_points(make_project):
    out = make_project({"Points": _points()})
    map_kind.main(["--datafile", "Points", "-x", "X", "-y", "Y", "--diagonal", "--norm", "vertical"])
    assert [p.name for p in out.iterdir()] == ["points_x_y_hist2d.png"]


def test_integer_bins_and_normalisation():
    assert np.allclose(map_kind.integer_bin_edges(0, 2), [-0.5, 0.5, 1.5, 2.5])
    h = np.array([[1.0, 3.0], [0.0, 0.0]])
    assert np.allclose(map_kind.normalize_hist2d(h, "vertical"), [[0.25, 0.75], [0.0, 0.0]])
    assert np.isclose(map_kind.normalize_hist2d(h, "global").sum(), 1)


def test_image_mode(make_project):
    grid = _maps().iloc[:1].rename(columns={"ZGrid": "Z"})
    out = make_project({"Grid": grid})
    map_kind.main(["--datafile", "Grid", "-x", "XGrid", "-y", "YGrid", "-z", "Z", "--logz", "--output_suffix", "img.png"])
    assert len(list(out.iterdir())) == 1


def test_contours_combined_with_palette(make_project):
    out = make_project({"one_s_Maps": _maps()[:1], "two_s_Maps": _maps()[1:]})
    map_kind.main([
        "--datafile", "Maps", "--configs", "one", "two", "--names", "s", "-x", "XGrid", "-y", "YGrid",
        "-z", "ZGrid", "--contour", "--combine_op", "squared_sum", "--fill_contours", "--combined_color", "cycle",
        "--contour_smoothing_sigma", "1", "--filename_select", "fill_contours",
    ])
    names = [p.name for p in out.iterdir()]
    assert names == ["maps_one_two_s_xgrid_ygrid_zgrid_squared_sum_fill_contours_contour.png"]


def test_palette_from_style_mapping():
    from plotipus import style

    style.configure(mappings={"bands": ["red", "rgb(0,0,255)"]})
    try:
        assert map_kind.band_hues("bands", 3)[:2] == ["red", (0.0, 0.0, 1.0)]
        assert map_kind.band_hues("black", 2) == ["black", "black"]
    finally:
        style.reset()


def test_legacy_contour_translation():
    kind, argv = translate(["scripts/script_compare_contour.py", "--datafile", "M", "-x", "a", "-y", "b", "-z", "c",
                            "--operation", "squared_sum", "--combined_color", "dune"])
    assert kind == "map"
    assert argv[argv.index("--combine_op") + 1] == "squared_sum"
    assert argv[argv.index("--combined_color") + 1] == "cycle"
    assert "--contour" in argv and argv[-1] == "contour.png"
    assert argv[argv.index("--contour_dof") + 1] == "1"


# --- Confidence contours (T02) ----------------------------------------------------------


def _capture():
    from plotipus import registry

    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    return figures


def _contour(make_project, *extra, frames=None):
    make_project(frames or {"Maps": _maps()[:1]})
    figures = _capture()
    map_kind.main(["--datafile", "Maps", "-x", "XGrid", "-y", "YGrid", "-z", "ZGrid", "--contour", *extra])
    return figures[0].axes[0]


def _legend(ax):
    legend = ax.get_legend()
    return [t.get_text() for t in legend.get_texts()], legend.legend_handles


def test_contour_levels_dof():
    assert np.allclose(map_kind.contour_levels([1, 2, 3], "sigma_probability", 1), [1, 4, 9], atol=0.01)
    assert np.allclose(map_kind.contour_levels([1, 2, 3], "sigma_probability", 2), [2.30, 6.18, 11.83], atol=0.01)
    assert map_kind.contour_levels([1, 2, 3], "z_values", 2) == [1, 2, 3]


def test_contour_labels():
    levels = map_kind.contour_levels([1, 2, 3], "sigma_probability", 2)
    assert map_kind.sigma_labels(levels, [1, 2, 3], "sigma_probability", 2, "cl") == ["68.3% CL", "95.4% CL", "99.7% CL"]
    assert map_kind.sigma_labels(levels, [1, 2, 3], "sigma_probability", 2, "sigma")[0] == "$1\\sigma$ (2 dof)"
    assert map_kind.sigma_labels([1, 4, 9], [1, 2, 3], "sigma_probability", 1, "sigma") == [
        "$1\\sigma$", "$2\\sigma$", "$3\\sigma$"]
    assert map_kind.coverage_label(5) == "99.9999% CL"


def test_contour_lines_levels_and_legend(make_project):
    ax = _contour(make_project)
    lines = [c for c in ax.collections if type(c).__name__ == "QuadContourSet" and not c.filled]
    assert np.allclose(lines[0].levels, [2.30, 6.18, 11.83], atol=0.01)
    texts, handles = _legend(ax)
    assert texts == ["68.3% CL", "95.4% CL", "99.7% CL", "Best fit"]
    styles = [h.get_linestyle() for h in handles[:3]]
    assert len(set(styles)) == 3


def test_filled_contours_graded_from_best_fit(make_project):
    from matplotlib.colors import to_rgb

    ax = _contour(make_project, "--fill_contours")
    filled = [c for c in ax.collections if type(c).__name__ == "QuadContourSet" and c.filled][0]
    assert filled.levels[0] == -np.inf and len(filled.levels) == 4  # outside the last level: unfilled
    lightness = [np.mean(to_rgb(c)) for c in filled.get_facecolor()]
    assert lightness == sorted(lightness) and len(set(np.round(lightness, 3))) == 3
    texts, handles = _legend(ax)
    assert texts[:3] == ["68.3% CL", "95.4% CL", "99.7% CL"]
    swatches = {(tuple(np.round(h.get_facecolor(), 3)), str(h.get_linestyle())) for h in handles[:3]}
    assert len(swatches) == 3


def _best_fit(ax):
    from matplotlib.container import ErrorbarContainer

    return [c for c in ax.containers if isinstance(c, ErrorbarContainer)]


def test_best_fit_point_with_profile_errors(make_project):
    """On a Delta-chi2 map the best fit is an ink point with its 1-sigma profile intervals (Delta-chi2 <= 1
    projected on each axis): here sigma_x = 0.1, sigma_y = 0.2."""
    from matplotlib.colors import to_hex

    ax = _contour(make_project)
    marks = _best_fit(ax)
    assert len(marks) == 1
    point = marks[0].lines[0]
    assert np.isclose(point.get_xdata()[0], 0.4, atol=0.02) and np.isclose(point.get_ydata()[0], 1.0, atol=0.03)
    assert to_hex(point.get_color()) == to_hex(style.role("ink"))
    bx, by, xerr, yerr = map_kind.best_fit_point(*_maps()[["XGrid", "YGrid", "ZGrid"]].iloc[0])
    assert sum(xerr) == pytest.approx(0.2, abs=0.02) and sum(yerr) == pytest.approx(0.4, abs=0.04)
    texts, _ = _legend(ax)
    assert texts[-1] == "Best fit"
    assert not _best_fit(_contour(make_project, "--no_best_fit"))


def test_best_fit_cross_on_z_maps(make_project):
    ax = _contour(make_project, "--contour_level_mode", "z_values", "--contour_sigmas", "2", "4")
    assert [line for line in ax.get_lines() if line.get_marker() == "+"] and not _best_fit(ax)


def test_background_off_by_default_and_clipped(make_project):
    ax = _contour(make_project)
    assert len(ax.figure.axes) == 1  # no colorbar
    ax = _contour(make_project, "--background", "all")
    colorbar = ax.figure.axes[1]
    assert colorbar.get_ylabel() == r"$\Delta\chi^2$"
    assert np.isclose(ax.collections[0].norm.vmax, 11.83, atol=0.01)


def test_old_behaviour_options(make_project):
    ax = _contour(make_project, "--contour_dof", "1", "--contour_label", "sigma", "--background", "all")
    lines = [c for c in ax.collections if type(c).__name__ == "QuadContourSet"]
    assert np.allclose(lines[0].levels, [1, 4, 9])
    assert _legend(ax)[0][:3] == ["$1\\sigma$", "$2\\sigma$", "$3\\sigma$"]


def test_style_contours_section(make_project):
    from plotipus import style

    style.configure(contours={"dof": 1, "label": "sigma", "linestyles": ["-"]})
    ax = _contour(make_project)
    lines = [c for c in ax.collections if type(c).__name__ == "QuadContourSet"]
    assert np.allclose(lines[0].levels, [1, 4, 9])
    texts, handles = _legend(ax)
    assert texts[0] == "$1\\sigma$" and {h.get_linestyle() for h in handles[:3]} == {"-"}
    ax = _contour(make_project, "--contour_dof", "2")  # the CLI overrides the style
    assert np.allclose([c for c in ax.collections if type(c).__name__ == "QuadContourSet"][0].levels[0], 2.30, atol=0.01)


def test_dof_notice_once(make_project, monkeypatch, capsys):
    from plotipus import style

    monkeypatch.setattr(map_kind, "_NOTICES_SHOWN", set())
    monkeypatch.delenv("PLOTIPUS_NOTICE_DIR", raising=False)
    _contour(make_project)
    _contour(make_project)
    assert capsys.readouterr().out.count("now use 2 dof") == 1
    monkeypatch.setattr(map_kind, "_NOTICES_SHOWN", set())
    _contour(make_project, "--contour_dof", "2")
    style.configure(contours={"dof": 2})
    _contour(make_project)
    assert "now use 2 dof" not in capsys.readouterr().out


def test_several_maps_legend(make_project):
    frames = {"one_s_Maps": _maps()[:1], "two_s_Maps": _maps()[1:]}
    ax = _contour(make_project, "--configs", "one", "two", "--names", "s", "--fill_contours", frames=frames)
    texts, handles = _legend(ax)
    # One entry per map (its colour), then one per level (its line style).
    assert texts[-3:] == ["68.3% CL", "95.4% CL", "99.7% CL"] and len(texts) == 5
    assert handles[0].get_edgecolor() != handles[1].get_edgecolor()
    assert len(_best_fit(ax)) == 2  # one best fit per map, in its colour; no "Best fit" entry


def test_contour_shapes_and_points(make_project):
    from matplotlib.colors import to_hex
    from matplotlib.patches import Rectangle

    ax = _contour(make_project, "--line", "0", "0", "1", "2", "--line", "0", "2", "1", "0", "--square", "0.1", "0.2",
                  "0.3", "0.6", "--point", "0.4", "1.0", "--horizontal", "1")
    segments = [line for line in ax.get_lines() if list(line.get_ydata()) in ([0, 2], [2, 0])]
    assert len(segments) == 2 and all(to_hex(line.get_color()) == "#000000" for line in segments)
    assert [p for p in ax.patches if isinstance(p, Rectangle) and np.isclose(p.get_width(), 0.2)]
    assert to_hex(ax.collections[-1].get_facecolor()[0]) == "#000000"  # the --point marker
    assert ax.get_xlim() == (0.0, 1.0) and ax.get_ylim() == (0.0, 2.0)  # the grid keeps the frame


def test_contour_overlays_white_on_full_image(make_project):
    from matplotlib.colors import to_hex

    ax = _contour(make_project, "--background", "all", "--rangez", "0", "20", "--line", "0", "0", "1", "2")
    segment = [line for line in ax.get_lines() if list(line.get_ydata()) == [0, 2]][0]
    assert to_hex(segment.get_color()) == "#ffffff"


def test_contour_overlays_above_fills(make_project):
    ax = _contour(make_project, "--fill_contours", "--line", "0", "0", "1", "2", "--horizontal", "1")
    fills = max(c.get_zorder() for c in ax.collections if type(c).__name__ == "QuadContourSet")
    best_fit = _best_fit(ax)[0].lines[0].get_zorder()
    overlays = [line for line in ax.get_lines() if list(line.get_ydata()) in ([0, 2], [1, 1])]
    assert len(overlays) == 2 and all(fills < line.get_zorder() < best_fit for line in overlays)


# --- Colorbars (T09) -----------------------------------------------------------------


def _two_samples():
    rng = np.random.default_rng(1)
    rows = []
    for sample, n in (("signal", 400), ("background", 4000)):
        x = rng.uniform(0, 10, n)
        rows.append({"Sample": sample, "X": x, "Y": x + rng.normal(scale=1.0, size=n)})
    return pd.DataFrame(rows)


def _render(make_project, frame, *argv):
    from plotipus import registry

    make_project({"Events": frame})
    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    map_kind.main(["--datafile", "Events", "-x", "X", "-y", "Y", "--iterable", "Sample", *argv])
    fig = figures[0]
    colorbars = [ax._colorbar for ax in fig.axes if hasattr(ax, "_colorbar")]
    panels = [ax for ax in fig.axes if not hasattr(ax, "_colorbar") and ax.collections]
    return colorbars, [ax.collections[0] for ax in panels]


def test_shared_colorbar_and_norm(make_project):
    colorbars, meshes = _render(make_project, _two_samples(), "--logz")
    assert len(colorbars) == 1 and colorbars[0].ax.get_ylabel() == "Counts"
    assert len(meshes) == 2 and meshes[0].norm is meshes[1].norm
    smallest = min(m.get_array().compressed().min() for m in meshes)
    assert meshes[0].norm.vmin == smallest > 0
    assert meshes[0].norm.vmax == max(m.get_array().max() for m in meshes)


def test_each_colorbar_labelled(make_project):
    colorbars, meshes = _render(make_project, _two_samples(), "--colorbar", "each", "--labelz", "Events")
    assert [c.ax.get_ylabel() for c in colorbars] == ["Events", "Events"]
    assert meshes[0].norm is not meshes[1].norm


def test_norm_defaults_to_one_colorbar_per_panel(make_project):
    colorbars, _ = _render(make_project, _two_samples(), "--norm", "vertical")
    assert [c.ax.get_ylabel() for c in colorbars] == ["Normalized Counts (Columns)"] * 2


def test_empty_bins_masked(make_project):
    for argv in (["--logz"], []):
        _, meshes = _render(make_project, _two_samples(), *argv)
        values = meshes[0].get_array()
        assert np.ma.is_masked(values)
        assert values.compressed().min() > 0


def test_colorbar_geometry(make_project):
    colorbars, meshes = _render(make_project, _two_samples(), "--colorbar", "each")
    fig = colorbars[0].ax.figure
    for colorbar, mesh in zip(colorbars, meshes):
        panel = mesh.axes.get_position()
        bar = colorbar.ax.get_position()
        assert np.isclose(bar.height, panel.height)
        assert 0.035 < bar.width / panel.width < 0.05
        # Ticks and label stay inside the figure.
        assert colorbar.ax.get_tightbbox().transformed(fig.transFigure.inverted()).x1 <= 1


def test_contour_backgrounds_share_a_colorbar(make_project):
    from plotipus import registry

    make_project({"Maps": _maps()})
    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    map_kind.main(["--datafile", "Maps", "-x", "XGrid", "-y", "YGrid", "-z", "ZGrid", "--contour",
                   "--iterable", "Config", "--background", "first"])
    colorbars = [ax._colorbar for ax in figures[0].axes if hasattr(ax, "_colorbar")]
    panels = [ax for ax in figures[0].axes if not hasattr(ax, "_colorbar") and ax.get_visible()]
    assert len(panels) == 2
    assert len(colorbars) == 1 and colorbars[0].ax.get_ylabel() == r"$\Delta\chi^2$"


def test_variable_column_panels(make_project):
    """--variable_column works for map too: one titled panel per value of that column."""
    from plotipus import registry

    rng = np.random.default_rng(1)
    frame = pd.DataFrame([{"Shape": shape, "X": x, "Y": x + rng.normal(scale=0.2, size=x.size)}
                          for shape, x in (("Wide", rng.normal(size=400)), ("Narrow", rng.normal(scale=0.3, size=400)))])
    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    make_project({"Shapes": frame})
    map_kind.main(["--datafile", "Shapes", "-x", "X", "-y", "Y", "--variable_column", "Shape",
                   "--variables", "Wide", "Narrow"])
    titles = [ax.get_title() for ax in figures[-1].axes if ax.get_title()]
    assert titles == ["Wide", "Narrow"]


def test_contour_panels_follow_the_selection(make_project):
    """Hue values outside the --select rows add no empty contour panels."""
    from plotipus import registry

    frame = _maps().assign(Kind=["fit", "fit"], Sample=["a", "b"])
    extra = frame.iloc[:1].assign(Kind="other", Sample="c")
    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    make_project({"Maps": pd.concat([frame, extra], ignore_index=True)})
    map_kind.main(["--datafile", "Maps", "-x", "XGrid", "-y", "YGrid", "-z", "ZGrid", "--contour",
                   "--select", "Kind", "-s", "fit", "--iterable", "Sample"])
    assert len([ax for ax in figures[-1].axes if ax.get_title()]) == 2


def test_sample_regions_hold_their_fractions():
    """The thresholds keep the densest bins until each fraction of the entries is reached."""
    from plotipus.kinds.map import sample_region_thresholds

    density = np.array([[1.0, 2.0], [3.0, 4.0]])  # total 10
    assert sample_region_thresholds(density, [0.4, 0.7, 1.0]) == [4.0, 3.0, 1.0]


def test_contour_without_z_draws_sample_regions(make_project):
    """map --contour without -z: the 2D histogram with one outline and legend entry per sigma."""
    from matplotlib.contour import ContourSet

    from plotipus import registry

    rng = np.random.default_rng(3)
    xy = rng.multivariate_normal([0, 0], [[1, 0.5], [0.5, 1]], 20000)
    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    make_project({"Points": pd.DataFrame([{"X": xy[:, 0], "Y": xy[:, 1]}])})
    map_kind.main(["--datafile", "Points", "-x", "X", "-y", "Y", "--contour", "--bins", "40"])
    ax = figures[-1].axes[0]
    assert len([c for c in ax.collections if isinstance(c, ContourSet)]) == 3
    assert [t.get_text() for t in ax.get_legend().get_texts()] == ["68.3%", "95.4%", "99.7%"]


def test_identical_contour_legends_drawn_once(make_project):
    """Panels whose confidence-level legends are the same show it once, in the last panel."""
    from plotipus import registry

    frame = _maps().assign(Sample=["Data", "Simulation"])
    make_project({"Scan": frame})
    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    map_kind.main(["--datafile", "Scan", "-x", "XGrid", "-y", "YGrid", "-z", "ZGrid", "--iterable", "Sample",
                   "--contour", "--fill_contours"])
    axes = [ax for ax in figures[0].axes if ax.get_title()]
    assert len(axes) == 2
    assert [ax.get_legend() is not None for ax in axes] == [False, True]


def test_legend_panels_keep_differing_legends():
    from matplotlib.patches import Patch

    same = [[Patch(color="C0", label="68%")], [Patch(color="C0", label="68%")]]
    assert map_kind.legend_panels(same) == [1]
    differ = [[Patch(color="C0", label="68%")], [Patch(color="C1", label="68%")]]
    assert map_kind.legend_panels(differ) == [0, 1]
    assert map_kind.legend_panels([[], same[0]]) == [1]


def test_panels_compact_by_default(make_project):
    """Several panels share one y range; only the first shows the y label and tick labels."""
    frames = {"Points": pd.concat([_points().assign(Sample="a"), _points().assign(Sample="b")])}
    make_project(frames)
    figures = _capture()
    map_kind.main(["--datafile", "Points", "-x", "X", "-y", "Y", "--iterable", "Sample"])
    map_kind.main(["--datafile", "Points", "-x", "X", "-y", "Y", "--iterable", "Sample", "--no-compact"])
    first, second = figures[0].axes[:2]
    assert first.get_ylim() == second.get_ylim() and second.get_ylabel() == ""
    assert second.yaxis.get_tick_params(which="major")["labelleft"] is False
    assert figures[1].axes[1].get_ylabel() != ""


def test_wrapped_panels_keep_y_labels_in_the_first_column(make_project):
    """Three panels wrap at two columns on slides (rule L3): the panel that
    starts the second row keeps its y label and tick labels."""
    make_project({"Points": pd.concat([_points().assign(Sample=s) for s in "abc"])})
    figures = _capture()
    map_kind.main(["--datafile", "Points", "-x", "X", "-y", "Y", "--iterable", "Sample"])
    a, b, c = [ax for ax in figures[0].axes if ax.get_visible() and ax.get_label() != "<colorbar>"][:3]
    assert c.get_subplotspec().rowspan.start == 1 and c.get_subplotspec().colspan.start == 0
    assert a.get_ylim() == b.get_ylim() == c.get_ylim()
    assert c.get_ylabel() != "" and b.get_ylabel() == ""
    assert c.yaxis.get_tick_params(which="major")["labelleft"] is not False


def test_diagonal_spans_the_matched_axes(make_project):
    """--diagonal crosses the whole panel, also where --matchx widens it past
    this panel's data."""
    from matplotlib.lines import AxLine

    rng = np.random.default_rng(2)
    frame = pd.DataFrame([{"Sample": s, "X": x, "Y": x + rng.normal(scale=0.3, size=x.size)}
                          for s, x in (("narrow", rng.uniform(0, 4, 500)), ("wide", rng.uniform(0, 10, 500)))])
    from plotipus import registry

    make_project({"Events": frame})
    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    map_kind.main(["--datafile", "Events", "-x", "X", "-y", "Y", "--iterable", "Sample", "--diagonal", "--matchx"])
    panels = [ax for ax in figures[0].axes if not hasattr(ax, "_colorbar") and ax.collections]
    for ax in panels:
        assert [l for l in ax.get_lines() if isinstance(l, AxLine)]


# --- T22.8: inline contour labels -------------------------------------------------------


def test_contour_labels_on_the_lines(make_project):
    ax = _contour(make_project, "--contour_labels")
    texts = {t.get_text() for t in ax.texts}
    assert texts & {"68.3% CL", "95.4% CL", "99.7% CL"}
    legend = ax.get_legend()
    assert legend is None or "68.3% CL" not in [t.get_text() for t in legend.get_texts()]


def test_contour_labels_keep_one_entry_per_map(make_project):
    frames = {"one_s_Maps": _maps()[:1], "two_s_Maps": _maps()[1:]}
    ax = _contour(make_project, "--configs", "one", "two", "--names", "s", "--contour_labels", frames=frames)
    texts, _ = _legend(ax)
    assert len(texts) == 2 and "68.3% CL" not in texts


# --- T22.3: annotated, categorical and normalised grids; colour scales ---------------------


def _confusion():
    names = np.array(["cat", "dog", "bird"])
    counts = np.array([[50.0, 3, 2], [5, 40, 10], [1, 8, 45]])
    return pd.DataFrame([{"Pred": names, "True_": names, "Count": counts}])


def _grid(make_project, frame, *extra):
    make_project({"Grid": frame})
    figures = _capture()
    map_kind.main(["--datafile", "Grid", "-x", "Pred", "-y", "True_", "-z", "Count", *extra])
    return figures[0]


def test_confusion_matrix_names_norm_annotate(make_project):
    fig = _grid(make_project, _confusion(), "--norm", "horizontal", "--annotate", ".0%", "--matrix")
    ax = fig.axes[0]
    assert [t.get_text() for t in ax.get_xticklabels()] == ["cat", "dog", "bird"]
    assert [t.get_text() for t in ax.get_yticklabels()] == ["cat", "dog", "bird"]
    assert ax.get_ylim()[0] > ax.get_ylim()[1]  # the first row at the top
    texts = {(t.get_position(), t.get_text()) for t in ax.texts}
    assert ((0.0, 0.0), "91%") in texts and ((1.0, 1.0), "73%") in texts
    rows = np.asarray(ax.collections[0].get_array()).reshape(3, 3)
    assert np.allclose(rows.sum(axis=1), 1)  # each row sums to 1
    light, dark = [t for t in ax.texts if t.get_text() in ("5%", "91%")]
    colours = {t.get_text(): t.get_color() for t in (light, dark)}
    from plotipus import style

    assert colours["91%"] == style.role("paper") and colours["5%"] == style.role("ink")


def test_numeric_grid_annotated_without_categories(make_project):
    frame = pd.DataFrame([{"Pred": np.arange(2.0), "True_": np.arange(2.0), "Count": np.array([[1.0, 2], [3, 4]])}])
    ax = _grid(make_project, frame, "--annotate").axes[0]
    assert sorted(t.get_text() for t in ax.texts) == ["1", "2", "3", "4"]
    assert ax.get_ylim()[0] < ax.get_ylim()[1]


def test_power_scale_zunder_and_no_colorbar(make_project):
    from matplotlib.colors import PowerNorm

    frame = pd.DataFrame([{"Pred": np.arange(3.0), "True_": np.arange(2.0),
                           "Count": np.array([[1.0, 10, 100], [1000, 0.5, 50]])}])
    fig = _grid(make_project, frame, "--zpower", "0.5", "--zmin", "1", "--zunder", "black", "--colorbar", "none",
                "--cmap", "magma")
    mesh = fig.axes[0].collections[0]
    assert isinstance(mesh.norm, PowerNorm) and mesh.norm.gamma == 0.5 and mesh.norm.vmin == 1
    assert mesh.get_cmap().name.startswith("magma")
    assert tuple(mesh.get_cmap().get_under()) == (0.0, 0.0, 0.0, 1.0)
    assert len(fig.axes) == 1  # no colorbar


def test_power_scale_colorbar_ticks_at_decades(make_project):
    frame = pd.DataFrame([{"Pred": np.arange(3.0), "True_": np.arange(2.0),
                           "Count": np.array([[1.0, 10, 100], [1000, 2, 50]])}])
    fig = _grid(make_project, frame, "--zpower", "0.5", "--zmin", "1")
    (cbar,) = [a for a in fig.axes if hasattr(a, "_colorbar")]
    assert [t.get_text() for t in cbar.get_yticklabels()] == ["1", "10", "100", "1000"]


def test_hist2d_cmap_and_log_axes(make_project):
    rng = np.random.default_rng(4)
    make_project({"Points": pd.DataFrame([{"X": rng.uniform(1, 100, 500), "Y": rng.uniform(1, 100, 500)}])})
    figures = _capture()
    map_kind.main(["--datafile", "Points", "-x", "X", "-y", "Y", "--cmap", "cividis", "--logx", "--logy"])
    ax = figures[0].axes[0]
    assert ax.collections[0].get_cmap().name.startswith("cividis")
    assert ax.get_xscale() == "log" and ax.get_yscale() == "log"


def test_contour_labels_at_given_positions_with_leaders(make_project):
    ax = _contour(make_project, "--contour_label_pos", "0.1", "0.2", "0.3", "0.4", "0.5", "0.6",
                  "--contour_label_leader")
    texts = {t.get_text(): t.get_position() for t in ax.texts}
    assert texts["68.3% CL"] == (0.1, 0.2) and texts["99.7% CL"] == (0.5, 0.6)
    leaders = [t for t in ax.texts if type(t).__name__ == "Annotation" and t.arrow_patch is not None]
    assert len(leaders) == 3 and ax.get_legend() is None or "68.3% CL" not in [
        t.get_text() for t in ax.get_legend().get_texts()]


# --- Hexbin and corner plots (T22.9) ---------------------------------------------------


def _hexbin(make_project, *argv, frame=None):
    make_project({"Events": frame if frame is not None else _two_samples()})
    figures = _capture()
    map_kind.main(["--datafile", "Events", "-x", "X", "-y", "Y", "--map_type", "hexbin", *argv])
    return figures


def test_hexbin_counts_and_shared_log_colorbar(make_project):
    from matplotlib.collections import PolyCollection
    from matplotlib.colors import LogNorm

    (fig,) = _hexbin(make_project, "--iterable", "Sample", "--logz", "--bins", "20")
    panels = [ax for ax in fig.axes if not hasattr(ax, "_colorbar")]
    hexes = [ax.collections[0] for ax in panels]
    assert all(isinstance(h, PolyCollection) for h in hexes)
    # Every point lands in one hexagon; empty hexagons are not drawn.
    assert sorted(h.get_array().sum() for h in hexes) == [400, 4000]
    assert all(h.get_array().min() >= 1 for h in hexes)
    assert isinstance(hexes[0].norm, LogNorm) and hexes[0].norm is hexes[1].norm
    (cbar,) = [ax for ax in fig.axes if hasattr(ax, "_colorbar")]
    assert cbar.get_ylabel() == "Counts"


def test_hexbin_global_norm_and_density(make_project):
    frame = _two_samples().iloc[1:]
    (fig,) = _hexbin(make_project, "--norm", "global", frame=frame)
    assert np.isclose(fig.axes[0].collections[0].get_array().sum(), 1)
    (fig,) = _hexbin(make_project, "--density", "--bins", "10", frame=frame)
    hexes = fig.axes[0].collections[0]
    x, y = frame["X"].iloc[0], frame["Y"].iloc[0]
    # Hexagons of half a lattice cell: the density integrates to one.
    area = (x.max() - x.min()) / 10 * (y.max() - y.min()) / int(10 / np.sqrt(3)) / 2
    assert np.isclose(hexes.get_array().sum() * area, 1, rtol=0.02)
    assert fig.axes[1].get_ylabel() == "Density"


def test_hexbin_refuses_row_norms(make_project, capsys):
    assert _hexbin(make_project, "--norm", "vertical") == []
    assert "hexbin" in capsys.readouterr().out


def _corner_frame():
    rng = np.random.default_rng(5)
    a = rng.normal(10, 2, 3000)
    b = a + rng.normal(0, 1, 3000)
    return pd.DataFrame([{"Sample": "s", "A": a, "B": b, "N": rng.poisson(np.clip(b, 0, None))}])


def _corner(make_project, *argv, config=""):
    make_project({"Events": _corner_frame()}, config=config)
    figures = _capture()
    map_kind.main(["--datafile", "Events", "--corner", "A", "B", "N", *argv])
    return figures


def test_corner_grid_layout_and_labels(make_project):
    (fig,) = _corner(make_project, "--corner_labels", "a (cm)", "b (cm)")
    cbars = [ax for ax in fig.axes if hasattr(ax, "_colorbar")]
    panels = [ax for ax in fig.axes if ax not in cbars]
    assert len(panels) == 6 and len(cbars) == 1  # lower triangle and diagonal; upper triangle empty
    grid = {(ax.get_subplotspec().rowspan.start, ax.get_subplotspec().colspan.start): ax for ax in panels}
    assert set(grid) == {(r, c) for r in range(3) for c in range(r + 1)}
    # Labels on the outer panels only; the missing label falls back to the column name.
    assert [grid[2, c].get_xlabel() for c in range(3)] == ["a (cm)", "b (cm)", "N"]
    assert [grid[r, 0].get_ylabel() for r in range(3)] == ["Counts", "b (cm)", "N"]
    assert grid[1, 1].get_xlabel() == grid[2, 1].get_ylabel() == ""
    assert not any(t.get_visible() and t.get_text() for t in grid[1, 0].get_xticklabels())
    assert not any(t.get_visible() and t.get_text() for t in grid[2, 1].get_yticklabels())
    # x shared down each column (with its diagonal), y along each row of 2D panels.
    assert grid[0, 0].get_xlim() == grid[1, 0].get_xlim() == grid[2, 0].get_xlim()
    assert grid[1, 1].get_xlim() == grid[2, 1].get_xlim()
    assert grid[2, 0].get_ylim() == grid[2, 1].get_ylim() == grid[2, 2].get_xlim()
    # Every panel keeps the proportions of one plot.
    from plotipus.plot import get_common_figsize

    width, height = get_common_figsize()
    box = grid[1, 0].get_position()
    fig_w, fig_h = fig.get_size_inches()
    assert np.isclose(fig_w / fig_h, width / height)
    assert np.isclose(box.width * fig_w / (box.height * fig_h), width / height, rtol=0.15)


def test_corner_diagonal_counts_with_errors_and_shared_colour_scale(make_project):
    (fig,) = _corner(make_project, "--logz", "--bins", "15")
    panels = [ax for ax in fig.axes if not hasattr(ax, "_colorbar")]
    grid = {(ax.get_subplotspec().rowspan.start, ax.get_subplotspec().colspan.start): ax for ax in panels}
    values = _corner_frame()["A"].iloc[0]
    band, step = grid[0, 0].patches[:2]
    counts, _ = np.histogram(values, bins=map_kind.corner_edges(values, _args()))
    assert np.allclose(step.get_data().values, counts)
    low, high = garwood(counts)
    assert np.allclose(band.get_data().baseline, low) and np.allclose(band.get_data().values, high)
    meshes = [grid[r, c].collections[0] for r, c in grid if r > c]
    assert len({id(m.norm) for m in meshes}) == 1 and type(meshes[0].norm).__name__ == "LogNorm"
    (cbar,) = [ax for ax in fig.axes if hasattr(ax, "_colorbar")]
    assert cbar.get_ylabel() == "Counts"


def _args(**overrides):
    args = map_kind.build_parser().parse_args(["--datafile", "x", "--bins", "15"])
    vars(args).update(overrides)
    return args


def test_corner_edges_integer_aligned():
    edges = map_kind.corner_edges(np.arange(0, 301), _args(bins=30))
    assert np.allclose(np.diff(edges), 11) and edges[0] == -0.5 and edges[-1] >= 300
    assert np.allclose(map_kind.corner_edges(np.arange(5), _args(bins=30)), np.arange(-0.5, 5.5))
    assert len(map_kind.corner_edges(np.linspace(0, 1, 50), _args(bins=8))) == 9


def test_corner_hexbin_and_errors(make_project, capsys):
    from matplotlib.collections import PolyCollection

    (fig,) = _corner(make_project, "--map_type", "hexbin")
    lower = [ax for ax in fig.axes if ax.collections and isinstance(ax.collections[0], PolyCollection)]
    assert len(lower) == 3
    make_project({"Events": pd.concat([_corner_frame()] * 2)})
    assert map_kind.main(["--datafile", "Events", "--corner", "A", "B"]) in ([None], [], None)
    assert "one row" in capsys.readouterr().out
    assert not map_kind.main(["--datafile", "Events", "--corner", "A"])
    assert not map_kind.main(["--datafile", "Events", "-x", "A"])
    assert "-x and -y" in capsys.readouterr().out


def _datasets():
    """Two datasets of one config in one file, told apart by a column (G8)."""
    frame = _maps().copy()
    frame["Dataset"] = ["SN", "CMB"]
    frame["Config"] = "joint"
    return frame


def test_contour_hue_overlays_datasets_of_one_file(make_project):
    ax = _contour(make_project, "--contour_hue", "Dataset", "--contour_sigmas", "1", "2",
                  frames={"Maps": _datasets()})
    lines = [c for c in ax.collections if type(c).__name__ == "QuadContourSet" and not c.filled]
    assert len(lines) == 2  # one contour set per dataset, in one panel
    assert len(ax.figure.axes) == 1
    colors = [tuple(np.round(c.get_edgecolor()[0], 3)) for c in lines]
    assert colors[0] != colors[1]
    texts, _ = _legend(ax)
    assert "SN" in texts and "CMB" in texts


def test_contour_hue_combines_the_datasets(make_project):
    ax = _contour(make_project, "--contour_hue", "Dataset", "--combine_op", "squared_sum", "--combined_contours_only",
                  frames={"Maps": _datasets()})
    (combined,) = [c for c in ax.collections if type(c).__name__ == "QuadContourSet" and not c.filled]
    assert len(combined.allsegs[0]) >= 1  # the joint region of both maps


def test_contour_hue_needs_maps(make_project, capsys):
    make_project({"Maps": _datasets()})
    assert map_kind.main(["--datafile", "Maps", "-x", "XGrid", "-y", "YGrid", "--contour_hue", "Dataset"]) == []
    assert "--contour_hue overlays -z maps" in capsys.readouterr().out
    make_project({"Maps": _datasets()})
    assert map_kind.main(["--datafile", "Maps", "-x", "XGrid", "-y", "YGrid", "-z", "ZGrid", "--contour",
                          "--contour_hue", "Nope"]) == []
    assert "no column 'Nope'" in capsys.readouterr().out


def test_contour_hue_takes_the_registered_colours(make_project, tmp_path):
    """C1: a --contour_hue dataset keeps its colors.json colour."""
    import json

    from matplotlib.colors import to_hex

    from plotipus.palettes import current_colors

    make_project({"Maps": _datasets()})
    (tmp_path / "colors.json").write_text(json.dumps({"Dataset": {"SN": "C3", "CMB": "C5"}}))
    figures = _capture()
    map_kind.main(["--datafile", "Maps", "-x", "XGrid", "-y", "YGrid", "-z", "ZGrid", "--contour",
                   "--contour_hue", "Dataset", "--contour_sigmas", "1"])
    lines = [c for c in figures[0].axes[0].collections if type(c).__name__ == "QuadContourSet" and not c.filled]
    assert [to_hex(c.get_edgecolor()[0]) for c in lines] == [to_hex(current_colors()[3]), to_hex(current_colors()[5])]


# --- Posterior corner plots (--corner --contour) --------------------------------------


def _posterior_frame():
    rng = np.random.default_rng(11)
    rows = []
    for name, shift in (("A", 0.0), ("B", 1.0)):
        draws = rng.multivariate_normal([shift, 5.0, 0.0], [[1.0, 0.6, 0.0], [0.6, 1.0, 0.0], [0.0, 0.0, 4e-10]], 20000)
        rows.append({"Chain": name, "P": draws[:, 0], "Q": draws[:, 1], "Tiny": 7.5e-5 + draws[:, 2], "W": np.ones(20000)})
    return pd.DataFrame(rows)


def _posterior(make_project, *argv, config=""):
    make_project({"Chains": _posterior_frame()}, config=config)
    figures = _capture()
    map_kind.main(["--datafile", "Chains", "--corner", "P", "Q", "--contour", *argv])
    return figures


def _corner_grid(fig):
    panels = [ax for ax in fig.axes if not hasattr(ax, "_colorbar") and ax.axison]
    return {(ax.get_subplotspec().rowspan.start, ax.get_subplotspec().colspan.start): ax for ax in panels}


def test_posterior_corner_regions_marginals_and_titles(make_project):
    (fig,) = _posterior(make_project, "--select", "Chain", "-s", "A", "--contour_sigmas", "1", "2",
                        "--corner_labels", "p", "q (GeV)", "--corner_truth", "0", "5")
    assert not [ax for ax in fig.axes if hasattr(ax, "_colorbar")]  # credible regions need no colour scale
    grid = _corner_grid(fig)
    assert set(grid) == {(0, 0), (1, 0), (1, 1)}
    # The median and the central 68.3% interval above each diagonal panel, the unit after the value.
    values = _posterior_frame()["Q"].iloc[0]
    low, median, high = np.percentile(values, [15.865, 50, 84.135])
    assert grid[1, 1].get_title() == f"q = ${median:.2f}^{{+{high - median:.2f}}}_{{-{median - low:.2f}}}$ GeV"
    assert grid[0, 0].get_title().startswith("p = $")
    assert grid[0, 0].get_ylabel() == "" and grid[1, 0].get_ylabel() == "q (GeV)"
    # The filled 68.3% region holds 68.3% of the points (to the binning and smoothing).
    from matplotlib.path import Path as MplPath

    filled, outlines = grid[1, 0].collections[:2]
    inner = filled.get_paths()[-1]
    points = np.column_stack([_posterior_frame()["P"].iloc[0], values])
    inside = np.zeros(len(points), dtype=bool)
    for polygon in inner.to_polygons():
        inside |= MplPath(polygon).contains_points(points)
    assert abs(inside.mean() - 0.683) < 0.03
    # Truth lines in every panel of their variable, a marker where two meet; all named in the legend.
    assert grid[0, 0].lines[-1].get_xdata()[0] == 0 and len(grid[1, 0].lines) == 3
    (holder,) = [ax for ax in fig.axes if not ax.axison]
    # The legend says what the regions and the shaded interval hold, and how many draws there are (T25.21).
    assert [t.get_text() for t in holder.get_legend().get_texts()] == [
        "68.3% (2D region)", "95.4% (2D region)", "median, central 68.3%", "Truth", r"$N = 20\,000$"]


def test_posterior_corner_overlays_hue_values(make_project):
    (fig,) = _posterior(make_project, "--contour_hue", "Chain", "--contour_sigmas", "1", "--weight", "W")
    grid = _corner_grid(fig)
    assert len(grid[1, 0].collections) == 4  # a filled set and its outline per chain
    faces = [grid[1, 0].collections[i].get_facecolor()[0] for i in (0, 2)]
    assert not np.allclose(faces[0][:3], faces[1][:3]) and np.isclose(faces[0][3], 0.6)
    assert grid[0, 0].get_title() == ""  # several samples: one line each, in their colour, not one title
    lines = grid[0, 0]._plotipus_sample_titles
    assert [line.get_text()[:2] for line in lines] == ["P ", "P "] and lines[0].get_color() != lines[1].get_color()
    (holder,) = [ax for ax in fig.axes if not ax.axison]
    assert [t.get_text() for t in holder.get_legend().get_texts()] == ["A", "B", "68.3% (2D region)", "Titles: median, central 68.3%"]
    # Both chains fit the shared range of each variable.
    assert grid[0, 0].get_xlim()[0] < -2 and grid[0, 0].get_xlim()[1] > 3


def test_posterior_corner_helpers_and_errors(make_project, capsys):
    values = np.arange(1.0, 101.0)
    assert np.allclose(map_kind.weighted_quantiles(values, None, [0.5]), [50.5])
    # A weight of zero removes a point; doubling the weights changes nothing.
    weights = np.where(values > 50, 0.0, 2.0)
    assert np.allclose(map_kind.weighted_quantiles(values, weights, [0.5]), [25.5])
    assert map_kind.credible_text(1.0, 1.2, 1.5) == "$1.20^{+0.30}_{-0.20}$"
    assert map_kind.credible_text(7.3e-5, 7.5e-5, 7.8e-5) == r"$(7.50^{+0.30}_{-0.20}) \times 10^{-5}$"
    assert map_kind._split_unit("$m$ [GeV]") == ("$m$", "GeV") and map_kind._split_unit("p") == ("p", None)
    assert _posterior(make_project) == [] and "--contour_hue" in capsys.readouterr().out  # two rows, no hue
    make_project({"Chains": _posterior_frame()})
    assert not map_kind.main(["--datafile", "Chains", "--corner", "P", "Q", "--weight", "W"])
    assert "--weight" in capsys.readouterr().out
    assert not map_kind.main(["--datafile", "Chains", "--corner", "P", "Q", "--contour_hue", "Chain"])


# --- Posterior corner plots: conventions, intervals, splits, the upper triangle (T25.21-T25.28) ---


def _shapes_frame(draws=40000):
    """One row: a two-peaked parameter, a cyclic phase peaked at the end of its axis, a parameter piled up at
    its bound 0, a label per draw, weights and a log-likelihood."""
    rng = np.random.default_rng(5)
    upper = rng.random(draws) < 0.7
    two = np.where(upper, rng.normal(0.6, 0.02, draws), rng.normal(0.4, 0.02, draws))
    phase = (rng.normal(3.0, 0.5, draws) + np.pi) % (2 * np.pi) - np.pi
    piled = np.abs(rng.normal(0, 1.0, draws))
    return pd.DataFrame([{"Two": two, "Phase": phase, "Piled": piled, "Label": np.where(upper, "up", "down"),
                          "W": np.ones(draws), "LogLike": -0.5 * ((two - 0.6) / 0.02) ** 2 - 0.5 * piled**2}])


def _shapes(make_project, variables, *argv):
    make_project({"Shapes": _shapes_frame()})
    figures = _capture()
    map_kind.main(["--datafile", "Shapes", "--corner", *variables, "--contour", "--contour_sigmas", "1", "2", *argv])
    return figures


def _legend_texts(fig):
    return [t.get_text() for ax in fig.axes for lg in [ax.get_legend()] if lg is not None for t in lg.get_texts()]


def test_posterior_statistics():
    """T25.21, T25.22: effective sample sizes, highest-density pieces, wrapped intervals."""
    from plotipus import posterior

    rng = np.random.default_rng(3)
    white = rng.normal(size=20000)
    assert posterior.chain_ess(white) > 0.85 * white.size
    ar = np.zeros(20000)  # an AR(1) chain with rho = 0.9: tau = (1 + rho) / (1 - rho) = 19
    for i in range(1, ar.size):
        ar[i] = 0.9 * ar[i - 1] + white[i]
    assert 0.5 * ar.size / 19 < posterior.chain_ess(ar) < 2 * ar.size / 19
    assert np.isclose(posterior.kish_ess(np.r_[np.ones(10), np.zeros(90)]), 10)
    assert posterior.sample_ess([white], None, [10000, 10000]) > 0.85 * white.size
    # Two separated peaks: two pieces, never merged; a single peak: one interval of the right content.
    two = np.r_[rng.normal(0.4, 0.02, 3000), rng.normal(0.6, 0.02, 7000)]
    fine, density = posterior.fine_density(two, None, np.linspace(0.3, 0.7, 41))
    pieces, mode = posterior.density_pieces(fine, density, 0.683)
    assert len(pieces) == 2 and pieces[0][1] < 0.5 < pieces[1][0] and abs(mode - 0.6) < 0.01
    fine, density = posterior.fine_density(white, None, np.linspace(-4, 4, 41))
    ((low, high),), _ = posterior.density_pieces(fine, density, 0.683)
    assert abs(low + 1) < 0.08 and abs(high - 1) < 0.08
    # A peak at the end of a cyclic axis: one piece whose upper end lies past the end.
    phase = (rng.normal(3.0, 0.3, 20000) + np.pi) % (2 * np.pi) - np.pi
    fine, density = posterior.fine_density(phase, None, np.linspace(-np.pi, np.pi, 41), cyclic=True)
    ((low, high),), _ = posterior.density_pieces(fine, density, 0.683, cyclic=True)
    assert abs(low - 2.7) < 0.05 and abs(high - 3.3) < 0.05 and high > np.pi
    # A hard bound: the density does not fall towards it (nothing is smoothed across).
    piled = np.abs(rng.normal(0, 1, 20000))
    fine, density = posterior.fine_density(piled, None, np.linspace(0, 4, 41), bound=(0.0, np.nan))
    assert fine[0] == 0 and density[0] > 0.9 * density[8]
    assert np.allclose(posterior.split_probabilities([white > 0, white < 0], None, 20000)[0][1], np.sqrt(0.25 / 20000), rtol=0.01)
    rho, error = posterior.correlation(white, white + rng.normal(size=white.size), None, 20000)
    assert abs(rho - 0.707) < 0.02 and np.isclose(error, (1 - rho**2) / np.sqrt(19999))


def test_posterior_corner_levels_and_sample_size(make_project, capsys):
    """T25.21: levels given as content, the marginal's interval at the first one, warnings for thin samples."""
    (fig,) = _posterior(make_project, "--select", "Chain", "-s", "A", "--corner_levels", "90")
    texts = _legend_texts(fig)
    assert texts[:2] == ["90% (2D region)", "median, central 90%"]
    values = _posterior_frame()["Q"].iloc[0]
    low, median, high = np.percentile(values, [5, 50, 95])
    assert _corner_grid(fig)[1, 1].get_title() == f"Q = ${median:.1f}^{{+{high - median:.1f}}}_{{-{median - low:.1f}}}$"
    capsys.readouterr()
    # 3 sigma of 20000 draws leaves 54 outside: fine; of a tenth of them, too few.
    frame = _posterior_frame().iloc[:1]
    frame = frame.assign(**{name: [frame[name].iloc[0][:2000]] for name in ("P", "Q", "Tiny", "W")})
    make_project({"Chains": frame})
    _capture()
    map_kind.main(["--datafile", "Chains", "--corner", "P", "Q", "--contour", "--contour_sigmas", "1", "3"])
    out = capsys.readouterr().out
    assert "99.7% region rests on about" in out and "--corner_mc_error" in out
    _posterior(make_project, "--select", "Chain", "-s", "A", "--contour_dof", "1", "--contour_sigmas", "1")
    assert "39.3%" in capsys.readouterr().out
    # Autocorrelated draws: the effective size is in the legend.
    rng = np.random.default_rng(2)
    chain = np.zeros((6000, 2))
    for i in range(1, len(chain)):
        chain[i] = 0.9 * chain[i - 1] + rng.normal(size=2)
    make_project({"Chains": pd.DataFrame([{"P": chain[:, 0], "Q": chain[:, 1]}])})
    figures = _capture()
    map_kind.main(["--datafile", "Chains", "--corner", "P", "Q", "--contour", "--contour_sigmas", "1"])
    assert any(text.startswith(r"$N = 6\,000$, ESS = $") for text in _legend_texts(figures[0]))


def test_posterior_corner_intervals_follow_the_marginal(make_project, capsys):
    """T25.22: highest-density pieces as a union, a cyclic interval past the end of its axis, a limit at a bound."""
    (fig,) = _shapes(make_project, ["Two", "Phase", "Piled"], "--corner_interval", "hdi", "--corner_cyclic", "Phase",
                     "--corner_bound", "Piled", "0", "nan")
    grid = _corner_grid(fig)
    title = grid[0, 0].get_title()
    assert title.startswith(r"Two $\in$ [$0.") and r"$\cup$" in title
    assert len([c for c in grid[0, 0].collections if c.get_alpha() == 0.25]) == 2  # two shaded pieces
    # The phase panel spans one period; the mode near 3.0 with an interval that passes pi.
    assert np.allclose(grid[1, 1].get_xlim(), (-np.pi, np.pi))
    assert grid[1, 1].get_title().startswith("Phase = $3.0") or grid[1, 1].get_title().startswith("Phase = $2.9")
    assert len([c for c in grid[1, 1].collections if c.get_alpha() == 0.25]) == 2  # shaded on both sides of the end
    # hdi was asked for: the bounded marginal keeps an interval that starts at the bound.
    assert grid[2, 2].get_title().startswith("Piled = $") and grid[2, 2].get_xlim()[0] == 0
    assert "mode, 68.3% HDI" in _legend_texts(fig)
    capsys.readouterr()
    # By default a marginal highest at its bound gets a limit holding the outer level, with a warning.
    (fig,) = _shapes(make_project, ["Two", "Piled"], "--corner_bound", "Piled", "0", "nan")
    limit = np.percentile(_shapes_frame()["Piled"].iloc[0], 95.45)
    assert _corner_grid(fig)[1, 1].get_title() == f"Piled $<$ ${limit:.1f}$ (95.4%)"
    assert "one-sided limit" in capsys.readouterr().out
    assert {"median, central 68.3%", "95.4% limit"} <= set(_legend_texts(fig))
    # The regions of a bounded variable reach the bound; those of a cyclic one, both ends.
    (fig,) = _shapes(make_project, ["Piled", "Phase"], "--corner_bound", "Piled", "0", "nan", "--corner_cyclic", "Phase")
    vertices = np.concatenate([path.vertices for path in _corner_grid(fig)[1, 0].collections[0].get_paths()])
    assert vertices[:, 0].min() <= 0 and vertices[:, 1].max() >= np.pi and vertices[:, 1].min() <= -np.pi
    assert not _shapes(make_project, ["Two", "Piled"], "--corner_cyclic", "Nope")
    assert not _shapes(make_project, ["Two", "Piled"], "--corner_cyclic", "Piled", "5", "1")  # not a range
    assert "LOW HIGH" in capsys.readouterr().out


def test_posterior_corner_split_probabilities(make_project, capsys):
    """T25.23: the probability of each side of a value and of each label, with its error and the odds."""
    (fig,) = _shapes(make_project, ["Two", "Piled"], "--corner_split", "Two", "0.5", "--corner_split", "Label",
                     "--prior_odds", "2")
    frame = _shapes_frame()
    p = float((frame["Two"].iloc[0] > 0.5).mean())
    error = np.sqrt(p * (1 - p) / 40000)
    texts = _legend_texts(fig)
    assert f"$P$(Two $>$ 0.5) = {p:.3f} $\\pm$ {error:.3f}" in texts
    first = frame["Label"].iloc[0][0]  # the labels in their order of appearance; the first against the second
    assert f"$P$(Label = {first}) = {p if first == 'up' else 1 - p:.3f} $\\pm$ {error:.3f}" in texts
    assert sum(text.startswith("Bayes factor (prior odds 2)") for text in texts) == 2
    grid = _corner_grid(fig)
    assert any(line.get_linestyle() == ":" and line.get_xdata()[0] == 0.5 for line in grid[0, 0].lines)
    # The parts stacked in the diagonal add up to the marginal.
    (fig,) = _shapes(make_project, ["Two", "Piled"], "--corner_split", "Two", "0.5", "--corner_split_marginals")
    steps = [patch for patch in _corner_grid(fig)[1, 1].patches if hasattr(patch, "get_data")]
    parts = [step.get_data().values for step in steps if step.get_linestyle() not in ("-", "solid")]
    (whole,) = [step.get_data().values for step in steps if step.get_linestyle() in ("-", "solid")]
    assert len(parts) == 2 and np.allclose(parts[0] + parts[1], whole)
    assert any(text.startswith("posterior odds") for text in _legend_texts(fig))
    assert not _shapes(make_project, ["Two", "Piled"], "--corner_split", "Nope")
    assert "--corner_split" in capsys.readouterr().out


def test_posterior_corner_profile_likelihood_above(make_project, capsys):
    """T25.24: delta chi2 regions of the draws in the mirrored cells, the 1D profile over the marginals."""
    (fig,) = _shapes(make_project, ["Two", "Piled"], "--corner_upper", "profile", "--loglike", "LogLike", "--bins", "20")
    grid = _corner_grid(fig)
    assert set(grid) == {(0, 0), (1, 0), (1, 1), (0, 1)}
    mirrored = grid[0, 1]  # x: Piled, y: Two
    assert mirrored.get_shared_x_axes().joined(mirrored, grid[1, 1])
    assert np.allclose(mirrored.get_ylim(), grid[0, 0].get_xlim())
    # The best draw is where the likelihood peaks (Two = 0.6, Piled = 0), and the 2.30 region holds it.
    (star,) = [line for line in mirrored.lines if line.get_marker() == "*"]
    assert abs(star.get_ydata()[0] - 0.6) < 0.01 and star.get_xdata()[0] < 0.2
    outlines = mirrored.collections[1]
    assert np.allclose(outlines.levels, [2.2957, 6.1801], atol=1e-3)
    # The 1D profile is a dashed line that peaks at 0.6 although 30% of the posterior sits at 0.4.
    (profile,) = [line for line in grid[0, 0].lines if line.get_linestyle() == "--"]
    assert abs(profile.get_xdata()[np.argmax(profile.get_ydata())] - 0.6) < 0.02
    texts = _legend_texts(fig)
    assert "Best draw" in texts and "Profile, $-2\\Delta\\ln L <$ 2.30" in texts
    assert not [ax for ax in fig.axes if not ax.axison]  # no legend cell: the legend is above the grid
    assert not _shapes(make_project, ["Two", "Piled"], "--corner_upper", "profile")
    assert "--loglike" in capsys.readouterr().out


def test_posterior_corner_correlations_and_mc_error(make_project, capsys):
    """T25.25, T25.27: the coefficient with its error in the mirrored cell; resampled outer outlines."""
    (fig,) = _posterior(make_project, "--select", "Chain", "-s", "A", "--corner_upper", "corr", "--corner_mc_error", "5",
                        "--contour_sigmas", "1", "2")
    grid = _corner_grid(fig)
    values = _posterior_frame()
    rho = np.corrcoef(values["P"].iloc[0], values["Q"].iloc[0])[0, 1]
    assert np.isclose(grid[0, 1]._plotipus_rho[0], rho) and abs(rho - 0.6) < 0.02
    assert grid[0, 1].texts[0].get_text() == f"$\\rho = {rho:+.3f} \\pm {(1 - rho**2) / np.sqrt(19999):.3f}$"
    assert len(grid[1, 0].collections) == 2 + 5  # the regions, their outlines and five resampled outer outlines
    assert "95.4%, 5 resamplings" in _legend_texts(fig)
    # Several samples: one line each, in their colours.
    (fig,) = _posterior(make_project, "--contour_hue", "Chain", "--corner_upper", "corr")
    assert len(_corner_grid(fig)[0, 1].texts) == 2
    # No coefficient for a cyclic pair.
    (fig,) = _shapes(make_project, ["Two", "Phase"], "--corner_upper", "corr", "--corner_cyclic", "Phase")
    assert not _corner_grid(fig)[0, 1].texts and "cyclic" in capsys.readouterr().out


def test_posterior_corner_bands_and_option_errors(make_project, capsys):
    """T25.28: an outside constraint as a hatched band across the variable's panels, named in the legend."""
    (fig,) = _posterior(make_project, "--select", "Chain", "-s", "A", "--corner_band", "Q", "5.5", "6", "Other", "fit")
    grid = _corner_grid(fig)
    hatched = lambda ax: [patch for patch in ax.patches if patch.get_hatch()]  # noqa: E731
    assert len(hatched(grid[1, 0])) == 1 and len(hatched(grid[1, 1])) == 1 and not hatched(grid[0, 0])
    assert "Other fit" in _legend_texts(fig)
    assert not _posterior(make_project, "--select", "Chain", "-s", "A", "--corner_band", "Nope", "1", "2")
    make_project({"Chains": _posterior_frame()})
    assert not map_kind.main(["--datafile", "Chains", "--corner", "P", "Q", "--corner_upper", "corr"])
    assert "posterior corner plot" in capsys.readouterr().out


def _prior_frame(draws=30000):
    """A posterior and its flat prior: four parameters and a derived one (the product of the first two)."""
    rng = np.random.default_rng(8)
    post = {"A": rng.normal(0.5, 0.05, draws), "B": rng.normal(0.2, 0.1, draws), "C": rng.normal(0, 1, draws),
            "D": rng.normal(3, 0.33, draws)}
    flat = {"A": rng.uniform(0, 1, draws), "B": rng.uniform(-0.5, 0.5, draws), "C": rng.uniform(-8, 8, draws),
            "D": rng.uniform(2.5, 3.5, draws)}
    return pd.DataFrame([{"Sample": name, **columns, "Derived": columns["A"] * columns["B"]}
                         for name, columns in (("Prior", flat), ("Posterior", post))])


def _prior(make_project, *argv, variables=("A", "B", "C", "D"), config=""):
    make_project({"Fit": _prior_frame()}, config=config)
    figures = _capture()
    map_kind.main(["--datafile", "Fit", "--corner", *variables, "--contour", "--contour_sigmas", "1", "2",
                   "--contour_hue", "Sample", *argv])
    return figures


def test_posterior_corner_prior_shrinkage_and_block(make_project, capsys):
    """T25.26: the prior as a dashed outline, the posterior's width and shift in prior widths, derived
    parameters in the block of the upper triangle."""
    (fig,) = _prior(make_project, "--corner_prior", "Prior", "--corner_shrinkage", "--corner_block", "Derived",
                    "--corner_block_labels", "a b")
    grid = _corner_grid(fig)
    assert set(grid) == {(r, c) for r in range(4) for c in range(r + 1)}  # the prior adds no panel
    # One posterior sample is left: it keeps the first palette colour, its titles and intervals.
    steps = [patch for patch in grid[0, 0].patches if hasattr(patch, "get_data")]
    assert [step.get_linestyle() in ("-", "solid") for step in steps] == [True, False]  # the posterior, then the dashed prior
    frame = _prior_frame()
    prior, post = (frame[frame["Sample"] == name].iloc[0] for name in ("Prior", "Posterior"))
    ratio = np.diff(np.percentile(post["A"], [15.865, 84.135]))[0] / np.diff(np.percentile(prior["A"], [15.865, 84.135]))[0]
    shift = (np.median(post["A"]) - np.median(prior["A"])) / (0.5 * np.diff(np.percentile(prior["A"], [15.865, 84.135]))[0])
    title = grid[0, 0].get_title()
    assert title.startswith("A = $0.50") and title.endswith(f"\n$\\sigma/\\sigma_0$ = {ratio:.2f}, $\\Delta/\\sigma_0$ = ${shift:+.2f}$")
    # D is hardly narrower than its prior: a warning names it.
    assert "D: the posterior is 0.9" in capsys.readouterr().out
    # The ranges come from the posterior alone (the prior of C spans +-8), and a flat prior has no outline in the pairs.
    assert grid[2, 2].get_xlim()[1] < 6
    assert len(grid[1, 0].collections) == 2
    # The block: one inset panel over the top-right 2 x 2 cells, with the derived marginal, its prior and its interval.
    (holder,) = [ax for ax in fig.axes if not ax.axison]
    spec = holder.get_subplotspec()
    assert (spec.rowspan.start, spec.rowspan.stop, spec.colspan.start, spec.colspan.stop) == (0, 2, 2, 4)
    (panel,) = holder.child_axes
    assert panel.get_xlabel() == "a b" and panel.get_title().startswith("a b = $0.09")
    assert len([patch for patch in panel.patches if hasattr(patch, "get_data")]) == 2
    texts = _legend_texts(fig)
    assert "Prior" in texts and map_kind.SHRINKAGE_LEGEND in texts and "Posterior" not in texts
    # Correlations fill the cells outside the block only.
    (fig,) = _prior(make_project, "--corner_prior", "Prior", "--corner_block", "Derived", "--corner_upper", "corr")
    assert {key for key in _corner_grid(fig) if key[1] > key[0]} == {(0, 1), (2, 3)}
    # A prior that is narrower than the panel is outlined in the pairs.
    make_project({"Fit": _prior_frame().assign(Sample=["Posterior", "Prior"])})  # the narrow sample as the prior
    figures = _capture()
    map_kind.main(["--datafile", "Fit", "--corner", "A", "B", "--contour", "--contour_hue", "Sample", "--corner_prior", "Prior",
                   "--percentile", "0", "100"])
    assert len(_corner_grid(figures[0])[1, 0].collections) == 3
    capsys.readouterr()
    # Fewer than four variables: no block, said so; errors for a missing prior, block column or hue.
    (fig,) = _prior(make_project, "--corner_block", "Derived", variables=("A", "B", "C"))
    assert "four or more" in capsys.readouterr().out and not any(ax.child_axes for ax in fig.axes)
    assert not _prior(make_project, "--corner_prior", "Nope")
    assert not _prior(make_project, "--corner_block", "Nope")
    assert not _prior(make_project, "--corner_shrinkage")
    make_project({"Fit": _prior_frame()})
    assert not map_kind.main(["--datafile", "Fit", "--corner", "A", "B", "--contour", "--select", "Sample", "-s", "Posterior",
                              "--corner_prior", "Prior"])
    assert "--contour_hue" in capsys.readouterr().out


def test_posterior_corner_is_double_width_on_paper(make_project, capsys):
    """A posterior corner plot takes the double-column width where panels side by side keep one plot's width."""
    paper = 'medium = "paper"\n'
    map_kind._NOTICES_SHOWN.clear()  # notices are printed once per process
    (fig,) = _posterior(make_project, "--select", "Chain", "-s", "A", config=paper)
    assert np.allclose(fig.get_size_inches(), (6.8, 5.1)) and "double-column width" in capsys.readouterr().out
    (fig,) = _posterior(make_project, "--select", "Chain", "-s", "A", "--width", "single", config=paper)
    assert np.allclose(fig.get_size_inches(), (3.4, 2.55))
    (fig,) = _corner(make_project, config=paper)  # a corner of histograms keeps the column
    assert np.allclose(fig.get_size_inches(), (3.4, 2.55))


def test_posterior_corner_titles_of_several_samples(make_project, capsys):
    """T25.2 (left open by T25.21): one title line per overlaid sample, up to three, each with its own interval."""
    (fig,) = _posterior(make_project, "--contour_hue", "Chain", "--contour_sigmas", "1")
    frame = _posterior_frame()
    lines = _corner_grid(fig)[1, 1]._plotipus_sample_titles
    for line, name in zip(lines, ("A", "B")):
        low, median, high = np.percentile(frame[frame["Chain"] == name]["Q"].iloc[0], [15.865, 50, 84.135])
        assert line.get_text() == f"Q = ${median:.2f}^{{+{high - median:.2f}}}_{{-{median - low:.2f}}}$"
    # More than three samples: no titles, said once.
    many = pd.concat([_posterior_frame().assign(Chain=f"C{i}") for i in range(4)])
    make_project({"Chains": many})
    figures = _capture()
    map_kind.main(["--datafile", "Chains", "--corner", "P", "Q", "--contour", "--contour_hue", "Chain"])
    assert not hasattr(_corner_grid(figures[0])[0, 0], "_plotipus_sample_titles") and "up to 3" in capsys.readouterr().out


def test_posterior_corner_second_sample_in_the_upper_triangle(make_project, capsys):
    """T25.2: --corner_upper sample VALUE draws that value's regions in the mirrored cells, with every sample on the diagonal."""
    (fig,) = _posterior(make_project, "--contour_hue", "Chain", "--corner_upper", "sample", "B", "--contour_sigmas", "1")
    grid = _corner_grid(fig)
    assert set(grid) == {(r, c) for r in range(2) for c in range(2)} | {(0, 1)}
    frame = _posterior_frame()
    # The lower triangle keeps chain A alone (P in x, Q in y), the mirrored cell chain B alone (Q in x, P in y: the axes
    # of the pair exchanged, so that each shares its x with the diagonal panel of its column).
    assert len(grid[1, 0].collections) == 2 and len(grid[0, 1].collections) == 2
    paths = lambda ax: np.concatenate([path.vertices for path in ax.collections[1].get_paths()])  # noqa: E731
    assert abs(np.mean(paths(grid[1, 0])[:, 0]) - 0.0) < 0.3 and abs(np.mean(paths(grid[1, 0])[:, 1]) - 5.0) < 0.3
    assert abs(np.mean(paths(grid[0, 1])[:, 0]) - 5.0) < 0.3 and abs(np.mean(paths(grid[0, 1])[:, 1]) - 1.0) < 0.3
    assert grid[0, 1].get_shared_x_axes().joined(grid[0, 1], grid[1, 1]) and grid[0, 1].yaxis.get_label_position() == "right"
    assert len(grid[0, 0].patches) == 2  # both samples on the diagonal
    assert not [ax for ax in fig.axes if not ax.axison]  # the legend is above the grid
    assert not _posterior(make_project, "--contour_hue", "Chain", "--corner_upper", "sample", "Nope")
    assert "not a value of Chain (A, B)" in capsys.readouterr().out
    assert not _posterior(make_project, "--corner_upper", "sample", "B")
    assert not _posterior(make_project, "--contour_hue", "Chain", "--corner_upper", "sample")
    assert "--corner_upper takes" in capsys.readouterr().out


def test_posterior_corner_truth_level(make_project, capsys):
    """T25.28: the probability below the reference in the title, the content of the smallest region through it by the marker."""
    (fig,) = _posterior(make_project, "--select", "Chain", "-s", "A", "--corner_truth", "0", "5", "--corner_truth_level",
                        "--contour_sigmas", "1", "2")
    grid = _corner_grid(fig)
    frame = _posterior_frame()
    values = frame["P"].iloc[0]
    p = float((values < 0).mean())
    error = np.sqrt(p * (1 - p) / 20000)
    assert grid[0, 0].get_title().endswith(f"\n$P$(< Truth) = {p:.3f} $\\pm$ {error:.3f}")
    # The truth is the centre of chain A, so the smallest region through it holds almost nothing: a few percent.
    (note,) = [t for t in grid[1, 0].texts if t.get_text().endswith("%")]
    assert 0 <= float(note.get_text()[:-1]) < 10
    assert "% at the truth: smallest region through it" in _legend_texts(fig)
    # A truth far outside the panel gets no note; several samples get one each and a short probability in the title.
    (fig,) = _posterior(make_project, "--contour_hue", "Chain", "--corner_truth", "50", "5", "--corner_truth_level")
    assert not [t for t in _corner_grid(fig)[1, 0].texts if t.get_text().endswith("%")]
    (fig,) = _posterior(make_project, "--contour_hue", "Chain", "--corner_truth", "0.5", "5", "--corner_truth_level")
    assert len([t for t in _corner_grid(fig)[1, 0].texts if t.get_text().endswith("%")]) == 2
    assert "$P_<$" in _corner_grid(fig)[0, 0]._plotipus_sample_titles[0].get_text()
    capsys.readouterr()
    assert not _posterior(make_project, "--select", "Chain", "-s", "A", "--corner_truth_level")
    assert "--corner_truth" in capsys.readouterr().out


def test_corner_colorbar_spans_the_grid(make_project):
    (fig,) = _corner(make_project)
    fig.canvas.draw()
    (cbar,) = [ax for ax in fig.axes if hasattr(ax, "_colorbar")]
    grid = _corner_grid(fig)
    bar, top, bottom = cbar.get_position(), grid[0, 0].get_position(), grid[2, 2].get_position()
    assert np.isclose(bar.y1, top.y1, atol=0.01) and np.isclose(bar.y0, bottom.y0, atol=0.01)
    # As wide as the bar of a single plot: 1.5 panels' share for three columns.
    assert np.isclose(bar.width, 0.04 * 1.5 * bottom.width, rtol=0.05)
