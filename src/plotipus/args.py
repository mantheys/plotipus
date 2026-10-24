"""Command-line arguments shared by every plot kind, plus label helpers.

``COMMON_ARG_SPECS`` holds one entry per option (flags and argparse kwargs);
a kind picks the ones it supports with :func:`add_common_args`, optionally
overriding kwargs. :func:`add_panel_args` registers the per-panel options a
second time with a prefix (``lower_``) for lower panels.
"""

import argparse
import ast
import copy
import re

import numpy as np

from rich import print as rprint

from . import palettes, registry, style


def _auto_wrap_mathtext(value):
    """Wrap simple caret/subscript math notation in Matplotlib math text delimiters.

    This keeps plain text labels unchanged, but turns examples like
    "Cross Section (10^{-38} cm^{2})" into
    "Cross Section ($10^{-38} cm^{2}$)".
    """
    if not isinstance(value, str):
        return value

    if "$" in value:
        return value

    if re.search(r"[\^_]\{[^}]+\}", value) is None:
        return value

    wrapped = re.sub(
        r"\(([^()]*[\^_]\{[^}]+\}[^()]*)\)",
        lambda match: f"(${match.group(1)}$)",
        value,
    )

    if wrapped != value:
        return wrapped

    return f"${value}$"


def parse_plot_label(value):
    """Parse CLI label values, including raw-literal-like terminal input.

    Supported forms:
    - r'...'/r"..." passed as a single argument token.
    - shell-collapsed form from bash, e.g. r'Cross Section (...)' becoming
      rCross Section (...).
    - explicit r* prefix for unambiguous raw-style input, e.g.
      r*Cross Section (10^{-38} cm^{2}).
    """
    if value is None or not isinstance(value, str):
        return value

    text = value.strip()
    if not text:
        return value

    # Treat the literal string "None" as an explicit request for no label.
    if text.lower() == "none":
        return ""

    if text.startswith(("r'", 'r"', "R'", 'R"')):
        try:
            text = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            pass
    elif text.startswith(("r*", "R*")):
        text = text[2:].lstrip()
    elif (
        len(text) > 1
        and text[0] in {"r", "R"}
        and text[1].isupper()
        and any(token in text for token in ("^{", "_{", "\\", "$"))
    ):
        text = text[1:]

    return _auto_wrap_mathtext(text)


