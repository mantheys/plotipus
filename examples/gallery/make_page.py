"""Render every gallery command into its own folder, once per medium of
plotipus.toml (slides and paper), and write output/gallery.md: the figures
by catalogue section, each medium side by side with the command below, the
tables as LaTeX, and the entries still waiting for a task.

    python make_page.py              # after python make_data.py
    python make_page.py --jobs 8

The commands come from input/plots/gallery_scripts.txt and
input/tables/gallery_scripts.txt (format in their headers).
tests/test_gallery.py renders the same entries with :func:`render_all`.
"""

import argparse
import html
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from plotipus.args import with_medium
from plotipus.runner import build_command

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

HERE = Path(__file__).resolve().parent
LISTS = {"plots": HERE / "input" / "plots" / "gallery_scripts.txt",
         "tables": HERE / "input" / "tables" / "gallery_scripts.txt"}
# The media every figure is drawn for: [project] media of plotipus.toml.
MEDIA = tomllib.loads((HERE / "plotipus.toml").read_text())["project"]["media"]
SECTION = re.compile(r"#\s*==\s*(\S+)\s+(.*)")
ROW = re.compile(r"#\s*([A-J]\d+)\s+(.*)")
NEEDS = re.compile(r"#\s*needs\s+(T[\d.]+):\s*(.*)")


@dataclass
class Render:
    returncode: int
    log: str
    files: list  # every file written, also in sub-folders

    @property
    def ok(self):
        return self.returncode == 0 and bool(self.files)


@dataclass
class Entry:
    kind: str  # plots or tables
    section: str
    row: str  # catalogue id, e.g. A1
    title: str
    command: str
    needs: str = None  # the task an entry waits for
    renders: dict = field(default_factory=dict)  # medium (None for tables) -> Render

    @property
    def ok(self):
        return bool(self.renders) and all(r.ok for r in self.renders.values())


def read_entries(kinds=("plots", "tables")):
    """The entries of the gallery lists, rendered and pending, in file order."""
    entries = []
    for kind in kinds:
        section, row, title = "", None, ""
        for line in LISTS[kind].read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            if match := SECTION.fullmatch(text):
                section = f"{match[1]} {match[2]}"
            elif match := NEEDS.fullmatch(text):
                entries.append(Entry(kind, section, row, title, match[2], needs=match[1]))
            elif match := ROW.fullmatch(text):
                row, title = match[1], match[2]
            elif not text.startswith("#"):
                entries.append(Entry(kind, section, row, title, " ".join(text.split())))
    return entries


def render(entry, out_dir, medium=None):
    """Run one entry's command (for ``medium``, when given) with its outputs
    in ``out_dir`` (emptied first); stores and returns the :class:`Render`."""
    out_dir = Path(out_dir)
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True)
    argv = build_command(entry.command, [str(out_dir)], root=HERE)
    if medium is not None:
        argv = with_medium(argv, medium)
    proc = subprocess.run([sys.executable, "-m", "plotipus", *argv], cwd=HERE, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True)
    entry.renders[medium] = Render(proc.returncode, proc.stdout, sorted(f for f in out_dir.rglob("*") if f.is_file()))
    return entry.renders[medium]


def render_all(entries, out_dir, jobs=None, media=MEDIA):
    """Render the entries that do not wait for a task, in parallel: figures
    once per medium in ``out_dir/<medium>/<NN>-<row>``, tables once in
    ``out_dir/tables/<NN>-<row>``."""
    todo = [e for e in entries if e.needs is None]
    runs = []
    for index, entry in enumerate(todo):
        name = f"{index:02d}-{entry.row}"
        if entry.kind == "tables":
            runs.append((entry, Path(out_dir) / "tables" / name, None))
        else:
            runs += [(entry, Path(out_dir) / medium / name, medium) for medium in media]
    with ThreadPoolExecutor(jobs or os.cpu_count()) as pool:
        list(pool.map(lambda run: render(*run), runs))
    return todo


def _image(render, page_dir):
    png = next((f for f in render.files if f.suffix == ".png"), None)
    return f'<img src="{png.relative_to(page_dir).as_posix()}" width="100%">' if png else ""


def _figure_rows(entry, page_dir, media):
    cells = "".join(f'<td width="{100 // len(media)}%" valign="top">{_image(entry.renders[m], page_dir)}</td>'
                    for m in media)
    return [f'<tr><td colspan="{len(media)}"><b>{entry.row}</b> {html.escape(entry.title)}</td></tr>',
            f"<tr>{cells}</tr>",
            f'<tr><td colspan="{len(media)}"><details><summary>command</summary>'
            f"<pre>plotipus {html.escape(entry.command, quote=False)}</pre></details></td></tr>"]


def write_page(entries, page, media=MEDIA):
    """output/gallery.md: per section, the figures with one column per
    medium, the tables as LaTeX and a list of the entries waiting for a
    task. Returns the entries that failed."""
    page = Path(page)
    rendered = [e for e in entries if e.needs is None]
    pending = [e for e in entries if e.needs is not None]
    failed = [e for e in rendered if not e.ok]
    lines = ["# plotipus gallery", "",
             "One example per working row of the chart catalogue (docs/design/catalogue.md), "
             "generated by `make -C examples gallery` from `examples/gallery/input/*/gallery_scripts.txt`. "
             f"Each figure is drawn for every medium ({', '.join(media)}), side by side. "
             f"{len(rendered) - len(failed)} examples rendered, {len(failed)} failed, "
             f"{len(pending)} waiting for a task.", ""]
    for section in dict.fromkeys(e.section for e in entries):
        lines += [f"## {section}", ""]
        figures = [e for e in rendered if e.section == section and e.kind == "plots" and e not in failed]
        if figures:
            lines.append("<table>")
            lines.append("<tr>" + "".join(f"<th>{m}</th>" for m in media) + "</tr>")
            for entry in figures:
                lines += _figure_rows(entry, page.parent, media)
            lines += ["</table>", ""]
        for entry in (e for e in rendered if e.section == section and e.kind == "tables" and e not in failed):
            files = entry.renders[None].files
            tex = next((f for f in files if f.suffix == ".tex"), files[0])
            lines += [f"**{entry.row}** {entry.title}", "", "```latex", tex.read_text().strip(), "```", "",
                      f"`plotipus {entry.command}`", ""]
        for entry in (e for e in failed if e.section == section):
            media_failed = ", ".join(str(m or "table") for m, r in entry.renders.items() if not r.ok)
            lines += [f"**{entry.row}** {entry.title}: failed ({media_failed})", "", f"`plotipus {entry.command}`", ""]
        waiting = [e for e in pending if e.section == section]
        if waiting:
            lines += ["Waiting for a task:", ""]
            lines += [f"- **{e.row}** {e.title}: needs {e.needs}" for e in waiting]
            lines.append("")
    page.write_text("\n".join(lines), encoding="utf-8")
    return failed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jobs", "-j", type=int, default=None, help="Commands run in parallel (default: all CPUs)")
    options = parser.parse_args(argv)
    output = HERE / "output"
    entries = read_entries()
    render_all(entries, output / "gallery", options.jobs)
    failed = write_page(entries, output / "gallery.md")
    for entry in failed:
        for medium, result in entry.renders.items():
            if not result.ok:
                print(f"FAILED {entry.row} ({medium or 'table'}): plotipus {entry.command}\n{result.log}")
    print(f"Gallery written to {output / 'gallery.md'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
