"""The gallery (examples/gallery, T23): every uncommented command of its
lists renders, each into its own folder, and gives one figure for every
medium of the gallery project (slides and paper; tables: a .tex file, and
with --html its HTML twin)."""

import importlib.util
import sys
from pathlib import Path

import pytest

GALLERY = Path(__file__).resolve().parents[1] / "examples" / "gallery"

# One worker runs these: make_data writes the gallery data into the repository.
pytestmark = [pytest.mark.slow, pytest.mark.xdist_group("gallery")]


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
    failures = [f"{e.row} {medium} (exit {r.returncode}): {r.log[-2000:]}"
                for e in rendered for medium, r in e.renders.items() if r.returncode != 0]
    assert not failures, "\n\n".join(failures)
    assert page.MEDIA == ["slides", "paper"]
    for entry in rendered:
        if entry.kind == "plots":
            assert set(entry.renders) == set(entry.media()), entry.row
            for medium, result in entry.renders.items():
                assert [f.suffix for f in result.files] == [".png"], (entry.row, medium, result.files)
        else:
            suffixes = sorted(f.suffix for f in entry.renders[None].files)
            assert ".tex" in suffixes and len(suffixes) <= 2, (entry.row, suffixes)
    pinned = next(e for e in rendered if e.row == "H8")
    assert pinned.media() == ["paper"] and set(pinned.renders) == {"paper"}
    missing = page.write_page(entries, tmp_path / "gallery.md")
    assert not missing
