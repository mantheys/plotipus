"""Figure layout shared by the plot kinds: panel grids, upper/lower panel
stacks, reference overlays, titles, notes and saving."""

import math

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.transforms import Bbox
from rich import print as rprint

from . import registry, style
from .format import make_title_from_args
from .io import make_name_from_args, save_figure_to_paths
from .plot import (
    add_centered_suptitle,
    apply_note_to_figure,
    create_common_subplots,
    create_common_two_panel_figure,
    draw_bands,
    draw_horizontal_lines,
    draw_lines,
    draw_squares,
    draw_vertical_lines,
    lower_height_ratios,
    measured_layout_enabled,
    place_point_label,
    set_axis_tick_labels,
)
from .args import (
    normalize_point_labels,
    normalize_square_labels,
    normalize_line_labels,
    parse_line_segments,
    parse_point_pairs,
    parse_square_quads,
)


def grid_shape(n_panels):
    """(nrows, ncols): one row up to three panels, else a near-square grid."""
    if n_panels <= 3:
        return 1, max(1, n_panels)
    ncols = math.ceil(math.sqrt(n_panels))
    return math.ceil(n_panels / ncols), ncols


def wrap_limit():
    """Most facets side by side (the medium's ``facet_columns``), or None:
    rule L3, facets keep a single plot's size, so a row wider than the medium
    allows wraps instead of shrinking. --layout panels (one plot split in
    parts) and --single_panel_size do not wrap."""
    limit = style.figure_facet_columns
    if not limit or style.figure_layout_mode == "panels" or style.figure_single_panel:
        return None
    return int(limit)


def wrap_shape(n_panels, shape=None):
    """The grid of ``n_panels``: ``shape`` (default :func:`grid_shape`), a
    single row wrapped at :func:`wrap_limit` columns. A grid of several rows
    given by the caller is kept."""
    limit = wrap_limit()
    if shape is None:
        shape = (1, max(1, n_panels)) if limit else grid_shape(n_panels)
    if limit and shape[0] == 1 and shape[1] > limit:
        return math.ceil(n_panels / limit), limit
    return tuple(shape)


def create_panels(n_panels=1, n_lower=0, grid=True, height_ratios=None, shape=None, wrap=True):
    """Figure with ``n_panels`` upper panels and ``n_lower`` lower panels
    below each of them (sharing x).

    Returns ``(fig, upper, lower, (nrows, ncols))`` where ``upper`` is a flat
    list of axes (row by row) and ``lower[i]`` the list of lower axes under
    ``upper[i]``. ``shape`` (nrows, ncols) fixes the grid; with lower panels
    and several rows each row of the grid is an upper panel and its lower
    panels, with a narrow gap before the next row. With ``wrap``, a row
    wider than the medium's ``facet_columns`` wraps (:func:`wrap_shape`).
    """
    from .inset import target

    inset = target()
    if inset is not None:
        # An inset pass (plotipus.inset): every panel is the inset axes, without lower panels.
        return inset.figure, [inset] * max(1, n_panels), [[] for _ in range(max(1, n_panels))], (1, 1)
    if shape is None and not (grid and n_lower <= 0):
        shape = (1, max(1, n_panels))
    given = shape
    shape = wrap_shape(n_panels, shape) if wrap else shape or grid_shape(n_panels)
    fig, upper, lower, shape = _create_panels(n_panels, n_lower, height_ratios, shape)
    # A row wrapped into several rows: callers share y over all of them and title every panel.
    fig._plotipus_wrapped = shape[0] > 1 and (given is None or given[0] == 1) and wrap_limit() is not None
    return fig, upper, lower, shape