COMMON_ARG_SPECS = {
    "datafile": {
        "flags": ["--datafile"],
        "kwargs": {
            "nargs": "+",
            "type": str,
            "default": None,
            "help": "Path/name of the input data file(s) (pkl format). Provide "
            "multiple values to merge several files into one run.",
        },
    },
    "path": {
        "flags": ["--path"],
        "kwargs": {
            "nargs": "+",
            "type": str,
            "default": None,
            "help": "Base path(s) for --datafile lookups. Provide a single value to "
            "apply to every --datafile entry, or exactly as many values as "
            "--datafile entries to pick a different path per file. Relative "
            "values resolve inside the project data root. Pass 'default' to use "
            "the data root itself for that entry.",
        },
    },
    "configs": {
        "flags": ["--configs"],
        "kwargs": {
            "nargs": "+",
            "type": str,
            "default": None,
            "help": "Configuration(s) to load: files {config}_{name}_{datafile}.pkl, rows of column Config",
        },
    },
    "names": {
        "flags": ["--names", "-n"],
        "kwargs": {
            "nargs": "+",
            "type": str,
            "default": None,
            "help": "Name(s)/sample(s) to load: files {config}_{name}_{datafile}.pkl, rows of column Name",
        },
    },
    "variables": {
        "flags": ["--variables", "--facet", "-v"],
        "kwargs": {
            "nargs": "+",
            "type": str,
            "default": None,
            "help": "Values of the Variable column to keep, one panel each",
        },
    },
    "iterable": {
        "flags": ["--iterable", "--hue", "--i", "-i"],
        "kwargs": {
            "type": str,
            "default": None,
            "help": "Column whose values are drawn as separate series (colour)",
        },
    },
    "select": {
        "flags": ["--select"],
        "kwargs": {
            "nargs": "+",
            "action": "extend",
            "default": None,
            "help": "Columns/keys used for filtering. Repeat the flag to add more "
            "keys (e.g. --select Type --select Radius), or list them all in one "
            "invocation (--select Type Radius) - both accumulate.",
        },
    },
    "save_values": {
        "flags": ["--save_values", "-s"],
        "kwargs": {
            "nargs": "+",
            "action": "extend",
            "default": None,
            "help": "Values used alongside --select filtering. Repeat the flag to "
                "add more values, matched positionally to --select. Repeating a "
                "select key keeps any of its supplied values.",
        },
    },
    "remove_value": {
        "flags": ["--remove_value"],
        "kwargs": {
            "nargs": "+",
            "action": "extend",
            "default": None,
            "help": "Values used alongside --select to remove matching rows instead "
            "of keeping them. Repeat the flag to add more values.",
        },
    },
    "filename_select": {
        "flags": ["--filename_select"],
        "kwargs": {
            "nargs": "+",
            "action": "extend",
            "default": None,
            "help": "Which --select key(s) must always appear in the output "
            "filename (e.g. --filename_select FlashMatch), protected from the "
            "automatic length-based trimming in make_name_from_args - use this "
            "to keep otherwise-identical runs from overwriting each other's "
            "output file when they only differ in one --select/--save_values "
            "pair. Without this flag, filename generation is unchanged.",
        },
    },
    "filename_suffix": {
        "flags": ["--filename_suffix"],
        "kwargs": {
            "type": str,
            "default": None,
            "help": "Text appended to the output filename, for runs that differ only in an option "
            "the filename does not encode (e.g. --path to another sample folder).",
        },
    },
    "x": {
        "flags": ["-x"],
        "kwargs": {
            "type": str,
            "default": None,
            "help": "Column name for x-axis values",
        },
    },
    "y": {
        "flags": ["-y"],
        "kwargs": {
            "type": str,
            "default": None,
            "help": "Column name for y-axis values",
        },
    },
    "z": {
        "flags": ["-z"],
        "kwargs": {
            "type": str,
            "default": None,
            "help": "Column name for z-axis values",
        },
    },
    "reduce": {
        "flags": ["--reduce"],
        "kwargs": {
            "action": "store_true",
            "default": False,
            "help": "Reduce number of plotted lines for clarity",
        },
    },
    "bins": {
        "flags": ["--bins", "-b"],
        "kwargs": {
            "type": int,
            "default": 50,
            "help": "Number of bins for histogram",
        },
    },
    "percentile": {
        "flags": ["--percentile", "-p"],
        "kwargs": {
            "nargs": 2,
            "type": float,
            "default": None,
            "help": "Percentile range for axis limits",
        },
    },
    "labelx": {
        "flags": ["--labelx"],
        "kwargs": {
            "type": parse_plot_label,
            "default": None,
            "help": "Label for x-axis on plot",
        },
    },
    "labely": {
        "flags": ["--labely"],
        "kwargs": {
            "type": parse_plot_label,
            "default": None,
            "help": "Label for y-axis on plot",
        },
    },
    "labelz": {
        "flags": ["--labelz"],
        "kwargs": {
            "type": parse_plot_label,
            "default": None,
            "help": "Label for z/legend axis on plot",
        },
    },
    "logx": {
        "flags": ["--logx"],
        "kwargs": {
            "action": "store_true",
            "default": False,
            "help": "Set x-axis to logarithmic scale",
        },
    },
    "logy": {
        "flags": ["--logy"],
        "kwargs": {
            "action": "store_true",
            "default": False,
            "help": "Set y-axis to logarithmic scale",
        },
    },
    "logz": {
        "flags": ["--logz"],
        "kwargs": {
            "action": "store_true",
            "default": False,
            "help": "Set z-axis to logarithmic scale",
        },
    },
    "rangex": {
        "flags": ["--rangex"],
        "kwargs": {
            "nargs": 2,
            "type": float,
            "default": None,
            "help": "Range for x-axis (min max)",
        },
    },
    "rangey": {
        "flags": ["--rangey"],
        "kwargs": {
            "nargs": 2,
            "type": float,
            "default": None,
            "help": "Range for y-axis (min max)",
        },
    },
    "rangez": {
        "flags": ["--rangez"],
        "kwargs": {
            "nargs": 2,
            "type": float,
            "default": None,
            "help": "Range for z-axis/colorbar (min max)",
        },
    },
    "density": {
        "flags": ["--density"],
        "kwargs": {
            "action": "store_true",
            "default": False,
            "help": "Normalize to density",
        },
    },
    "zoom": {
        "flags": ["--zoom"],
        "kwargs": {
            "action": "store_true",
            "default": False,
            "help": "Enable zoom behavior",
        },
    },
    "norm": {
        "flags": ["--norm"],
        "kwargs": {
            "type": str,
            "choices": ["global", "horizontal", "vertical", "combined"],
            "default": None,
            "help": "Normalize the 2D histogram: 'global' makes the whole histogram sum to 1, "
            "'horizontal' normalizes each y-slice so it sums to 1 across x, "
            "'vertical' normalizes each x-slice so it sums to 1 across y, "
            "'combined' divides each bin by the sum of its own row and column totals",
        },
    },
    "matchx": {
        "flags": ["--matchx"],
        "kwargs": {
            "action": "store_true",
            "default": False,
            "help": "Match x-axis ranges across subplots",
        },
    },
    "matchy": {
        "flags": ["--matchy"],
        "kwargs": {
            "action": "store_true",
            "default": False,
            "help": "Match y-axis ranges across subplots",
        },
    },
    "horizontal": {
        "flags": ["--horizontal"],
        "kwargs": {
            "type": float,
            "nargs": "+",
            "default": None,
            "help": "Draw horizontal line(s) at specified y value(s)",
        },
    },
    "horizontal_label": {
        "flags": ["--horizontal_label"],
        "kwargs": {
            "type": str,
            "nargs": "+",
            "default": None,
            "help": "Label(s) for horizontal line(s), one per line",
        },
    },
    "horizontal_style": {
        "flags": ["--horizontal_style"],
        "kwargs": {
            "type": str,
            "nargs": "+",
            "default": None,
            "help": "Linestyle(s) for horizontal line(s) (e.g. -- : -. -), one per line",
        },
    },
    "horizontal_color": {
        "flags": ["--horizontal_color"],
        "kwargs": {
            "type": str,
            "nargs": "+",
            "default": None,
            "help": "Color(s) for horizontal line(s) (e.g. gray red C0), one per line",
        },
    },
    "vertical": {
        "flags": ["--vertical"],
        "kwargs": {
            "type": float,
            "nargs": "+",
            "default": None,
            "help": "Draw vertical line(s) at specified x value(s)",
        },
    },
    "vertical_label": {
        "flags": ["--vertical_label"],
        "kwargs": {
            "type": str,
            "nargs": "+",
            "default": None,
            "help": "Label(s) for vertical line(s), one per line",
        },
    },
    "vertical_style": {
        "flags": ["--vertical_style"],
        "kwargs": {
            "type": str,
            "nargs": "+",
            "default": None,
            "help": "Linestyle(s) for vertical line(s) (e.g. -- : -. -), one per line",
        },
    },
    "vertical_color": {
        "flags": ["--vertical_color"],
        "kwargs": {
            "type": str,
            "nargs": "+",
            "default": None,
            "help": "Color(s) for vertical line(s) (e.g. gray red C0), one per line",
        },
    },
    "xtick": {
        "flags": ["--xtick"],
        "kwargs": {
            "type": float,
            "nargs": "+",
            "default": None,
            "help": "X-axis position(s) at which to place a custom tick label",
        },
    },
    "xtick_label": {
        "flags": ["--xtick_label"],
        "kwargs": {
            "type": str,
            "nargs": "+",
            "default": None,
            "help": "Label(s) for custom x-axis tick(s), one per --xtick value",
        },
    },
    "xtick_height": {
        "flags": ["--xtick_height"],
        "kwargs": {
            "type": float,
            "default": None,
            "help": "How far (axes fraction) custom x-tick labels sit below the axis; "
            "raise/lower to fit them in the space before the fixed-position x-axis title",
        },
    },
    "xtick_side": {
        "flags": ["--xtick_side"],
        "kwargs": {
            "type": str,
            "choices": ["below", "above"],
            "nargs": "+",
            "default": None,
            "help": "Place custom x-tick label(s) below or above the axis line they're anchored to "
            "(default: below); one per --xtick value, reusing the last if shorter",
        },
    },
    "xtick_edge": {
        "flags": ["--xtick_edge"],
        "kwargs": {
            "type": str,
            "choices": ["bottom", "top"],
            "nargs": "+",
            "default": None,
            "help": "Anchor custom x-tick label(s) to the bottom or top axis line (default: bottom); "
            "one per --xtick value, reusing the last if shorter",
        },
    },
    "ytick": {
        "flags": ["--ytick"],
        "kwargs": {
            "type": float,
            "nargs": "+",
            "default": None,
            "help": "Y-axis position(s) at which to place a custom tick label",
        },
    },
    "ytick_label": {
        "flags": ["--ytick_label"],
        "kwargs": {
            "type": str,
            "nargs": "+",
            "default": None,
            "help": "Label(s) for custom y-axis tick(s), one per --ytick value",
        },
    },
    "ytick_height": {
        "flags": ["--ytick_height"],
        "kwargs": {
            "type": float,
            "default": None,
            "help": "How far (axes fraction) custom y-tick labels sit left of the axis; "
            "raise/lower to fit them in the space before the fixed-position y-axis title",
        },
    },
    "ytick_side": {
        "flags": ["--ytick_side"],
        "kwargs": {
            "type": str,
            "choices": ["left", "right"],
            "nargs": "+",
            "default": None,
            "help": "Place custom y-tick label(s) left or right of the axis line they're anchored to "
            "(default: left); one per --ytick value, reusing the last if shorter",
        },
    },
    "ytick_edge": {
        "flags": ["--ytick_edge"],
        "kwargs": {
            "type": str,
            "choices": ["left", "right"],
            "nargs": "+",
            "default": None,
            "help": "Anchor custom y-tick label(s) to the left or right axis line (default: left); "
            "one per --ytick value, reusing the last if shorter",
        },
    },
    "square": {
        "flags": ["--square"],
        "kwargs": {
            "nargs": "+",
            "type": float,
            "action": "append",
            "default": None,
            "metavar": "SQUARE",
            "help": "Draw rectangle(s) as float values grouped into x1 y1 x2 y2 (opposite corners); supports 4, 8, 12... values",
        },
    },
    "square_label": {
        "flags": ["--square_label"],
        "kwargs": {
            "nargs": "+",
            "type": str,
            "default": None,
            "help": "Label(s) for square(s); one label per square",
        },
    },
    "square_style": {
        "flags": ["--square_style"],
        "kwargs": {
            "type": str,
            "nargs": "+",
            "default": None,
            "help": "Linestyle(s) for square edge(s) (e.g. -- : -. -), one per square",
        },
    },
    "square_color": {
        "flags": ["--square_color"],
        "kwargs": {
            "type": str,
            "nargs": "+",
            "default": None,
            "help": "Color(s) for square edge(s) (e.g. gray red C0), one per square",
        },
    },
    "line": {
        "flags": ["--line"],
        "kwargs": {
            "nargs": "+",
            "type": float,
            "action": "append",
            "default": None,
            "metavar": "LINE",
            "help": "Draw custom line segment(s) as float values grouped into x1 y1 x2 y2 (endpoints); supports 4, 8, 12... values",
        },
    },
    "line_label": {
        "flags": ["--line_label"],
        "kwargs": {
            "nargs": "+",
            "type": str,
            "default": None,
            "help": "Label(s) for line(s); one label per line",
        },
    },
    "line_style": {
        "flags": ["--line_style"],
        "kwargs": {
            "type": str,
            "nargs": "+",
            "default": None,
            "help": "Linestyle(s) for line(s) (e.g. -- : -. -), one per line",
        },
    },
    "line_color": {
        "flags": ["--line_color"],
        "kwargs": {
            "type": str,
            "nargs": "+",
            "default": None,
            "help": "Color(s) for line(s) (e.g. gray red C0), one per line",
        },
    },
    "point": {
        "flags": ["--point"],
        "kwargs": {
            "nargs": "+",
            "type": float,
            "action": "append",
            "default": None,
            "metavar": "POINT",
            "help": "Draw point(s) as float values grouped into x y pairs; supports 2, 4, 6... values",
        },
    },
    "point_label": {
        "flags": ["--point_label"],
        "kwargs": {
            "nargs": "+",
            "type": str,
            "default": None,
            "help": "Point label(s); provide one label per point",
        },
    },
    "plot_style": {
        "flags": ["--plot_style", "--line_plot_style"],
        "kwargs": {
            "dest": "plot_style",
            "type": str,
            "default": "-",
            "help": "Plot line style",
        },
    },
    "plot_type": {
        "flags": ["--plot_type"],
        "kwargs": {
            "type": str,
            "default": None,
            "help": "Plot type override",
        },
    },
    "title": {
        "flags": ["--title"],
        "kwargs": {
            "type": parse_plot_label,
            "default": None,
            "help": "Title for the plot. Pass None to suppress the title entirely.",
        },
    },
    "output": {
        "flags": ["--output", "-o"],
        "kwargs": {
            "nargs": "+",
            "type": str,
            "default": None,
            "help": "Output filepath",
        },
    },
    "subfolder": {
        "flags": ["--subfolder"],
        "kwargs": {
            "type": str,
            "default": None,
            "help": "Save the plot inside this subfolder of the output path(s)",
        },
    },
    "debug": {
        "flags": ["--debug", "-d"],
        "kwargs": {
            "action": "store_true",
            "help": "Enable debug mode",
        },
    },
    "note": {
        "flags": ["--note"],
        "kwargs": {
            "type": str,
            "default": None,
            "help": "Text annotation to add to the plot (positioned automatically in best location)",
        },
    },
    "multiply": {
        "flags": ["--multiply"],
        "kwargs": {
            "type": float,
            "default": None,
            "help": "Multiply every --y value (and its error, if present) by this "
            "factor before plotting - e.g. for unit conversion or rescaling",
        },
    },
    "errory": {
        "flags": ["--errory"],
        "kwargs": {
            "action": "store_true",
            "default": False,
            "help": "Plot y-axis error bars/bands (requires an {y}Error or "
            "{y}Error+/{y}Error- column)",
        },
    },
    "errory_type": {
        "flags": ["--errory_type"],
        "kwargs": {
            "type": str,
            "default": "bars",
            "choices": ["bars", "bands"],
            "help": "Style of y-axis error display: 'bars' (errorbar) or 'bands' "
            "(shaded fill_between)",
        },
    },
}


