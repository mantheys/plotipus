import numpy as np
import pandas as pd

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
    assert texts == ["68.3% CL", "95.4% CL", "99.7% CL"]
    styles = [h.get_linestyle() for h in handles]
    assert len(set(styles)) == 3


def test_filled_contours_graded_from_best_fit(make_project):
    from matplotlib.colors import to_rgb

    ax = _contour(make_project, "--fill_contours")
    filled = [c for c in ax.collections if type(c).__name__ == "QuadContourSet" and c.filled][0]
    assert filled.levels[0] == -np.inf and len(filled.levels) == 4  # outside the last level: unfilled
    lightness = [np.mean(to_rgb(c)) for c in filled.get_facecolor()]
    assert lightness == sorted(lightness) and len(set(np.round(lightness, 3))) == 3
    texts, handles = _legend(ax)
    assert texts == ["68.3% CL", "95.4% CL", "99.7% CL"]
    swatches = {(tuple(np.round(h.get_facecolor(), 3)), str(h.get_linestyle())) for h in handles}
    assert len(swatches) == 3


def test_best_fit_marker(make_project):
    ax = _contour(make_project)
    marks = [line for line in ax.get_lines() if line.get_marker() == "+"]
    assert len(marks) == 1
    assert np.isclose(marks[0].get_xdata()[0], 0.4, atol=0.02) and np.isclose(marks[0].get_ydata()[0], 1.0, atol=0.03)
    assert not [line for line in _contour(make_project, "--no_best_fit").get_lines() if line.get_marker() == "+"]


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
    assert _legend(ax)[0] == ["$1\\sigma$", "$2\\sigma$", "$3\\sigma$"]


def test_style_contours_section(make_project):
    from plotipus import style

    style.configure(contours={"dof": 1, "label": "sigma", "linestyles": ["-"]})
    ax = _contour(make_project)
    lines = [c for c in ax.collections if type(c).__name__ == "QuadContourSet"]
    assert np.allclose(lines[0].levels, [1, 4, 9])
    texts, handles = _legend(ax)
    assert texts[0] == "$1\\sigma$" and {h.get_linestyle() for h in handles} == {"-"}
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
    assert len([line for line in ax.get_lines() if line.get_marker() == "+"]) == 2


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
    best_fit = [line for line in ax.get_lines() if line.get_marker() == "+"][0].get_zorder()
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
