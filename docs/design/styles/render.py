"""Render the example commands in every shipped style, side by side.

    python docs/design/styles/render.py [name ...]   # e.g. paper open-dark

Each name (slides, slides-dark, paper, paper-dark, open, open-dark,
classic) is selected by the project style list (``style = [name,
"style.json"]``, the examples' mappings). Outputs: ``<name>/png/NN_<slug>.png``
and ``compare/NN_<slug>.png`` (slides, slides-dark, paper, open, open-dark,
classic). The paper/open/hep/slides folders also keep the prototypes the
shipped styles were ported from (plotipus-<name>.mplstyle, style.json).
"""

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
NAMES = ["slides", "slides-dark", "paper", "paper-dark", "open", "open-dark", "classic"]
SHEET = ["slides", "slides-dark", "paper", "open", "open-dark", "classic"]

# A representative set of the example commands of examples/input/plots/example_scripts.txt.
COMMANDS = {
    "01_hue_style": "line --datafile Distributions -x Bin -y Counts --hue Distribution --style Sample --data_hue Data --select Distribution -s Exponential Landau Chi-squared --errory --density --labelx x",
    "02_ratio": "line --datafile Distributions -x Bin -y Counts --hue Sample --select Distribution -s Landau --data_hue Data --errory --lower ratio --labelx x --lower_labely 'Data / Sim.'",
    "03_stacked_significance": "line --datafile Distributions -x Bin -y Counts --hue Sample --select Distribution Sample -s Resonance Background Signal --stacked --lower group --reference_group Signal --other_group Background --group_significance --lower_labely '$S/\\sqrt{B}$' --labelx 'Mass (GeV)'",
    "04_data_stack": "line --datafile Distributions -x Bin -y Counts --hue Sample --select Distribution -s Resonance --data_hue Data --stacked --errory --lower ratio --labelx 'Mass (GeV)'",
    "05_binned_std": "line --datafile Distributions -x Value -y Residual --binned --estimator std --hue Sample --select Distribution -s Exponential --bins 11 --rangex 0 10",
    "06_hist2d": "map --datafile Distributions -x Value -y Smeared --select Distribution -s Exponential --iterable Sample --diagonal --logz",
    "07_contour": "map --datafile Distributions -x MeanScan -y SigmaScan -z Chi2Scan --select Distribution -s Gaussian --iterable Sample --contour --fill_contours",
    "08_fit": "line --datafile Distributions -x Bin -y Counts --select Distribution Sample -s Resonance Data --fit --data_hue Data --lower pull --chi2 --max_fit_params 3",
}


def render(name, workdir):
    project = workdir / name
    (project / "input" / "data").mkdir(parents=True)
    shutil.copy(EXAMPLES / "make_data.py", project / "make_data.py")
    subprocess.run([sys.executable, "make_data.py"], cwd=project, check=True, capture_output=True)
    shutil.copy(EXAMPLES / "style.json", project / "style.json")
    (project / "plotipus.toml").write_text(
        f'[project]\ndata_root = "input/data"\noutput = "output"\nstyle = ["{name}", "style.json"]\n')
    out = HERE / name / "png"
    out.mkdir(parents=True, exist_ok=True)
    for slug, command in COMMANDS.items():
        target = project / "out" / slug
        result = subprocess.run([sys.executable, "-m", "plotipus", *shlex.split(command), "-o", str(target)],
                                cwd=project, capture_output=True, text=True)
        pngs = sorted(target.glob("*.png"))
        if result.returncode or not pngs:
            print(f"[{name}] {slug} failed:\n{result.stdout[-800:]}{result.stderr[-800:]}")
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
    names = sys.argv[1:] or NAMES
    with tempfile.TemporaryDirectory() as tmp:
        for name in names:
            render(name, Path(tmp))
    compare([HERE / name / "png" for name in SHEET], SHEET)


if __name__ == "__main__":
    main()
