"""Assemble the static plotipus page: web/ plus the figures of docs/.

    python web/build.py                      # writes build/site
    python -m http.server -d build/site      # open http://localhost:8000

The figures are the ones the documentation shows (docs/images, docs/design/styles), scaled down for the web;
the gallery's commands are read from docs/options.md and its paper figures from docs/images/options/paper
(`make -C examples docs` renders both). Each gallery card also shows the rows of the example data its command
draws: build.py runs examples/make_data.py into a temporary folder and reads them back. The citation comes from
CITATION.cff. The result is plain files: any static host serves it (web/deploy.sh pushes it to GitHub Pages).
"""

import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

WEB = Path(__file__).resolve().parent
ROOT = WEB.parent
DOCS = ROOT / "docs"
PAGE = ["index.html", "style.css", "home.js"]
STYLES = ["slides", "slides-dark", "paper", "paper-dark", "open", "open-dark", "classic"]
# other figures of docs/design/styles, by their name on the page
STYLE_EXTRAS = {
    "compare.png": "compare/02_ratio.png",
    "dune-preliminary.png": "paper+dune+preliminary/png/03_stacked_significance.png",
    "atlas-wip.png": "slides+atlas+wip/png/03_stacked_significance.png",
}
WIDTH = 1200  # pixels of a single figure on the page (a card is at most ~1060 CSS px wide)
DOCS_URL = "https://github.com/mantheys/plotipus/blob/main/docs/options.md"
FIGURE = re.compile(r"!\[([^\]]*)\]\(images/options/(\w+)\.png\)\n\n```bash\n(plotipus (\w+) .*?)\n```", re.S)

# The gallery is grouped by the task a physicist has in mind, not by plot kind. A figure of docs/options.md
# missing here goes to the last group with a warning: place new figures on purpose.
TASKS = {
    "Data and simulation": ["datamc", "datastack", "encodings", "errors", "bands", "configs", "facets", "flow", "kde"],
    "Fits and residuals": ["datafit", "fit", "ratio", "column"],
    "Searches and significance": ["significance", "yields", "overlays"],
    "Likelihood and Bayesian": ["contours", "sigmas", "posterior", "posteriors", "intervals", "hypotheses", "profile",
                                "upper", "correlations", "prior", "corner"],
    "Detector performance": ["binned", "box", "violin", "colorbar", "hexbin", "scatter", "hue"],
    "Comparisons and presentation": ["moments", "ranking", "violins", "palette", "rate"],
}
EXCERPT_ROWS = 3  # rows of the example data shown under a gallery card


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "site")
    args = parser.parse_args()
    if args.out.exists():
        shutil.rmtree(args.out)
    images = args.out / "images"
    images.mkdir(parents=True)
    for name in PAGE:
        shutil.copy(WEB / name, args.out / name)
    fill_citation(args.out / "index.html")
    for folder in ("mascot", "famous", "styleguide", "options", "options/paper"):
        for source in sorted((DOCS / "images" / folder).glob("*.png")):
            scaled(source, images / folder / source.name)
    styles = DOCS / "design" / "styles"
    for style in STYLES:
        for source in sorted((styles / style / "png").glob("*.png")):
            scaled(source, images / "styles" / style / source.name)
    for name, source in STYLE_EXTRAS.items():
        scaled(styles / source, images / "styles" / name)
    with tempfile.TemporaryDirectory() as data:
        subprocess.run([sys.executable, str(ROOT / "examples" / "make_data.py"), data], check=True, capture_output=True)
        figures = gallery(images, Path(data))
    (args.out / "gallery.json").write_text(json.dumps({"tasks": list(TASKS), "figures": figures}, indent=1,
                                                      ensure_ascii=False))
    check(args.out)
    size = sum(path.stat().st_size for path in args.out.rglob("*") if path.is_file())
    print(f"{args.out}: {len(figures)} gallery figures, {size / 1e6:.1f} MB")