def add_common_args(parser, arg_names, overrides=None):
    overrides = overrides or {}

    if "datafile" in arg_names and "path" not in arg_names:
        arg_names = list(arg_names) + ["path"]

    for arg_name in arg_names:
        if arg_name not in COMMON_ARG_SPECS:
            raise KeyError(f"Unknown common arg '{arg_name}'")

        base = COMMON_ARG_SPECS[arg_name]
        flags = list(base["flags"])
        kwargs = copy.deepcopy(base["kwargs"])

        override = copy.deepcopy(overrides.get(arg_name, {}))
        if "flags" in override:
            flags = list(override.pop("flags"))

        kwargs.update(override)
        parser.add_argument(*flags, **kwargs)

    if "--capitalize_legend" not in parser._option_string_actions:
        parser.add_argument(
            "--capitalize_legend",
            action="store_true",
            default=False,
            help="Capitalize the first letter of each word in legend entries",
        )

    if "--legend_loc" not in parser._option_string_actions:
        parser.add_argument(
            "--legend_loc",
            action=_LegendLocAction,
            default=None,
            help="Legend location for all panels (matplotlib loc, e.g. 'lower left'); default from the style",
        )

    if "--legend_ncol" not in parser._option_string_actions:
        parser.add_argument(
            "--legend_ncol",
            type=int,
            action=_LegendNcolAction,
            default=None,
            help="Number of legend columns for all legends (e.g. 2 to halve the height of a long legend)",
        )

    if "--palette" not in parser._option_string_actions:
        parser.add_argument(
            "--palette",
            action=_PaletteAction,
            choices=palettes.names(),
            default=None,
            help="Categorical colour palette (default: the style's palette, petroff10); tab10 restores "
            "matplotlib's default colours.",
        )


