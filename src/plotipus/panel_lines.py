"""Per-panel options: x range, title, x label and reference lines.

Kinds with several panels (``--panels`` columns or ``--variables`` values)
take one value per panel for each ``--panel_*`` option. Reference-line
entries may be ``none`` (no line in that panel) or several comma-separated
values; ``--panel_vertical_file``/``--panel_vertical_keys`` read the vertical
positions from a file (see :mod:`plotipus.values`).

Usage: :func:`add_panel_line_args` on the parser, :func:`resolve_panel_lines`
right after parsing, then :func:`draw_panel_lines` per panel.
"""

from rich import print as rprint

from . import style
from .args import parse_plot_label
from .plot import draw_horizontal_lines, draw_vertical_lines

_LINE_OPTIONS = ("panel_vertical", "panel_horizontal")
_STRING_OPTIONS = (
    "panel_vertical_label",
    "panel_vertical_style",
    "panel_vertical_color",
    "panel_horizontal_label",
    "panel_horizontal_style",
    "panel_horizontal_color",
)


def add_panel_line_args(parser, horizontal=True):
    """Add the ``--panel_*`` options (horizontal lines only when ``horizontal``)."""
    add = parser.add_argument
    add("--panel_rangex", nargs="+", type=float, default=None,
        help="Per-panel x range as flattened min max pairs, two values per panel.")
    add("--panel_title", nargs="+", type=parse_plot_label, default=None, help="Title of each panel.")
    add("--panel_labelx", nargs="+", type=parse_plot_label, default=None, help="x-axis label of each panel.")
    add("--panel_vertical", nargs="+", type=str, default=None,
        help="Vertical line(s) per panel: a value, comma-separated values, or 'none'.")
    add("--panel_vertical_file", type=str, default=None,
        help="Read --panel_vertical from a file (json, yaml, pkl, csv); with --panel_vertical_keys.")
    add("--panel_vertical_keys", nargs="+", type=str, default=None,
        help="Dot-separated key per panel into --panel_vertical_file ('none' to skip, {placeholders} allowed).")
    add("--panel_vertical_label", nargs="+", type=str, default=None, help="Label(s) per panel (comma-separated).")
    add("--panel_vertical_style", nargs="+", type=str, default=None, help="Line style(s) per panel (default '--').")
    add("--panel_vertical_color", nargs="+", type=str, default=None, help="Colour(s) per panel (default gray).")
    if horizontal:
        add("--panel_horizontal", nargs="+", type=str, default=None,
            help="Horizontal line per panel: a value or 'none'.")
        add("--panel_horizontal_label", nargs="+", type=str, default=None, help="Label per panel.")
        add("--panel_horizontal_style", nargs="+", type=str, default=None, help="Line style per panel.")
        add("--panel_horizontal_color", nargs="+", type=str, default=None, help="Colour per panel.")


def parse_panel_line_values(raw_values, flag_name, error=None):
    """One list of floats per panel (None for 'none'/'skip'/'')."""
    if raw_values is None:
        return None
    parsed = []
    for raw in raw_values:
        if str(raw).strip().lower() in ("none", "skip", ""):
            parsed.append(None)
            continue
        values = []
        for piece in str(raw).split(","):
            try:
                values.append(float(piece))
            except ValueError:
                message = f"{flag_name} values must be numbers or 'none' to skip a panel, got '{piece}' in '{raw}'"
                if error is None:
                    raise ValueError(message)
                error(message)
        parsed.append(values)
    return parsed


def parse_panel_line_strings(raw_values):
    """One list of strings per panel (each entry split on commas)."""
    if raw_values is None:
        return None
    return [str(raw).split(",") for raw in raw_values]


def resolve_panel_lines(args, parser=None, n_panels=None, unit="panel"):
    """Read --panel_vertical_file, parse every --panel_* option in place and,
    when ``n_panels`` is given, check each has one entry per panel."""
    error = parser.error if parser is not None else (lambda message: (_ for _ in ()).throw(ValueError(message)))
    file_given = getattr(args, "panel_vertical_file", None) is not None
    keys_given = getattr(args, "panel_vertical_keys", None) is not None
    if file_given or keys_given:
        if not (file_given and keys_given):
            error("--panel_vertical_file and --panel_vertical_keys must be given together")
        from .values import build_context, read_values_as_strings

        try:
            args.panel_vertical = read_values_as_strings(args.panel_vertical_file, args.panel_vertical_keys, build_context(args))
        except (OSError, KeyError, ValueError) as err:
            error(f"--panel_vertical_file: {err}")
        rprint(f"[cyan]Info:[/cyan] --panel_vertical from {args.panel_vertical_file}: {args.panel_vertical}")

    for name in _LINE_OPTIONS:
        if hasattr(args, name):
            setattr(args, name, parse_panel_line_values(getattr(args, name), f"--{name}", error))
    for name in _STRING_OPTIONS:
        if hasattr(args, name):
            setattr(args, name, parse_panel_line_strings(getattr(args, name)))

    if n_panels is None:
        return args
    rangex = getattr(args, "panel_rangex", None)
    if rangex is not None and len(rangex) != 2 * n_panels:
        error(f"--panel_rangex must provide exactly 2 values per {unit} ({2 * n_panels} expected, got {len(rangex)}).")
    for name in ("panel_title", "panel_labelx", *_LINE_OPTIONS, *_STRING_OPTIONS):
        values = getattr(args, name, None)
        if values is not None and len(values) != n_panels:
            error(f"--{name} must provide exactly one value per {unit} ({n_panels} expected, got {len(values)}).")
    return args


def has_panel_lines(args):
    return any(getattr(args, name, None) is not None for name in (*_LINE_OPTIONS, *_STRING_OPTIONS))


def _entry(values, idx):
    return values[idx] if values is not None else None


def panel_rangex(args, idx):
    """(min, max) of panel ``idx`` from --panel_rangex, or None."""
    rangex = getattr(args, "panel_rangex", None)
    if rangex is None:
        return None
    return rangex[2 * idx], rangex[2 * idx + 1]


def draw_panel_lines(ax, args, idx):
    """Draw the --panel_horizontal and --panel_vertical lines of panel ``idx``."""
    horizontal = getattr(args, "panel_horizontal", None)
    if horizontal is not None and horizontal[idx] is not None:
        draw_horizontal_lines(
            ax,
            horizontal[idx],
            labels=_entry(getattr(args, "panel_horizontal_label", None), idx),
            styles=_entry(getattr(args, "panel_horizontal_style", None), idx),
            colors=_entry(getattr(args, "panel_horizontal_color", None), idx),
            fontsize=style.linelabelfontsize,
        )
    vertical = getattr(args, "panel_vertical", None)
    if vertical is not None and vertical[idx] is not None:
        draw_vertical_lines(
            ax,
            vertical[idx],
            labels=_entry(getattr(args, "panel_vertical_label", None), idx),
            styles=_entry(getattr(args, "panel_vertical_style", None), idx),
            colors=_entry(getattr(args, "panel_vertical_color", None), idx),
            fontsize=style.linelabelfontsize,
        )
