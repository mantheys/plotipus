"""Text annotations for the famous-plot reproductions (a project plugin).

Adds ``--text X Y TEXT`` (repeatable) to every kind: experiment labels,
energies and luminosities, panel letters, region and resonance labels. Each
text can set its coordinates (``axes`` fractions or ``data``), the panel it
goes on (index into the figure's axes, colorbars excluded), colour, size,
rotation, weight, style and alignment through the ``--text_*`` lists, matched
by position (the last value repeats). A figure hook draws them just before
the figure is saved. The project setting ``text_scale`` (``[settings]`` in
plotipus.toml) scales every text, so a smaller medium (the paper gallery)
keeps the same commands.

``--single_panel_size`` resizes a multi-panel figure to the style's
single-panel size before it is saved, keeping the margins, so that a grid of
panels matches the other figures of a gallery.

plotipus has no built-in equivalent yet: experiment labels are planned in T17,
``--text`` in T22.8 and figure sizes per medium in T14.
"""

from matplotlib.font_manager import FontProperties

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
    registry.add_argument("--single_panel_size", action="store_true", default=False,
                          help="Resize the figure to the style's single-panel size (famous-plot plugin).")
    registry.add_figure_hook(resize)
    registry.add_figure_hook(draw_texts)


def _pick(values, index, default):
    if not values:
        return default
    return values[min(index, len(values) - 1)]


def _text_scale():
    from plotipus import project

    current = project._PROJECT
    return float(current.settings.get("text_scale", 1.0)) if current is not None else 1.0


def resize(fig, args):
    if getattr(args, "single_panel_size", False):
        from plotipus.plot import apply_common_figure_margins, get_common_figsize

        fig.set_size_inches(*get_common_figsize(ncols=1))
        apply_common_figure_margins(fig)


def draw_texts(fig, args):
    texts = getattr(args, "text", None)
    if not texts:
        return
    axes = [ax for ax in fig.axes if ax.get_label() != "<colorbar>"]
    scale = _text_scale()
    for i, (x, y, text) in enumerate(texts):
        ax = axes[int(_pick(args.text_axes, i, 0))]
        size = _pick(args.text_size, i, "x-large")
        named = not str(size).replace(".", "", 1).isdigit()
        points = FontProperties(size=size).get_size_in_points() if named else float(size)
        ax.text(float(x), float(y), text,
                transform=ax.transData if _pick(args.text_coords, i, "axes") == "data" else ax.transAxes,
                color=_pick(args.text_color, i, "black"),
                fontsize=points * scale,
                rotation=float(_pick(args.text_rotation, i, 0)),
                fontweight=_pick(args.text_weight, i, "normal"),
                fontstyle=_pick(args.text_style, i, "normal"),
                ha=_pick(args.text_ha, i, "left"), va="center", zorder=10)
