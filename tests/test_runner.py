"""plotipus run: commands in forked children of a preloaded runner, or one
Python per command (--isolate subprocess)."""

import hashlib

import numpy as np
import pandas as pd
import pytest
from PIL import Image

from plotipus.runner import fork_available, run_list

pytestmark = pytest.mark.skipif(not fork_available(), reason="os.fork is not available")


@pytest.fixture
def spectra_list(make_project):
    x = np.arange(0.5, 10, 1.0)
    frame = pd.DataFrame([{"Energy": x, "Counts": s * np.exp(-x / 3), "Sample": sample}
                          for sample, s in (("A", 1.0), ("B", 2.0))])
    out = make_project({"Spectra": frame}, 'plots = "lists"\n')
    lists = out.parents[1] / "lists"
    lists.mkdir()

    def write(*lines):
        (lists / "demo_scripts.txt").write_text("\n".join(lines) + "\n")
        return out

    return write


def _digest(path):
    return hashlib.md5(path.read_bytes()).hexdigest()


def test_forked_commands_write_their_plots_in_order(spectra_list, capsys):
    out = spectra_list(
        "line --datafile Spectra -x Energy -y Counts --hue Sample --output_suffix one.png",
        "line --datafile Spectra -x Energy -y Counts --hue Sample --logy --output_suffix two.png",
    )
    assert run_list("demo", jobs=2, isolate="fork") == 0
    printed = capsys.readouterr().out
    assert printed.index("one.png") < printed.index("two.png")  # in list order, whichever finished first
    assert (out / "spectra_energy_counts_sample_one.png").exists()
    assert (out / "spectra_energy_counts_sample_logy_two.png").exists()


def test_a_failing_command_is_reported(spectra_list, capsys):
    out = spectra_list(
        "line --datafile Missing -x Energy -y Counts",
        "line --datafile Spectra -x Energy -y Counts --no_such_option",
        "line --datafile Spectra -x Energy -y Counts --output_suffix fine.png",
    )
    assert run_list("demo", isolate="fork") >= 1
    printed = capsys.readouterr().out
    assert "unrecognized arguments: --no_such_option" in printed
    assert (out / "spectra_energy_counts_fine.png").exists()


def test_commands_do_not_share_state(spectra_list):
    """A command's medium and options do not reach the next one (each is a fresh fork)."""
    out = spectra_list(
        "line --datafile Spectra -x Energy -y Counts --medium paper --output_suffix paper.png",
        "line --datafile Spectra -x Energy -y Counts --output_suffix plain.png",
    )
    assert run_list("demo", isolate="fork") == 0
    with Image.open(next(out.rglob("*paper.png"))) as image:
        paper = image.size
    with Image.open(out / "spectra_energy_counts_plain.png") as image:
        plain = image.size
    assert paper != plain  # the second command is drawn at the project's default size, not paper's


def test_fork_and_subprocess_draw_the_same_figures(spectra_list):
    out = spectra_list("line --datafile Spectra -x Energy -y Counts --hue Sample --plot_type step "
                       "--sigma_lines 1 --logy --output_suffix same.png")
    name = "spectra_energy_counts_sample_logy_same.png"
    assert run_list("demo", isolate="subprocess") == 0
    subprocess_digest = _digest(out / name)
    (out / name).unlink()
    assert run_list("demo", isolate="fork") == 0
    assert _digest(out / name) == subprocess_digest