def _create_panels(n_panels, n_lower, height_ratios, shape):
    if n_lower > 0 and shape[0] > 1:
        return _grid_with_lower(n_panels, n_lower, shape, height_ratios)
    if n_lower <= 0:
        nrows, ncols = shape
        fig, ax = create_common_subplots(nrows=nrows, ncols=ncols)
        upper = list(np.asarray(ax).flatten())
        for extra in upper[n_panels:]:
            extra.set_visible(False)
        return fig, upper[:n_panels], [[] for _ in range(n_panels)], (nrows, ncols)

    ratios = height_ratios or lower_height_ratios(n_lower)
    fig, gs = create_common_two_panel_figure(ncols=n_panels, height_ratios=ratios) if n_lower == 1 else _stacked_figure(n_panels, ratios)
    upper, lower = [], []
    for col in range(n_panels):
        top = fig.add_subplot(gs[0, col] if n_panels > 1 else gs[0])
        bottoms = []
        for row in range(1, n_lower + 1):
            bottoms.append(fig.add_subplot(gs[row, col] if n_panels > 1 else gs[row], sharex=top))
        top.tick_params(labelbottom=False)
        for ax in bottoms[:-1]:
            ax.tick_params(labelbottom=False)
        upper.append(top)
        lower.append(bottoms)
    return fig, upper, lower, (1, n_panels)


# Gap between the rows of a grid with lower panels, as a share of an upper panel's height.
GRID_ROW_GAP = 0.15


def _grid_with_lower(n_panels, n_lower, shape, height_ratios=None):
    """``create_panels`` for several rows of upper panels with lower panels:
    one gridspec whose rows are, per grid row, the upper panel, its lower
    panels and (between rows) a spacer."""
    from .plot import apply_common_figure_margins, apply_panel_font_scale, get_common_figsize

    nrows, ncols = shape
    ratios = list(height_ratios or lower_height_ratios(n_lower))
    full = list(ratios)
    for _ in range(nrows - 1):
        full += [GRID_ROW_GAP * ratios[0]] + ratios
    apply_panel_font_scale(ncols)
    width, height = get_common_figsize(ncols=ncols, nrows=nrows, height_ratios=ratios)
    height *= sum(full) / (nrows * sum(ratios))
    fig = plt.figure(figsize=(width, height))
    hspace = style.figure_two_panel_hspace
    gs = fig.add_gridspec(nrows=len(full), ncols=ncols, height_ratios=full, hspace=hspace)
    apply_common_figure_margins(fig, hspace=hspace)
    upper, lower = [], []
    for index in range(n_panels):
        row, col = divmod(index, ncols)
        base = row * (len(ratios) + 1)
        top = fig.add_subplot(gs[base, col])
        bottoms = [fig.add_subplot(gs[base + k, col], sharex=top) for k in range(1, n_lower + 1)]
        top.tick_params(labelbottom=False)
        for ax in bottoms[:-1]:
            ax.tick_params(labelbottom=False)
        upper.append(top)
        lower.append(bottoms)
    return fig, upper, lower, (nrows, ncols)


def share_grid(upper, lower, shape, sharex="none", sharey="none"):
    """Share axes across a grid of panels (``upper`` row by row, ``lower[i]``
    under ``upper[i]``): ``sharex`` col (down each column) or all, ``sharey``
    row (along each row) or all; lower panels share y with the lower panels
    of the same row. Shared axes keep tick labels on the outer panels only:
    x on the bottom row of each column, y on the first column."""
    nrows, ncols = shape
    n = len(upper)

    def cell(i):
        return divmod(i, ncols)

    for i in range(n):
        row, col = cell(i)
        if sharex in ("col", "all"):
            leader = col if sharex == "col" else 0
            if i != leader:
                upper[i].sharex(upper[leader])
        if sharey in ("row", "all"):
            leader = row * ncols if sharey == "row" else 0
            if i != leader:
                upper[i].sharey(upper[leader])
                for ax, lead in zip(lower[i], lower[leader]):
                    ax.sharey(lead)
    if sharex in ("col", "all"):
        for i in range(n):
            row, col = cell(i)
            if i + ncols < n:  # a panel below: no x tick labels or x label here
                for ax in (upper[i], *lower[i]):
                    ax.tick_params(which="both", labelbottom=False)
                    ax._plotipus_inner_x = True
    if sharey in ("row", "all"):
        for i in range(n):
            if cell(i)[1] > 0:
                for ax in (upper[i], *lower[i]):
                    ax.tick_params(which="both", labelleft=False)
                    ax._plotipus_inner_y = True


