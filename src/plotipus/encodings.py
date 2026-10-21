"""How series are told apart: colour (hue), line style/fill (style) and legends.

Two columns encode the series of a plot:

* ``--iterable`` / ``--hue``: one colour per value (from
  ``--iterable_color_mapping`` or the colour cycle ``C0, C1, ...``).
* ``--comparable`` / ``--style``: one line style per value (or, with
  ``--comparable_fill_strength``, one fill opacity), explained by a second,
  black legend.

``--invert_style`` swaps the two roles. :func:`draw_legends` places the
primary (colour) legend and the secondary (style) legend where they cover the
least data.
"""

import copy

import matplotlib
import matplotlib.lines as mlines
import matplotlib.patches as mpatches
import numpy as np

from . import style
from .args import map_iterable_label
from .plot import (
    apply_legend_pair_clear_of_data,
    apply_legend_style,
    apply_legend_style_clear_of_data,
    apply_legend_style_free,
    enable_legend_frame,
)

LINESTYLES = ["-", "--", ":", "-."]
HATCHES = ["", "/", "\\", "x", ".", "o"]
FILL_ALPHAS = [0.8, 0.55, 0.35, 0.15]


def add_encoding_args(parser, comparable_default=None, comparable_flags=("--comparable", "--style", "-c")):
    """Options of the hue/style encodings and their legends."""
    add = parser.add_argument
    add(*comparable_flags, dest="comparable", type=str, default=comparable_default,
        help="Column drawn as a second series dimension: one line style (or fill opacity) per value, "
        "explained by a separate legend.")
    add("--comparable_linestyles", nargs="+", type=str, default=None,
        help="Line styles cycled over the comparable values (default: - -- : -.).")
    add("--comparable_reverse", action="store_true", default=False,
        help="Reverse the order of the styles assigned to the comparable values.")
    add("--comparable_linewidths", nargs="+", type=float, default=None,
        help="Line width for all comparable values (one value) or one per value.")
    add("--comparable_fill_strength", action="store_true", default=False,
        help="Encode comparable values by fill opacity (solid lines, fading fills) instead of line style.")
    add("--comparable_hatches", nargs="+", type=str, default=None,
        help="Hatch pattern per comparable value (with --fill).")
    add("--comparable_mapping", type=str, default=None,
        help="Mapping (style mappings) renaming the comparable values in the legend.")
    add("--comparable_title", type=str, default=None,
        help="Heading of the comparable legend (default: the column name; 'None' for no heading).")
    add("--comparable_order_reverse", action="store_true", default=False,
        help="Reverse the draw and legend order of the comparable values.")
    add("--comparable_legend_loc", type=str, default=None,
        help="Pin the comparable legend to a matplotlib loc (default: least obstructed corner).")
    add("--comparable_legend_panel", type=int, default=None,
        help="Index of the panel carrying the comparable legend (default: --legend_panel).")
    add("--iterable_mapping", "--hue_mapping", dest="iterable_mapping", type=str, default=None,
        help="Mapping (style mappings) renaming the hue values in the legend; its key order sets the draw order.")
    add("--iterable_color_mapping", "--hue_color_mapping", dest="iterable_color_mapping", type=str, default=None,
        help="Mapping (style mappings) giving the colour of each hue value (Cn, names, hex, rgb(r,g,b)); "
        "its key order sets the draw order.")
    add("--iterable_reverse", action="store_true", default=False,
        help="Reverse the colours (or, with --invert_style, line styles) assigned to the hue values.")
    add("--iterable_order_reverse", action="store_true", default=False,
        help="Reverse the draw and legend order of the hue values.")
    add("--invert_style", action="store_true", default=False,
        help="Swap roles: colours for the comparable values, line styles for the hue values.")
    add("--fill", action="store_true", default=False,
        help="Fill step outlines with a translucent colour.")
    add("--fill_alpha", nargs="+", type=float, default=None,
        help="Fill opacity: flat value with --fill; with --comparable_fill_strength one value scales "
        "the default sequence 0.8 0.55 0.35 0.15 and N values set each comparable's opacity.")
    add("--fill_hatch_color", action="store_true", default=False,
        help="Draw fill hatches at full opacity in the line colour.")
    add_legend_args(parser)


def add_legend_args(parser):
    add = parser.add_argument
    add("--draw_legend", type=str, default="both", choices=["both", "iterable", "comparable", "none"],
        help="Which legends to draw: both, iterable (colours), comparable (styles) or none.")
    add("--no_legend", action="store_true", default=False, help="Draw no legend.")
    add("--single_legend", action="store_true", default=False,
        help="Draw the legend also when there is a single hue value.")
    add("--legend_frame", nargs="?", type=float, const=0.8, default=None, metavar="ALPHA",
        help="Draw legends on a translucent white box (opacity ALPHA, default 0.8).")
    add("--legend_free", action="store_true", default=False,
        help="Place a single legend at the free position covering the least data (not only corners).")
    add("--legend_panel", type=int, default=-1,
        help="Index of the panel carrying the legend (default -1: the last one).")


