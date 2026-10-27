import numpy as np
import pandas as pd
import pytest

from plotipus import style
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
    assert colours["91%"] == "white" and colours["5%"] == "black"


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