class _LegendLocAction(argparse.Action):
    """Override the configured legend location (style legend_style.loc)
    for every legend drawn by this run."""

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)
        style.set_legend_option("loc", values)


class _LegendNcolAction(argparse.Action):
    """Override the number of legend columns (style legend_style.ncol)
    for every legend drawn by this run."""

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)
        style.set_legend_option("ncol", values)


class _PaletteAction(argparse.Action):
    """Make the named palette the colour cycle (style key palette) for
    every figure drawn by this run."""

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)
        palettes.apply(values)


_WARNED_MAPPINGS = set()


def _mapping_lookup(mapping_dict, value):
    """``mapping_dict[value]`` trying the value, its int and its str form;
    None when absent."""
    if mapping_dict is None:
        return None
    candidates = [value]
    try:
        as_int = int(value)
        if as_int == value or isinstance(value, str):
            candidates += [as_int, str(as_int)]
    except (ValueError, TypeError):
        pass
    candidates.append(str(value))
    for candidate in candidates:
        try:
            if candidate in mapping_dict:
                return mapping_dict[candidate]
        except TypeError:
            continue
    return None


def _missing_mapping(mapping_name):
    if mapping_name not in _WARNED_MAPPINGS:
        _WARNED_MAPPINGS.add(mapping_name)
        rprint(
            f"[yellow]Warning:[/yellow] Mapping '{mapping_name}' was not found or is not a "
            "dictionary. Falling back to default labeling."
        )