def setup_legend_frame(args):
    if getattr(args, "legend_frame", None) is not None:
        enable_legend_frame(args.legend_frame)


def legend_selection(args):
    if getattr(args, "no_legend", False):
        return "none"
    return getattr(args, "draw_legend", "both") or "both"


def _reverse_index(index, n_total, reverse):
    if reverse and n_total is not None:
        return n_total - 1 - index
    return index


def resolve_linestyle(index, args, n_total=None, reverse=None):
    if getattr(args, "comparable_fill_strength", False):
        return "-"
    styles = list(getattr(args, "comparable_linestyles", None) or LINESTYLES)
    effective_reverse = getattr(args, "comparable_reverse", False) if reverse is None else reverse
    return styles[_reverse_index(index, n_total, effective_reverse) % len(styles)]


def resolve_fill_alpha(index, args, n_total=None):
    index = _reverse_index(index, n_total, getattr(args, "comparable_reverse", False))
    fill_alpha = getattr(args, "fill_alpha", None)
    if fill_alpha is not None and n_total is not None and len(fill_alpha) == n_total:
        return fill_alpha[index % len(fill_alpha)]
    alpha = FILL_ALPHAS[index % len(FILL_ALPHAS)]
    if fill_alpha:
        alpha = min(alpha * fill_alpha[0], 1.0)
    return alpha


def resolve_linewidth(index, args, n_total=None):
    widths = getattr(args, "comparable_linewidths", None)
    if not widths:
        return None
    index = _reverse_index(index, n_total, getattr(args, "comparable_reverse", False))
    if n_total is not None and len(widths) == n_total:
        return widths[index % len(widths)]
    return widths[0]


def resolve_hatch(index, args, n_total=None):
    hatches = list(getattr(args, "comparable_hatches", None) or HATCHES)
    index = _reverse_index(index, n_total, getattr(args, "comparable_reverse", False))
    return hatches[index % len(hatches)]


def resolve_cycle_color(index, n_total=None, reverse=False):
    """``C{index}``, counted from the end when ``reverse``."""
    return f"C{_reverse_index(index, n_total, reverse)}"


def fill_options(index, args, n_total):
    """(fill_alpha, fill_hatch) of the comparable value at ``index``."""
    strength = getattr(args, "comparable_fill_strength", False)
    if strength:
        return resolve_fill_alpha(index, args, n_total=n_total), None
    if getattr(args, "fill", False):
        alpha = (getattr(args, "fill_alpha", None) or [0.15])[0]
        return alpha, resolve_hatch(index, args, n_total=n_total)
    return None, None


def order_values(values, args):
    """Hue values in draw order: the key order of --iterable_color_mapping (or
    --iterable_mapping) first, then the rest in data order; reversed by
    --iterable_order_reverse."""
    values = list(values)
    mapping_name = getattr(args, "iterable_color_mapping", None) or getattr(args, "iterable_mapping", None)
    mapping = style.get_mapping_dict(mapping_name)
    if mapping is not None:
        present = set(values)
        in_map = [v for v in mapping if v in present]
        values = in_map + [v for v in values if v not in set(mapping)]
    if getattr(args, "iterable_order_reverse", False):
        values = values[::-1]
    return values


def comparable_legend_title(args):
    title = getattr(args, "comparable_title", None)
    if title == "None":
        return None
    return title if title is not None else getattr(args, "comparable", None)


def iterable_legend_title(args):
    title = args.labelz if getattr(args, "labelz", None) is not None else getattr(args, "iterable", None)
    return None if title == "None" else title


def comparable_maps(values, column, args):
    """{label: linestyle} and {label: fill alpha} for the comparable legend."""
    style_map, alpha_map = {}, {}
    if len(values) <= 1:
        return style_map, alpha_map
    for index, value in enumerate(values):
        label = map_iterable_label(value, column, getattr(args, "comparable_mapping", None))
        if getattr(args, "comparable_fill_strength", False):
            alpha_map[label] = resolve_fill_alpha(index, args, n_total=len(values))
        else:
            style_map[label] = resolve_linestyle(index, args, n_total=len(values))
    return style_map, alpha_map


