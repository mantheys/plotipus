"""Shipped styles (T16): every name renders at its size, the dark themes keep
their colours readable, classic matches the look before the redesign, and
named styles do not leak into each other."""

import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from matplotlib.colors import to_hex, to_rgb

import plotipus.project as project
from plotipus import palettes, registry, style
from plotipus.kinds import line
from plotipus.legacy import kind_module

DATA = Path(__file__).resolve().parent / "data"
sys.path.insert(0, str(DATA))
from make_classic_reference import EXAMPLES, describe  # noqa: E402

SIZES = {"slides": (8, 4.5), "slides-dark": (8, 4.5), "paper": (3.4, 2.55), "paper-dark": (3.4, 2.55),
         "open": (8, 4.5), "open-dark": (8, 4.5), "classic": (8, 6)}


@pytest.fixture
def spectra():
    x = np.arange(0.5, 10, 1.0)
    return pd.DataFrame([{"Energy": x, "Counts": s * np.exp(-x / 3), "Sample": sample}
                         for sample, s in (("A", 1.0), ("B", 2.0))])


def _draw(*argv):
    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    line.main(["--datafile", "Spectra", "-x", "Energy", "-y", "Counts", "--hue", "Sample", *argv])
    return figures[-1]


@pytest.mark.parametrize("name", list(style.NAMES))
def test_every_name_renders_at_its_size(make_project, spectra, name):
    make_project({"Spectra": spectra})
    fig = _draw("--style_preset", name)
    assert tuple(fig.get_size_inches()) == pytest.approx(SIZES[name])


def test_names_in_the_project_style_list(make_project, spectra, tmp_path):
    (tmp_path / "extra.json").write_text('{"plot_settings": {"default_linewidth": 3}}')
    make_project({"Spectra": spectra}, 'style = ["paper", "extra.json"]\n')
    fig = _draw()
    assert tuple(fig.get_size_inches()) == pytest.approx(SIZES["paper"])
    assert plt.rcParams["font.family"] == ["serif"] and style.default_linewidth == 3


def test_medium_and_theme_change_the_parts_of_a_name(make_project, spectra):
    make_project({"Spectra": spectra}, 'style = ["open"]\n')
    fig = _draw("--theme", "dark")
    assert to_hex(fig.get_facecolor()) == "#1b1d22"
    assert not fig.axes[0].spines["top"].get_visible()  # still the open frame
    fig = _draw("--medium", "paper")
    assert tuple(fig.get_size_inches()) == pytest.approx(SIZES["paper"])


def _luminance(color):
    channels = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in to_rgb(color)]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast(a, b):
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


@pytest.mark.parametrize("name", ["slides-dark", "paper-dark", "open-dark"])
def test_dark_cycle_contrast(make_project, spectra, name):
    make_project({"Spectra": spectra})
    _draw("--style_preset", name)
    project.apply_rendering(preset=name)
    background = plt.rcParams["axes.facecolor"]
    colors = palettes.current_colors()
    assert len(colors) == 10
    assert all(_contrast(c, background) >= 3 for c in colors), [(c, _contrast(c, background)) for c in colors]
    assert style.diverging_cmap == "berlin"
    # Same order as the light palette: only the darkest entries are lightened.
    light = palettes.get("petroff10")
    assert sum(a != b for a, b in zip(colors, light)) == 3


def test_classic_pins(make_project, spectra):
    make_project({"Spectra": spectra}, 'style = ["classic"]\n')
    project.load_project()
    assert palettes.active == "tab10"
    assert style.contours["dof"] == 1 and style.figure_fixed_margins
    assert plt.rcParams["savefig.dpi"] == 100
    assert style.auto_title and not style.sci_in_label
    assert style.role_colors(style.fit_color) == "red" and style.role_colors(style.zero_line_color) == "red"


# Example commands whose output the redesign changed on purpose (bug fixes).
CLASSIC_FIXED = {
    "--diagonal --logz": "B08: one colorbar for the row instead of one per panel (T09)",
    "--contour --fill_contours": "B03/B08: Delta chi2 maps carry no colorbar; one figure column per map (T02, T09)",
    "--plot_type box": "B16: one legend entry per group, coloured by group (T10)",
}


@pytest.fixture(scope="module")
def classic_project(tmp_path_factory):
    root = tmp_path_factory.mktemp("classic")
    shutil.copy(EXAMPLES / "make_data.py", root / "make_data.py")
    subprocess.run([sys.executable, "make_data.py"], cwd=root, check=True, capture_output=True)
    shutil.copy(EXAMPLES / "style.json", root / "style.json")
    (root / "plotipus.toml").write_text('[project]\ndata_root = "input/data"\noutput = "output"\n'
                                        'style = ["classic", "style.json"]\n')
    return root