def map_iterable_label(iterable_value, iterable_name, mapping_name=None, unique_iterables_count=None):
    """Display label of one value of column ``iterable_name``: from the named
    mapping when given, else from a plugin label hook for that column
    (``registry.label_hooks``), else the value itself."""
    if mapping_name is not None:
        mapping_dict = style.get_mapping_dict(mapping_name)
        if mapping_dict is None:
            _missing_mapping(mapping_name)
            return str(iterable_value)
        label = _mapping_lookup(mapping_dict, iterable_value)
        return str(iterable_value) if label is None else str(label)

    hook = registry.label_hooks.get(iterable_name)
    if hook is not None:
        label = hook(iterable_value, unique_iterables_count)
        if label is not None:
            return str(label)

    return str(iterable_value)


def map_iterable_color(iterable_value, mapping_name, iterable_name=None):
    """Colour of one value from the named mapping (``Cn``, names, hex and
    ``rgb(r,g,b)``), else from a plugin colour hook for the column; None lets
    the caller fall back to the colour cycle."""
    if mapping_name is None:
        hook = registry.color_hooks.get(iterable_name)
        return style.resolve_mapped_color(hook(iterable_value)) if hook is not None else None

    mapping_dict = style.get_mapping_dict(mapping_name)
    if mapping_dict is None:
        _missing_mapping(mapping_name)
        return None
    return style.resolve_mapped_color(_mapping_lookup(mapping_dict, iterable_value))


