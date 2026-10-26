import argparse
import json
import pickle
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from matplotlib.colors import to_hex
from matplotlib.legend import Legend

from plotipus import registry, style
from plotipus.args import map_iterable_color, map_iterable_label
from plotipus.format import format_with_error, _format_value_with_paren_error
from plotipus.io import import_data, make_name_from_args, read_pickle_frame
from plotipus.legacy import expand_abbreviations, option_values, rename
from plotipus.lower import group_difference, operation_series, pairwise, parse_lower
from plotipus.selection import filter_dataframe
from plotipus.transforms import combine, edges_from_centers, merge_groups, mirror, rebin_rows


def ns(**kwargs):
    defaults = dict(datafile=None, path=None, configs=None, names=None, variables=None, select=None,
                    save_values=None, remove_value=None, iterable=None, debug=False)
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def test_style_configure_and_mappings():
    style.configure(font_sizes={"titlefontsize": "small"}, mappings={"m": {"a": "Alpha", "1": "One"}})
    assert style.titlefontsize == "small"
    assert map_iterable_label("a", "col", "m") == "Alpha"
    assert map_iterable_label(1.0, "col", "m") == "One"
    assert map_iterable_label("zz", "col", "m") == "zz"
    style.configure(mappings={"c": {"a": "rgb(255, 0, 0)"}})
    assert map_iterable_color("a", "c") == (1.0, 0.0, 0.0)
    style.reset()


def test_style_mplstyle_key(tmp_path):
    (tmp_path / "local.mplstyle").write_text("font.size: 7\n")
    (tmp_path / "style.json").write_text(json.dumps({"mplstyle": ["dark_background", "local.mplstyle"],
                                                     "rcparams": {"lines.linewidth": 3}}))
    try:
        style.configure(tmp_path / "style.json")
        assert to_hex(plt.rcParams["axes.facecolor"]) == "#000000"
        assert plt.rcParams["font.size"] == 7 and plt.rcParams["lines.linewidth"] == 3
        assert to_hex(style.role("ink")) == "#ffffff" and to_hex(style.role("paper")) == "#000000"
        # A later file's mplstyle overrides an earlier file's rcparams.
        style.configure({"mplstyle": "default"})
        assert plt.rcParams["font.size"] == 10 and to_hex(plt.rcParams["axes.facecolor"]) == "#ffffff"
    finally:
        style.reset()


def test_style_roles_default_and_explicit():
    assert to_hex(style.role("ink")) == "#000000" and to_hex(style.role("paper")) == "#ffffff"
    assert style.role("muted") == "#808080" and style.role("faint") == "#e6e6e6"
    try:
        style.configure(roles={"muted": "rgb(255, 0, 0)", "accent": "00ff00"},
                        mappings={"c": {"a": "role:muted"}})
        assert style.role("muted") == (1.0, 0.0, 0.0) and to_hex(style.role("accent")) == "#00ff00"
        assert map_iterable_color("a", "c") == (1.0, 0.0, 0.0)
        with pytest.raises(ValueError):
            style.role("background")
    finally:
        style.reset()


def _figures():
    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    return figures


def _spectra_frame():
    x = np.arange(0.5, 10, 1.0)
    return pd.DataFrame([{"Energy": x, "Counts": s * np.exp(-x / 3), "Sample": sample, "Stage": stage}
                         for sample, s in (("A", 1.0), ("B", 2.0)) for stage in ("Raw", "Smooth")])


def test_ink_role_colours_style_handles_and_fit(make_project, tmp_path):
    from plotipus.kinds import line

    (tmp_path / "style.json").write_text('{"roles": {"ink": "#ff00ff"}}')
    x = np.linspace(-5, 5, 41)
    fits = pd.DataFrame([{"Values": x, "Counts": 10 * np.exp(-0.5 * x ** 2), "FitFunctionLabel": "Gaussian",
                          "Params": [10.0, 0.0, 1.0], "ParamsError": [0.1, 0.1, 0.1],
                          "ParamsLabel": ["A", "mu", "sigma"], "ParamsUnit": ["", "", ""]}])
    make_project({"Spectra": _spectra_frame(), "Fits": fits}, 'style = ["style.json"]\n')
    figures = _figures()
    line.main(["--datafile", "Spectra", "-x", "Energy", "-y", "Counts", "--hue", "Sample", "--style", "Stage",
               "--plot_type", "line"])
    legends = [a for a in figures[0].axes[0].get_children() if isinstance(a, Legend)]
    style_legend = next(lg for lg in legends if [t.get_text() for t in lg.get_texts()] == ["Raw", "Smooth"])
    assert {to_hex(h.get_color()) for h in style_legend.legend_handles} == {"#ff00ff"}

    line.main(["--datafile", "Fits", "-x", "Values", "-y", "Counts", "--fit", "--lower", "residual"])
    upper = figures[1].axes[0]
    fit_line = next(ln for ln in upper.get_lines() if ln.get_label() == "Fit")
    assert to_hex(fit_line.get_color()) == "#ff00ff"


