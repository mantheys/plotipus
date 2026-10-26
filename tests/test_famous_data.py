"""The famous-plot datasets of examples/famous: generators, column
conventions and the commands of famous_scripts.txt."""

import shlex
import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pytest

import plotipus
from plotipus.runner import build_command, read_commands

FAMOUS = Path(__file__).resolve().parents[1] / "examples" / "famous"
sys.path.insert(0, str(FAMOUS))

import make_data  # noqa: E402

COMMANDS = read_commands(FAMOUS / "input" / "plots" / "famous_scripts.txt")
ERROR_SUFFIXES = ("Error+", "Error-", "Error")


@pytest.fixture(scope="module")
def frames():
    return {name: frame for generator in make_data.GENERATORS.values() for name, frame in generator().items()}


def _is_array(value):
    return isinstance(value, (list, tuple, np.ndarray))


def _option(tokens, flag):
    return tokens[tokens.index(flag) + 1] if flag in tokens else None


def test_every_figure_has_a_generator_and_a_command():
    assert set(make_data.GENERATORS) == {"F01", "F03", "F04", "F05", "F06", "F08", "F09", "F10", "F11", "F12",
                                         "F13", "F14", "F15", "F16", "F17", "F19", "F20", "F21", "F22", "F25"}
    used = {_option(shlex.split(command), "--datafile") for command in COMMANDS}
    names = {name.split("_")[-1] for generator in make_data.GENERATORS.values() for name in generator()}
    assert names <= used


def test_generators_are_seeded(frames):
    again = make_data.GENERATORS["F01"]()["HiggsDiphoton"]
    assert np.array_equal(again["Events"].iloc[0], frames["HiggsDiphoton"]["Events"].iloc[0])


def test_build_is_small_and_fast(tmp_path):
    start = time.perf_counter()
    written = make_data.main(out=tmp_path)
    assert time.perf_counter() - start < 10
    assert len(written) == len(set(written))
    assert sum(path.stat().st_size for path in tmp_path.glob("*.pkl")) < 5e6


def test_errors_match_values_and_are_non_negative(frames):
    for name, frame in frames.items():
        for column in frame.columns:
            suffix = next((s for s in ERROR_SUFFIXES if column.endswith(s)), None)
            if suffix is None or column[: -len(suffix)] not in frame.columns:
                continue
            base = column[: -len(suffix)]
            if suffix != "Error":
                partner = base + ("Error-" if suffix == "Error+" else "Error+")
                assert partner in frame.columns, f"{name}: {column} without {partner}"
            for value, error in zip(frame[base], frame[column]):
                if not _is_array(error):
                    continue
                assert len(error) == len(value), f"{name}: {column}"
                error = np.asarray(error, dtype=float)
                assert np.all(error[np.isfinite(error)] >= 0), f"{name}: {column}"


def test_plotted_columns_have_matching_lengths(frames):
    for command in COMMANDS:
        tokens = shlex.split(command)
        name, x, y, z = (_option(tokens, flag) for flag in ("--datafile", "-x", "-y", "-z"))
        frame = next(f for key, f in frames.items() if key.split("_")[-1] == name)
        for _, row in frame.iterrows():
            if not (_is_array(row.get(x)) and _is_array(row.get(y))):
                continue
            if z is None:
                assert len(row[x]) == len(row[y]), f"{name}: {x}, {y}"
            else:
                assert np.shape(row[z]) == (len(row[y]), len(row[x])), f"{name}: {z}"


def test_stored_fits_are_complete(frames):
    from plotipus.fits import get_function

    import models

    plotipus.fits.register_module(models)
    for name, frame in frames.items():
        if "Params" not in frame.columns:
            continue
        for _, row in frame[frame["Params"].apply(_is_array)].iterrows():
            n = len(row["Params"])
            assert len(row["ParamsError"]) == n and len(row["ParamsLabel"]) == n, name
            assert get_function(row["FitFunction"]) is not None, name


def test_hubble_table_is_the_published_one(frames):
    hubble = frames["Hubble1929"].set_index("Sample")
    assert len(hubble.loc["Individual nebulae", "Distance"]) == 24
    assert len(hubble.loc["Groups", "Distance"]) == 9
    assert hubble.loc["Individual nebulae", "Params"] == [465.0]