def _format_unit(unit):
    """Wrap unit in math-mode delimiters if it contains LaTeX commands.

    Handles partially-math strings like ``$\\mu$s`` by extracting the content
    of inline ``$...$`` pairs and re-wrapping the whole unit in a single block.
    """
    if not unit:
        return unit
    # Already a single, complete math-mode block — return as-is.
    if re.fullmatch(r'\$[^$]+\$', unit):
        return unit
    # Contains LaTeX commands or partial math delimiters — normalise and wrap.
    if re.search(r'\\[a-zA-Z]+|[\^_]\{|\$', unit):
        # Replace inline $...$ pairs with their content (adding a trailing space
        # so e.g. "$\mu$s" becomes "\mu s" rather than "\mus").
        cleaned = re.sub(r'\$([^$]*)\$', r'\1 ', unit).strip()
        cleaned = cleaned.replace('$', '')
        return f"${cleaned}$"
    return unit


def resolve_axis_label(explicit_label, col_name, df=None):
    """Return axis label with unit from a *Unit column appended when available.

    The unit is appended unless the base label already ends with a parenthetical
    group — which indicates the caller has already included unit information.
    Units containing LaTeX commands (e.g. \\sigma, $\\mu$s) are normalised into
    a single math-mode block automatically.
    """
    if explicit_label == "":
        return ""
    base = explicit_label if explicit_label is not None else (col_name or "")
    if df is not None and col_name is not None:
        # Try exact match first, then progressively strip leading camel-case
        # words (e.g. "SmoothedCounts" -> "Counts") to find a *Unit column.
        candidates = [col_name]
        parts = re.findall(r'[A-Z][a-z0-9]*|[a-z0-9]+', col_name)
        for i in range(1, len(parts)):
            candidates.append("".join(parts[i:]))
        unit_col = next((f"{c}Unit" for c in candidates if f"{c}Unit" in df.columns), None)
        if unit_col is not None:
            units = df[unit_col].dropna()
            if not units.empty:
                unit = str(units.iloc[0]).strip()
                if unit:
                    formatted = _format_unit(unit)
                    already_present = (
                        f"({formatted})" in base
                        or f"({unit})" in base
                        # a trailing "(...)" group, optionally raised to a power
                        # such as "(kT · year)$^{-1}$", already carries the unit
                        or bool(re.search(r'\([^)]+\)(\$\^\{[^}]*\}\$)?\s*$', base))
                    )
                    if not already_present:
                        return f"{base} ({formatted})"
    return base