def test_lower_zero_line_is_muted_dashed(make_project):
    from plotipus.kinds import line

    make_project({"Spectra": _spectra_frame()})
    figures = _figures()
    common = ["--datafile", "Spectra", "-x", "Energy", "-y", "Counts", "--hue", "Sample", "--select", "Stage",
              "-s", "Raw", "--lower", "ratio", "--lower_zero_line"]
    line.main(common)
    line.main([*common, "--lower_zero_color", "red"])

    def zero_line(fig):
        return next(ln for ln in fig.axes[1].get_lines() if list(ln.get_ydata()) == [0, 0])

    assert to_hex(zero_line(figures[0]).get_color()) == "#808080"
    assert zero_line(figures[0]).get_linestyle() == "--"
    assert to_hex(zero_line(figures[1]).get_color()) == "#ff0000"


def test_no_hard_coded_colours_in_source():
    source = Path(style.__file__).parent
    pattern = re.compile(r'color="(black|k|r|red|gray|grey|white)"')
    hits = [f"{path.relative_to(source)}:{n}" for path in sorted(source.rglob("*.py"))
            for n, text in enumerate(path.read_text().splitlines(), 1) if pattern.search(text)]
    assert hits == []


def test_label_hook_used_without_mapping():
    registry.add_label_hook("PDG", lambda value, n: {11: "Electron"}.get(int(value)))
    try:
        assert map_iterable_label(11, "PDG") == "Electron"
        assert map_iterable_label(13, "PDG") == "13"
    finally:
        registry.label_hooks.clear()


def test_import_with_config_name_prefixes(make_project):
    frame = pd.DataFrame({"x": [[1, 2, 3]], "y": [[4, 5, 6]], "Config": ["a"], "Name": ["n"]})
    make_project({"a_n_Spectrum": frame, "Plain": frame})
    df = import_data(ns(datafile=["Spectrum"], configs=["a"], names=["n"]))
    assert len(df) == 1 and df["_Datafile"].iloc[0] == "Spectrum" and df["_Occurrence"].iloc[0] == 0
    assert len(import_data(ns(datafile=["Plain"]))) == 1
    assert import_data(ns(datafile=["Missing"])).empty


def test_resolver_and_post_load_hooks(make_project, tmp_path):
    frame = pd.DataFrame({"v": [1]})
    make_project({})
    other = tmp_path / "elsewhere"
    other.mkdir()
    with open(other / "File.pkl", "wb") as handle:
        pickle.dump(frame, handle)
    registry.add_resolver(lambda entry, input_dir, prefix, is_default: [other / f"{prefix}{entry}.pkl"])
    registry.add_post_load(lambda df, path, input_dir: df.assign(Tag="hooked"))
    df = import_data(ns(datafile=["File"]))
    assert df["Tag"].iloc[0] == "hooked"


def test_unpickler_resolves_functions_by_name(tmp_path):
    import plotipus.fits as fits

    path = tmp_path / "f.pkl"
    # Pickle a reference to a module function, then make the module unimportable.
    payload = pickle.dumps({"F": [fits.gaussian]}, protocol=0)
    payload = payload.replace(b"plotipus.fits", b"gone.module")
    path.write_bytes(payload)
    assert read_pickle_frame(path)["F"].iloc[0] is fits.gaussian


def test_make_name_drops_expendable_parts_first():
    args = ns(datafile=["Data"], configs=["c1"], names=["n1"], x="X", y="Y", variables=["v" * 200])
    name = make_name_from_args(args, suffix="line.png")
    assert name == "data_c1_n1_x_y_line.png"
    args.filename_select = ["variables"]
    assert "v" * 20 in make_name_from_args(args, suffix="line.png")



def test_select_values_beyond_the_keys():
    """Values beyond the last --select key belong to it."""
    df = pd.DataFrame({"A": ["p", "q", "r"], "B": ["x", "y", "y"]})
    assert list(filter_dataframe(df, ns(select=["A"], save_values=["p", "r"]))["A"]) == ["p", "r"]
    assert list(filter_dataframe(df, ns(select=["B", "A"], save_values=["y", "q", "r"]))["A"]) == ["q", "r"]


