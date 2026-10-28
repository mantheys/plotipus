"""The project's colour registry (style guide C1): a category keeps its
colour in every figure of the project.

``colors.json`` next to ``plotipus.toml`` maps each hue column to its
values' colours, ``{"Sample": {"Signal": "C1", "Background": "C0"}}``
(palette slots ``Cn``, or any colour a mapping takes). ``plotipus colors``
writes it from the project's data and command lists, keeping the colours
already given; plots only read it. A ``--iterable_color_mapping`` (or a
plugin colour hook) still wins, data (``--data_hue``) stay in ink, and
``--hue_cmap`` colours ordered values from its colour map instead. A value
missing from a registered column takes a free palette colour with a
warning naming the command that adds it.
"""

import json
import shlex
from pathlib import Path

import numpy as np
import pandas as pd
from rich import print as rprint

REGISTRY_NAME = "colors.json"
HUE_FLAGS = ("--hue", "--iterable", "--i", "-i", "--contour_hue")
DATA_FLAGS = ("--data_hue", "--overlay")

_cache = {}  # path -> (mtime, registry)
_warned = set()


def registry_path():
    """``colors.json`` at the root of the current project."""
    from .project import load_project

    return load_project().root / REGISTRY_NAME


def load(path=None):
    """The registry {column: {value: colour}}, {} without a file."""
    path = Path(path) if path is not None else registry_path()
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {}
    if path not in _cache or _cache[path][0] != mtime:
        _cache[path] = (mtime, json.loads(path.read_text(encoding="utf-8")))
    return _cache[path][1]


def registered_color(args, column, value):
    """Colour of ``value`` of ``column`` in the registry, or None (no
    registry entry for the column, or --hue_cmap). A value missing from a
    registered column warns once."""
    if column is None or value is None or getattr(args, "hue_cmap", None):
        return None
    entries = load().get(str(column))
    if entries is None:
        return None
    color = entries.get(str(value))
    if color is None:
        if (column, str(value)) not in _warned:
            _warned.add((column, str(value)))
            rprint(f"[yellow]Warning:[/yellow] {column}={value} has no colour in {REGISTRY_NAME}: it takes a free "
                   "palette colour here, maybe another elsewhere. 'plotipus colors' adds it (rule C1).")
        return None
    from . import style

    return style.resolve_mapped_color(color)


def hue_color(value, args, column):
    """Colour of a hue value: its --iterable_color_mapping (or plugin hook)
    colour, else its registered colour, else None (the next free one)."""
    from .args import map_iterable_color

    return (map_iterable_color(value, args.iterable_color_mapping, column)
            or registered_color(args, column, value))


def avoid_registered(colors, args, column):
    """Keep the registered colours of ``column`` off the values missing from
    the registry, so they do not look like a registered value of another
    figure."""
    if column is None or getattr(args, "hue_cmap", None):
        return
    from . import style

    entries = load().get(str(column)) or {}
    colors.avoid(style.resolve_mapped_color(c) for c in entries.values())


# --- plotipus colors -----------------------------------------------------------------------------


def _list_columns(lines):
    """(hue columns, data values) of plot command lines: the --hue columns of
    commands without --hue_cmap, and every --data_hue value (data stay ink)."""
    columns, data = [], set()
    for line in lines:
        try:
            tokens = shlex.split(line)
        except ValueError:
            continue
        for i, token in enumerate(tokens):
            if token in HUE_FLAGS and i + 1 < len(tokens) and "--hue_cmap" not in tokens:
                if tokens[i + 1] not in columns:
                    columns.append(tokens[i + 1])
            elif token in DATA_FLAGS:
                for value in tokens[i + 1:]:
                    if value.startswith("--"):
                        break
                    data.add(value)
    return columns, data


def _values(frames, column, exclude):
    """Scalar values of ``column`` over ``frames``, in order of appearance."""
    seen = []
    for frame in frames:
        if column not in frame.columns:
            continue
        for value in frame[column].tolist():
            if value is None or isinstance(value, (list, tuple, dict, np.ndarray)) or pd.isna(value):
                continue
            key = str(value)
            if key not in seen and key not in exclude:
                seen.append(key)
    return seen


def update(columns=None, dry_run=False):
    """Add the hue values of the project's data to ``colors.json``: the
    ``columns`` given, else the --hue columns of its plot command lists.
    Registered values keep their colour; new ones take the free palette
    slots of their column in order of appearance (sorted data files). Returns
    {column: [added values]}."""
    from .io import read_pickle_frame
    from .palettes import current_colors
    from .project import load_project
    from .runner import read_commands

    project = load_project()
    lines = [line for path in sorted(Path(project.plots_dir).glob("*_scripts.txt")) for line in read_commands(path)]
    listed, data = _list_columns(lines)
    columns = list(columns or listed)
    frames = [read_pickle_frame(path) for path in sorted(Path(project.data_root).rglob("*.pkl"))]
    path = project.root / REGISTRY_NAME
    registry = {column: dict(entries) for column, entries in load(path).items()}
    n = len(current_colors())
    added = {}
    for column in columns:
        entries = registry.setdefault(column, {})
        new = [v for v in _values(frames, column, data) if v not in entries]
        used = {color for color in entries.values()}
        free = [f"C{k}" for k in range(n) if f"C{k}" not in used]
        if len(new) > len(free):
            rprint(f"[yellow]Warning:[/yellow] {column}: {len(entries) + len(new)} values for the {n} palette "
                   "colours; colours repeat (--palette picks a longer palette, --hue_cmap suits ordered values).")
        for k, value in enumerate(new):
            entries[value] = free[k] if k < len(free) else f"C{len(entries) % n}"
        added[column] = new
        if not entries:
            del registry[column]
    for column, values in added.items():
        print(f"{column}: " + (", ".join(f"{v} = {registry[column][v]}" for v in values) if values else "no new values"))
    if not dry_run:
        path.write_text(json.dumps(registry, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote {path}")
    return added