def scaled(source, target):
    """Copy a figure, at most WIDTH pixels per panel column wide (multi-panel figures are 2:1 or wider)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        limit = WIDTH * (2 if image.width > 1.9 * image.height else 1)
        if image.width <= limit:
            shutil.copy(source, target)
            return
        height = round(image.height * limit / image.width)
        image.resize((limit, height), Image.LANCZOS).save(target, optimize=True)


def github_anchor(heading):
    """The anchor GitHub gives a heading: lower case, punctuation dropped, spaces as hyphens."""
    return re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")


def gallery(images, data):
    """The figures of docs/options.md that are followed by their command: image (slides and paper), kind, task,
    title, alt text, command, the rows of the example data it draws and the options.md section that explains it
    (a GitHub link to the heading above the figure)."""
    task_of = {name: task for task, names in TASKS.items() for name in names}
    text = (DOCS / "options.md").read_text()
    headings = [(m.start(), m.group(1).strip()) for m in re.finditer(r"^#{2,3} (.+)$", text, re.M)]
    figures, untasked = [], []
    for match in FIGURE.finditer(text):
        alt, name, command, kind = match.groups()
        heading = next((h for position, h in reversed(headings) if position < match.start()), None)
        if name not in task_of:
            untasked.append(name)
        title = re.search(r"--title '([^']*)'", command)
        with Image.open(images / "options" / f"{name}.png") as image:
            wide = image.width > 1.9 * image.height
        paper = images / "options" / "paper" / f"{name}.png"
        figures.append({"image": f"images/options/{name}.png",
                        "paper": f"images/options/paper/{name}.png" if paper.exists() else None,
                        "kind": kind, "task": task_of.get(name, list(TASKS)[-1]),
                        "title": title.group(1) if title else alt, "alt": alt, "command": command, "wide": wide,
                        "data": excerpt(command, data), "section": heading,
                        "docs": DOCS_URL + ("#" + github_anchor(heading) if heading else "")})
    if not figures:
        raise SystemExit("no figure with a command found in docs/options.md")
    if untasked:
        print(f"warning: no task in web/build.py TASKS for {', '.join(untasked)}: shown under '{list(TASKS)[-1]}'")
    unused = sorted(set(task_of) - {f["image"].split("/")[-1][:-4] for f in figures})
    if unused:
        print(f"warning: TASKS names figures docs/options.md does not have: {', '.join(unused)}")
    order = {name: i for i, name in enumerate(n for names in TASKS.values() for n in names)}
    return sorted(figures, key=lambda f: (list(TASKS).index(f["task"]), order.get(f["image"].split("/")[-1][:-4], 999)))


def _selection_pairs(select, values):
    """plotipus's own pairing of --select keys and values (values past the last key belong to it), so the
    excerpt shows the rows the command draws."""
    sys.path.insert(0, str(ROOT / "src"))
    from plotipus.selection import selection_pairs

    return selection_pairs(select, values)


def _options(command):
    """{option: [values]} of a command line (values run to the next option; negative numbers are values)."""
    options, current = {}, None
    for token in shlex.split(command)[2:]:
        if token.startswith("-") and not re.fullmatch(r"-[\d.]+(e-?\d+)?", token):
            current = token
            options.setdefault(current, [])
        elif current is not None:
            options[current].append(token)
    return options


def excerpt(command, data):
    """The first rows of the example data the command draws, with the columns it uses: {file, shown, total,
    columns, rows}; None when the data cannot be read (the card then shows the command only)."""
    options = _options(command)
    datafile = (options.get("--datafile") or [None])[0]
    configs, names = options.get("--configs"), options.get("--names") or [None]
    try:
        if configs:
            paths = [data / "_".join(p for p in (c, n, datafile) if p) for c in configs for n in names]
            frame = pd.concat([pd.read_pickle(f"{p}.pkl") for p in paths], ignore_index=True)
            shown_file = f"input/data/{{{','.join(configs)}}}_{names[0]}_{datafile}.pkl"
        else:
            frame = pd.read_pickle(data / f"{datafile}.pkl")
            shown_file = f"input/data/{datafile}.pkl"
    except (OSError, ValueError, TypeError):
        print(f"warning: no example data for the gallery card of: {command[:80]}")
        return None
    total = len(frame)
    selected = {}
    for column, value in _selection_pairs(options.get("--select", []), options.get("-s", [])):
        selected.setdefault(column, []).append(value)
    variable_column = (options.get("--variable_column") or ["Variable"])[0]
    if options.get("--variables") and variable_column in frame.columns:
        selected.setdefault(variable_column, []).extend(options["--variables"])
    for column, values in selected.items():
        if column in frame.columns:
            frame = frame[frame[column].astype(str).isin(values)]
    keys = [c for c in selected if c in frame.columns and frame[c].nunique() > 1] if len(frame) else []
    if configs:  # the rows of several files: which file each comes from
        keys = [c for c in ("Config", "Name") if c in frame.columns and frame[c].nunique() > 1] + keys
    groups = [v for flag in ("--hue", "--style", "--iterable", "--contour_hue", "--variable_column", "--facet_row")
              for v in options.get(flag, [])]
    drawn = [v for flag in ("-x", "-y", "-z", "--corner", "--colorby", "--sizeby", "--weight") for v in options.get(flag, [])]
    errors = [f"{c}{suffix}" for c in options.get("-y", []) for suffix in ("Error", "Error+", "Error-")]
    if "--fit" in options:
        errors.append("FitFunctionLabel")
    columns = []
    for column in keys + groups + drawn + errors:
        if column in frame.columns and column not in columns:
            columns.append(column)
    if not columns:
        return None
    group = next((c for c in groups if c in frame.columns), None)
    rows = frame.drop_duplicates(subset=[group]) if group is not None else frame
    rows = rows.head(EXCERPT_ROWS)
    y = next((c for c in options.get("-y", []) if c in frame.columns), None)
    return {"file": shown_file, "shown": len(frame), "total": total, "columns": columns,
            "rows": [_row(row, columns, y) for _, row in rows.iterrows()]}


def _row(row, columns, y):
    """The cells of one row; its arrays start where the drawn y values do (a histogram's empty first bins say
    nothing about the data)."""
    start = 0
    if y is not None and isinstance(row[y], (np.ndarray, list)) and np.asarray(row[y]).ndim == 1:
        values = np.asarray(row[y])
        if values.dtype.kind in "iuf" and np.any(values != 0):
            start = int(np.argmax(values != 0))
    length = len(row[y]) if start else None
    return [_cell(row[c], start if length is not None and _length(row[c]) == length else 0) for c in columns]


def _length(value):
    return len(value) if isinstance(value, (np.ndarray, list, tuple)) and np.asarray(value).ndim == 1 else None


def _number(value):
    """Three significant figures, in plain notation between 0.001 and 10^6 (2920, not 2.92e+03)."""
    value = float(value)
    if value == int(value) and abs(value) < 1e6:
        return str(int(value))
    if 1e-3 <= abs(value) < 1e6:
        text = f"{value:.{max(0, 2 - int(np.floor(np.log10(abs(value)))))}f}"
        return text.rstrip("0").rstrip(".") if "." in text else text
    return f"{value:.3g}"


def _cell(value, start=0):
    """A cell as the reader would picture it: arrays by three values (from ``start``) and their length, 2D grids
    by their shape."""
    if isinstance(value, (np.ndarray, list, tuple)):
        array = np.asarray(value)
        if array.ndim > 1:
            return f"{' × '.join(str(n) for n in array.shape)} grid"
        part = array[start:start + 3]
        head = ", ".join(_number(v) if array.dtype.kind in "iuf" else str(v) for v in part)
        before = "…, " if start else ""
        after = ", …" if start + 3 < len(array) else ""
        return f"[{before}{head}{after}] ({len(array)})"
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "—"
    if isinstance(value, (int, float, np.integer, np.floating)):
        return _number(value)
    return str(value)


def fill_citation(page):
    """{{DOI}}, {{CITE_TEXT}} and {{BIBTEX}} in the page, from CITATION.cff (one source for the citation)."""
    cff = (ROOT / "CITATION.cff").read_text()

    def field(name):
        match = re.search(rf'^[\s-]*{name}:\s*"?([^"\n]+?)"?\s*$', cff, re.M)
        if not match:
            raise SystemExit(f"CITATION.cff has no {name}")
        return match.group(1)

    family, given, title, doi = field("family-names"), field("given-names"), field("title"), field("doi")
    version, year, url = field("version"), field("date-released")[:4], field("repository-code")
    bibtex = (f"@software{{{family.lower()}_plotipus,\n"
              f"  author    = {{{family}, {given}}},\n"
              f"  title     = {{{{{title}}}}},\n"
              f"  version   = {{{version}}},\n"
              f"  year      = {{{year}}},\n"
              f"  doi       = {{{doi}}},\n"
              f"  url       = {{{url}}}\n}}")
    text = f"{family}, {given[0]}. ({year}). {title} (version {version}). Zenodo. https://doi.org/{doi}"
    html = page.read_text()
    for key, value in (("DOI", doi), ("CITE_TEXT", text), ("BIBTEX", bibtex)):
        html = html.replace("{{" + key + "}}", value.replace("&", "&amp;").replace("<", "&lt;"))
    left = re.findall(r"\{\{\w+\}\}", html)
    if left:
        raise SystemExit("placeholders left in index.html: " + ", ".join(left))
    page.write_text(html)


def check(out):
    """Every image the page names must exist: a figure renamed in docs/ fails the build, not the page."""
    text = "".join((out / name).read_text() for name in PAGE)
    named = set(re.findall(r'images/[\w/+.-]+\.png', text))
    named |= {f"images/famous/{name}.png" for name in re.findall(r'^  \["([\w-]+)", ', text, re.M) if "_" not in name and name not in STYLES}
    named |= {f"images/styles/{style}/{example}.png" for style in STYLES for example in re.findall(r'\["(\d\d_\w+)"', text)}
    missing = sorted(name for name in named if not (out / name).exists())
    if missing:
        raise SystemExit("images named by the page but not found in docs/: " + ", ".join(missing))


if __name__ == "__main__":
    main()
