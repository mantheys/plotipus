"""Insets: a small plot inside a panel.

``--inset X0 X1 [Y0 Y1]`` zooms into the panel: the same command drawn again
in a box (``--inset_pos x y w h``, fractions of the panel), its range the
zoom, with a frame and connectors on the zoomed region. ``--inset_args
'OPTIONS'`` draws a variation instead: the command with these options on top
(another selection, other -x/-y, ``--binned``), as in a CMS inset of a
tighter selection or the seasonal cycle beside the Keeling curve.

The inset is drawn by the kind's own figure code: while :func:`drawing_into`
is active, :func:`plotipus.panels.create_panels` hands out the inset axes,
and the title, note and saving of that pass are skipped. The figure-level
options of the main command (lower panels, ranges, axis labels, reference
lines, the title and legend) do not carry into the inset; give them in
``--inset_args`` when the inset needs them.
"""

import contextlib
import copy
import shlex

from rich import print as rprint

from . import style

_TARGETS = []

# Options of the main figure that an inset starts without.
_RESET = {
    "lower": None, "rangex": None, "rangey": None, "labelx": None, "labely": None, "title": None, "note": None,
    "horizontal": None, "horizontal_label": None, "vertical": None, "vertical_label": None,
    "horizontal_band": None, "vertical_band": None, "sigma_lines": None, "delta_chi2_lines": None,
    "cl_lines": None, "point": None, "square": None, "line": None, "inset": None, "inset_args": None,
    "variables": None, "facet_row": None, "facet_col": None, "panel_grid": None, "panel_title": None,
    "panel_labely": None, "panel_rangey": None, "direct_labels": False, "mean_band": False,
    "no_hue_colorbar": True, "compact": None,
}


def add_inset_args(parser):
    group = parser.add_argument_group("inset")
    add = group.add_argument
    add("--inset", nargs="+", type=float, default=None, metavar="X0 X1 [Y0 Y1]",
        help="Zoom inset: the panel redrawn over x in [X0, X1] (and y in [Y0, Y1]) in a box, with connectors to "
        "the zoomed region.")
    add("--inset_args", type=str, default=None, metavar="'OPTIONS'",
        help="Inset of a variation of the command: these options on top of it (e.g. \"--select Selection -s "
        "'KD > 0.5'\" or \"-x Month --binned --estimator mean\"). Lower panels, ranges, labels, reference lines "
        "and the title do not carry over.")
    add("--inset_pos", nargs=4, type=float, default=[0.55, 0.55, 0.42, 0.42], metavar=("X", "Y", "W", "H"),
        help="Inset box in fractions of the panel: lower-left corner, width and height (default upper right).")
    add("--inset_panel", type=int, default=0, help="Index of the panel holding the inset (default 0).")


def target():
    """The axes an inset pass draws into, or None."""
    return _TARGETS[-1] if _TARGETS else None


@contextlib.contextmanager
def drawing_into(ax):
    _TARGETS.append(ax)
    try:
        yield ax
    finally:
        _TARGETS.pop()


def inset_namespace(args, parser):
    """The inset's arguments: ``args`` without the figure-level options, with
    --inset_args parsed on top (list options it names are replaced, not
    extended)."""
    ns = copy.copy(args)
    zoom = not args.inset_args
    for name, value in _RESET.items():
        if hasattr(ns, name) and not (zoom and name in ("labelx", "labely")):  # a zoom keeps the axis labels
            setattr(ns, name, value)
    tokens = shlex.split(args.inset_args) if args.inset_args else []
    for action in parser._actions:
        if any(token in action.option_strings for token in tokens) and isinstance(getattr(ns, action.dest, None), list):
            setattr(ns, action.dest, None)
    for action in parser._actions:
        action.required = False
    ns = parser.parse_args(tokens, namespace=ns)
    ns.no_legend = True  # the main legend explains the inset
    if args.inset and not args.inset_args:
        ns.rangex = list(args.inset[:2])
        ns.rangey = list(args.inset[2:4]) if len(args.inset) >= 4 else None
    return ns


def draw_inset(fig, panels, args, parser, draw):
    """Draw the inset of --inset/--inset_args into panel --inset_panel of
    ``panels`` with ``draw(namespace)`` (the kind's figure function)."""
    if not (getattr(args, "inset", None) or getattr(args, "inset_args", None)):
        return None
    if args.inset is not None and len(args.inset) not in (2, 4):
        rprint("[yellow]Warning:[/yellow] --inset takes X0 X1 or X0 X1 Y0 Y1; no inset drawn.")
        return None
    parent = panels[min(args.inset_panel, len(panels) - 1)]
    ax = parent.inset_axes(args.inset_pos)
    ax.set_zorder(parent.get_zorder() + 5)
    ns = inset_namespace(args, parser)
    with drawing_into(ax):
        draw(ns)
    ax.tick_params(labelsize=style.linelabelfontsize)
    for label in (ax.xaxis.label, ax.yaxis.label):
        label.set_fontsize(style.linelabelfontsize)
    if args.inset:
        ax.set_xlim(*args.inset[:2])
        if len(args.inset) >= 4:
            ax.set_ylim(*args.inset[2:4])
        if not args.inset_args:
            parent.indicate_inset_zoom(ax, edgecolor=style.role("muted"))
    ax._plotipus_inset = True
    return ax
