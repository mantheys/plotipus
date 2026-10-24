"""Render the same example commands in every candidate style, side by side.

    python docs/design/styles/render.py [candidate ...]   # e.g. paper open+slides

Each candidate directory holds ``plotipus-<name>.mplstyle`` (rcParams) and
``style.json`` (plotipus settings). plotipus has no style-file key for a
.mplstyle yet, so its rcParams are copied into the ``rcparams`` section of
the project style here. Outputs: ``<candidate>/png/NN_<slug>.png`` and
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

# The example commands of examples/input/plots/example_scripts.txt (all but hist and scatter).
COMMANDS = {
    "01_spectra_hue_style": "line --datafile Spectra -x Energy -y Counts --hue Sample --style Stage --iterable_mapping sample_names --iterable_color_mapping sample_colors --plot_type step --logy --labelx 'Energy (MeV)'",
    "02_ratio": "line --datafile Spectra -x Energy -y Counts --hue Sample --select Stage -s Raw --plot_type step --logy --lower ratio --lower_labely 'Ratio to Signal' --output_suffix ratio",
    "03_stacked_significance": "line --datafile Spectra -x Energy -y Counts --hue Sample --select Stage -s Raw --stacked --logy --lower group --reference_group signal --other_group background calibration --group_significance --lower_labely '$S/\\sqrt{B}$' --lower_plot_type stepmid",
    "04_efficiency_bands": "line --datafile Efficiency --configs small large --names signal -x Values -y Efficiency --by_config --plot_type line --errory --errory_type bands --combine_op mean --combined_label 'Average'",
    "05_binned_mean": "line --datafile Events -x TrueEnergy -y Resolution --hue Sample --binned --estimator mean --bins 15 --plot_type errorbar --labely 'Mean Resolution'",
    "06_hist2d": "map --datafile Events -x TrueEnergy -y RecoEnergy --iterable Sample --diagonal --logz",
    "07_contour": "map --datafile Contour -x XGrid -y YGrid -z ZGrid --contour --contour_sigmas 1 2 3 --fill_contours",
    "08_cat_bars": "cat --datafile Spectra -x Stage -y Counts --integrate_over Energy --hue Sample --kind bar --labely 'Total Counts'",
}


def read_mplstyle(path):
    """``key: value`` lines of a .mplstyle file, as strings rcParams validates."""
    rc = {}
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            key, value = line.split(":", 1)
            rc[key.strip()] = value.strip()
    return rc


def project_style(candidate):
    """Merged project style of ``candidate`` (``base+overlay`` applies an overlay folder's style.json)."""
    candidate, *overlays = candidate.split("+")
    if candidate == "current":
        return json.loads((EXAMPLES / "style.json").read_text())
    folder = HERE / candidate
    merged = json.loads((folder / "style.json").read_text())
    merged["rcparams"] = {**read_mplstyle(folder / f"plotipus-{candidate}.mplstyle"), **merged.get("rcparams", {})}
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
