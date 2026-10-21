"""Translate command lines written for the original plotting scripts
(``scripts/script_*.py``) into plotipus kind invocations.

Each kind module may define ``LEGACY = {script_name: translate}`` where
``translate(tokens) -> tokens`` rewrites the arguments of one line (script
path removed) into arguments of that kind; plugins can add more through
``registry.legacy_scripts``. Option abbreviations accepted by the old
parsers (``--name`` for ``--names``) are expanded against the new parser.
"""

import importlib
import shlex
from pathlib import Path

from . import registry

KINDS = ("line", "scatter", "hist", "map", "cat", "table")


def kind_module(kind):
    if kind in registry.kinds:
        module = registry.kinds[kind]
        return importlib.import_module(module) if isinstance(module, str) else module
    if kind not in KINDS:
        raise KeyError(f"Unknown plot kind '{kind}' (available: {', '.join(KINDS + tuple(registry.kinds))})")
    return importlib.import_module(f"plotipus.kinds.{kind}")


def _translators():
    table = {}
    for kind in KINDS:
        try:
            module = kind_module(kind)
        except ImportError:
            continue
        for script, translate in getattr(module, "LEGACY", {}).items():
            table[script] = (kind, translate)
    for script, (kind, extra) in registry.legacy_scripts.items():
        table[script] = (kind, (lambda tokens, extra=extra: list(extra) + list(tokens)) if not callable(extra) else extra)
    return table


def script_name(token):
    name = Path(token).name
    return name[:-3] if name.endswith(".py") else name


def is_legacy(tokens):
    return bool(tokens) and tokens[0].endswith(".py")


def expand_abbreviations(tokens, parser):
    """Replace unique option prefixes by the full option of ``parser``."""
    options = list(parser._option_string_actions)
    out = []
    for token in tokens:
        if token.startswith("--") and "=" not in token and token not in parser._option_string_actions:
            matches = [o for o in options if o.startswith(token)]
            if len(matches) == 1:
                token = matches[0]
            elif len(matches) > 1:
                # Prefer the option whose remainder is a plural 's' (--name -> --names).
                plural = [o for o in matches if o == token + "s"]
                if plural:
                    token = plural[0]
        out.append(token)
    return out


def translate(tokens):
    """``(kind, args)`` for a command line given as tokens (legacy script
    path first, or a kind name first)."""
    if not tokens:
        raise ValueError("empty command")
    if not is_legacy(tokens):
        return tokens[0], list(tokens[1:])
    name = script_name(tokens[0])
    table = _translators()
    if name not in table:
        raise KeyError(f"No translation for legacy script '{name}'")
    kind, translate_fn = table[name]
    args = translate_fn(list(tokens[1:]))
    parser = kind_module(kind).build_parser()
    return kind, expand_abbreviations(args, parser)


def translate_line(line):
    kind, args = translate(shlex.split(line))
    return kind, args


# --- Helpers for translators ---------------------------------------------------------


def option_values(tokens, flag):
    """Values following ``flag`` (up to the next option), or None."""
    if flag not in tokens:
        return None
    i = tokens.index(flag)
    values = []
    for token in tokens[i + 1:]:
        if token.startswith("-") and not _is_number(token):
            break
        values.append(token)
    return values


def _is_number(token):
    try:
        float(token)
        return True
    except ValueError:
        return False


def has(tokens, *flags):
    return any(flag in tokens for flag in flags)


def rename(tokens, mapping):
    """Rename options (``{"--old": "--new"}``; a None target drops the option
    together with its values)."""
    out = []
    skipping = False
    for token in tokens:
        if token.startswith("-") and not _is_number(token):
            skipping = False
            if token in mapping:
                target = mapping[token]
                if target is None:
                    skipping = True
                    continue
                out.extend(target if isinstance(target, (list, tuple)) else [target])
                continue
        elif skipping:
            continue
        out.append(token)
    return out


def replace_value(tokens, flag, old, new):
    out = list(tokens)
    for i, token in enumerate(out[:-1]):
        if token == flag and out[i + 1] == old:
            out[i + 1] = new
    return out
