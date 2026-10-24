"""Text annotations for the famous-plot reproductions (a project plugin).

Adds ``--text X Y TEXT`` (repeatable) to every kind: experiment labels,
energies and luminosities, panel letters, region and resonance labels. Each
text can set its coordinates (``axes`` fractions or ``data``), the panel it
goes on (index into the figure's axes, colorbars excluded), colour, size,
rotation, weight, style and alignment through the ``--text_*`` lists, matched
by position (the last value repeats). A figure hook draws them just before
the figure is saved.

plotipus has no built-in equivalent yet: experiment labels are planned in T17
and ``--text`` in T22.8.
"""

OPTIONS = {
    "coords": "Coordinates of each --text: 'axes' (fractions, default) or 'data'.",
    "axes": "Index of the panel of each --text (default 0, the first axes).",
    "color": "Colour of each --text.",
    "size": "Font size of each --text (points or names such as 'large').",
    "rotation": "Rotation of each --text in degrees.",
    "weight": "Font weight of each --text ('normal', 'bold').",
    "style": "Font style of each --text ('normal', 'italic').",
    "ha": "Horizontal alignment of each --text ('left', 'center', 'right').",
}


def setup(registry):
    registry.add_argument("--text", nargs=3, action="append", default=None, metavar=("X", "Y", "TEXT"),
                          help="Text at (X, Y); repeat for more texts (famous-plot plugin).")
    for name, text in OPTIONS.items():
        registry.add_argument(f"--text_{name}", nargs="+", default=None, help=text)
    registry.add_figure_hook(draw_texts)


def _pick(values, index, default):
    if not values:
        return default
    return values[min(index, len(values) - 1)]


def draw_texts(fig, args):
    texts = getattr(args, "text", None)
    if not texts:
        return
    axes = [ax for ax in fig.axes if ax.get_label() != "<colorbar>"]
    for i, (x, y, text) in enumerate(texts):
        ax = axes[int(_pick(args.text_axes, i, 0))]
        size = _pick(args.text_size, i, "x-large")
        ax.text(float(x), float(y), text,
                transform=ax.transData if _pick(args.text_coords, i, "axes") == "data" else ax.transAxes,
                color=_pick(args.text_color, i, "black"),
                fontsize=float(size) if str(size).replace(".", "", 1).isdigit() else size,
                rotation=float(_pick(args.text_rotation, i, 0)),
                fontweight=_pick(args.text_weight, i, "normal"),
                fontstyle=_pick(args.text_style, i, "normal"),
                ha=_pick(args.text_ha, i, "left"), va="center", zorder=10)