def resolve_plot_kwargs(selected_plot_type):
    """Resolve plot type to plot_type and drawstyle kwargs.

    Args:
        selected_plot_type: Plot type string (e.g., 'step', 'plot', 'line')

    Returns:
        dict: Kwargs dict with plot_type and optional drawstyle
    """
    if selected_plot_type == "step":
        return {
            "plot_type": "plot",
            "drawstyle": "steps-mid",
        }
    return {
        "plot_type": selected_plot_type,
    }


# Options that exist once per panel; add_panel_args registers them again with
# a prefix (e.g. --lower_labely) for the lower panels.
PANEL_ARG_NAMES = (
    "labely",
    "rangey",
    "logy",
    "plot_type",
    "horizontal",
    "horizontal_label",
    "horizontal_style",
    "horizontal_color",
)


def add_panel_args(parser, prefix="lower_", names=PANEL_ARG_NAMES, aliases=None):
    """Register the per-panel options under ``--{prefix}{option}`` (dest
    ``{prefix}{option}``, default None = inherit/skip). ``aliases`` maps an
    option name to extra (legacy) flags, e.g. ``{"labely": ["--bottom_labely"]}``."""
    aliases = aliases or {}
    for name in names:
        base = COMMON_ARG_SPECS[name]
        kwargs = copy.deepcopy(base["kwargs"])
        kwargs["default"] = None
        kwargs.pop("choices", None)
        kwargs["dest"] = f"{prefix}{name}"
        if "help" in kwargs:
            kwargs["help"] = f"[{prefix.rstrip('_')} panel] " + kwargs["help"]
        flags = [f"--{prefix}{flag.lstrip('-')}" for flag in base["flags"] if flag.startswith("--")]
        flags += [flag for flag in aliases.get(name, []) if flag not in parser._option_string_actions]
        parser.add_argument(*flags, **kwargs)


