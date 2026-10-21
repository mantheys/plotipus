import argparse
import pickle

import numpy as np
import pandas as pd

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