def test_anscombe_statistics(frames):
    quartet = frames["Anscombe"].query("Type == 'Data'")
    assert np.allclose(quartet["MeanY"], 7.50, atol=0.01)
    assert np.allclose(quartet["Correlation"], 0.816, atol=0.001)
    assert np.allclose([p[0] for p in quartet["Params"]], 0.500, atol=0.001)


def test_physics_anchors(frames):
    z_lineshape = frames["ZLineshape"].set_index("Model")
    assert 30.0 < np.max(z_lineshape.loc["3$\\nu$", "CrossSection"]) < 31.0
    firas = frames["FIRAS"].iloc[0]
    assert abs(firas["Params"][0] - 2.725) < 1e-3
    limit = frames["HiggsLimit"].set_index("Limit").loc["Expected"]
    ratio = np.array([limit[c][0] for c in ("MuLimit2SigmaLow", "MuLimit1SigmaLow", "MuLimit1SigmaHigh",
                                            "MuLimit2SigmaHigh")]) / limit["MuLimit"][0]
    assert np.allclose(ratio, [0.535, 0.719, 1.394, 1.865], atol=0.005)


@pytest.mark.parametrize("command", COMMANDS, ids=[f"{i:02d}" for i in range(len(COMMANDS))])
def test_command_renders(command, frames, make_project):
    config = (f'python_path = ["{FAMOUS.as_posix()}"]\nplugins = ["models", "annotations", "colorscale"]\n'
              f'style = ["{(FAMOUS / "style.json").as_posix()}"]\n')
    out = make_project(frames, config=config)
    kind, *argv = build_command(command)
    try:
        outputs = plotipus.plot(kind, argv)
    finally:
        plt.close("all")
    assert outputs, command
    for output in outputs:
        assert (out / output).exists(), output


def test_paper_style_keeps_one_figure_size(frames, make_project):
    """The paper gallery: a 2 x 2 grid with --single_panel_size is saved at
    the single-panel size of the paper style (3.5 x 2.7 in at 300 dpi)."""
    from PIL import Image

    styles = ", ".join(f'"{(path).as_posix()}"' for path in (FAMOUS / "style.json", FAMOUS / "paper" / "paper.json"))
    config = (f'python_path = ["{FAMOUS.as_posix()}"]\nplugins = ["models", "annotations", "colorscale"]\n'
              f'style = [{styles}]\n'
              "[settings]\ntext_scale = 0.75\n")
    out = make_project(frames, config=config)
    command = next(c for c in COMMANDS if c.startswith("line --datafile Anscombe") and "--single_panel_size" in c)
    kind, *argv = build_command(command)
    try:
        outputs = plotipus.plot(kind, argv)
    finally:
        plt.close("all")
    assert Image.open(out / outputs[0]).size == (1050, 810)


def test_gaia_counts_match_the_paper(frames):
    """F22 is real Gaia DR2 data: the paper's query gives the 65,921,112 stars
    of its Fig. 1 caption."""
    hrd = frames["HRDiagram"].set_index("Name")
    assert hrd.loc["all", "TotalStars"] == 65_921_112
    stars = hrd.loc["all", "Stars"]
    assert stars.shape == (len(hrd.loc["all", "MG"]), len(hrd.loc["all", "BPRP"]))
    assert np.nanmin(stars) >= 1


def test_real_datasets(frames):
    """F06, F09, F13, F14, F15 and F12 read the public files in data/."""
    assert len(frames["SupernovaHubble"].set_index("Series").loc["Union2.1 SNe", "Redshift"]) == 580
    keeling = frames["Keeling"].set_index("Series").loc["Monthly mean", "CO2"]
    assert keeling[0] == pytest.approx(315.71)
    mbh = frames["HockeyStick"].set_index("Series").loc["Instrumental"]
    assert mbh["Year"][-1] == 1998 and mbh["Anomaly"][-1] == pytest.approx(0.78)
    assert len(frames["FIRAS"].iloc[0]["Wavenumber"]) == 43
    strain = frames["GW150914"].query("Component == 'H1 observed'").iloc[0]["Strain"]
    assert len(strain) == 3441
    assert frames["RotationCurves"]["Galaxy"].nunique() == 22
