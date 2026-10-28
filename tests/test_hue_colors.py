"""The project colour registry, colors.json (style guide C1)."""

import json

import numpy as np
import pandas as pd
from matplotlib.colors import to_hex

from plotipus import hue_colors, registry
from plotipus.kinds import line


def _frame(samples):
    x = np.arange(5.0)
    return pd.DataFrame([{"Sample": s, "X": x, "Y": x * (i + 1)} for i, s in enumerate(samples)])


def _colors(make_project, frame, *argv, registry_entries=None):
    out = make_project({"Spectrum": frame})
    if registry_entries is not None:
        (out.parents[1] / "colors.json").write_text(json.dumps(registry_entries))
    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    line.main(["--datafile", "Spectrum", "-x", "X", "-y", "Y", "--hue", "Sample", "--plot_type", "line", *argv])
    ax = figures[-1].axes[0]
    return {l.get_label(): to_hex(l.get_color()) for l in ax.get_lines() if not l.get_label().startswith("_")}


def _cycle(k):
    from plotipus.palettes import current_colors

    return to_hex(current_colors()[k])


def test_registered_colour_is_kept_in_every_figure(make_project):
    """C1: a category keeps its colour whichever others share the figure."""
    entries = {"Sample": {"A": "C0", "B": "C1", "C": "C2"}}
    both = _colors(make_project, _frame(["A", "B", "C"]), registry_entries=entries)
    alone = _colors(make_project, _frame(["C"]), registry_entries=entries)
    assert alone["C"] == both["C"] == _cycle(2)


def test_without_registry_colours_follow_the_order(make_project):
    assert _colors(make_project, _frame(["C"]))["C"] == _cycle(0)


def test_mapping_wins_over_the_registry(make_project, tmp_path):
    (tmp_path / "style.json").write_text(json.dumps({"mappings": {"own": {"A": "black"}}}))
    out = make_project({"Spectrum": _frame(["A", "B"])}, 'style = ["style.json"]\n')
    (out.parents[1] / "colors.json").write_text(json.dumps({"Sample": {"A": "C3", "B": "C4"}}))
    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    line.main(["--datafile", "Spectrum", "-x", "X", "-y", "Y", "--hue", "Sample", "--plot_type", "line",
               "--iterable_color_mapping", "own"])
    colors = {l.get_label(): to_hex(l.get_color()) for l in figures[-1].axes[0].get_lines()}
    assert colors["A"] == "#000000" and colors["B"] == _cycle(4)


def test_unregistered_value_warns_and_avoids_registered_colours(make_project, capsys):
    colors = _colors(make_project, _frame(["A", "New"]), registry_entries={"Sample": {"A": "C1", "B": "C0"}})
    assert colors["A"] == _cycle(1)
    assert colors["New"] not in (_cycle(0), _cycle(1))  # not B's colour either: B is red in other figures
    assert "Sample=New has no colour in colors.json" in capsys.readouterr().out


def test_hue_cmap_ignores_the_registry(make_project):
    colors = _colors(make_project, _frame(["A", "B"]), "--hue_cmap", "viridis",
                     registry_entries={"Sample": {"A": "C0", "B": "C1"}})
    assert _cycle(0) not in colors.values()


def test_data_stay_ink_even_when_registered(make_project):
    from plotipus import style

    colors = _colors(make_project, _frame(["Data", "A"]), "--data_hue", "Data",
                     registry_entries={"Sample": {"Data": "C5", "A": "C0"}})
    assert colors.get("Data", to_hex(style.role("ink"))) == to_hex(style.role("ink"))


def test_update_registers_the_hue_values_of_the_command_lists(make_project, tmp_path, capsys):
    make_project({"Spectrum": _frame(["Data", "A", "B"]), "Other": _frame(["B", "C"])})
    plots = tmp_path / "input" / "plots"
    plots.mkdir(parents=True, exist_ok=True)
    (plots / "main_scripts.txt").write_text(
        "line --datafile Spectrum -x X -y Y --hue Sample --data_hue Data\n"
        "line --datafile Other -x X -y Y --hue Run --hue_cmap viridis\n")
    (tmp_path / "colors.json").write_text(json.dumps({"Sample": {"B": "C0"}}))
    added = hue_colors.update()
    registered = json.loads((tmp_path / "colors.json").read_text())
    assert list(registered) == ["Sample"]  # Run is on a colour map
    # B kept; the new values in the order of the sorted data files (Other, then Spectrum); Data (ink) left out
    assert registered["Sample"] == {"B": "C0", "C": "C1", "A": "C2"}
    assert added == {"Sample": ["C", "A"]}
    assert hue_colors.update(dry_run=True) == {"Sample": []}  # nothing new the second time


def test_update_warns_when_the_palette_runs_out(make_project, tmp_path, capsys):
    make_project({"Many": _frame([f"S{i}" for i in range(12)])})
    hue_colors.update(["Sample"])
    registered = json.loads((tmp_path / "colors.json").read_text())["Sample"]
    assert len(registered) == 12 and registered["S0"] == "C0"
    assert "colours repeat" in capsys.readouterr().out