def draw_legends(
    ax,
    args,
    primary_title,
    handles,
    labels,
    secondary_title=None,
    style_map=None,
    alpha_map=None,
    selection=None,
    **loc_kwargs,
):
    """Draw the primary (colour) legend and, when ``style_map``/``alpha_map``
    describe a second encoding, an independent secondary legend for it.

    Unpinned legends go where they cover the least data; the pair is placed
    jointly so the two never overlap. ``selection`` is ``both``,
    ``iterable``, ``comparable`` or ``none``.
    """
    explicit_loc = getattr(args, "legend_loc", None)
    comparable_loc = getattr(args, "comparable_legend_loc", None)
    if loc_kwargs:
        primary_loc_kwargs = dict(loc_kwargs)
    elif explicit_loc:
        primary_loc_kwargs = {"loc": explicit_loc}
    else:
        primary_loc_kwargs = {}

    if alpha_map and handles:
        # Fill-strength mode: show each colour as a filled swatch.
        def _swatch(handle):
            getter = getattr(handle, "get_edgecolor", None) or getattr(handle, "get_color", None)
            color = getter() if getter else "black"
            if isinstance(color, (list, tuple, np.ndarray)) and len(color) and isinstance(color[0], (list, tuple, np.ndarray)):
                color = color[0]
            rgb = matplotlib.colors.to_rgb(color)
            return mpatches.Patch(facecolor=(*rgb, 0.45), edgecolor=rgb, linewidth=2)

        handles = [_swatch(h) for h in handles]
    elif style_map and handles:
        # The secondary legend explains the line styles: draw colours solid.
        def _solid(handle):
            proxy = copy.copy(handle)
            if hasattr(proxy, "set_linestyle"):
                proxy.set_linestyle("-")
            return proxy

        handles = [_solid(h) for h in handles]

    primary_kwargs = dict(
        title=primary_title,
        handles=handles,
        labels=labels,
        capitalize_labels=getattr(args, "capitalize_legend", False),
    )
    has_secondary = bool(style_map or alpha_map)
    secondary_kwargs = None
    if has_secondary:
        widths = list(getattr(args, "comparable_linewidths", None) or [])
        if alpha_map:
            proxies = [
                mpatches.Patch(
                    facecolor=(0.5, 0.5, 0.5, alpha),
                    edgecolor="black",
                    linewidth=widths[i] if len(widths) == len(alpha_map) else 1.0,
                )
                for i, alpha in enumerate(alpha_map.values())
            ]
            secondary_labels = list(alpha_map.keys())
        else:
            proxies = [
                mlines.Line2D([], [], color="black", linestyle=line_style,
                              linewidth=widths[i] if len(widths) == len(style_map) else 1.5)
                for i, line_style in enumerate(style_map.values())
            ]
            secondary_labels = list(style_map.keys())
        secondary_kwargs = dict(
            title=None if secondary_title is None else str(secondary_title),
            handles=proxies,
            labels=secondary_labels,
            capitalize_labels=False,
        )

    def _place_secondary_around(primary_legend):
        ax.add_artist(primary_legend)
        if comparable_loc:
            return apply_legend_style(ax, loc=comparable_loc, **secondary_kwargs)
        fig = ax.figure
        fig.canvas.draw()
        return apply_legend_style_clear_of_data(
            ax,
            avoid_boxes=[primary_legend.get_window_extent(fig.canvas.get_renderer())],
            **secondary_kwargs,
        )

    selection = selection or legend_selection(args)
    draw_primary = selection in ("both", "iterable")
    draw_secondary = selection in ("both", "comparable") and has_secondary
    if not draw_primary and not draw_secondary:
        return None

    if not draw_primary:
        if comparable_loc:
            return apply_legend_style(ax, loc=comparable_loc, **secondary_kwargs)
        return apply_legend_style_clear_of_data(ax, **secondary_kwargs)

    if primary_loc_kwargs:
        primary = apply_legend_style(ax, **primary_loc_kwargs, **primary_kwargs)
        return _place_secondary_around(primary) if draw_secondary else primary

    if not draw_secondary:
        if getattr(args, "legend_free", False):
            # Placed before the axes are finalised: apply scales/ranges first.
            if getattr(args, "logy", False):
                ax.set_yscale("log")
            if getattr(args, "logx", False):
                ax.set_xscale("log")
            if getattr(args, "rangey", None):
                ax.set_ylim(*args.rangey)
            if getattr(args, "rangex", None):
                ax.set_xlim(*args.rangex)
            return apply_legend_style_free(ax, **primary_kwargs)
        return apply_legend_style_clear_of_data(ax, **primary_kwargs)

    return apply_legend_pair_clear_of_data(ax, primary_kwargs, secondary_kwargs, secondary_loc=comparable_loc)
