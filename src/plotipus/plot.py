import re
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.transforms import Bbox
from matplotlib import cbook
from matplotlib.legend import Legend
from typing import Any

from . import style as _style

def panel_font_scale(ncols=1):
    """Text scale of a figure with ``ncols`` panel columns (plot_settings.figure_layout.panel_font_scale)."""
    return _style.figure_panel_font_scale.get(max(1, int(ncols)), 1.0)


def apply_panel_font_scale(ncols=1):
    """Set the base font size for the next figure; every relative font size
    (x-large, xx-large, ...) and the tick labels follow it."""
    plt.rcParams["font.size"] = _style.base_font_size * panel_font_scale(ncols)


PLOT_STYLE_OPTIONS = {
    "-": "-",
    "--": "--",
    ":": ":",
    "-.": "-.",
    "solid": "-",
    "dashed": "--",
    "dotted": ":",
    "dashdot": "-.",
    "none": "None",
    "": "None",
}


def get_common_figsize(ncols=1, nrows=1):
    panel_count = max(1, int(ncols))
    width = _style.figure_base_width + _style.figure_panel_width * (panel_count - 1)
    height = _style.figure_height * max(1, int(nrows))
    return (float(width), float(height))


def apply_common_figure_margins(fig, hspace=None):
    """Apply common margins to a figure, converting from absolute inches to normalized coordinates.
    
    Args:
        fig: matplotlib Figure object
        hspace: Optional override for hspace (height space between subplots)
    """
    if not isinstance(_style.figure_margins_inches, dict):
        return
    
    figwidth = fig.get_figwidth()
    figheight = fig.get_figheight()
    # Enlarged text (apply_panel_font_scale) needs proportionally wider margins.
    text_scale = float(plt.rcParams["font.size"]) / _style.base_font_size
    
    # Convert absolute-inch margins to normalized coordinates (0-1 scale)
    margins_normalized = {}
    for key, value in _style.figure_margins_inches.items():
        if key in ("left", "right", "bottom", "top"):
            value = value * text_scale
        if key == "left":
            margins_normalized[key] = value / figwidth
        elif key == "right":
            # right is measured from right edge, so: 1 - (right_inch / width)
            margins_normalized[key] = 1 - (value / figwidth)
        elif key == "bottom":
            margins_normalized[key] = value / figheight
        elif key == "top":
            # top is measured from top edge, so: 1 - (top_inch / height)
            margins_normalized[key] = 1 - (value / figheight)
        else:
            # wspace, hspace, etc. are already in proper units
            margins_normalized[key] = value
    
    if hspace is not None:
        margins_normalized["hspace"] = hspace
    
    if margins_normalized:
        fig.subplots_adjust(**margins_normalized)


def create_common_subplots(nrows=1, ncols=1, **kwargs) -> tuple[Any, Any]:
    apply_panel_font_scale(ncols)
    fig, ax = plt.subplots(
        nrows=nrows,
        ncols=ncols,
        figsize=get_common_figsize(ncols=ncols, nrows=nrows),
        constrained_layout=False,
        **kwargs,
    )
    apply_common_figure_margins(fig)
    return fig, ax


def create_common_two_panel_figure(ncols=1, height_ratios=(3, 1), hspace=None) -> tuple[Any, Any]:
    apply_panel_font_scale(ncols)
    fig = plt.figure(figsize=get_common_figsize(ncols=ncols))
    resolved_hspace = _style.figure_two_panel_hspace if hspace is None else hspace
    grid = fig.add_gridspec(
        nrows=2,
        ncols=ncols,
        height_ratios=height_ratios,
        hspace=resolved_hspace,
    )
    apply_common_figure_margins(fig, hspace=resolved_hspace)
    return fig, grid


# --- Measured layout ---------------------------------------------------------
#
# The figure size is the print size. Before saving, the margins (and the
# space between panels) are set from what was drawn: the tight box of every
# panel (tick labels, axis labels, offset texts, titles, legends, colorbars)
# plus figure_layout.pad_inches, never less than figure_layout.margins_inches.
# "fixed_margins": true keeps the old fixed-inch margins instead.


def measured_layout_enabled():
    return not _style.figure_fixed_margins


def reserve_top(fig, artist):
    """Stack ``artist`` (a figure-level text, e.g. an experiment header)
    between the figure title and the panels; the layout makes room for it."""
    fig.__dict__.setdefault("_plotipus_top_artists", []).append(artist)


def _minimum_margins(fig):
    """figure_layout.margins_inches (scaled with the text) in inches."""
    margins = _style.figure_margins_inches if isinstance(_style.figure_margins_inches, dict) else {}
    text_scale = float(plt.rcParams["font.size"]) / _style.base_font_size
    return {side: float(margins.get(side, 0.0)) * text_scale for side in ("left", "right", "bottom", "top")}


def _layout_panels(fig):
    """(gridspec, [(ax, rows, cols)]) of the visible gridspec panels, or None
    when they do not share one gridspec."""
    panels = []
    for ax in fig.axes:
        spec = ax.get_subplotspec()
        if not ax.get_visible() or spec is None or hasattr(ax, "_colorbar"):
            continue
        panels.append((ax, spec.rowspan, spec.colspan, spec.get_gridspec()))
    gridspecs = {id(gs) for *_, gs in panels}
    if not panels or len(gridspecs) != 1:
        return None
    return panels[0][3], [(ax, rows, cols) for ax, rows, cols, _ in panels]


def _panel_overhangs(fig, panels, renderer):
    """Inches each panel's drawn box (with the colorbars it carries) reaches
    beyond its gridspec slot: {ax: (left, right, bottom, top)}."""
    dpi = fig.dpi
    width, height = fig.get_size_inches()
    extra = {}
    for cax in fig.axes:
        parents = getattr(cax, "_plotipus_colorbar_of", None)
        if parents and cax.get_visible():
            owner = max(parents, key=lambda a: a.get_position(original=True).x1)
            extra.setdefault(owner, []).append(cax.get_tightbbox(renderer, for_layout_only=True))
    overhangs = {}
    for ax, _, _ in panels:
        boxes = [ax.get_tightbbox(renderer, for_layout_only=True), *extra.get(ax, [])]
        box = Bbox.union([b for b in boxes if b is not None and b.width > 0])
        slot = ax.get_position(original=True)
        overhangs[ax] = (
            max(0.0, slot.x0 * width - box.x0 / dpi),
            max(0.0, box.x1 / dpi - slot.x1 * width),
            max(0.0, slot.y0 * height - box.y0 / dpi),
            max(0.0, box.y1 / dpi - slot.y1 * height),
        )
    return overhangs


def _top_artists(fig):
    artists = [getattr(fig, "_suptitle", None), *getattr(fig, "_plotipus_top_artists", [])]
    return [a for a in artists if a is not None and a.get_visible() and a.get_text()]


def _spacing(gaps, available, count, minimum):
    """gridspec wspace/hspace (a fraction of the panel size) leaving ``gaps``
    inches between ``count`` panels in ``available`` inches."""
    if count < 2:
        return minimum
    gap = max(gaps, default=0.0)
    panel = (available - (count - 1) * gap) / count
    return max(minimum, gap / panel) if panel > 0 else minimum


def apply_measured_layout(fig, iterations=2):
    """Set the margins and panel spacing of ``fig`` from its drawn extents
    (see the section comment); the figure size never changes."""
    if not measured_layout_enabled() or _layout_panels(fig) is None:
        return
    # Text widths depend on the resolution (hinting), so measure at the
    # resolution the file is saved at.
    save_dpi = plt.rcParams["savefig.dpi"]
    figure_dpi = fig.dpi
    if save_dpi != "figure":
        fig.set_dpi(float(save_dpi))
    try:
        _measured_layout(fig, iterations)
    finally:
        fig.set_dpi(figure_dpi)


def _measured_layout(fig, iterations):
    found = _layout_panels(fig)
    gridspec, panels = found
    nrows, ncols = gridspec.get_geometry()
    pad = _style.figure_pad_inches
    minimum = _minimum_margins(fig)
    width, height = fig.get_size_inches()
    params = fig.subplotpars
    min_wspace = gridspec.wspace if gridspec.wspace is not None else params.wspace
    min_hspace = gridspec.hspace if gridspec.hspace is not None else params.hspace
    # Upper/lower stacks keep their configured gap; grids of panels are measured.
    fixed_hspace = gridspec.hspace is not None
    fig.align_ylabels([ax for ax, _, _ in panels])

    for _ in range(iterations):
        fig.draw_without_rendering()
        renderer = fig.canvas.get_renderer()
        over = _panel_overhangs(fig, panels, renderer)
        header = sum(a.get_window_extent(renderer).height / fig.dpi + pad for a in _top_artists(fig))

        def side(index, test):
            return max((over[ax][index] for ax, rows, cols in panels if test(rows, cols)), default=0.0)

        left = max(minimum["left"], side(0, lambda r, c: c.start == 0) + pad)
        right = max(minimum["right"], side(1, lambda r, c: c.stop == ncols) + pad)
        bottom = max(minimum["bottom"], side(2, lambda r, c: r.stop == nrows) + pad)
        top = max(minimum["top"], side(3, lambda r, c: r.start == 0) + pad + header)
        wgaps = [side(1, lambda r, c, k=k: c.stop == k + 1) + side(0, lambda r, c, k=k: c.start == k + 1) + pad
                 for k in range(ncols - 1)]
        hgaps = [side(2, lambda r, c, k=k: r.stop == k + 1) + side(3, lambda r, c, k=k: r.start == k + 1) + pad
                 for k in range(nrows - 1)]
        # Never squeeze the panels below a quarter of the figure.
        left, right = (min(left, 0.375 * width), min(right, 0.375 * width))
        bottom, top = (min(bottom, 0.375 * height), min(top, 0.375 * height))
        update = dict(left=left / width, right=1 - right / width, bottom=bottom / height, top=1 - top / height,
                      wspace=_spacing(wgaps, width - left - right, ncols, min_wspace))
        if not fixed_hspace:
            update["hspace"] = _spacing(hgaps, height - bottom - top, nrows, min_hspace)
        gridspec.update(**update)
        params.update(**update)
    _place_top_artists(fig, panels)


