"""Record the figures of the example commands as the pre-redesign code drew
them, for tests/test_styles.py (classic must match).

    git archive b227ed0 src | tar -x -C /tmp/old
    PYTHONPATH=/tmp/old/src python tests/data/make_classic_reference.py

b227ed0 is main before the redesign (before T01). Commands that the old code
cannot run (newer options) are left out. The record holds each figure's size
and the colour of every legend entry, per axes.
"""

import json
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib.colors import to_hex  # noqa: E402

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parents[1] / "examples"


def handle_color(handle):
    """Colour of a legend handle (line, patch, collection, error bars)."""
    for getter in ("get_color", "get_facecolor", "get_edgecolor"):
        try:
            if hasattr(handle, "lines") and handle.lines:  # ErrorbarContainer
                return to_hex(handle.lines[0].get_color())
            value = getattr(handle, getter)()
        except (AttributeError, TypeError, IndexError):
            continue
        if hasattr(value, "ndim") and value.ndim == 2:
            value = value[0] if len(value) else None
        if value is not None and len(value):
            return to_hex(value)
    return None


def describe(fig):
    axes = []
    for ax in fig.axes:
        if not ax.get_visible():
            continue
        handles, labels = ax.get_legend_handles_labels()
        axes.append([[label, handle_color(handle)] for handle, label in zip(handles, labels)])
    return {"size": [round(float(v), 4) for v in fig.get_size_inches()], "axes": axes}


def main():
    from plotipus import registry
    from plotipus.legacy import kind_module

    commands = [line for line in (EXAMPLES / "input/plots/example_scripts.txt").read_text().splitlines()
                if line.strip() and not line.startswith("#")]
    record = {}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shutil.copy(EXAMPLES / "make_data.py", root / "make_data.py")
        subprocess.run([sys.executable, "make_data.py"], cwd=root, check=True, capture_output=True)
        shutil.copy(EXAMPLES / "style.json", root / "style.json")
        (root / "plotipus.toml").write_text('[project]\ndata_root = "input/data"\noutput = "output"\n'
                                            'style = ["style.json"]\n')
        import os

        os.chdir(root)
        for command in commands:
            figures = []
            registry.figure_hooks.clear()
            registry.add_figure_hook(lambda fig, args: figures.append(fig))
            kind, *argv = shlex.split(command)
            try:
                kind_module(kind).main(argv)
            except (Exception, SystemExit):
                continue
            if figures:
                record[command] = [describe(fig) for fig in figures]
    (HERE / "classic_reference.json").write_text(json.dumps(record, indent=1) + "\n")
    print(f"{len(record)} of {len(commands)} commands recorded")


if __name__ == "__main__":
    main()