def test_filename_groups_select_values(make_project):
    from plotipus.kinds import line

    x = np.arange(3.0)
    frame = pd.DataFrame([{"X": x, "Y": x * k, "Sample": s} for k, s in ((1, "a"), (2, "b"), (3, "c"))])
    make_project({"F": frame})
    outputs = line.main(["--datafile", "F", "-x", "X", "-y", "Y", "--hue", "Sample", "--select", "Sample",
                         "-s", "a", "c"])
    assert "sample_a_c" in outputs[0]

def test_filter_dataframe_select_and_remove():
    df = pd.DataFrame({"A": ["p", "q", "r"], "B": [1, 2, np.nan], "Variable": ["u", "u", "w"]})
    out = filter_dataframe(df, ns(select=["A", "A"], save_values=["p", "r"]))
    assert list(out["A"]) == ["p", "r"]
    out = filter_dataframe(df, ns(select=["B"], remove_value=["nan"]))
    assert list(out["A"]) == ["p", "q"]
    assert list(filter_dataframe(df, ns(variables=["w"]))["A"]) == ["r"]


def test_number_formatting():
    assert _format_value_with_paren_error("f", 1.234, 0.056) == "1.23(6)"
    assert _format_value_with_paren_error(".4g", 79.88, 3.006) == "80(3)"
    assert _format_value_with_paren_error(".4g", 0.9764, 0.0225) == "0.98(2)"
    assert _format_value_with_paren_error(".4g", 2.5e7, 3e5) == "2.50(3)e+07"
    row = {("Y", "mean"): 12.345, ("YError", "<lambda>"): 0.12}
    assert format_with_error(row, argparse.Namespace(y="Y", operation="mean")) == "12.3 ± 0.1"


def test_transforms():
    np.testing.assert_allclose(edges_from_centers([1, 2, 3]), [0.5, 1.5, 2.5, 3.5])
    np.testing.assert_allclose(edges_from_centers([1, 2, 4]), [0.5, 1.5, 3, 5])
    frame = pd.DataFrame({"x": [np.arange(4.0)], "y": [np.ones(4)]})
    out = rebin_rows(frame, "x", "y", 2, sum_y=True)
    np.testing.assert_allclose(out.at[0, "y"], [2, 2])
    x, y = mirror([0, 1, 2], [1, 2, 3])
    np.testing.assert_allclose(x, [0, 1, 2, 3, 4])
    np.testing.assert_allclose(y, [1, 2, 3, 2, 1])
    grid = np.array([0.0, 1.0, 2.0])
    total, error = combine([(grid, np.ones(3), np.ones(3)), (grid, np.ones(3), np.ones(3))], grid, "sum")
    np.testing.assert_allclose(total, 2)
    np.testing.assert_allclose(error, np.sqrt(2))
    merged = merge_groups(pd.DataFrame({"h": [1, 2, 3], "y": [[1.0], [2.0], [4.0]], "k": ["a"] * 3}), "h", "y", ["1,2=A"])
    assert list(merged["h"]) == ["A", 3]


def test_lower_operations():
    np.testing.assert_allclose(pairwise([2.0, 4.0], [1.0, 8.0], "ratio"), [0.5, 2.0])
    out = operation_series(["a", "b", "c"], [np.ones(2), 2 * np.ones(2), 3 * np.ones(2)], "subtract",
                           reference_sum=["b", "c"], reference_sum_label="bc")
    assert out[0][0] == "bc"
    np.testing.assert_allclose(out[0][1], 4)
    (label, values, errors), = group_difference(
        ["s", "b"], [np.array([4.0]), np.array([16.0])], [np.array([1.0]), np.array([2.0])],
        ["s"], None, "S", ["b"], None, "B", significance=True)
    np.testing.assert_allclose(values, 1.0)
    assert parse_lower("column:Sig").kind == "column" and parse_lower("ratio").kind == "operation"


def test_legacy_helpers():
    tokens = ["--operation", "ratio", "--x", "-1", "--keep", "a"]
    assert option_values(tokens, "--x") == ["-1"]
    assert rename(tokens, {"--operation": None, "--keep": "--kept"}) == ["--x", "-1", "--kept", "a"]
    parser = argparse.ArgumentParser()
    parser.add_argument("--names")
    parser.add_argument("--name_columns")
    assert expand_abbreviations(["--name", "a"], parser) == ["--names", "a"]


def test_legend_without_entries():
    import matplotlib.pyplot as plt

    from plotipus.plot import apply_legend_style

    fig, ax = plt.subplots()
    ax.plot([0, 1])
    legend = apply_legend_style(ax, title="Sample")  # nothing labelled
    assert legend is not None and legend.get_texts() == []
    assert apply_legend_style(ax, handles=[], labels=[]).get_texts() == []
    plt.close(fig)