def _stacked_figure(ncols, height_ratios):
    from .plot import apply_common_figure_margins, apply_panel_font_scale, get_common_figsize

    apply_panel_font_scale(ncols)
    if style.figure_width is not None:
        fig = plt.figure(figsize=get_common_figsize(ncols=ncols, height_ratios=height_ratios))
    else:
        width, height = get_common_figsize(ncols=ncols)
        fig = plt.figure(figsize=(width, height * (1 + 0.15 * (len(height_ratios) - 2))))
    hspace = style.figure_two_panel_hspace
    grid = fig.add_gridspec(nrows=len(height_ratios), ncols=ncols, height_ratios=height_ratios, hspace=hspace)
    apply_common_figure_margins(fig, hspace=hspace)
    return fig, grid


# Colorbar geometry (style_spec §2.9): as tall as the axes, 4% of one axes'
# width, 2% of it as padding.
COLORBAR_WIDTH = 0.04
COLORBAR_PAD = 0.02


class _ColorbarLocator:
    """Places a colorbar right of its panels whenever they move: as tall as
    the panels, COLORBAR_WIDTH of one panel's width, after COLORBAR_PAD."""

    def __init__(self, axes):
        self.axes = axes

    def __call__(self, cax, renderer):
        boxes = [ax.get_position() for ax in self.axes]
        width = boxes[0].width
        y0, y1 = min(b.y0 for b in boxes), max(b.y1 for b in boxes)
        return Bbox.from_bounds(max(b.x1 for b in boxes) + COLORBAR_PAD * width, y0, COLORBAR_WIDTH * width, y1 - y0)


def add_colorbar(fig, mappable, axes, label=None):
    """Colorbar right of ``axes`` (one axes, or a row sharing it), labelled
    on its right."""
    axes = list(np.atleast_1d(axes))
    if measured_layout_enabled():
        # The bar follows the panels; the measured layout makes room for it.
        locator = _ColorbarLocator(axes)
        cax = fig.add_axes(locator(None, None))
        cax.set_axes_locator(locator)
        cax._plotipus_colorbar_of = axes
        cbar = fig.colorbar(mappable, cax=cax)
        if label is not None:
            cbar.set_label(label)
        cbar.ax.yaxis.set_label_position("right")
        return cbar
    boxes = [ax.get_position() for ax in axes]
    width = boxes[0].width
    span = max(b.x1 for b in boxes) - min(b.x0 for b in boxes)
    fig_width, fig_height = fig.get_size_inches()
    aspect = boxes[0].height * fig_height / (COLORBAR_WIDTH * width * fig_width)
    cbar = fig.colorbar(mappable, ax=axes if len(axes) > 1 else axes[0], fraction=COLORBAR_WIDTH * width / span,
                        pad=COLORBAR_PAD * width / span, shrink=1.0, aspect=aspect)
    if label is not None:
        cbar.set_label(label)
    cbar.ax.yaxis.set_label_position("right")
    _fit_colorbar(fig, cbar, axes, max(b.x1 for b in boxes))
    return cbar


def _fit_colorbar(fig, cbar, axes, right):
    """Move the colorbar left, narrowing ``axes``, until its ticks and label
    end at ``right`` (the panels' original right edge) instead of in the
    margin, where they would be cut."""
    fig.canvas.draw()
    to_figure = fig.transFigure.inverted()
    overflow = cbar.ax.get_tightbbox().transformed(to_figure).x1 - right
    if overflow <= 0:
        return
    boxes = [ax.get_position() for ax in axes]
    left, edge = min(b.x0 for b in boxes), max(b.x1 for b in boxes)
    scale = (edge - left - overflow) / (edge - left)
    for ax, box in zip(axes, boxes):
        ax.set_position([left + (box.x0 - left) * scale, box.y0, box.width * scale, box.height])
    bar = cbar.ax.get_position(original=True)
    cbar.ax.set_position([bar.x0 - overflow, bar.y0, bar.width, bar.height])