# --- Overlay values (--point, --square, --line) ---------------------------------


def parse_point_pairs(point_values):
    if point_values is None:
        return []

    if isinstance(point_values, (list, tuple)) and len(point_values) > 0 and isinstance(
        point_values[0], (list, tuple, np.ndarray)
    ):
        flattened = [value for group in point_values for value in group]
    else:
        flattened = list(point_values)

    if len(flattened) % 2 != 0:
        raise ValueError(
            "--point expects an even number of float values (x y pairs)."
        )

    return [
        (float(flattened[idx]), float(flattened[idx + 1]))
        for idx in range(0, len(flattened), 2)
    ]


def normalize_point_labels(point_labels, n_points):
    if point_labels is None:
        return None, None

    if isinstance(point_labels, str):
        labels = [point_labels]
    else:
        labels = list(point_labels)

    if len(labels) != n_points:
        return None, (
            f"--point_label expects {n_points} label(s) to match --point pairs, "
            f"but got {len(labels)}."
        )

    return labels, None


def parse_square_quads(square_values):
    if square_values is None:
        return []

    if isinstance(square_values, (list, tuple)) and len(square_values) > 0 and isinstance(
        square_values[0], (list, tuple, np.ndarray)
    ):
        flattened = [value for group in square_values for value in group]
    else:
        flattened = list(square_values)

    if len(flattened) % 4 != 0:
        raise ValueError(
            "--square expects a multiple-of-4 number of float values (x1 y1 x2 y2 per square)."
        )

    return [
        (
            float(flattened[idx]),
            float(flattened[idx + 1]),
            float(flattened[idx + 2]),
            float(flattened[idx + 3]),
        )
        for idx in range(0, len(flattened), 4)
    ]


def normalize_square_labels(square_labels, n_squares):
    if square_labels is None:
        return None, None

    if isinstance(square_labels, str):
        labels = [square_labels]
    else:
        labels = list(square_labels)

    if len(labels) != n_squares:
        return None, (
            f"--square_label expects {n_squares} label(s) to match --square groups, "
            f"but got {len(labels)}."
        )

    return labels, None


def parse_line_segments(line_values):
    if line_values is None:
        return []

    if isinstance(line_values, (list, tuple)) and len(line_values) > 0 and isinstance(
        line_values[0], (list, tuple, np.ndarray)
    ):
        flattened = [value for group in line_values for value in group]
    else:
        flattened = list(line_values)

    if len(flattened) % 4 != 0:
        raise ValueError(
            "--line expects a multiple-of-4 number of float values (x1 y1 x2 y2 per line)."
        )

    return [
        (
            float(flattened[idx]),
            float(flattened[idx + 1]),
            float(flattened[idx + 2]),
            float(flattened[idx + 3]),
        )
        for idx in range(0, len(flattened), 4)
    ]


def normalize_line_labels(line_labels, n_lines):
    if line_labels is None:
        return None, None

    if isinstance(line_labels, str):
        labels = [line_labels]
    else:
        labels = list(line_labels)

    if len(labels) != n_lines:
        return None, (
            f"--line_label expects {n_lines} label(s) to match --line groups, "
            f"but got {len(labels)}."
        )

    return labels, None
