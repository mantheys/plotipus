"""Render the same example commands in every candidate style, side by side.

    python docs/design/styles/render.py [candidate ...]   # e.g. paper open+slides

Each candidate directory holds ``plotipus-<name>.mplstyle`` (rcParams) and
``style.json`` (plotipus settings); the project style names the .mplstyle
with the ``mplstyle`` key. Outputs: ``<candidate>/png/NN_<slug>.png`` and
``compare/NN_<slug>.png`` (current look, then each candidate).
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
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
EXAMPLES = REPO / "examples"
CANDIDATES = ["paper", "open", "hep"]

# A representative set of the example commands of examples/input/plots/example_scripts.txt.
COMMANDS = {
    "01_hue_style": "line --datafile Distributions -x Bin -y Counts --hue Distribution --style Sample --select Distribution -s Exponential Landau Chi-squared --plot_type step --labelx x",
    "02_ratio": "line --datafile Distributions -x Bin -y Counts --hue Sample --select Distribution -s Landau --plot_type step --lower ratio --reference_value Simulation --labelx x --lower_labely 'Data / Sim.'",
    "03_stacked_significance": "line --datafile Distributions -x Bin -y Counts --hue Sample --select Distribution Sample -s Resonance Background Signal --stacked --lower group --reference_group Signal --other_group Background --group_significance --lower_labely '$S/\\sqrt{B}$' --labelx 'Mass (GeV)'",
    "04_data_stack": "line --datafile Distributions -x Bin -y Counts --hue Sample --select Distribution -s Resonance --data_hue Data --stacked --errory --lower ratio --labelx 'Mass (GeV)'",
    "05_binned_std": "line --datafile Distributions -x Value -y Residual --binned --estimator std --hue Sample --select Distribution -s Exponential --bins 11 --rangex 0 10",
    "06_hist2d": "map --datafile Distributions -x Value -y Smeared --select Distribution -s Exponential --iterable Sample --diagonal --logz",
    "07_contour": "map --datafile Distributions -x MeanScan -y SigmaScan -z Chi2Scan --select Distribution -s Gaussian --iterable Sample --contour --fill_contours",
    "08_fit": "line --datafile Distributions -x Bin -y Counts --select Distribution Sample -s Resonance Data --fit --data_hue Data --lower pull --chi2 --max_fit_params 3",
}


def project_style(candidate):
    """Merged project style of ``candidate`` (``base+overlay`` applies an overlay folder's style.json)."""
    candidate, *overlays = candidate.split("+")
    if candidate == "current":
        return json.loads((EXAMPLES / "style.json").read_text())
    folder = HERE / candidate
    merged = json.loads((folder / "style.json").read_text())
    merged["mplstyle"] = str(folder / f"plotipus-{candidate}.mplstyle")
    merged["mappings"] = json.loads((EXAMPLES / "style.json").read_text())["mappings"]
    for overlay in overlays:
        merged = _deep_merge(merged, json.loads((HERE / overlay / "style.json").read_text()))
    return merged


def _deep_merge(base, update):
    merged = dict(base)
    for key, value in update.items():
        merged[key] = _deep_merge(merged[key], value) if isinstance(value, dict) and isinstance(merged.get(key), dict) else value
    return merged


def render(candidate, workdir):
    project = workdir / candidate
    (project / "input" / "data").mkdir(parents=True)
    shutil.copy(EXAMPLES / "make_data.py", project / "make_data.py")
    subprocess.run([sys.executable, "make_data.py"], cwd=project, check=True, capture_output=True)
    (project / "style.json").write_text(json.dumps(project_style(candidate), indent=2))
    (project / "plotipus.toml").write_text(
        '[project]\ndata_root = "input/data"\noutput = "output"\nstyle = ["style.json"]\n')
    out = workdir / "current_png" if candidate == "current" else HERE / candidate.split("+")[-1] / "png"
    out.mkdir(parents=True, exist_ok=True)
    for slug, command in COMMANDS.items():
        target = project / "out" / slug
        result = subprocess.run([sys.executable, "-m", "plotipus", *shlex.split(command), "-o", str(target)],
                                cwd=project, capture_output=True, text=True)
        pngs = sorted(target.glob("*.png"))
        if result.returncode or not pngs:
            print(f"[{candidate}] {slug} failed:\n{result.stdout[-800:]}{result.stderr[-800:]}")
            continue
        shutil.copy(pngs[0], out / f"{slug}.png")
    return out


def compare(folders, names):
    dest = HERE / "compare"
    dest.mkdir(exist_ok=True)
    for slug in COMMANDS:
        images = [(n, f / f"{slug}.png") for n, f in zip(names, folders) if (f / f"{slug}.png").exists()]
        fig, axes = plt.subplots(1, len(images), figsize=(4.2 * len(images), 3.6), squeeze=False)
        for ax, (name, path) in zip(axes[0], images):
            ax.imshow(mpimg.imread(path))
            ax.set_title(name, fontsize=12, family="DejaVu Sans")
            ax.axis("off")
        fig.tight_layout()
        fig.savefig(dest / f"{slug}.png", dpi=160)
        plt.close(fig)


def main():
    candidates = sys.argv[1:] or CANDIDATES + ["open+slides"]
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        folders = [render("current", workdir)] + [render(c, workdir) for c in candidates]
        compare(folders, ["current"] + candidates)


if __name__ == "__main__":
    main()