def _place_top_artists(fig, panels):
    """Stack the title (and reserved header artists) just above the panels,
    the title centred over them."""
    artists = _top_artists(fig)
    if not artists:
        return
    fig.draw_without_rendering()
    renderer = fig.canvas.get_renderer()
    to_figure = fig.transFigure.inverted()
    tops = [ax.get_tightbbox(renderer, for_layout_only=True) for ax, _, _ in panels]
    y = max(to_figure.transform((0, b.y1))[1] for b in tops if b is not None)
    pad = _style.figure_pad_inches / fig.get_figheight()
    slots = [ax.get_position(original=True) for ax, _, _ in panels]
    centre = (min(b.x0 for b in slots) + max(b.x1 for b in slots)) / 2
    for artist in reversed(artists):
        y += pad
        artist.set_verticalalignment("bottom")
        artist.set_y(y)
        if getattr(artist, "_plotipus_centered", False):
            artist.set_x(centre)
        y += to_figure.transform((0, artist.get_window_extent(renderer).height))[1] - to_figure.transform((0, 0))[1]


def _resolve_plot_style(plot_style):
    if plot_style is None:
        return None

    key = str(plot_style).strip()
    key_normalized = key.lower()

    if key_normalized in PLOT_STYLE_OPTIONS:
        return PLOT_STYLE_OPTIONS[key_normalized]

    if key in PLOT_STYLE_OPTIONS:
        return PLOT_STYLE_OPTIONS[key]

    available = ", ".join(PLOT_STYLE_OPTIONS.keys())
    raise ValueError(
        f"Unknown plot_style '{plot_style}'. Available options: {available}"
    )


def _apply_plot_style(kwargs, plot_style):
    if plot_style is None:
        return
    if "ls" in kwargs or "linestyle" in kwargs:
        return
    kwargs["ls"] = plot_style

from matplotlib.colors import LogNorm, to_rgba
from matplotlib.ticker import ScalarFormatter


def apply_tick_formatter(ax, axis="both"):
    """Plain tick numbers with a common power of ten (``ScalarFormatter`` with
    mathtext, limits from the style's ``axes.formatter.limits``) on the linear
    axes of ``ax``; log axes keep matplotlib's 10^n labels. With
    ``sci_in_label`` the power of ten moves into the axis label when the
    figure is saved (:func:`finish_tick_labels`)."""
    for name in ("x", "y"):
        if axis not in (name, "both"):
            continue
        target = getattr(ax, f"{name}axis", None)
        if target is not None and target.get_scale() == "linear":
            target.set_major_formatter(ScalarFormatter(useMathText=True))


def apply_scientific_threshold_formatter(ax, threshold=0.1, axis="both"):
    """Deprecated: use :func:`apply_tick_formatter` (``threshold`` is ignored)."""
    import warnings

    warnings.warn("apply_scientific_threshold_formatter is deprecated; use apply_tick_formatter.",
                  DeprecationWarning, stacklevel=2)
    apply_tick_formatter(ax, axis=axis)


def _offset_label(formatter):
    """The offset/multiplier text of a drawn ``ScalarFormatter`` (mathtext
    "$\\times10^{-2}$" with ``useMathText``), or None when it shows none."""
    return formatter.get_offset().replace(r"\mathdefault{}", "") or None


def _label_with_offset(label, offset):
    """``label`` with ``offset`` inside its trailing unit, "Rate (Hz)" ->
    "Rate ($\\times10^{-5}$ Hz)", else appended, "Density ($\\times10^{-2}$)"."""
    unit = re.match(r"^(.*?)\s*([(\[])([^()\[\]]*)([)\]])\s*$", label)
    if unit and unit.group(3).strip():
        head, opening, inner, closing = unit.groups()
        return f"{head} {opening}{offset} {inner.strip()}{closing}"
    return f"{label} ({offset})"


def finish_tick_labels(fig, sci_in_label=None):
    """Write every common power of ten as "$\\times10^{n}$" (mathtext) and,
    with ``sci_in_label`` (default: the style's ``plot_settings.sci_in_label``),
    move the offset text of each labelled axis into its label ("Density
    ($\\times10^{-2}$)", "Rate ($\\times10^{-5}$ Hz)") before saving."""
    if sci_in_label is None:
        sci_in_label = _style.sci_in_label
    formatters = [(axis, axis.get_major_formatter()) for ax in fig.axes for axis in (ax.xaxis, ax.yaxis)]
    formatters = [(axis, f) for axis, f in formatters if isinstance(f, ScalarFormatter)]
    for _, formatter in formatters:
        formatter.set_useMathText(True)
    if not sci_in_label:
        return
    fig.draw_without_rendering()
    for axis, formatter in formatters:
        offset = _offset_label(formatter)
        label = axis.label.get_text()
        if offset is None or not label.strip() or not axis.offsetText.get_visible():
            continue
        axis.label.set_text(_label_with_offset(label, offset))
        axis.offsetText.set_visible(False)


def _capitalize_legend_label(label):
    if not isinstance(label, str):
        return label

    words = label.split(" ")
    formatted_words = []
    for word in words:
        if not word:
            formatted_words.append(word)
            continue

        exception = _style.capitalize_exceptions.get(word.lower())
        if exception is not None:
            formatted_words.append(exception)
            continue

        first_char = word[0]
        if first_char.isalpha():
            formatted_words.append(first_char.upper() + word[1:])
        else:
            formatted_words.append(word)

    return " ".join(formatted_words)


def _normalize_boolean_legend_label(label, title):
    title_text = str(title).strip() if title is not None else ""
    if not title_text:
        return label

    if isinstance(label, bool):
        return title_text if label else f"Not {title_text}"

    if isinstance(label, str):
        label_text = label.strip().lower()
        if label_text == "true":
            return title_text
        if label_text == "false":
            return f"Not {title_text}"

    return label


def _is_boolean_legend_label(label):
    if isinstance(label, bool):
        return True

    if isinstance(label, str):
        return label.strip().lower() in {"true", "false"}

    return False


