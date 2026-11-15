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
import os
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
                                "upper", "smooth", "correlations", "prior", "corner"],
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
        showcase = tables(data)
    (args.out / "gallery.json").write_text(json.dumps({"tasks": list(TASKS), "figures": figures}, indent=1,
                                                      ensure_ascii=False))
    (args.out / "tables.json").write_text(json.dumps(showcase, indent=1, ensure_ascii=False))
    check(args.out)
    size = sum(path.stat().st_size for path in args.out.rglob("*") if path.is_file())
    print(f"{args.out}: {len(figures)} gallery figures, {len(showcase)} tables, {size / 1e6:.1f} MB")


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
                        "title": title.group(1) if title else alt, "alt": alt, "command": command, "python": python_call(command), "wide": wide,
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


# The tables of the Tables tab: each command is run on the example data when the site is built, and its LaTeX and
# HTML outputs are shown with it. (docs/options.md, "Tables", explains every option.)
TABLES = [
    ("Mean and spread, with errors that set the digits",
     "One row per configuration, one column per variable, each cell a value with its error. The error decides how many "
     "digits are printed, so a precise value gets more of them (1.963 ± 0.010 beside 1.99 ± 0.01), and a column group "
     "per sample puts data beside simulation.",
     "plotipus table --datafile Moments -y Value --select Sample -s Data Simulation --variables Mean Std "
     "--column_group Sample --missing '—'"),
    ("Fit parameters",
     "The parameters of a stored fit, one row per fit, as value ± error with the labels the fit was drawn with.",
     "plotipus table --datafile Distributions --select Distribution Sample -s Resonance Data --fit_params"),
    ("Row statistics",
     "Means, variances, the Pearson correlation, the least-squares line and the number of points of each row's "
     "x and y arrays: the table of a data-against-simulation comparison.",
     "plotipus table --datafile Distributions -x X -y Y --select Distribution -s 'Bivariate Gaussian' "
     "--row_name Sample --stats mean var corr line n"),
]
TEX_SYMBOLS = {r"\pm": "±", r"\,": "\u2009", r"\sigma": "σ", r"\mu": "μ", r"\tau": "τ", r"\chi": "χ", r"\Gamma": "Γ",
               r"\alpha": "α", r"\beta": "β", r"\theta": "θ", r"\Delta": "Δ", r"\times": "×", r"\sim": "∼"}


def tex_html(text):
    """The HTML of a table cell: the plain text escaped, and each $...$ run as HTML (symbols, sub- and superscripts).
    Anything beyond that small subset is an error, so that a new kind of cell is handled on purpose."""
    def math(match):
        body = match.group(1)
        for command, symbol in TEX_SYMBOLS.items():
            body = re.sub(re.escape(command) + (r"(?![A-Za-z])" if command[-1].isalpha() else ""), lambda _, symbol=symbol: symbol, body)
        def script(m):
            tag = "sub" if m.group(1) == "_" else "sup"
            return f"<{tag}>{m.group(2) or m.group(3)}</{tag}>"
        body = re.sub(r"([_^])(?:\{([^{}]*)\}|(\w))", script, body)
        if "\\" in body:
            raise SystemExit(f"web/build.py: LaTeX in a table cell is beyond tex_html: {match.group(0)}")
        return body.replace(" - ", " − ").replace("-", "−")
    return re.sub(r"\$([^$]*)\$", math, text)


def table_html(html):
    """The <table> of plotipus's --html output, without its inline styling and with its cells as HTML."""
    table = re.search(r"<table.*?</table>", html, re.S).group(0)
    table = re.sub(r'<table[^>]*>', "<table>", table)
    table = re.sub(r' (style|halign|class)="[^"]*"', "", table)
    def cell(match):
        text = tex_html(match.group(1)) if "$" in match.group(1) else match.group(1)
        return ">" + re.sub(r"(?<![\w.])-(?=\d)", "−", text) + "<"  # a typographic minus before a number
    return re.sub(r">([^<>]+)<", cell, table)


def tables(data):
    """The tables showcase: title, text, command, the Python call, the LaTeX source and the table as HTML."""
    shown = []
    with tempfile.TemporaryDirectory() as work:
        work = Path(work)
        (work / "plotipus.toml").write_text(f'[project]\ndata_root = "{data}"\noutput = "out"\n')
        for index, (title, text, command) in enumerate(TABLES):
            target = work / f"table{index}"
            result = subprocess.run([sys.executable, "-m", "plotipus", *shlex.split(command)[1:], "--html", "-o", str(target)],
                                    cwd=work, capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(ROOT / "src")})
            texs, htmls = sorted(target.rglob("*.tex")), sorted(target.rglob("*.html"))
            if result.returncode or not texs or not htmls:
                raise SystemExit(f"web/build.py: the table command failed:\n{command}\n{result.stdout[-600:]}{result.stderr[-600:]}")
            shown.append({"title": title, "text": text, "command": command, "python": python_call(command),
                          "latex": texs[0].read_text().strip(), "html": table_html(htmls[0].read_text())})
    return shown


def _python_string(text):
    """A Python literal of text: a raw string when it holds backslashes (LaTeX labels), so that it reads as typed."""
    if "\\" in text and '"' not in text and not text.endswith("\\"):
        return f'r"{text}"'
    return json.dumps(text, ensure_ascii=False)


def python_call(command):
    """The command line as the plotipus.plot call that draws the same figure from Python, one option per line."""
    tokens = shlex.split(command)
    lines, current = [_python_string(tokens[1])], None
    for token in tokens[2:]:
        if token.startswith("-") and not re.fullmatch(r"-[\d.]+(e-?\d+)?", token):
            lines.append(current := [_python_string(token)])
        else:
            current.append(_python_string(token))
    body = "".join(f"    {line if isinstance(line, str) else ', '.join(line)},\n" for line in lines)
    return f"import plotipus\n\nplotipus.plot(\n{body})"


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
