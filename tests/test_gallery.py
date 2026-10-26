"""The gallery (examples/gallery, T23): every uncommented command of its
lists renders, each into its own folder, and gives one figure (tables: a
.tex file, and with --html its HTML twin)."""

import importlib.util
import sys
from pathlib import Path

import pytest

GALLERY = Path(__file__).resolve().parents[1] / "examples" / "gallery"

pytestmark = pytest.mark.slow


def _load(name):
    spec = importlib.util.spec_from_file_location(f"gallery_{name}", GALLERY / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def page():
    _load("make_data").main()
    return _load("make_page")


def test_lists_parse(page):
    entries = page.read_entries()
    assert all(e.row and e.section and e.title for e in entries)
    assert {e.kind for e in entries} == {"plots", "tables"}
    rendered = [e for e in entries if e.needs is None]
    assert len({e.row for e in rendered}) == len(rendered)


def test_every_command_renders(page, tmp_path):
    entries = page.read_entries()
    rendered = page.render_all(entries, tmp_path)
    failures = [f"{e.row} (exit {e.returncode}): {e.log[-2000:]}" for e in rendered if e.returncode != 0]
    assert not failures, "\n\n".join(failures)
    for entry in rendered:
        suffixes = sorted(f.suffix for f in entry.files)
        if entry.kind == "plots":
            assert suffixes == [".png"], (entry.row, entry.files)
        else:
            assert ".tex" in suffixes and len(suffixes) <= 2, (entry.row, entry.files)
    missing = page.write_page(entries, tmp_path / "gallery.md")
    assert not missing
