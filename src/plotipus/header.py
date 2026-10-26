"""Experiment header and status watermark (T17).

The header is a label (e.g. the experiment name, bold) followed by a status
("Preliminary"), and a right-hand text ("13.6 TeV, 140 fb$^{-1}$"):

* ``position: above`` (default): above the first panel's top-left corner,
  with the right-hand text above the last panel's top-right corner, and
  above any panel title;
* ``position: inside`` (LHCb, ALICE, DUNE): in the top-left corner, the
  right-hand text on the line below; the y range gets headroom when data
  runs under it (:func:`make_room`).

The label and status share one baseline (offsetbox packers). The boxes are
artists of the axes, so the measured layout (T13) makes room for them and
legends (T15) avoid them. The settings come from the style's
``header`` section (experiment presets, ``[header]`` in plotipus.toml) and
the ``--label``, ``--label_status``, ``--label_right``, ``--watermark`` and
``--watermark_style`` options. Sizes are fractions of the medium's
``font.size``; colours are the ``ink`` and ``muted`` roles.
"""

import math

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.offsetbox import AnchoredOffsetbox, HPacker, TextArea, VPacker
from matplotlib.transforms import offset_copy
from rich import print as rprint

from . import style

WATERMARKS = {
    "wip": "Work In Progress",
    "preliminary": "Preliminary",
    "internal": "Internal",
    "simulation": "Simulation",
    "draft": "Draft",
}

DEFAULTS = {
    "label": None,
    "status": None,
    "right": None,
    "position": "above",
    "label_weight": "bold",
    "label_style": "normal",
    "status_weight": "normal",
    "status_style": "normal",
    # Sizes relative to font.size (mplhep: 1.3, 1, 1/1.1).
    "label_size": 1.3,
    "status_size": 1.0,
    "right_size": 0.91,
    "watermark": None,
    "watermark_style": "corner",
}

# Options that override the style's header section.
_OPTIONS = {"label": "label", "label_status": "status", "label_right": "right",
            "label_position": "position", "watermark": "watermark", "watermark_style": "watermark_style"}

_PAPER_REMINDED = False


def settings(args=None):
    """The header settings: defaults, the style's ``header``, then the options."""
    merged = {**DEFAULTS, **style.header}
    for option, key in _OPTIONS.items():
        value = getattr(args, option, None)
        if value is not None:
            merged[key] = value
    return merged


def watermark_text(value):
    """Text of a watermark value: a preset name, free text, or None (none)."""
    if value is None or str(value).strip().lower() in ("", "none"):
        return None
    return WATERMARKS.get(str(value).strip().lower(), str(value))


def header_axes(fig):
    """The upper panels of ``fig`` in reading order (no colorbars, no lower panels)."""
    found = []
    for ax in fig.axes:
        spec = ax.get_subplotspec()
        if not ax.get_visible() or spec is None or hasattr(ax, "_colorbar"):
            continue
        box = ax.get_position()
        if any(other is not ax and other.get_visible() and other.get_position().y0 >= box.y1 - 1e-6
               for other in ax.get_shared_x_axes().get_siblings(ax)):
            continue  # a lower panel
        found.append((spec.rowspan.start, spec.colspan.start, ax))
    return [ax for *_, ax in sorted(found, key=lambda item: item[:2])]


def _title_rise(ax):
    """Points above the axes top that clear the panel title, if any."""
    titles = [t for t in (ax.title, ax._left_title, ax._right_title) if t.get_visible() and t.get_text()]
    if not titles:
        return 0.3 * plt.rcParams["font.size"]
    size = max(t.get_fontsize() for t in titles)
    return plt.rcParams["axes.titlepad"] + 1.3 * size


def _mark(artist, inside):
    artist._plotipus_header = "inside" if inside else "above"
    return artist


def header_artists(ax, where=None):
    """The header boxes of ``ax`` (``where``: "inside" or "above")."""
    return [a for a in ax.artists if getattr(a, "_plotipus_header", None) in ((where,) if where else ("inside", "above"))]


