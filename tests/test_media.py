"""Media, widths and themes (T14): one command list renders for slides,
paper and web, each at its printed size and in its own output folder."""

import numpy as np
import pandas as pd
import pytest

from plotipus import registry, style
from plotipus.cli import main as cli_main
from plotipus.kinds import line


@pytest.fixture
def spectra():
    x = np.arange(0.5, 10, 1.0)
    return pd.DataFrame([{"Energy": x, "Counts": s * np.exp(-x / 3), "CountsError": 0.1 * np.ones_like(x),
                          "Sample": sample, "Variable": variable}
                         for sample, s in (("A", 1.0), ("B", 2.0)) for variable in ("E", "F")])


def _sizes(*argv):
    sizes = []
    registry.add_figure_hook(lambda fig, args: sizes.append(tuple(fig.get_size_inches())))
    line.main(["--datafile", "Spectra", "-x", "Energy", "-y", "Counts", "--hue", "Sample", "--select",
               "Variable", "-s", "E", *argv])
    return sizes


def test_width_presets_and_inches(make_project, spectra):
    make_project({"Spectra": spectra})
    assert _sizes("--medium", "paper", "--width", "single")[0] == pytest.approx((3.4, 0.75 * 3.4))
    assert _sizes("--medium", "paper", "--width", "5")[0] == pytest.approx((5, 3.75))
    assert _sizes("--width", "5", "--aspect", "0.5")[0] == pytest.approx((5, 2.5))
    # The medium's default width: slides draw at 8 x 4.5 in, paper at a column.
    assert _sizes("--medium", "slides")[0] == pytest.approx((8, 4.5))
    assert _sizes("--medium", "paper")[0][0] == pytest.approx(3.4)


def test_no_medium_keeps_the_old_size(make_project, spectra):
    make_project({"Spectra": spectra})
    assert _sizes()[0] == pytest.approx((style.figure_base_width, style.figure_height))


def test_panels_share_the_width(make_project, spectra):
    make_project({"Spectra": spectra})
    sizes = _sizes("--medium", "paper", "--width", "double", "--select", "Variable", "-s", "E", "F",
                   "--variables", "E", "F")
    assert sizes[-1] == pytest.approx((6.8, 3.0))


def test_lower_panel_adds_thirty_percent(make_project, spectra):
    make_project({"Spectra": spectra})
    (width, height), = _sizes("--medium", "paper")
    (width_lower, height_lower), = _sizes("--medium", "paper", "--lower", "ratio")
    assert width_lower == pytest.approx(width)
    assert height_lower == pytest.approx(1.3 * height)


def test_project_media_write_one_file_per_medium(make_project, spectra, monkeypatch):
    out = make_project({"Spectra": spectra}, 'media = ["slides", "paper"]\nplots = "lists"\n')
    lists = out.parents[1] / "lists"
    lists.mkdir()
    (lists / "demo_scripts.txt").write_text(
        "line --datafile Spectra -x Energy -y Counts --hue Sample --select Variable -s E\n")
    assert cli_main(["run", "demo"]) == 0
    name = "spectra_energy_counts_sample_variable_e_line.png"
    assert (out / name).exists() and (out / "paper" / name).exists()


def test_theme_and_medium_folders(make_project, spectra):
    out = make_project({"Spectra": spectra}, 'medium = "slides"\n')
    line.main(["--datafile", "Spectra", "-x", "Energy", "-y", "Counts", "--theme", "dark"])
    line.main(["--datafile", "Spectra", "-x", "Energy", "-y", "Counts", "--medium", "web"])
    line.main(["--datafile", "Spectra", "-x", "Energy", "-y", "Counts", "--medium", "slides"])
    name = "spectra_energy_counts_line.png"
    assert (out / "slides-dark" / name).exists()
    assert (out / "web" / name).exists()
    assert (out / name).exists()  # the project's own medium keeps today's path


def test_medium_all_renders_every_project_medium(make_project, spectra):
    out = make_project({"Spectra": spectra}, 'media = ["slides", "paper", "web"]\n')
    outputs = line.main(["--datafile", "Spectra", "-x", "Energy", "-y", "Counts", "--medium", "all"])
    name = "spectra_energy_counts_line.png"
    assert outputs == [name] * 3
    assert (out / name).exists() and (out / "paper" / name).exists() and (out / "web" / name).exists()


def test_paper_drops_an_explicit_title(make_project, spectra, capsys):
    make_project({"Spectra": spectra})
    titles = []
    registry.add_figure_hook(lambda fig, args: titles.append(fig._suptitle.get_text() if fig._suptitle else ""))
    base = ["--datafile", "Spectra", "-x", "Energy", "-y", "Counts", "--title", "Spectra"]
    line.main([*base, "--medium", "paper"])
    assert "dropped" in capsys.readouterr().out
    line.main([*base, "--medium", "paper", "--keep_title"])
    line.main([*base, "--medium", "slides"])
    assert titles == ["", "Spectra", "Spectra"]


def test_media_auto_title_off(make_project, spectra):
    make_project({"Spectra": spectra})
    titles = []
    registry.add_figure_hook(lambda fig, args: titles.append(fig._suptitle.get_text() if fig._suptitle else ""))
    line.main(["--datafile", "Spectra", "-x", "Energy", "-y", "Counts", "--medium", "slides"])
    line.main(["--datafile", "Spectra", "-x", "Energy", "-y", "Counts"])
    assert titles[0] == "" and titles[1]  # no medium: the old automatic title


def test_style_is_restored_after_a_medium(make_project, spectra):
    make_project({"Spectra": spectra})
    before = (style.figure_width, dict(style.widths))
    line.main(["--datafile", "Spectra", "-x", "Energy", "-y", "Counts", "--medium", "paper", "--theme", "dark"])
    assert (style.figure_width, dict(style.widths)) == before
    assert style.role("paper") != "#1b1d22"


def test_project_style_files_have_the_last_word(make_project, spectra, tmp_path):
    (tmp_path / "style.json").write_text('{"widths": {"single": 3.0}}')
    make_project({"Spectra": spectra}, 'style = ["style.json"]\n')
    assert _sizes("--medium", "paper")[0][0] == pytest.approx(3.0)


def test_dry_run_prints_the_resolution(make_project, spectra, capsys):
    out = make_project({"Spectra": spectra}, 'plots = "lists"\n')
    lists = out.parents[1] / "lists"
    lists.mkdir()
    (lists / "demo_scripts.txt").write_text("line --datafile Spectra -x Energy -y Counts\n")
    assert cli_main(["run", "demo", "--medium", "all", "--theme", "dark", "--dry_run"]) == 0
    printed = capsys.readouterr().out.splitlines()
    assert len(printed) == 3
    assert "medium=paper theme=dark width=3.4 x 2.55 in layers=[paper, dark] -> plots/paper-dark" in printed[1]


def test_unknown_width_is_an_argument_error(make_project, spectra, capsys):
    make_project({"Spectra": spectra})
    with pytest.raises(SystemExit):
        line.main(["--datafile", "Spectra", "-x", "Energy", "-y", "Counts", "--width", "poster"])
    assert "Unknown width 'poster'" in capsys.readouterr().err