def apply_axis_options(ax, args, prefix="", x=True):
    """Ranges and log scales from ``--{prefix}rangey``, ``--{prefix}logy``
    (and the shared x options when ``x``)."""
    if x and getattr(args, "rangex", None) is not None:
        ax.set_xlim(args.rangex[0], args.rangex[1])
    rangey = getattr(args, f"{prefix}rangey", None)
    if rangey is not None:
        ax.set_ylim(rangey[0], rangey[1])
    if getattr(args, f"{prefix}logy", False):
        ax.set_yscale("log")
    if x and getattr(args, "logx", False):
        ax.set_xscale("log")


def draw_horizontal_overlay(ax, args, prefix=""):
    draw_horizontal_lines(
        ax,
        getattr(args, f"{prefix}horizontal", None),
        labels=getattr(args, f"{prefix}horizontal_label", None),
        styles=getattr(args, f"{prefix}horizontal_style", None),
        colors=getattr(args, f"{prefix}horizontal_color", None),
        fontsize=style.linelabelfontsize,
        label_pos=getattr(args, f"{prefix}horizontal_label_pos", None) or getattr(args, "horizontal_label_pos", "right"),
    )


def draw_overlays(ax, args, vertical=None, labels=True):
    """Reference overlays of one panel: horizontal/vertical lines, points,
    rectangles, segments and custom ticks. ``vertical`` replaces --vertical
    (e.g. per-panel positions); ``labels`` False draws unlabelled lines."""
    for axis, name in (("x", "vertical"), ("y", "horizontal")):
        draw_bands(ax, axis, getattr(args, f"{name}_band", None), labels=getattr(args, f"{name}_band_label", None),
                   colors=getattr(args, f"{name}_band_color", None), fontsize=style.linelabelfontsize)
    draw_horizontal_overlay(ax, args)
    draw_vertical_lines(
        ax,
        vertical if vertical is not None else getattr(args, "vertical", None),
        labels=getattr(args, "vertical_label", None) if labels else None,
        styles=getattr(args, "vertical_style", None),
        colors=getattr(args, "vertical_color", None),
        fontsize=style.linelabelfontsize,
    )

    points = parse_point_pairs(getattr(args, "point", None))
    point_labels, warning = normalize_point_labels(getattr(args, "point_label", None), len(points))
    if warning:
        rprint(f"[yellow]Warning:[/yellow] {warning}")
    for i, (px, py) in enumerate(points):
        ax.scatter(px, py, color=style.role("muted"), s=40, zorder=6)
        if point_labels is not None:
            place_point_label(ax, px, py, point_labels[i], fontsize=style.linelabelfontsize)

    squares = parse_square_quads(getattr(args, "square", None))
    if squares:
        square_labels, warning = normalize_square_labels(getattr(args, "square_label", None), len(squares))
        if warning:
            rprint(f"[yellow]Warning:[/yellow] {warning}")
        draw_squares(
            ax, squares, labels=square_labels,
            styles=getattr(args, "square_style", None),
            colors=getattr(args, "square_color", None),
            fontsize=style.linelabelfontsize,
        )

    segments = parse_line_segments(getattr(args, "line", None))
    if segments:
        line_labels, warning = normalize_line_labels(getattr(args, "line_label", None), len(segments))
        if warning:
            rprint(f"[yellow]Warning:[/yellow] {warning}")
        draw_lines(
            ax, segments, labels=line_labels,
            styles=getattr(args, "line_style", None),
            colors=getattr(args, "line_color", None),
            fontsize=style.linelabelfontsize,
        )

    for axis in ("x", "y"):
        set_axis_tick_labels(
            ax,
            axis,
            getattr(args, f"{axis}tick", None),
            getattr(args, f"{axis}tick_label", None),
            height=getattr(args, f"{axis}tick_height", None) or 0.09,
            side=getattr(args, f"{axis}tick_side", None),
            edge=getattr(args, f"{axis}tick_edge", None),
        )