def _humanize_legend_title(title):
    """Split a bare CamelCase column name used as legend title
    (e.g. ``SpectrumType`` -> ``Spectrum Type``); anything with spaces,
    math or punctuation is returned unchanged."""
    if not isinstance(title, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", title):
        return title
    words = re.findall(r"[A-Z][a-z0-9]*|[a-z0-9]+", title)
    # Keep short-word jargon (e.g. OpHits) glued together.
    if len(words) < 2 or any(len(word) < 3 for word in words):
        return title
    return " ".join(words)




def is_redundant_legend_title(title):
    return isinstance(title, str) and title.strip().lower() in _style.redundant_legend_titles


_LEGEND_FRAME = {}


def enable_legend_frame(alpha=0.8):
    """Draw every following legend on a translucent paper-coloured box (--legend_frame)."""
    _LEGEND_FRAME.update(frameon=True, facecolor="role:paper", edgecolor="none", framealpha=alpha)


def apply_legend_style(
    ax,
    title=None,
    handles=None,
    labels=None,
    capitalize_labels=False,
    **overrides,
):
    style = dict(_style.legend_style) if isinstance(_style.legend_style, dict) else {}

    if "fontsize" not in style:
        style["fontsize"] = _style.legendfontsize
    if "title_fontsize" not in style:
        style["title_fontsize"] = _style.legendtitlefontsize

    if title is not None and not is_redundant_legend_title(title):
        style["title"] = _humanize_legend_title(title)
    style.update(_LEGEND_FRAME)

    style.update(overrides)
    style = _style.role_colors(style)
    if is_redundant_legend_title(style.get("title")):
        style.pop("title")

    if handles is None and labels is None:
        handles, labels = ax.get_legend_handles_labels()

    if labels is not None and any(_is_boolean_legend_label(label) for label in labels):
        style.pop("title", None)

    if labels is not None:
        labels = [_normalize_boolean_legend_label(label, title) for label in labels]

    if labels is not None and capitalize_labels:
        labels = [_capitalize_legend_label(label) for label in labels]

    if handles is not None and labels is not None and not len(handles) and not len(labels):
        # Nothing labelled: an empty legend (matplotlib 3.11 rejects empty handles together with empty labels).
        return ax.legend(handles=[], **style)

    if handles is not None or labels is not None:
        return ax.legend(handles=handles, labels=labels, **style)

    return ax.legend(**style)


LEGEND_PLACEMENT_CANDIDATES = (
    "upper left",
    "upper right",
    "center left",
    "center right",
    "lower left",
    "lower right",
)


def sample_axes_data_points(ax):
    """Sample the data drawn on *ax* as display-coordinate points.

    Line vertices and collection offsets are transformed to display
    coordinates; points outside the axes (NaN gaps, clipped tails) are
    dropped. Used only to measure where a legend would cover data.
    """
    points = []
    for line in ax.lines:
        try:
            x_data = np.asarray(line.get_xdata(), dtype=float)
            y_data = np.asarray(line.get_ydata(), dtype=float)
        except (TypeError, ValueError):
            continue  # categorical axis; nothing numeric to sample
        if x_data.size == 0 or x_data.shape != y_data.shape:
            continue
        points.append(ax.transData.transform(np.column_stack((x_data, y_data))))
    for collection in ax.collections:
        try:
            offsets = np.asarray(collection.get_offsets(), dtype=float)
        except (AttributeError, TypeError, ValueError):
            offsets = np.empty((0, 2))
        if offsets.size:
            points.append(ax.transData.transform(offsets))

    if not points:
        return np.zeros((0, 2))

    all_points = np.vstack(points)
    return all_points[np.isfinite(all_points).all(axis=1)]


def sample_axes_drawn_points(ax, spacing_px=3.0):
    """Sample everything drawn on *ax* densely along its drawn path.

    Unlike sample_axes_data_points, this follows each segment of lines
    (including their step drawstyle) and of patches (e.g. step histograms
    from ax.hist), with one point every *spacing_px* display pixels, so a
    legend box placed between two vertices still registers the data it
    covers. Used by the free legend placement.
    """
    paths = []
    for line in ax.lines:
        try:
            xy = np.asarray(line.get_xydata(), dtype=float)
        except (TypeError, ValueError):
            continue
        if xy.ndim != 2 or len(xy) == 0:
            continue
        drawstyle = line.get_drawstyle()
        if drawstyle in cbook.STEP_LOOKUP_MAP and drawstyle != "default" and len(xy) > 1:
            xs, ys = cbook.STEP_LOOKUP_MAP[drawstyle](xy[:, 0], xy[:, 1])
            xy = np.column_stack((xs, ys))
        if ax.get_yscale() == "log":
            # Steps that drop to y = 0 cannot be placed on a log axis: pin them
            # below the axes so their vertical edges are still sampled.
            xy = xy.copy()
            xy[:, 1] = np.where(xy[:, 1] > 0, xy[:, 1], ax.get_ylim()[0] * 1e-3)
        paths.append(ax.transData.transform(xy))
    for patch in ax.patches:
        path = patch.get_path()
        if path is None or len(path.vertices) == 0:
            continue
        vertices = np.asarray(patch.get_patch_transform().transform(path.vertices), dtype=float)
        if ax.get_yscale() == "log" and patch.get_transform().contains_branch(ax.transData):
            # Step outlines drop to y = 0, which a log axis cannot place: pin those
            # vertices below the axes so the vertical edges are still sampled.
            vertices[:, 1] = np.where(vertices[:, 1] > 0, vertices[:, 1], ax.get_ylim()[0] * 1e-3)
            paths.append(ax.transData.transform(vertices))
        else:
            paths.append(patch.get_transform().transform(path.vertices))
    for collection in ax.collections:
        # Line collections (e.g. error bars) are sampled along their segments.
        for segment in getattr(collection, "get_segments", lambda: [])():
            segment = np.asarray(segment, dtype=float)
            if segment.ndim == 2 and len(segment):
                paths.append(collection.get_transform().transform(segment))
        try:
            offsets = np.asarray(collection.get_offsets(), dtype=float)
        except (AttributeError, TypeError, ValueError):
            offsets = np.empty((0, 2))
        if offsets.size:
            paths.append(ax.transData.transform(offsets))

    points = []
    for display in paths:
        display = display[np.isfinite(display).all(axis=1)]
        if len(display) == 0:
            continue
        points.append(display)
        if len(display) < 2:
            continue
        starts, ends = display[:-1], display[1:]
        lengths = np.hypot(*(ends - starts).T)
        for start, end, length in zip(starts, ends, lengths):
            n_steps = int(length // spacing_px)
            if n_steps > 1:
                frac = np.linspace(0, 1, n_steps + 1)[1:-1, None]
                points.append(start + frac * (end - start))
    if not points:
        return np.zeros((0, 2))
    all_points = np.vstack(points)
    axes_box = ax.get_window_extent()
    inside = (
        (all_points[:, 0] >= axes_box.x0) & (all_points[:, 0] <= axes_box.x1)
        & (all_points[:, 1] >= axes_box.y0) & (all_points[:, 1] <= axes_box.y1)
    )
    return all_points[inside]


def apply_legend_style_free(ax, grid=13, pad_px=6.0, inset_px=10.0, **legend_kwargs):
    """Draw a legend at the free position (not only a corner) clearest of data.

    Probes the legend on a grid of anchor positions spanning the axes and
    keeps the one covering the fewest densely sampled drawn points; ties go
    to the position farthest from the nearest drawn point. Opt-in per plot
    (--legend_free): the default placement stays apply_legend_style_clear_of_data.
    """
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    data_points = sample_axes_drawn_points(ax)
    axes_box = ax.get_window_extent(renderer)
    probe_box = probe_legend_box(ax, renderer, "upper left", **legend_kwargs)
    width = probe_box.width / axes_box.width
    height = probe_box.height / axes_box.height
    # Keep the legend off the axes frame, like the default corner padding.
    inset_x = inset_px / axes_box.width
    inset_y = inset_px / axes_box.height
    if width + 2 * inset_x >= 1 or height + 2 * inset_y >= 1:
        return apply_legend_style_clear_of_data(ax, **legend_kwargs)

    best = None
    for fx in np.linspace(inset_x, 1 - width - inset_x, grid):
        for fy in np.linspace(height + inset_y, 1 - inset_y, grid):
            x0 = axes_box.x0 + fx * axes_box.width
            y1 = axes_box.y0 + fy * axes_box.height
            box = Bbox.from_extents(x0, y1 - probe_box.height, x0 + probe_box.width, y1)
            score = _legend_obstruction_score(box, data_points, pad_px=pad_px)
            if len(data_points):
                cx = np.clip(data_points[:, 0], box.x0, box.x1)
                cy = np.clip(data_points[:, 1], box.y0, box.y1)
                clearance = float(np.min(np.hypot(data_points[:, 0] - cx, data_points[:, 1] - cy)))
            else:
                clearance = 0.0
            key = (score, -clearance)
            if best is None or key < best[0]:
                best = (key, (fx, fy))

    # Legend frame padding (borderaxespad) is not applied with an explicit
    # anchor in axes fraction, so the probed and drawn boxes coincide.
    return apply_legend_style(
        ax, loc="upper left", bbox_to_anchor=best[1], borderaxespad=0.0, **legend_kwargs
    )


def _legend_obstruction_score(legend_box, data_points, avoid_boxes=(), pad_px=10.0, avoid_pad_px=2.0):
    """Count how much a candidate legend box obstructs the plot.

    One point per data sample inside the padded box, plus a dominant penalty
    for any overlap with the given avoid boxes (e.g. legends already placed).
    """
    padded = Bbox.from_extents(
        legend_box.x0 - pad_px,
        legend_box.y0 - pad_px,
        legend_box.x1 + pad_px,
        legend_box.y1 + pad_px,
    )
    score = 0.0
    if len(data_points):
        inside = (
            (data_points[:, 0] >= padded.x0)
            & (data_points[:, 0] <= padded.x1)
            & (data_points[:, 1] >= padded.y0)
            & (data_points[:, 1] <= padded.y1)
        )
        score += float(inside.sum())
    for avoid in avoid_boxes:
        if avoid is None:
            continue
        padded_avoid = Bbox.from_extents(
            avoid.x0 - avoid_pad_px,
            avoid.y0 - avoid_pad_px,
            avoid.x1 + avoid_pad_px,
            avoid.y1 + avoid_pad_px,
        )
        overlap = Bbox.intersection(padded, padded_avoid)
        if overlap is not None and overlap.width > 0 and overlap.height > 0:
            score += 1e6 + overlap.width * overlap.height
    return score


def _legend_variants(ax, renderer, legend_kwargs, max_height_fraction):
    """Return the legend kwargs variants to try: as given, plus column-folded.

    The folded variant is appended only when folding actually changes the
    column count, so a pinned style is never overridden.
    """
    variants = [dict(legend_kwargs)]
    folded = dict(legend_kwargs)
    fold_legend_columns(ax, renderer, folded, max_height_fraction)
    if folded.get("ncol") != variants[0].get("ncol"):
        variants.append(folded)
    return variants


def apply_legend_style_clear_of_data(
    ax,
    avoid_boxes=(),
    candidate_locs=LEGEND_PLACEMENT_CANDIDATES,
    pad_px=10.0,
    max_height_fraction=0.2,
    **legend_kwargs,
):
    """Draw a legend at the location least obstructed by data.

    Probes each candidate corner with the final legend content, scores how
    many sampled data points the legend box would cover (plus penalties for
    overlapping any *avoid_boxes*, such as legends already on the axes), and
    keeps the winner. Falls back to the first candidate on an empty axes.

    A legend taller than *max_height_fraction* of the axes is additionally
    tried with more columns (while it still fits the axes width), since an
    oversized legend cannot avoid the data anywhere; the variant/corner
    combination with the least obstruction wins.
    """
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    variants = _legend_variants(ax, renderer, legend_kwargs, max_height_fraction)
    data_points = sample_axes_drawn_points(ax)
    avoid = [b for b in avoid_boxes if b is not None]

    best = None
    for variant in variants:
        for loc in candidate_locs:
            probe_box = probe_legend_box(ax, renderer, loc, **variant)
            score = _legend_obstruction_score(probe_box, data_points, avoid, pad_px=pad_px)
            if best is None or score < best[0]:
                best = (score, loc, variant)

    return apply_legend_style(ax, loc=best[1], **best[2])


def apply_legend_pair_clear_of_data(
    ax,
    primary_kwargs,
    secondary_kwargs,
    candidate_locs=LEGEND_PLACEMENT_CANDIDATES,
    pad_px=10.0,
    max_height_fraction=0.2,
    primary_loc=None,
    secondary_loc=None,
):
    """Draw two legends on the same axes with a joint obstruction score.

    Tries every pair of candidate corners (and, for oversized legends, the
    column-folded variants) and keeps the combination that covers the least
    data overall, with a dominant penalty whenever the two boxes would
    overlap. *primary_loc* / *secondary_loc* pin one of the two legends to a
    fixed location; the other is then placed around it.

    The caller must keep the primary legend alive (``ax.add_artist``) when it
    is superseded by the secondary axes legend; both are returned.
    """
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    primary_variants = _legend_variants(ax, renderer, primary_kwargs, max_height_fraction)
    secondary_variants = _legend_variants(ax, renderer, secondary_kwargs, max_height_fraction)
    data_points = sample_axes_drawn_points(ax)

    primary_locs = (primary_loc,) if primary_loc else candidate_locs
    secondary_locs = (secondary_loc,) if secondary_loc else candidate_locs

    def cached_box(which, loc, variant):
        return probe_legend_box(ax, renderer, loc, **variant)

    best = None
    for variant_primary in primary_variants:
        for loc_primary in primary_locs:
            box_primary = cached_box("primary", loc_primary, variant_primary)
            score_primary = _legend_obstruction_score(box_primary, data_points, (), pad_px)
            for variant_secondary in secondary_variants:
                for loc_secondary in secondary_locs:
                    if loc_secondary == loc_primary:
                        continue
                    box_secondary = cached_box("secondary", loc_secondary, variant_secondary)
                    score_secondary = _legend_obstruction_score(
                        box_secondary, data_points, (box_primary,), pad_px
                    )
                    total = score_primary + score_secondary
                    if best is None or total < best[0]:
                        best = (
                            total,
                            loc_primary,
                            variant_primary,
                            loc_secondary,
                            variant_secondary,
                        )

    if best is None:
        # Only reachable when both legends are pinned to the same location.
        best = (
            0.0,
            primary_locs[0],
            primary_variants[0],
            secondary_locs[-1] if len(secondary_locs) > 1 else "lower right",
            secondary_variants[0],
        )

    leg_primary = apply_legend_style(ax, loc=best[1], **best[2])
    ax.add_artist(leg_primary)
    leg_secondary = apply_legend_style(ax, loc=best[3], **best[4])
    return leg_primary, leg_secondary


def fold_legend_columns(ax, renderer, legend_kwargs, max_height_fraction=0.2):
    """Fold a legend into more columns while it is taller than the fraction.

    No-op when a column count is already pinned through the style or explicit
    kwargs, or when the legend already fits. Mutates *legend_kwargs* in place.
    """
    style_ncol = _style.legend_style.get("ncol") if isinstance(_style.legend_style, dict) else None
    if "ncol" in legend_kwargs or style_ncol is not None:
        return

    axes_box = ax.get_window_extent(renderer)
    box, n_entries = probe_legend_box(ax, renderer, LEGEND_PLACEMENT_CANDIDATES[0], with_entries=True, **legend_kwargs)
    ncol = 1
    while box.height > max_height_fraction * axes_box.height and ncol < n_entries:
        trial_box, _ = probe_legend_box(
            ax, renderer, LEGEND_PLACEMENT_CANDIDATES[0], with_entries=True, ncol=ncol + 1, **legend_kwargs
        )
        if trial_box.width > 0.95 * axes_box.width:
            break
        ncol += 1
        box = trial_box
    if ncol > 1:
        legend_kwargs["ncol"] = ncol


def probe_legend_box(ax, renderer, loc, with_entries=False, **legend_kwargs):
    """Create a throwaway legend at *loc* and return its window extent."""
    probe = apply_legend_style(ax, loc=loc, **legend_kwargs)
    box = probe.get_window_extent(renderer)
    n_entries = max(1, len(probe.get_texts()))
    probe.remove()
    if with_entries:
        return box, n_entries
    return box


# Plot types whose y errors follow --errory_type (bar charts and scatter
# points keep their own error bars).
_ERROR_PLOT_TYPES = ("line", "step", "plot", "errorbar")


def errory_type(args, plot_type):
    """--errory_type, or its default for the plot type: bands for lines and
    steps, bars for points."""
    selected = getattr(args, "errory_type", None)
    if selected is not None:
        return selected
    return "bars" if plot_type in ("errorbar", "scatter") else "bands"


def _draw_band(ax, x, x_edges, y, errory, color, plot_type, drawstyle=None):
    """Shade y ± errory (1-D symmetric, or 2xN lower/upper) in the series
    colour: stepwise across the bins for steps."""
    y = np.asarray(y, dtype=float)
    errory = np.asarray(errory, dtype=float)
    low, high = (y - errory, y + errory) if errory.ndim == 1 else (y - errory[0], y + errory[1])
    band = dict(color=color, alpha=_style.band_alpha, edgecolor="none", linewidth=0)
    if plot_type == "step" and x_edges is not None and len(x_edges) == len(y) + 1:
        ax.fill_between(np.asarray(x_edges, dtype=float), np.append(low, low[-1]), np.append(high, high[-1]),
                        step="post", **band)
    elif plot_type == "step":
        ax.fill_between(x, low, high, step="mid", **band)
    elif drawstyle in ("steps", "steps-pre", "steps-mid", "steps-post"):
        ax.fill_between(x, low, high, step=drawstyle.partition("-")[2] or "pre", **band)
    else:
        ax.fill_between(x, low, high, **band)


def plot_data(
    args,
    ax,
    x,
    x_edges=None,
    y=None,
    errory=None,
    errory_sym=None,
    label=None,
    color=None,
    linestyle=None,
    errorx=None,
    plot_type=None,
    **kwargs,
):
    """Plot data using a shared set of matplotlib-backed plot modes.

    Supported ``plot_style`` options: ``-``, ``--``, ``:``, ``-.``,
    ``solid``, ``dashed``, ``dotted``, ``dashdot``.
    """

    plot_type = plot_type or getattr(args, "plot_type", None)
    if plot_type is None:
        plot_type = "step" if x_edges is not None else "plot"

    explicit_plot_style = kwargs.pop("plot_style", None)
    selected_plot_style = (
        explicit_plot_style
        if explicit_plot_style is not None
        else linestyle if linestyle is not None else getattr(args, "plot_style", None)
    )
    resolved_plot_style = _resolve_plot_style(selected_plot_style)

    # The error type is resolved before the plot type: a band (or bars on a
    # step) is drawn here, in the series colour, and the branch below draws
    # the central line, step or points.
    if errory is not None and plot_type in _ERROR_PLOT_TYPES:
        bands = errory_type(args, plot_type) == "bands"
        if bands or plot_type in ("step", "plot"):
            if color is None:
                color = ax._get_lines.get_next_color()
            if bands:
                _draw_band(ax, x, x_edges, y, errory, color, plot_type, kwargs.get("drawstyle"))
            else:
                ax.errorbar(x, y, yerr=errory, fmt="none", color=color,
                            linewidth=kwargs.get("linewidth", _style.default_linewidth))
            errory = None

    if plot_type == "scatter":
        kwargs.setdefault("linewidth", _style.default_linewidth)
        ax.errorbar(
            x,
            y,
            yerr=errory if getattr(args, "errory", False) else None,
            fmt=kwargs.pop("fmt", "o"),
            label=label,
            color=color,
            **kwargs,
        )
        return None

    if plot_type == "line":
        kwargs.setdefault("linewidth", _style.default_linewidth)
        if errory is not None:
            errorbar_kwargs = dict(kwargs)
            _apply_plot_style(errorbar_kwargs, resolved_plot_style)
            ax.errorbar(
                x,
                y,
                xerr=errorx if getattr(args, "errory_x", False) else None,
                yerr=errory if errory_sym == "symmetric" else errory,
                label=label,
                color=color,
                **errorbar_kwargs,
            )
        else:
            plot_kwargs = dict(kwargs)
            _apply_plot_style(plot_kwargs, resolved_plot_style)
            ax.plot(x, y, label=label, color=color, **plot_kwargs)
        return None

    if plot_type == "step":
        hist_kwargs = dict(kwargs)
        hist_kwargs.setdefault("linewidth", _style.default_linewidth)
        _apply_plot_style(hist_kwargs, resolved_plot_style)
        fill_alpha = hist_kwargs.pop("fill_alpha", None)
        fill_hatch = hist_kwargs.pop("fill_hatch", None)
        fill_hatch_color = hist_kwargs.pop("fill_hatch_color", False)
        hist_align = hist_kwargs.pop("align", getattr(args, "align", "mid"))
        histtype = hist_kwargs.pop("histtype", "step")
        if (
            getattr(args, "step_open", False)
            and histtype == "step"
            and fill_alpha is None
            and x_edges is not None
            and y is not None
            and len(x_edges) == len(np.asarray(y)) + 1
        ):
            # Open outline (no baseline edges): for binned ratios such as
            # efficiencies, where a drop to zero at the first/last bin edge
            # would read as a zero fraction rather than the end of the data.
            ax.stairs(
                np.asarray(y, dtype=float),
                np.asarray(x_edges, dtype=float),
                baseline=None,
                label=label,
                color=color,
                **hist_kwargs,
            )
            return None
        if (
            histtype == "step"
            and x_edges is not None
            and y is not None
            and len(x_edges) == len(np.asarray(y)) + 1
            and not np.isfinite(np.asarray(y, dtype=float)).all()
        ):
            # A NaN weight puts a NaN vertex in the hist polygon and the whole
            # outline disappears (e.g. a ratio to an empty bin); stairs leaves
            # a gap at the undefined bins instead.
            values, edges = np.asarray(y, dtype=float), np.asarray(x_edges, dtype=float)
            ax.stairs(values, edges, label=label, color=color, **hist_kwargs)
            if fill_alpha is not None:
                ax.stairs(values, edges, fill=True, color=color, alpha=fill_alpha, hatch=fill_hatch or "", linewidth=0)
            return None
        ax.hist(
            x,
            bins=x_edges,
            weights=y,
            histtype=histtype,
            align=hist_align,
            label=label,
            color=color,
            **hist_kwargs,
        )
        if fill_alpha is not None:
            if fill_hatch_color and fill_hatch:
                # Transparent face at fill_alpha, then a separate full-opacity
                # hatch-only pass so hatch lines match the data line color.
                ax.hist(
                    x, bins=x_edges, weights=y,
                    histtype="stepfilled", align=hist_align, label=None,
                    color=color, alpha=fill_alpha, linewidth=0,
                )
                ax.hist(
                    x, bins=x_edges, weights=y,
                    histtype="stepfilled", align=hist_align, label=None,
                    facecolor=(0, 0, 0, 0), edgecolor=color,
                    hatch=fill_hatch, linewidth=0,
                )
            else:
                ax.hist(
                    x, bins=x_edges, weights=y,
                    histtype="stepfilled", align=hist_align, label=None,
                    color=color, alpha=fill_alpha,
                    hatch=fill_hatch or "", linewidth=0,
                )
        return None

    if plot_type == "plot":
        plot_kwargs = dict(kwargs)
        fill_alpha = plot_kwargs.pop("fill_alpha", None)
        fill_hatch = plot_kwargs.pop("fill_hatch", None)
        fill_hatch_color = plot_kwargs.pop("fill_hatch_color", False)
        plot_kwargs.setdefault("linewidth", _style.default_linewidth)
        _apply_plot_style(plot_kwargs, resolved_plot_style)
        drawstyle = plot_kwargs.get("drawstyle", None)
        step_mode = "mid" if drawstyle == "steps-mid" else ("pre" if drawstyle == "steps-pre" else ("post" if drawstyle == "steps-post" else None))
        ax.plot(x, y, label=label, color=color, **plot_kwargs)
        if fill_alpha is not None and step_mode is not None:
            ax.fill_between(x, y, 0, step=step_mode, color=color, alpha=fill_alpha,
                            hatch=fill_hatch or "", linewidth=0)
        elif fill_alpha is not None:
            ax.fill_between(x, y, 0, color=color, alpha=fill_alpha,
                            hatch=fill_hatch or "", linewidth=0)
        return None

    if plot_type == "errorbar":
        errorbar_kwargs = dict(kwargs)
        errorbar_kwargs.setdefault("linewidth", _style.default_linewidth)
        # Measured points are not joined unless --connect is given.
        _apply_plot_style(errorbar_kwargs, resolved_plot_style if getattr(args, "connect", False) else "none")
        return ax.errorbar(
            x,
            y,
            xerr=errorbar_kwargs.pop("xerr", errorx),
            yerr=errorbar_kwargs.pop("yerr", errory),
            fmt=errorbar_kwargs.pop("fmt", "o"),
            label=label,
            color=color,
            **errorbar_kwargs,
        )

    if plot_type == "scatter_points":
        return ax.scatter(x, y, label=label, color=color, **kwargs)

    if plot_type == "bar":
        kwargs.setdefault("linewidth", _style.default_linewidth)
        return ax.bar(
            x,
            y,
            yerr=kwargs.pop("yerr", errory),
            label=label,
            color=color,
            **kwargs,
        )

    if plot_type == "barh":
        kwargs.setdefault("linewidth", _style.default_linewidth)
        return ax.barh(
            x,
            y,
            xerr=kwargs.pop("xerr", errorx),
            label=label,
            color=color,
            **kwargs,
        )

    if plot_type == "boxplot":
        boxplot_data = kwargs.pop("boxplot_data", y)
        if color is not None:
            # Edge, whiskers, caps and median in the series colour, the face at
            # alpha 0.25, fliers as small hollow markers; the legend shows one box.
            kwargs.setdefault("patch_artist", True)
            kwargs.setdefault("boxprops", {"facecolor": to_rgba(color, 0.25), "edgecolor": color})
            for key in ("medianprops", "whiskerprops", "capprops"):
                kwargs.setdefault(key, {"color": color})
            kwargs.setdefault("flierprops", {"marker": "o", "markersize": 3, "markerfacecolor": "none",
                                             "markeredgecolor": color})
        return ax.boxplot(boxplot_data, label=label, **kwargs)

    if plot_type == "hist2d":
        return ax.hist2d(
            x,
            y,
            bins=kwargs.pop("bins", getattr(args, "bins", None)),
            range=kwargs.pop("range", None),
            norm=LogNorm() if getattr(args, "logz", False) else None,
            density=kwargs.pop("density", getattr(args, "density", False)),
            **kwargs,
        )

    if plot_type == "image":
        z = kwargs.pop("z", None)
        norm = LogNorm() if getattr(args, "logz", False) else None
        return ax.pcolormesh(x, y, z, norm=norm, shading="auto", **kwargs)

    raise ValueError(f"Unknown plot type: {plot_type}")


def add_note_to_axes(ax, note_text, fontsize=None):
    """Add a text annotation to the best position on an axes.

    Tries the corners and the middle of the sides (upper right first) and
    keeps the one covering the least drawn data, never on a legend.
    
    Args:
        ax: matplotlib axes object
        note_text: Text string to display
        fontsize: Font size for the note text (uses _style.note_style default if None)
    
    Returns:
        matplotlib text object
    """
    if note_text is None or not str(note_text).strip():
        return None
    
    text_str = str(note_text).strip()
    
    # Get note style from config
    note_cfg = _style.role_colors(_style.note_style) if isinstance(_style.note_style, dict) else {}
    configured_fontsize = note_cfg.get("fontsize", "large")
    bbox_cfg = note_cfg.get("bbox", {
        "boxstyle": "round,pad=0.5",
        "facecolor": _style.role("paper"),
        "alpha": 0.8,
        "edgecolor": _style.role("muted"),
        "linewidth": 0.5,
    })
    
    # Use provided fontsize or fall back to config
    if fontsize is None:
        fontsize = configured_fontsize
    
    # Candidate anchors (x, y) in axes coordinates, in order of preference;
    # the note goes where it covers the least drawn data, clear of legends.
    positions = [(0.98, 0.98), (0.02, 0.98), (0.02, 0.02), (0.98, 0.02), (0.98, 0.5), (0.02, 0.5)]
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    points = sample_axes_drawn_points(ax)
    legends = [a.get_window_extent(renderer) for a in ax.get_children() if isinstance(a, Legend)]

    def place(x, y):
        return ax.text(
            x, y, text_str,
            transform=ax.transAxes,
            fontsize=fontsize,
            ha="right" if x > 0.5 else "left",
            va="top" if y > 0.5 else "bottom" if y < 0.5 else "center",
            bbox=dict(bbox_cfg),
            zorder=100,  # above the data
        )

    best = None
    for x, y in positions:
        probe = place(x, y)
        score = _legend_obstruction_score(probe.get_window_extent(renderer), points, legends)
        probe.remove()
        if best is None or score < best[0]:
            best = (score, x, y)
    text_obj = place(best[1], best[2])

    return text_obj


def get_main_axes(fig):
    """Return *fig*'s axes with colorbar axes filtered out.

    Colorbars are skipped both by class name and by a size heuristic
    (colorbar axes are thin slivers next to the plot they annotate).
    """
    main_axes = []
    for ax in fig.get_axes():
        if hasattr(ax, 'cbar') or 'colorbar' in str(type(ax).__name__).lower():
            continue
        bbox = ax.get_position()
        if bbox.width < 0.05 or bbox.height < 0.05:
            continue
        main_axes.append(ax)

    # Fallback: filtering removed everything (e.g. all axes are small), so
    # just return the unfiltered list rather than reporting no axes at all.
    return main_axes if main_axes else fig.get_axes()


def add_centered_suptitle(fig, title, fontsize=None, **kwargs):
    """Add a figure title centered on the main plot axes, not the full canvas.

    fig.suptitle() centers on the whole figure by default, which drifts off
    the visual center of the plot frame whenever the axes are asymmetric —
    e.g. a colorbar occupying space on the right. This centers the title
    over the combined bounding box of the non-colorbar axes instead.
    """
    main_axes = get_main_axes(fig)
    if main_axes:
        x0 = min(ax.get_position().x0 for ax in main_axes)
        x1 = max(ax.get_position().x1 for ax in main_axes)
        kwargs.setdefault("x", (x0 + x1) / 2)

    text = fig.suptitle(title, fontsize=fontsize, **kwargs)
    text._plotipus_centered = True
    _shorten_title_to_fit(fig, text)
    return text




def _text_fits_figure(fig, text, margin=-0.01):
    try:
        renderer = fig.canvas.get_renderer()
        bbox = text.get_window_extent(renderer=renderer)
    except Exception:
        return True
    fig_width = fig.bbox.width
    return bbox.x0 >= -margin * fig_width and bbox.x1 <= (1 + margin) * fig_width


def _shorten_title_to_fit(fig, text):
    """Swap long analysis names for their short forms, one at a time, until
    the title fits inside the figure (or no short form is left)."""
    if text is None or _text_fits_figure(fig, text):
        return text
    current = text.get_text()
    for long_form, short_form in _style.title_short_forms:
        if long_form not in current:
            continue
        current = current.replace(long_form, short_form)
        text.set_text(current)
        if _text_fits_figure(fig, text):
            break
    return text


def apply_note_to_figure(fig, note_text, fontsize=None):
    """Apply a text annotation to the best position on a figure's main axes.

    Automatically finds the first non-colorbar axes and places the note there.
    Uses _style.note_style configuration for fontsize and styling if not explicitly provided.

    Args:
        fig: matplotlib figure object
        note_text: Text string to display
        fontsize: Font size for the note text (uses _style.note_style default if None)

    Returns:
        matplotlib text object, or None if no valid axes found
    """
    if note_text is None or not str(note_text).strip():
        return None

    main_axes = get_main_axes(fig)
    if not main_axes:
        return None

    return add_note_to_axes(main_axes[0], note_text, fontsize=fontsize)


def format_ref_value(v):
    """Format a float reference-line value as a compact string label.
    Public so callers can opt into the same default formatting used by
    draw_vertical_lines/draw_horizontal_lines when building their own labels.
    """
    if v == int(v):
        return str(int(v))
    return f"{v:g}"


def _ref_line_get(seq, i, default):
    """Index into seq by position, reusing the last element when out-of-range.
    Returns *default* when seq is None or empty."""
    if not seq:
        return default
    return seq[i] if i < len(seq) else seq[-1]


def _measure_text_extent_data(ax, label, fontsize):
    """Return (width, height) of `label` in data units at the current view."""
    fig = ax.figure
    try:
        renderer = fig.canvas.get_renderer()
    except AttributeError:
        try:
            fig.canvas.draw()
            renderer = fig.canvas.get_renderer()
        except Exception:
            return None
    except Exception:
        return None

    text = ax.text(0, 0, str(label), fontsize=fontsize, alpha=0)
    try:
        bbox = text.get_window_extent(renderer=renderer)
    except Exception:
        return None
    finally:
        text.remove()

    inv = ax.transData.inverted()
    p0 = inv.transform((0, 0))
    p1 = inv.transform((bbox.width, bbox.height))
    return abs(p1[0] - p0[0]), abs(p1[1] - p0[1])


def _rects_overlap(a, b):
    ax0, ax1, ay0, ay1 = a
    bx0, bx1, by0, by1 = b
    return not (ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0)


def _label_avoid_box(text_obj, ax, fontsize):
    """Data-space bounding box of a placed label, for later collision checks."""
    size = _measure_text_extent_data(ax, text_obj.get_text(), fontsize)
    if size is None:
        return None
    width, height = size
    x_text, y_text = text_obj.get_position()
    ha = text_obj.get_ha()
    va = text_obj.get_va()

    if ha == "right":
        bx0, bx1 = x_text - width, x_text
    elif ha == "left":
        bx0, bx1 = x_text, x_text + width
    else:
        bx0, bx1 = x_text - width / 2.0, x_text + width / 2.0

    if va == "top":
        by0, by1 = y_text - height, y_text
    elif va == "bottom":
        by0, by1 = y_text, y_text + height
    else:
        by0, by1 = y_text - height / 2.0, y_text + height / 2.0

    return (bx0, bx1, by0, by1)


def draw_vertical_lines(ax, values, labels=None, styles=None, colors=None, fontsize=None):
    """Draw one or more vertical reference lines on *ax*.

    Each positional list (``labels``, ``styles``, ``colors``) is matched to
    ``values`` by index; if shorter than ``values`` the last element is reused
    as a default.

    No label is shown unless ``labels`` is explicitly provided. Use
    ``format_ref_value`` to build default numeric-value labels yourself if
    that's what a particular caller wants.
    """
    if values is None:
        return
    vals = values if isinstance(values, (list, tuple)) else [values]

    avoid_boxes = []
    for i, v in enumerate(vals):
        color = _ref_line_get(colors, i, _style.role("muted"))
        style = _ref_line_get(styles, i, "--")
        label = _ref_line_get(labels, i, None) if labels is not None else None
        xlim = ax.get_xlim()
        if v < xlim[0] or v > xlim[1]:
            ax.set_xlim(min(xlim[0], v), max(xlim[1], v))
        ax.axvline(v, color=color, linestyle=style, linewidth=1, zorder=5)
        if label:
            text_obj = place_vertical_label(ax, v, label, fontsize=fontsize, avoid=avoid_boxes)
            if text_obj is not None:
                box = _label_avoid_box(text_obj, ax, fontsize)
                if box is not None:
                    avoid_boxes.append(box)


def draw_horizontal_lines(ax, values, labels=None, styles=None, colors=None, fontsize=None):
    """Draw one or more horizontal reference lines on *ax*.

    Each positional list (``labels``, ``styles``, ``colors``) is matched to
    ``values`` by index; if shorter than ``values`` the last element is reused
    as a default.

    No label is shown unless ``labels`` is explicitly provided. Use
    ``format_ref_value`` to build default numeric-value labels yourself if
    that's what a particular caller wants.
    """
    if values is None:
        return
    vals = values if isinstance(values, (list, tuple)) else [values]

    avoid_boxes = []
    for i, v in enumerate(vals):
        color = _ref_line_get(colors, i, _style.role("muted"))
        style = _ref_line_get(styles, i, "--")
        label = _ref_line_get(labels, i, None) if labels is not None else None
        ylim = ax.get_ylim()
        if v < ylim[0] or v > ylim[1]:
            ax.set_ylim(min(ylim[0], v), max(ylim[1], v))
        ax.axhline(v, color=color, linestyle=style, linewidth=1, zorder=5)
        if label is not None and label:
            text_obj = place_horizontal_label(ax, v, label, fontsize=fontsize, avoid=avoid_boxes)
            if text_obj is not None:
                box = _label_avoid_box(text_obj, ax, fontsize)
                if box is not None:
                    avoid_boxes.append(box)


def draw_squares(ax, quads, labels=None, styles=None, colors=None, fontsize=None, fill=False, alpha=None):
    """Draw one or more rectangles on *ax*.

    ``quads`` is a sequence of ``(x1, y1, x2, y2)`` tuples giving two opposite
    corners of each rectangle (order-independent). Each positional list
    (``labels``, ``styles``, ``colors``) is matched to ``quads`` by index; if
    shorter than ``quads`` the last element is reused as a default.
    """
    if quads is None:
        return
    quads = list(quads)

    for i, (x1, y1, x2, y2) in enumerate(quads):
        color = _ref_line_get(colors, i, _style.role("muted"))
        style = _ref_line_get(styles, i, "-")
        label = _ref_line_get(labels, i, None) if labels is not None else None

        x0, x1e = min(x1, x2), max(x1, x2)
        y0, y1e = min(y1, y2), max(y1, y2)

        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        if x0 < xlim[0] or x1e > xlim[1]:
            ax.set_xlim(min(xlim[0], x0), max(xlim[1], x1e))
        if y0 < ylim[0] or y1e > ylim[1]:
            ax.set_ylim(min(ylim[0], y0), max(ylim[1], y1e))

        rect = Rectangle(
            (x0, y0),
            x1e - x0,
            y1e - y0,
            fill=fill,
            facecolor=color if fill else "none",
            edgecolor=color,
            linestyle=style,
            linewidth=1,
            alpha=alpha,
            zorder=5,
        )
        ax.add_patch(rect)

        if label:
            ax.text(
                (x0 + x1e) / 2,
                y1e,
                str(label),
                ha="center",
                va="bottom",
                fontsize=fontsize,
                zorder=6,
            )


def draw_lines(ax, segments, labels=None, styles=None, colors=None, fontsize=None):
    """Draw one or more custom line segments on *ax*.

    ``segments`` is a sequence of ``(x1, y1, x2, y2)`` tuples giving the two
    endpoints of each line. Each positional list (``labels``, ``styles``,
    ``colors``) is matched to ``segments`` by index; if shorter than
    ``segments`` the last element is reused as a default.
    """
    if segments is None:
        return
    segments = list(segments)

    for i, (x1, y1, x2, y2) in enumerate(segments):
        color = _ref_line_get(colors, i, _style.role("muted"))
        style = _ref_line_get(styles, i, "--")
        label = _ref_line_get(labels, i, None) if labels is not None else None

        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        x_lo, x_hi = min(x1, x2), max(x1, x2)
        y_lo, y_hi = min(y1, y2), max(y1, y2)
        if x_lo < xlim[0] or x_hi > xlim[1]:
            ax.set_xlim(min(xlim[0], x_lo), max(xlim[1], x_hi))
        if y_lo < ylim[0] or y_hi > ylim[1]:
            ax.set_ylim(min(ylim[0], y_lo), max(ylim[1], y_hi))

        ax.plot([x1, x2], [y1, y2], color=color, linestyle=style, linewidth=_style.default_linewidth, zorder=5)

        if label:
            ax.text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                str(label),
                ha="center",
                va="bottom",
                fontsize=fontsize,
                zorder=6,
            )


def _label_data_halfwidth(ax, axis, label, fontsize):
    """Estimate half the on-screen width/height of *label* in data units.

    Used to displace nearby automatic ticks so a custom tick label doesn't
    visually collide with its neighbors. Returns None if it cannot be
    measured (e.g. no renderer available yet), in which case callers should
    fall back to a coarser heuristic.
    """
    fig = ax.figure
    try:
        renderer = fig.canvas.get_renderer()
    except AttributeError:
        try:
            fig.canvas.draw()
            renderer = fig.canvas.get_renderer()
        except Exception:
            return None
    except Exception:
        return None

    text = ax.text(0, 0, str(label), fontsize=fontsize, alpha=0)
    try:
        bbox = text.get_window_extent(renderer=renderer)
    except Exception:
        return None
    finally:
        text.remove()

    inv = ax.transData.inverted()
    p0 = inv.transform((0, 0))
    if axis == "x":
        p1 = inv.transform((bbox.width, 0))
        return abs(p1[0] - p0[0]) / 2.0
    p1 = inv.transform((0, bbox.height))
    return abs(p1[1] - p0[1]) / 2.0


def _draw_pointer_tick_label(
    ax, axis, position, label, fontsize=None, height=0.09, color=None, side=None, edge=None
):
    """Draw a long tick-like arrow at `position` pointing at the axis, with
    `label` placed just beyond its tail (further out than a normal tick
    label). `height` is the single, user-tunable distance (axes fraction)
    from the axis to the label -- shrink it to fit the label in the space
    before a fixed-position axis title; the arrow tail sits just short of it,
    with only a small fixed cosmetic gap to the text.

    `edge` selects which of the two parallel spines to anchor the pointer to
    ("bottom"/"top" for `axis="x"`, "left"/"right" for `axis="y"`; defaults
    to the conventional one). `side` selects which direction the label sits
    relative to that spine ("below"/"above" for `axis="x"`, "left"/"right"
    for `axis="y"`; defaults to pointing away from the plot).
    """
    if fontsize is None:
        fontsize = _style.linelabelfontsize
    if color is None:
        color = _style.role("ink")

    text_gap = min(0.012, height * 0.25)
    tail_offset = height - text_gap

    if axis == "x":
        edge = edge or "bottom"
        side = side or "below"
        anchor = 0.0 if edge == "bottom" else 1.0
        direction = -1.0 if side == "below" else 1.0

        trans = ax.get_xaxis_transform()
        tail = (position, anchor + direction * tail_offset)
        head = (position, anchor)
        text_xy = (position, anchor + direction * height)
        ha = "center"
        va = "top" if side == "below" else "bottom"
    else:
        edge = edge or "left"
        side = side or "left"
        anchor = 0.0 if edge == "left" else 1.0
        direction = -1.0 if side == "left" else 1.0

        trans = ax.get_yaxis_transform()
        tail = (anchor + direction * tail_offset, position)
        head = (anchor, position)
        text_xy = (anchor + direction * height, position)
        ha = "right" if side == "left" else "left"
        va = "center"

    arrow = ax.annotate(
        "",
        xy=head,
        xycoords=trans,
        xytext=tail,
        textcoords=trans,
        arrowprops=dict(arrowstyle="-|>", color=color, lw=1, shrinkA=0, shrinkB=0),
        annotation_clip=False,
    )
    text = ax.text(
        *text_xy,
        str(label),
        transform=trans,
        ha=ha,
        va=va,
        fontsize=fontsize,
        clip_on=False,
    )
    return arrow, text




def _expand_margins_for_artists(fig, artists, pad_px=4):
    """Grow the figure canvas (never the Axes box itself) just enough that
    *artists* aren't clipped by the figure edge (used for pointer tick labels
    that sit outside the normal tick-label margin).

    Shrinking the subplot margins within a fixed-size figure would eat into
    the plotted area -- i.e. `--xtick_height` would visibly shorten/narrow
    the plot. Instead, the figure is enlarged by exactly the overflow amount
    and the Axes box is kept at its original absolute (inch) size and shifted
    to make room, so only the surrounding whitespace grows.
    """
    if measured_layout_enabled():
        return  # the pointer labels belong to the axes, so the layout makes room
    try:
        renderer = fig.canvas.get_renderer()
    except Exception:
        return

    fig_w, fig_h = fig.bbox.width, fig.bbox.height
    min_x0, max_x1, min_y0, max_y1 = 0.0, fig_w, 0.0, fig_h
    for artist in artists:
        if artist is None:
            continue
        try:
            bbox = artist.get_window_extent(renderer=renderer)
        except Exception:
            continue
        min_x0 = min(min_x0, bbox.x0)
        max_x1 = max(max_x1, bbox.x1)
        min_y0 = min(min_y0, bbox.y0)
        max_y1 = max(max_y1, bbox.y1)

    left_deficit = (-min_x0 + pad_px) if min_x0 < 0 else 0
    right_deficit = (max_x1 - fig_w + pad_px) if max_x1 > fig_w else 0
    bottom_deficit = (-min_y0 + pad_px) if min_y0 < 0 else 0
    top_deficit = (max_y1 - fig_h + pad_px) if max_y1 > fig_h else 0

    if not (left_deficit or right_deficit or bottom_deficit or top_deficit):
        return

    dpi = fig.dpi
    fig_w_in, fig_h_in = fig.get_figwidth(), fig.get_figheight()
    left_in, right_in = left_deficit / dpi, right_deficit / dpi
    bottom_in, top_in = bottom_deficit / dpi, top_deficit / dpi

    params = fig.subplotpars
    # Absolute (inch) position of the current Axes box, to be preserved.
    axes_left_in = params.left * fig_w_in
    axes_right_in = params.right * fig_w_in
    axes_bottom_in = params.bottom * fig_h_in
    axes_top_in = params.top * fig_h_in

    new_w_in = fig_w_in + left_in + right_in
    new_h_in = fig_h_in + bottom_in + top_in

    new_axes_left_in = axes_left_in + left_in
    new_axes_bottom_in = axes_bottom_in + bottom_in
    new_axes_right_in = new_axes_left_in + (axes_right_in - axes_left_in)
    new_axes_top_in = new_axes_bottom_in + (axes_top_in - axes_bottom_in)

    fig.set_size_inches(new_w_in, new_h_in, forward=True)
    fig.subplots_adjust(
        left=new_axes_left_in / new_w_in,
        right=new_axes_right_in / new_w_in,
        bottom=new_axes_bottom_in / new_h_in,
        top=new_axes_top_in / new_h_in,
    )


def set_axis_tick_labels(ax, axis, values, labels, fontsize=None, height=0.09, side=None, edge=None):
    """Mark specific ``values`` on *axis* ("x" or "y") with a long pointer
    tick and a label placed beyond it, further out than the regular tick
    labels. Nearby automatic ticks that would visually collide with the new
    label are dropped; all other automatic ticks are left untouched.
    `height` is the distance (axes fraction) from the axis to the label --
    the axis title's own position is never touched, so shrink `height` to
    fit the label within the fixed space before it.

    `edge` picks which spine the pointer is anchored to ("bottom"/"top" for
    `axis="x"`, "left"/"right" for `axis="y"`). `side` picks which direction
    the label sits relative to that spine ("below"/"above" for `axis="x"`,
    "left"/"right" for `axis="y"`). Both default to the conventional side
    (outside the plot, on the usual axis). Either may be a single value
    (applied to every tick) or a list matched to ``values`` by position,
    reusing the last element when shorter (same convention as
    ``vertical_style``/``vertical_color``).
    """
    if values is None or labels is None:
        return

    # Resolve once so the collision-avoidance sizing below matches the font
    # size the label is actually drawn at.
    if fontsize is None:
        fontsize = _style.linelabelfontsize

    vals = values if isinstance(values, (list, tuple)) else [values]
    labs = labels if isinstance(labels, (list, tuple)) else [labels]
    sides = side if isinstance(side, (list, tuple)) else ([side] if side is not None else None)
    edges = edge if isinstance(edge, (list, tuple)) else ([edge] if edge is not None else None)

    get_lim = ax.get_xlim if axis == "x" else ax.get_ylim
    get_ticks = ax.get_xticks if axis == "x" else ax.get_yticks
    set_ticks = ax.set_xticks if axis == "x" else ax.set_yticks

    ax.figure.canvas.draw()
    get_ticklabels = ax.get_xticklabels if axis == "x" else ax.get_yticklabels

    lim = get_lim()
    tick_range = lim[1] - lim[0] if lim[1] != lim[0] else 1.0
    tol = abs(tick_range) * 1e-6
    fallback_gap = abs(tick_range) * 0.09
    padding = 1.5

    existing = [
        (float(t), text.get_text())
        for t, text in zip(get_ticks(), get_ticklabels())
        if min(lim) - tol <= t <= max(lim) + tol
    ]

    # The regular tick labels only ever sit below the x-axis / left of the
    # y-axis, so a custom label only risks colliding with them (and thus
    # only needs to displace them) when it lands in that same spot.
    default_side = "below" if axis == "x" else "left"
    default_edge = "bottom" if axis == "x" else "left"

    for i, (v, label) in enumerate(zip(vals, labs)):
        v = float(v)
        label = str(label)

        if v < min(lim) or v > max(lim):
            lim = (min(lim[0], v), max(lim[1], v))

        resolved_side = _ref_line_get(sides, i, None) or default_side
        resolved_edge = _ref_line_get(edges, i, None) or default_edge
        if resolved_side != default_side or resolved_edge != default_edge:
            continue

        halfwidth_new = _label_data_halfwidth(ax, axis, label, fontsize)

        def _too_close(t, l):
            halfwidth_existing = _label_data_halfwidth(ax, axis, l, fontsize)
            if halfwidth_new is not None and halfwidth_existing is not None:
                gap = (halfwidth_new + halfwidth_existing) * padding
            else:
                gap = fallback_gap
            return abs(t - v) <= max(gap, tol)

        existing = [(t, l) for t, l in existing if not _too_close(t, l)]

    remaining_ticks = sorted(t for t, _ in existing)

    if axis == "x":
        ax.set_xlim(lim)
    else:
        ax.set_ylim(lim)

    set_ticks(remaining_ticks)

    drawn_artists = []
    for i, (v, label) in enumerate(zip(vals, labs)):
        arrow, text = _draw_pointer_tick_label(
            ax,
            axis,
            float(v),
            str(label),
            fontsize=fontsize,
            height=height,
            side=_ref_line_get(sides, i, None),
            edge=_ref_line_get(edges, i, None),
        )
        drawn_artists.extend([arrow, text])

    # The axis title's position is left untouched; `length` controls how far
    # out the pointer label sits, so callers can tune it to fit within the
    # space before the title rather than the title moving to make room.
    _expand_margins_for_artists(ax.figure, drawn_artists)


def place_vertical_label(ax, x_value, label_text, fontsize=None, pad_fraction=0.02, avoid=None):
    """Place a label next to a vertical line at `x_value` in the least-populated vertical gap.

    The function inspects existing plotted data (lines, scatter collections, bars)
    and chooses the largest empty vertical gap at `x_value` to place the text.

    Args:
        ax: matplotlib Axes
        x_value: numeric x coordinate where the vertical line is placed
        label_text: text to display
        fontsize: optional font size
        pad_fraction: fraction of x-range to offset the label horizontally from the line
        avoid: optional list of (x0, x1, y0, y1) data-space boxes (e.g. other
            labels placed earlier in the same batch) the new label should not
            overlap; it is nudged up/down until clear of all of them.

    Returns:
        matplotlib Text object or None
    """
    if label_text is None or not str(label_text).strip():
        return None

    text_str = str(label_text).strip()

    try:
        x0 = float(x_value)
    except Exception:
        # Fallback: place in upper-right corner
        return add_note_to_axes(ax, text_str, fontsize=fontsize)

    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    x_range = xlim[1] - xlim[0] if xlim[1] != xlim[0] else 1.0

    # Collect y-positions occupied at/near x0
    y_occupied = []

    # Line2D objects
    for line in ax.get_lines():
        try:
            xd = np.asarray(line.get_xdata())
            yd = np.asarray(line.get_ydata())
            if xd.size == 0:
                continue
            xmin, xmax = xd.min(), xd.max()
            if xmin <= x0 <= xmax:
                y_at = np.interp(x0, xd, yd)
                if np.isfinite(y_at):
                    y_occupied.append(float(y_at))
        except Exception:
            continue

    # PathCollections (scatter)
    for col in getattr(ax, "collections", []):
        try:
            offsets = col.get_offsets()
            if offsets is None or len(offsets) == 0:
                continue
            xs = np.asarray(offsets)[:, 0]
            ys = np.asarray(offsets)[:, 1]
            x_tol = x_range * 0.02
            mask = np.isfinite(xs) & (np.abs(xs - x0) <= x_tol)
            y_occupied.extend(list(ys[mask]))
        except Exception:
            continue

    # Bars / patches: treat rectangles as occupying their vertical span if x0 falls inside
    for patch in getattr(ax, "patches", []):
        try:
            bbox = patch.get_bbox()
            if bbox.x0 <= x0 <= bbox.x1:
                y_occupied.append((bbox.y0 + bbox.y1) / 2.0)
        except Exception:
            continue

    # Build candidate gaps between ylim edges and occupied positions
    clean_points = [float(y) for y in y_occupied if np.isfinite(y) and ylim[0] <= y <= ylim[1]]
    candidates = [ylim[0]] + sorted(clean_points) + [ylim[1]]

    # For each gap, evaluate how many plotted points are within a small
    # rectangle around (x0, y_center). Choose gap with minimal nearby points
    # (avoids placing label on top of lines). Tie-breaker: larger gap.
    x_tol = max(x_range * 0.03, 1e-8)
    y_range = ylim[1] - ylim[0]
    text_height_est = max(0.06 * y_range, 0.0)

    best_candidate = None
    best_score = None
    for i in range(len(candidates) - 1):
        y0_gap = candidates[i]
        y1_gap = candidates[i + 1]
        gap_size = y1_gap - y0_gap
        if gap_size <= 0:
            continue
        y_center = (y0_gap + y1_gap) / 2.0
        # text vertical span to avoid (use fraction of gap and estimated text height)
        y_span = min(gap_size * 0.9, text_height_est if text_height_est > 0 else gap_size)
        ymin = y_center - y_span / 2.0
        ymax = y_center + y_span / 2.0

        count = 0

        # Count line points in neighborhood
        for line in ax.get_lines():
            try:
                xd = np.asarray(line.get_xdata())
                yd = np.asarray(line.get_ydata())
                if xd.size == 0:
                    continue
                # consider only points near x0 (interpolation gives single value, but sample nearby)
                mask = np.isfinite(xd) & np.isfinite(yd) & (xd >= x0 - x_tol) & (xd <= x0 + x_tol) & (yd >= ymin) & (yd <= ymax)
                count += int(np.count_nonzero(mask))
            except Exception:
                continue

        # Count scatter/collection offsets
        for col in getattr(ax, "collections", []):
            try:
                offsets = col.get_offsets()
                if offsets is None or len(offsets) == 0:
                    continue
                xs = np.asarray(offsets)[:, 0]
                ys = np.asarray(offsets)[:, 1]
                mask = np.isfinite(xs) & np.isfinite(ys) & (xs >= x0 - x_tol) & (xs <= x0 + x_tol) & (ys >= ymin) & (ys <= ymax)
                count += int(np.count_nonzero(mask))
            except Exception:
                continue

        # Count patches (bars) that intersect the rectangle
        for patch in getattr(ax, "patches", []):
            try:
                bbox = patch.get_bbox()
                if (bbox.x1 >= x0 - x_tol) and (bbox.x0 <= x0 + x_tol) and (bbox.y1 >= ymin) and (bbox.y0 <= ymax):
                    count += 1
            except Exception:
                continue

        score = (count, -gap_size)  # prefer fewer counts, then larger gap
        if best_score is None or score < best_score:
            best_score = score
            best_candidate = (y_center, gap_size)

    if best_candidate is None:
        y_text = (ylim[0] + ylim[1]) / 2.0
    else:
        y_text = best_candidate[0]

    # Clamp y_text to stay between the outermost visible tick marks (not just ylim,
    # which extends beyond the ticks due to axis padding), with an extra margin for
    # the text box height so it does not overlap the frame or tick labels.
    margin = text_height_est / 2.0 if text_height_est > 0 else 0.03 * y_range
    yticks = np.asarray(ax.get_yticks())
    yticks_visible = yticks[(yticks >= ylim[0]) & (yticks <= ylim[1])]
    inner_min = float(yticks_visible.min()) if len(yticks_visible) > 0 else ylim[0]
    inner_max = float(yticks_visible.max()) if len(yticks_visible) > 0 else ylim[1]
    y_text = float(np.clip(y_text, inner_min + margin, inner_max - margin))

    # Horizontal offset: place label on side with more space (left/right)
    x_mid = (xlim[0] + xlim[1]) / 2.0
    if x0 > x_mid:
        ha = "right"
    else:
        ha = "left"

    # Offset the label in display space rather than data space: a fraction of
    # the x-range in data coordinates lands far from the line on log-scaled
    # axes, where the visual distance of a fixed data offset varies by decade.
    try:
        px_line = ax.transData.transform((x0, y_text))[0]
        px_xlim0 = ax.transData.transform((xlim[0], y_text))[0]
        px_xlim1 = ax.transData.transform((xlim[1], y_text))[0]
        width_px = abs(px_xlim1 - px_xlim0)
        if width_px <= 0:
            raise ValueError("zero axes width")
        pad_px = pad_fraction * width_px
        px_text = px_line + pad_px if ha == "left" else px_line - pad_px
        x_text = float(ax.transData.inverted().transform((px_text, px_line))[0])
    except Exception:
        pad = pad_fraction * x_range
        x_text = x0 + pad if ha == "left" else x0 - pad

    if avoid:
        size = _measure_text_extent_data(ax, text_str, fontsize)
        if size is not None:
            width, height = size
            step = height * 1.4 if height > 0 else 0.06 * y_range

            def _bbox_at(y_center):
                if ha == "right":
                    bx0, bx1 = x_text - width, x_text
                else:
                    bx0, bx1 = x_text, x_text + width
                return (bx0, bx1, y_center - height / 2.0, y_center + height / 2.0)

            candidate = y_text
            direction = -1.0
            magnitude = 1
            attempts = 0
            while (
                any(_rects_overlap(_bbox_at(candidate), box) for box in avoid)
                and attempts < 8
            ):
                candidate = float(
                    np.clip(y_text + direction * magnitude * step, inner_min + margin, inner_max - margin)
                )
                direction *= -1.0
                if attempts % 2 == 1:
                    magnitude += 1
                attempts += 1
            y_text = candidate

    text_obj = ax.text(
        x_text,
        y_text,
        text_str,
        fontsize=fontsize,
        ha=ha,
        va="center",
        zorder=100,
        bbox={"facecolor": _style.role("paper"), "alpha": 0.8, "edgecolor": "none"},
    )

    return text_obj


def place_horizontal_label(ax, y_value, label_text, fontsize=None, pad_fraction=0.02, avoid=None):
    """Place a label next to a horizontal line at `y_value` in the least-populated horizontal gap.

    Similar strategy to `place_vertical_label` but mirrored for x positions.

    Args:
        avoid: optional list of (x0, x1, y0, y1) data-space boxes (e.g. other
            labels placed earlier in the same batch) the new label should not
            overlap; it is nudged left/right until clear of all of them.
    """
    if label_text is None or not str(label_text).strip():
        return None

    text_str = str(label_text).strip()

    try:
        y0 = float(y_value)
    except Exception:
        return add_note_to_axes(ax, text_str, fontsize=fontsize)

    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    y_range = ylim[1] - ylim[0] if ylim[1] != ylim[0] else 1.0

    x_occupied = []

    # Lines
    for line in ax.get_lines():
        try:
            xd = np.asarray(line.get_xdata())
            yd = np.asarray(line.get_ydata())
            if yd.size == 0:
                continue
            ymin, ymax = yd.min(), yd.max()
            if ymin <= y0 <= ymax:
                x_at = np.interp(y0, yd, xd)
                if np.isfinite(x_at):
                    x_occupied.append(float(x_at))
        except Exception:
            continue

    # Scatter collections
    for col in getattr(ax, "collections", []):
        try:
            offsets = col.get_offsets()
            if offsets is None or len(offsets) == 0:
                continue
            xs = np.asarray(offsets)[:, 0]
            ys = np.asarray(offsets)[:, 1]
            y_tol = y_range * 0.02
            mask = np.isfinite(ys) & (np.abs(ys - y0) <= y_tol)
            x_occupied.extend(list(xs[mask]))
        except Exception:
            continue

    # Patches: rectangles that cross y0
    for patch in getattr(ax, "patches", []):
        try:
            bbox = patch.get_bbox()
            if bbox.y0 <= y0 <= bbox.y1:
                x_occupied.append((bbox.x0 + bbox.x1) / 2.0)
        except Exception:
            continue

    clean_points = [float(x) for x in x_occupied if np.isfinite(x) and xlim[0] <= x <= xlim[1]]
    candidates = [xlim[0]] + sorted(clean_points) + [xlim[1]]

    y_tol = max(y_range * 0.03, 1e-8)
    x_range_full = xlim[1] - xlim[0]
    text_width_est = max(0.12 * x_range_full, 0.0)

    best_candidate = None
    best_score = None
    for i in range(len(candidates) - 1):
        x0_gap = candidates[i]
        x1_gap = candidates[i + 1]
        gap_size = x1_gap - x0_gap
        if gap_size <= 0:
            continue
        x_center = (x0_gap + x1_gap) / 2.0
        x_span = min(gap_size * 0.9, text_width_est if text_width_est > 0 else gap_size)
        xmin = x_center - x_span / 2.0
        xmax = x_center + x_span / 2.0

        count = 0

        # Count line points in neighborhood
        for line in ax.get_lines():
            try:
                xd = np.asarray(line.get_xdata())
                yd = np.asarray(line.get_ydata())
                if yd.size == 0:
                    continue
                mask = np.isfinite(xd) & np.isfinite(yd) & (yd >= y0 - y_tol) & (yd <= y0 + y_tol) & (xd >= xmin) & (xd <= xmax)
                count += int(np.count_nonzero(mask))
            except Exception:
                continue

        for col in getattr(ax, "collections", []):
            try:
                offsets = col.get_offsets()
                if offsets is None or len(offsets) == 0:
                    continue
                xs = np.asarray(offsets)[:, 0]
                ys = np.asarray(offsets)[:, 1]
                mask = np.isfinite(xs) & np.isfinite(ys) & (ys >= y0 - y_tol) & (ys <= y0 + y_tol) & (xs >= xmin) & (xs <= xmax)
                count += int(np.count_nonzero(mask))
            except Exception:
                continue

        for patch in getattr(ax, "patches", []):
            try:
                bbox = patch.get_bbox()
                if (bbox.y1 >= y0 - y_tol) and (bbox.y0 <= y0 + y_tol) and (bbox.x1 >= xmin) and (bbox.x0 <= xmax):
                    count += 1
            except Exception:
                continue

        score = (count, -gap_size)
        if best_score is None or score < best_score:
            best_score = score
            best_candidate = (x_center, gap_size)

    if best_candidate is None:
        x_text = (xlim[0] + xlim[1]) / 2.0
    else:
        x_text = best_candidate[0]

    # Clamp x_text to stay between the outermost visible tick marks, with an
    # extra margin for the text box width so it does not overlap the frame.
    margin = text_width_est / 2.0 if text_width_est > 0 else 0.03 * x_range_full
    xticks = np.asarray(ax.get_xticks())
    xticks_visible = xticks[(xticks >= xlim[0]) & (xticks <= xlim[1])]
    inner_min = float(xticks_visible.min()) if len(xticks_visible) > 0 else xlim[0]
    inner_max = float(xticks_visible.max()) if len(xticks_visible) > 0 else xlim[1]
    x_text = float(np.clip(x_text, inner_min + margin, inner_max - margin))

    y_mid = (ylim[0] + ylim[1]) / 2.0
    pad = pad_fraction * y_range
    if y0 > y_mid:
        va = "top"
        y_pos = y0 - pad
    else:
        va = "bottom"
        y_pos = y0 + pad

    if avoid:
        size = _measure_text_extent_data(ax, text_str, fontsize)
        if size is not None:
            width, height = size
            step = width * 1.2 if width > 0 else 0.1 * x_range_full

            def _bbox_at(x_center):
                if va == "top":
                    by0, by1 = y_pos - height, y_pos
                else:
                    by0, by1 = y_pos, y_pos + height
                return (x_center - width / 2.0, x_center + width / 2.0, by0, by1)

            candidate = x_text
            direction = -1.0
            magnitude = 1
            attempts = 0
            while (
                any(_rects_overlap(_bbox_at(candidate), box) for box in avoid)
                and attempts < 8
            ):
                candidate = float(
                    np.clip(x_text + direction * magnitude * step, inner_min + margin, inner_max - margin)
                )
                direction *= -1.0
                if attempts % 2 == 1:
                    magnitude += 1
                attempts += 1
            x_text = candidate

    text_obj = ax.text(
        x_text,
        y_pos,
        text_str,
        fontsize=fontsize,
        ha="center",
        va=va,
        zorder=100,
        bbox={"facecolor": _style.role("paper"), "alpha": 0.8, "edgecolor": "none"},
    )

    return text_obj


def place_point_label(ax, point_x, point_y, label_text, fontsize=None):
    """Place a label next to a scattered point.

    Args:
        ax: matplotlib axes object
        point_x: x coordinate of the point
        point_y: y coordinate of the point
        label_text: text to display
        fontsize: optional font size

    Returns:
        matplotlib text object
    """
    if label_text is None or not str(label_text).strip():
        return None

    text_str = str(label_text).strip()

    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    x_range = xlim[1] - xlim[0]
    y_range = ylim[1] - ylim[0]
    x_offset = x_range * 0.02
    y_offset = y_range * 0.03

    text_obj = ax.text(
        point_x + x_offset,
        point_y + y_offset,
        text_str,
        fontsize=fontsize,
        ha="left",
        va="bottom",
        zorder=100,
        bbox={"facecolor": _style.role("paper"), "alpha": 0.8, "edgecolor": "none"},
    )

    return text_obj

