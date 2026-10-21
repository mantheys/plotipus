"""Read plot reference values (e.g. the positions of vertical/horizontal lines) from a file.

Used by the ``--*_file`` / ``--*_keys`` options of the plot kinds, so that values that
change when an upstream result is rerun (a selected cut, a threshold, a fit result...) are read
from the file that holds them instead of being typed into the command.

File formats, chosen by extension:
    .json               nested objects/arrays
    .yml / .yaml        nested mappings/sequences (needs PyYAML)
    .pkl / .pickle      a dict, list, pandas Series or single-row DataFrame
    .csv / .tsv         two columns, key and value (first row may be a header)

Keys are dot-separated paths into the loaded object (``a.b.0.c``; integers index lists).
Both the file path and the keys may contain ``{placeholder}`` fields, filled from a context
mapping (see ``build_context``). A key may also be ``none``/``skip``/'' to leave that entry empty,
or hold several comma-separated keys to return several values for one entry.
"""
import csv
import json
import os
import pickle


def build_context(args):
    """Placeholder values for file paths and keys: every string argument of `args` under its own
    name, and for list arguments their first element under the singular-free name
    (e.g. --configs a b -> {configs} = 'a', and {config} = 'a' as a convenience)."""
    context = {}
    for name, value in vars(args).items():
        if isinstance(value, (str, int, float)) and not isinstance(value, bool):
            context[name] = value
        elif isinstance(value, (list, tuple)) and value and isinstance(value[0], (str, int, float)):
            context[name] = value[0]
            if name.endswith("s"):
                context.setdefault(name[:-1], value[0])
    return context


def _load(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        with open(path) as f:
            return json.load(f)
    if ext in (".yml", ".yaml"):
        import yaml

        with open(path) as f:
            return yaml.safe_load(f)
    if ext in (".pkl", ".pickle"):
        with open(path, "rb") as f:
            obj = pickle.load(f)
        if hasattr(obj, "to_dict"):
            obj = obj.to_dict()
            # single-row DataFrame -> {column: value}
            if obj and all(isinstance(v, dict) and len(v) == 1 for v in obj.values()):
                obj = {k: next(iter(v.values())) for k, v in obj.items()}
        return obj
    if ext in (".csv", ".tsv"):
        with open(path, newline="") as f:
            rows = [r for r in csv.reader(f, delimiter="\t" if ext == ".tsv" else ",") if r]
        return {r[0].strip(): r[1].strip() for r in rows if len(r) >= 2}
    raise ValueError(f"Unsupported value file type '{ext}' ({path})")


def _lookup(obj, key, path):
    current = obj
    for part in key.split("."):
        if isinstance(current, (list, tuple)):
            try:
                current = current[int(part)]
                continue
            except (ValueError, IndexError):
                raise KeyError(f"'{part}' is not a valid index in key '{key}' of {path}")
        if not isinstance(current, dict) or part not in current:
            available = list(current.keys())[:20] if isinstance(current, dict) else type(current).__name__
            raise KeyError(f"key '{key}' not found in {path} (at '{part}'; available: {available})")
        current = current[part]
    return current


def read_values(path_template, key_templates, context=None):
    """Return one entry per key template: None for 'none'/'skip'/'', otherwise a list of the
    values found for its comma-separated keys. The path and keys are formatted with `context`."""
    context = context or {}
    path = os.path.expanduser(str(path_template).format(**context))
    obj = _load(path)
    entries = []
    for template in key_templates:
        if str(template).strip().lower() in ("none", "skip", ""):
            entries.append(None)
            continue
        values = []
        for key in str(template).split(","):
            values.append(_lookup(obj, key.strip().format(**context), path))
        entries.append(values)
    return entries


def read_values_as_strings(path_template, key_templates, context=None):
    """As read_values, but in the raw form of the --panel_vertical style options: one string per
    entry, comma-joined values or 'none'."""
    return [
        "none" if entry is None else ",".join(str(v) for v in entry)
        for entry in read_values(path_template, key_templates, context)
    ]