def grow_for_tick_labels(fig, rotated_x=False, categorical_y=False):
    """Enlarge a single-row figure so rotated x tick labels (below) or long
    categorical y labels (left) fit without shrinking the axes."""
    if not (rotated_x or categorical_y) or measured_layout_enabled():
        return
    params = fig.subplotpars
    left, right, bottom, top = params.left, params.right, params.bottom, params.top
    old_h, old_w = fig.get_figheight(), fig.get_figwidth()
    tl_bottom, tl_left = bottom, left
    try:
        fig.tight_layout()
        tl_bottom, tl_left = fig.subplotpars.bottom, fig.subplotpars.left
    except Exception:
        pass
    fig.subplots_adjust(left=left, right=right, bottom=bottom, top=top)

    if rotated_x:
        extra = max(0.0, (tl_bottom - bottom) * old_h) + 0.1
        if extra > 0.1:
            new_h = old_h + extra
            fig.set_figheight(new_h)
            new_top = 1.0 - (1.0 - top) * old_h / new_h
            fig.subplots_adjust(bottom=new_top - (top - bottom) * old_h / new_h, top=new_top)
    if categorical_y:
        extra = max(0.0, (tl_left - left) * old_w) + 0.1
        if extra > 0.1:
            new_w = old_w + extra
            fig.set_figwidth(new_w)
            new_right = 1.0 - (1.0 - right) * old_w / new_w
            fig.subplots_adjust(left=new_right - (right - left) * old_w / new_w, right=new_right)


def rotate_categorical_labels(fig):
    """Right-align rotated x tick labels (after drawing materialises them)."""
    fig.canvas.draw()
    for ax in fig.get_axes():
        plt.setp(ax.get_xticklabels(), ha="right")


def add_title_and_note(fig, args, tight_rows=1):
    """Figure title (--title or the datafile name) and --note."""
    from .inset import target

    if target() is not None:
        return
    title = make_title_from_args(args)
    if tight_rows > 1 and not measured_layout_enabled():
        try:
            fig.tight_layout(rect=[0, 0, 1, 0.95] if title else [0, 0, 1, 1.0])
        except Exception:
            pass
    if title:
        add_centered_suptitle(fig, title, fontsize=style.titlefontsize)
    apply_note_to_figure(fig, getattr(args, "note", None))


def apply_figure_hooks(fig, args):
    """Draw the experiment header and watermark (:mod:`plotipus.header`) and
    the --text/--region annotations (:mod:`plotipus.annotations`), then run
    the plugin figure hooks (logos, ...) on ``fig``."""
    from .annotations import draw_annotations
    from .header import draw as draw_header

    draw_header(fig, args)
    draw_annotations(fig, args)
    for hook in registry.figure_hooks:
        hook(fig, args)


def save(fig, args, idx=None, suffix="plot.png", prefix=None):
    """Save under the name built from the arguments (see
    :func:`plotipus.io.make_name_from_args`) into every --output directory."""
    from .inset import target

    if target() is not None:
        return None  # an inset pass draws into the main figure
    suffix = getattr(args, "output_suffix", None) or suffix
    if "." not in suffix:
        suffix = f"{suffix}.{getattr(args, 'format', None) or 'png'}"
    prefix = getattr(args, "filename_prefix", None) or prefix
    output_file = make_name_from_args(args, idx, prefix=prefix, suffix=suffix)
    apply_figure_hooks(fig, args)
    save_figure_to_paths(fig, getattr(args, "output", None), output_file, subfolder=getattr(args, "subfolder", None),
                         sci_in_label=getattr(args, "sci_in_label", None), log_labels=getattr(args, "log_labels", None))
    if not getattr(args, "show", False):
        plt.close(fig)
    return output_file