REFERENCE = json.loads((DATA / "classic_reference.json").read_text())


@pytest.mark.parametrize("command", list(REFERENCE), ids=[c.split("--output_suffix ")[-1] for c in REFERENCE])
def test_classic_matches_the_look_before_the_redesign(command, classic_project, monkeypatch):
    """Same figure size and series colours as the pre-redesign code (b227ed0,
    recorded by tests/data/make_classic_reference.py)."""
    monkeypatch.chdir(classic_project)
    monkeypatch.setattr(project, "_PROJECT", None)
    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    try:
        kind, *argv = shlex.split(command)
        kind_module(kind).main(argv)
        got = [describe(fig) for fig in figures]
    finally:
        registry.figure_hooks.clear()
        style.reset()
    expected = REFERENCE[command]
    fixed = next((why for key, why in CLASSIC_FIXED.items() if key in command), None)
    if fixed is None:
        assert got == expected
    elif "contour" not in command:
        assert [f["size"] for f in got] == [f["size"] for f in expected], fixed


def test_named_styles_do_not_leak(make_project, spectra):
    """Rendering a name after another gives the same style as rendering it first."""
    make_project({"Spectra": spectra})
    project.load_project()

    def state(name):
        project.apply_rendering(preset=name)
        config, rc = style.snapshot()
        config = {k: v for k, v in config.items() if k != "cli_geometry"}
        return json.dumps(config, sort_keys=True, default=str), {k: str(v) for k, v in rc.items()}

    fresh = {name: state(name) for name in style.NAMES}
    for first in ("open-dark", "classic", "paper"):
        for name in style.NAMES:
            state(first)
            assert state(name) == fresh[name], (first, name)


def test_plugin_settings_survive_a_named_style(make_project, spectra, tmp_path, monkeypatch):
    plugin = tmp_path / "my_plugin.py"
    plugin.write_text("import matplotlib.pyplot as plt\nfrom plotipus import style\n"
                      "def setup(registry):\n    plt.rcParams['lines.linestyle'] = ':'\n"
                      "    style.register_mappings({'nice': {'A': 'Alpha'}})\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    make_project({"Spectra": spectra}, 'plugins = ["my_plugin"]\n')
    project.load_project()
    for name in ("paper", "open-dark"):
        project.apply_rendering(preset=name)
        assert plt.rcParams["lines.linestyle"] == ":" and style.mappings["nice"] == {"A": "Alpha"}
    sys.modules.pop("my_plugin", None)


def test_plugin_colour_cycle_survives_project_style_files(make_project, spectra, tmp_path, monkeypatch):
    """A cycle a plugin sets in rcParams replaces the palette, also when
    project style files (without a palette) and --medium come after it."""
    (tmp_path / "cycle_plugin.py").write_text(
        "import matplotlib.pyplot as plt\nfrom cycler import cycler\n"
        "plt.rcParams['axes.prop_cycle'] = cycler(color=['#111111', '#222222'])\n")
    (tmp_path / "style.json").write_text('{"font_sizes": {"titlefontsize": 12}}')
    monkeypatch.syspath_prepend(str(tmp_path))
    make_project({"Spectra": spectra}, 'plugins = ["cycle_plugin"]\nstyle = ["style.json"]\n')
    project.load_project()
    for name in (None, "paper", "open-dark"):
        project.apply_rendering(preset=name)
        assert plt.rcParams["axes.prop_cycle"].by_key()["color"] == ["#111111", "#222222"]
    sys.modules.pop("cycle_plugin", None)


def test_save_style_writes_the_resolved_style(make_project, spectra):
    out = make_project({"Spectra": spectra})
    line.main(["--datafile", "Spectra", "-x", "Energy", "-y", "Counts", "--style_preset", "paper-dark",
               "--save_style"])
    record = json.loads((out / "paper-dark" / "spectra_energy_counts_line.style.json").read_text())
    assert [name for name, _ in record["layers"]] == ["plotipus", "paper", "dark"]
    assert record["rcParams"]["font.size"] == "8.0" or record["rcParams"]["font.size"] == 8.0
    assert record["settings"]["palette"] == "petroff10-dark"


def test_diverging_cmap_alias(make_project):
    from plotipus.kinds import map as map_kind

    grid = np.linspace(-1, 1, 5)
    frame = pd.DataFrame([{"X": grid, "Y": grid, "Z": np.outer(grid, grid)}])
    make_project({"Grid": frame})
    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    map_kind.main(["--datafile", "Grid", "-x", "X", "-y", "Y", "-z", "Z", "--cmap", "diverging",
                   "--style_preset", "slides-dark"])
    mesh = next(c for c in figures[0].axes[0].collections if c.get_array() is not None)
    assert mesh.get_cmap().name == "berlin"