def draw(fig, args=None):
    """Draw the header and the watermark on ``fig`` (before the layout pass).
    Returns the header and watermark artists."""
    cfg = settings(args)
    panels = header_axes(fig)
    if not panels:
        return []
    first = panels[0]
    last = max((ax for ax in panels if ax.get_subplotspec().rowspan.start == 0),
               key=lambda ax: ax.get_subplotspec().colspan.stop, default=first)
    base = float(plt.rcParams["font.size"])
    ink = style.role("ink")
    inside = cfg["position"] == "inside"
    gap = 0.35 * base

    def area(value, size, weight="normal", fontstyle="normal", color=ink):
        return TextArea(value, textprops=dict(fontsize=base * size, fontweight=weight, fontstyle=fontstyle,
                                              color=color))

    pieces = []
    if cfg["label"]:
        pieces.append(area(cfg["label"], cfg["label_size"], cfg["label_weight"], cfg["label_style"]))
    if cfg["status"]:
        pieces.append(area(cfg["status"], cfg["status_size"], cfg["status_weight"], cfg["status_style"]))
    lead = HPacker(children=pieces, align="baseline", pad=0, sep=gap) if pieces else None
    # The right-hand text: one line or several (e.g. one per centre-of-mass energy).
    right_lines = cfg["right"] if isinstance(cfg["right"], (list, tuple)) else [cfg["right"]] if cfg["right"] else []
    right_areas = [area(line, cfg["right_size"]) for line in right_lines if line]
    corner_mark = None
    value = watermark_text(cfg["watermark"])
    if value is not None and cfg["watermark_style"] != "diagonal":
        corner_mark = area(value, cfg["status_size"], fontstyle="italic", color=style.role("muted"))

    artists = []
    if inside:
        lines = [line for line in (lead, *right_areas, corner_mark) if line is not None]
        if lines:
            artists.append(_anchor(first, VPacker(children=lines, align="left", pad=0, sep=0.3 * base),
                                   "upper left", inside=True))
    else:
        if lead is not None:
            artists.append(_anchor(first, lead, "lower left", inside=False))
        if right_areas:
            right = right_areas[0] if len(right_areas) == 1 else VPacker(children=right_areas, align="right", pad=0,
                                                                          sep=0.2 * base)
            artists.append(_anchor(last, right, "lower right", inside=False))
        if corner_mark is not None:
            artists.append(_anchor(first, corner_mark, "upper left", inside=True))
    if value is not None:
        _paper_reminder(value)
        if cfg["watermark_style"] == "diagonal":
            artists += _diagonal(fig, panels, value)
    return artists


def _anchor(ax, child, loc, inside):
    """``child`` in the ``loc`` corner of the axes (inside) or on its top edge
    (above, clear of the panel title)."""
    if inside:
        box = AnchoredOffsetbox(loc=loc, child=child, pad=0, borderpad=0.8, frameon=False)
    else:
        x = 0 if "left" in loc else 1
        above = offset_copy(ax.transAxes, fig=ax.figure, y=_title_rise(ax), units="points")
        box = AnchoredOffsetbox(loc=loc, child=child, pad=0, borderpad=0, frameon=False,
                                bbox_to_anchor=(x, 1), bbox_transform=above)
    box.set_zorder(5)
    ax.add_artist(box)
    return _mark(box, inside)


def _paper_reminder(value):
    global _PAPER_REMINDED
    from .project import current_rendering

    rendering = current_rendering()
    if rendering is not None and rendering.medium == "paper" and not _PAPER_REMINDED:
        rprint(f"[yellow]Note:[/yellow] the watermark '{value}' is on in a paper figure (--watermark none drops it).")
        _PAPER_REMINDED = True


def _diagonal(fig, panels, value):
    """Large faint text across each panel, behind the data."""
    drawn = []
    width, height = fig.get_size_inches()
    for ax in panels:
        box = ax.get_position()
        w, h = box.width * width * 72, box.height * height * 72
        # Large enough to cross most of the axes diagonal (glyphs about 0.6 em wide).
        size = min(0.75 * math.hypot(w, h) / (0.6 * max(len(value), 1)), 0.6 * h)
        text = ax.text(0.5, 0.5, value, transform=ax.transAxes, ha="center", va="center",
                       rotation=math.degrees(math.atan2(h, w)), rotation_mode="anchor", fontsize=size,
                       fontweight="bold", color=style.role("muted"), alpha=0.15, zorder=0.5)
        text._plotipus_header = "watermark"
        drawn.append(text)
    return drawn


def make_room(fig):
    """Give an inside header headroom when data runs under it: extend the
    top of the y range (log axes by whole decades), unless the range is
    fixed. Returns whether any range changed."""
    from .plot import _Occupancy, axes_occupancy

    changed = False
    renderer = fig.canvas.get_renderer()
    for ax in fig.axes:
        boxes = [a.get_window_extent(renderer) for a in header_artists(ax, "inside")]
        # A range set by an earlier make_room stays adjustable (set_ylim turns autoscaling off).
        adjustable = ax.get_autoscaley_on() or getattr(ax, "_plotipus_header_room", False)
        if not boxes or not adjustable or getattr(ax, "_plotipus_fixed_ylim", False):
            continue
        ax.get_xlim(), ax.get_ylim()  # autoscale now (the layout may not have drawn)
        mask, (x0, y0) = axes_occupancy(ax, renderer, exclude=header_artists(ax))
        bottom_px = min(b.y0 for b in boxes) - 4
        columns = slice(max(0, int(min(b.x0 for b in boxes)) - x0), max(0, int(max(b.x1 for b in boxes)) - x0))
        rows = mask[:, columns].any(axis=1).nonzero()[0]
        if not len(rows) or rows.max() + y0 < bottom_px:
            continue
        fraction = (bottom_px - ax.bbox.y0) / ax.bbox.height
        if fraction <= 0.3:
            continue  # the header would take most of the axes: leave it
        top_px = rows.max() + y0
        to_data = ax.transData.inverted()
        low, high = ax.get_ylim()
        value = to_data.transform((0, top_px))[1]
        if ax.get_yscale() == "log":
            low_l, value_l = np.log10(low), np.log10(value)
            ax.set_ylim(low, 10 ** np.ceil(low_l + (value_l - low_l) / fraction))
        else:
            ax.set_ylim(low, max(high, low + (value - low) / fraction))
        ax._plotipus_header_room = True
        changed = True
    return changed
