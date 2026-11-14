"""Assemble the static plotipus page: web/ plus the figures of docs/.

    python web/build.py                      # writes build/site
    python -m http.server -d build/site      # open http://localhost:8000

The figures are the ones the documentation shows (docs/images, docs/design/styles), scaled down for the web;
the gallery's commands are read from docs/options.md, so the page follows the documentation. The result is
plain files: any static host serves it (web/deploy.sh pushes it to GitHub Pages).
"""

import argparse
import json
import re
import shutil
from pathlib import Path

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
FIGURE = re.compile(r"!\[([^\]]*)\]\(images/options/(\w+)\.png\)\n\n```bash\n(plotipus (\w+) .*?)\n```", re.S)


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
    for folder in ("mascot", "famous", "styleguide", "options"):
        for source in sorted((DOCS / "images" / folder).glob("*.png")):
            scaled(source, images / folder / source.name)
    styles = DOCS / "design" / "styles"
    for style in STYLES:
        for source in sorted((styles / style / "png").glob("*.png")):
            scaled(source, images / "styles" / style / source.name)
    for name, source in STYLE_EXTRAS.items():
        scaled(styles / source, images / "styles" / name)
    figures = gallery(images)
    (args.out / "gallery.json").write_text(json.dumps(figures, indent=1, ensure_ascii=False))
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


def gallery(images):
    """The figures of docs/options.md that are followed by their command: image, kind, title, alt text, command."""
    figures = []
    for alt, name, command, kind in FIGURE.findall((DOCS / "options.md").read_text()):
        title = re.search(r"--title '([^']*)'", command)
        with Image.open(images / "options" / f"{name}.png") as image:
            wide = image.width > 1.9 * image.height
        figures.append({"image": f"images/options/{name}.png", "kind": kind, "title": title.group(1) if title else alt,
                        "alt": alt, "command": command, "wide": wide})
    if not figures:
        raise SystemExit("no figure with a command found in docs/options.md")
    return figures


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