def test_note_avoids_data_and_legend():
    """The note goes to the corner covering the least data, never on the legend."""
    import matplotlib.pyplot as plt

    from plotipus.plot import add_note_to_axes

    fig, ax = plt.subplots()
    x = np.linspace(0, 1, 200)
    ax.plot(x, 0.5 + 0.5 * x, label="rising")  # fills the upper right
    ax.plot(x, np.full_like(x, 0.02), label="floor")  # fills the bottom
    ax.set_ylim(0, 1)
    ax.legend(loc="upper left")
    note = add_note_to_axes(ax, "note")
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    box = note.get_window_extent(renderer)
    assert not box.overlaps(ax.get_legend().get_window_extent(renderer))
    x0, y0 = ax.transAxes.inverted().transform((box.x0, box.y0))
    assert x0 > 0.5 and 0.2 < y0 < 0.6  # middle of the right side: the free area
    plt.close(fig)


def _density_hist(make_project, tmp_path, *argv, style_json=None):
    from plotipus.kinds import hist

    if style_json is not None:
        (tmp_path / "style.json").write_text(json.dumps(style_json))
    rng = np.random.default_rng(1)
    frame = pd.DataFrame([{"E": rng.normal(50, 10, 2000), "Sample": "a"}])
    make_project({"Ev": frame}, 'style = ["style.json"]\n' if style_json is not None else "")
    figures = _figures()
    hist.main(["--datafile", "Ev", "-x", "E", "--bins", "20", "--density", "--labely", "Density", *argv])
    return figures[0].axes[0]


def _tick_texts(axis):
    formatter = axis.get_major_formatter()
    return formatter.format_ticks(axis.get_majorticklocs())


def test_density_ticks_without_e_notation(make_project, tmp_path):
    ax = _density_hist(make_project, tmp_path)
    texts = _tick_texts(ax.yaxis)
    assert texts and not any("e-" in t for t in texts)
    assert ax.get_ylabel() == "Density"  # 0.04 prints as 0.04 within the default limits


def test_power_of_ten_moves_into_the_label(make_project, tmp_path):
    limits = {"rcparams": {"axes.formatter.limits": [-2, 4]}}
    ax = _density_hist(make_project, tmp_path, style_json=limits)
    assert not any("e-" in t for t in _tick_texts(ax.yaxis))
    assert ax.get_ylabel().replace("\u2212", "-").endswith(r"($\times\mathdefault{10^{-2}}$)")
    assert not ax.yaxis.offsetText.get_visible()


def test_sci_in_label_off_keeps_offset_text(make_project, tmp_path):
    limits = {"rcparams": {"axes.formatter.limits": [-2, 4]}}
    ax = _density_hist(make_project, tmp_path, "--no-sci_in_label", style_json=limits)
    assert ax.get_ylabel() == "Density"
    assert ax.yaxis.offsetText.get_visible() and ax.yaxis.get_major_formatter().get_offset()


def test_sci_in_label_style_setting(make_project, tmp_path):
    style_json = {"rcparams": {"axes.formatter.limits": [-2, 4]}, "plot_settings": {"sci_in_label": False}}
    ax = _density_hist(make_project, tmp_path, style_json=style_json)
    assert ax.get_ylabel() == "Density"


def test_log_axes_keep_decade_labels():
    from matplotlib.ticker import LogFormatterSciNotation

    from plotipus.plot import apply_tick_formatter, finish_tick_labels

    fig, ax = plt.subplots()
    ax.plot([1, 10, 100, 1000], [1e-3, 1, 1e2, 1e3])
    ax.set_yscale("log")
    ax.set_ylabel("Counts")
    apply_tick_formatter(ax)
    finish_tick_labels(fig)
    assert isinstance(ax.yaxis.get_major_formatter(), LogFormatterSciNotation)
    minor = ax.yaxis.get_minor_formatter()
    assert all(text == "" for text in minor.format_ticks(ax.yaxis.get_minorticklocs()))
    assert ax.get_ylabel() == "Counts"
    plt.close(fig)


def test_threshold_formatter_wrapper_is_deprecated():
    from matplotlib.ticker import ScalarFormatter

    from plotipus.plot import apply_scientific_threshold_formatter

    fig, ax = plt.subplots()
    with pytest.warns(DeprecationWarning):
        apply_scientific_threshold_formatter(ax, threshold=0.1, axis="y")
    assert isinstance(ax.yaxis.get_major_formatter(), ScalarFormatter)
    plt.close(fig)


def test_savefig_dpi_default():
    assert plt.rcParams["savefig.dpi"] == 300
