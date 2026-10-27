"""Free annotations of every kind: texts with optional arrows and shaded regions.

``--text X Y TEXT`` (repeatable) writes a text at (X, Y), in axes fractions
or data coordinates (``--text_coords``), on the panel ``--text_axes``, with
colour, size, rotation, weight, style and alignment from the ``--text_*``
lists, matched by position (the last value repeats). ``--arrow X2 Y2``
(repeatable, matched to the texts in order; ``nan nan`` for none) draws an
arrow from the text to (X2, Y2). Named sizes follow the medium's
``font.size``, shrunk by its ``style.text_scale`` (0.75 in paper).

``--region X,Y X,Y ...`` (repeatable) shades a polygon in data coordinates
under the data, in ``--region_color`` (default the muted role) with
``--region_alpha``, an optional ``--region_hatch`` and a ``--region_label``
written inside its visible part. Regions never widen the axis ranges.

Both are drawn just before the figure is saved, after the limits are set.
"""

import numpy as np
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Polygon
from matplotlib.path import Path
from matplotlib.transforms import Bbox
from rich import print as rprint

from . import style

TEXT_OPTIONS = {
    "coords": "Coordinates of each --text: 'axes' (fractions, default) or 'data'.",
    "axes": "Index of the panel of each --text (default 0, the first axes; colorbars are not counted).",
    "color": "Colour of each --text (default: the style's ink).",
    "size": "Font size of each --text (points or names such as 'large'; default x-large).",
    "rotation": "Rotation of each --text in degrees.",
    "weight": "Font weight of each --text ('normal', 'bold').",
    "style": "Font style of each --text ('normal', 'italic').",
    "ha": "Horizontal alignment of each --text ('left', 'center', 'right'; default left).",
}


def add_annotation_args(parser):
    group = parser.add_argument_group("annotations")
    add = group.add_argument
    add("--text", nargs=3, action="append", default=None, metavar=("X", "Y", "TEXT"),
        help="Text at (X, Y): axes fractions, or data coordinates with --text_coords data; repeat for more.")
    for name, text in TEXT_OPTIONS.items():
        add(f"--text_{name}", nargs="+", default=None, help=text)
    add("--arrow", nargs=2, action="append", type=float, default=None, metavar=("X2", "Y2"),
        help="Arrow from the matching --text (the first --arrow goes with the first --text) to (X2, Y2), in "
        "the text's coordinates; 'nan nan' skips a text.")
    add("--region", nargs="+", action="append", default=None, metavar="X,Y",
        help="Shaded polygon through the points X,Y (data coordinates; one quoted 'x,y x,y ...' also works), "
        "under the data and without widening the axes; repeat for more.")
    add("--region_color", nargs="+", default=None, help="Colour of each --region (default: the style's muted role).")
    add("--region_alpha", nargs="+", type=float, default=None, help="Opacity of each --region fill (default 0.3).")
    add("--region_hatch", nargs="+", default=None,
        help="Hatch of each --region ('//', 'xx', ...; 'none' for a plain fill).")
    add("--region_label", nargs="+", default=None, help="Label written inside each --region ('' for none).")
    add("--region_axes", nargs="+", type=int, default=None, help="Panel index of each --region (default 0).")


def _pick(values, index, default):
    if not values:
        return default
    return values[min(index, len(values) - 1)]


def _panels(fig):
    return [ax for ax in fig.axes if ax.get_label() != "<colorbar>" and not hasattr(ax, "_colorbar")]


def _fontsize(size):
    named = not str(size).replace(".", "", 1).isdigit()
    points = FontProperties(size=size).get_size_in_points() if named else float(size)
    return points * style.text_scale


def draw_annotations(fig, args):
    """The --region polygons and --text annotations of ``fig``."""
    panels = _panels(fig)
    if not panels:
        return
    for i, points in enumerate(getattr(args, "region", None) or []):
        _draw_region(panels, i, points, args)
    arrows = getattr(args, "arrow", None) or []
    for i, (x, y, text) in enumerate(getattr(args, "text", None) or []):
        ax = panels[min(int(_pick(args.text_axes, i, 0)), len(panels) - 1)]
        transform = ax.transData if _pick(args.text_coords, i, "axes") == "data" else ax.transAxes
        kwargs = dict(color=style.resolve_mapped_color(_pick(args.text_color, i, style.role("ink"))),
                      fontsize=_fontsize(_pick(args.text_size, i, "x-large")),
                      rotation=float(_pick(args.text_rotation, i, 0)),
                      fontweight=_pick(args.text_weight, i, "normal"), fontstyle=_pick(args.text_style, i, "normal"),
                      ha=_pick(args.text_ha, i, "left"), va="center", zorder=10)
        arrow = arrows[i] if i < len(arrows) else None
        if arrow is not None and np.all(np.isfinite(arrow)):
            ax.annotate(text, xy=tuple(arrow), xycoords=transform, xytext=(float(x), float(y)), textcoords=transform,
                        arrowprops=dict(arrowstyle="->", color=kwargs["color"], linewidth=style.default_linewidth * 0.75,
                                        shrinkA=2, shrinkB=2),
                        annotation_clip=False, **kwargs)
        else:
            ax.text(float(x), float(y), text, transform=transform, **kwargs)


def parse_region(points):
    """(N, 2) vertices of a --region from tokens 'x,y' (or one 'x,y x,y ...')."""
    vertices = []
    for token in " ".join(points).split():
        x, sep, y = token.partition(",")
        if not sep:
            raise ValueError(f"--region point '{token}' is not X,Y")
        vertices.append((float(x), float(y)))
    if len(vertices) < 3:
        raise ValueError("--region needs at least three X,Y points")
    return np.array(vertices)


def _draw_region(panels, i, points, args):
    try:
        vertices = parse_region(points)
    except ValueError as error:
        rprint(f"[yellow]Warning:[/yellow] {error}; region skipped.")
        return
    ax = panels[min(int(_pick(args.region_axes, i, 0)), len(panels) - 1)]
    color = style.resolve_mapped_color(_pick(args.region_color, i, style.role("muted")))
    hatch = _pick(args.region_hatch, i, None)
    hatch = None if hatch in (None, "", "none") else hatch
    xlim, ylim = ax.get_xlim(), ax.get_ylim()
    alpha = float(_pick(args.region_alpha, i, 0.3))
    ax.add_patch(Polygon(vertices, closed=True, facecolor=color, alpha=alpha, edgecolor="none", linewidth=0,
                         zorder=0.6))
    if hatch:
        # The hatch in full colour over the translucent fill.
        ax.add_patch(Polygon(vertices, closed=True, facecolor="none", edgecolor=color, hatch=hatch, linewidth=0,
                             zorder=0.61))
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    label = args.region_label[i] if args.region_label and i < len(args.region_label) else None
    if label:
        centre = _visible_centre(ax, vertices)
        if centre is not None:
            ax.text(*centre, label, transform=ax.transData, ha="center", va="center", fontsize=style.linelabelfontsize,
                    color=style.role("ink"), zorder=10)


def _visible_centre(ax, vertices):
    """Centre (data coordinates) of the part of the polygon inside the view."""
    display = ax.transData.transform(vertices)
    clipped = Path(np.vstack([display, display[:1]]), closed=True).clip_to_bbox(Bbox(ax.bbox.get_points()))
    corners = clipped.vertices[np.isfinite(clipped.vertices).all(axis=1)]
    if not len(corners):
        return None
    lo, hi = corners.min(axis=0), corners.max(axis=0)
    return ax.transData.inverted().transform((lo + hi) / 2)
