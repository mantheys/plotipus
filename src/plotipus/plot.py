import math
import re
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.legend_handler import HandlerPatch
from matplotlib.patches import Rectangle, StepPatch
from matplotlib.transforms import Bbox
from matplotlib.legend import Legend
from typing import Any

from . import style as _style

def panel_font_scale(ncols=1):
    """Text scale of a figure with ``ncols`` panel columns (plot_settings.figure_layout.panel_font_scale)."""
    return _style.figure_panel_font_scale.get(max(1, int(ncols)), 1.0)


def apply_panel_font_scale(ncols=1):
    """Set the base font size for the next figure; every relative font size
    (x-large, xx-large, ...) and the tick labels follow it. Only in the old
    geometry (no --width) or with fixed_margins: text is otherwise drawn at
    its printed size, never scaled to fit more panels."""
    scale = panel_font_scale(ncols) if _style.figure_width is None or _style.figure_fixed_margins else 1.0
    plt.rcParams["font.size"] = _style.base_font_size * scale


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


# Height of a lower panel relative to its upper panel when drawing at a width.
LOWER_PANEL_FRACTION = 0.3


def lower_height_ratios(n_lower):
    """Height ratios of an upper panel and ``n_lower`` lower panels."""
    if _style.figure_width is None:
        return [3] + [1] * n_lower
    return [1] + [LOWER_PANEL_FRACTION] * n_lower


def get_common_figsize(ncols=1, nrows=1, height_ratios=None):
    """Figure size (inches). At a --width (or the medium's), each row is one
    plot's height; facets side by side widen the figure, each adding the
    style's ``facet_width`` share of one plot's width (``--layout panels``
    keeps one plot's width instead). ``height_ratios`` (upper panel first)
    add the lower panels' height, or share it (``lower_panels: share``).
    Without a width, the old geometry: base width plus a panel width per
    extra column. With --single_panel_size every figure has the size of one
    panel."""
    if _style.figure_single_panel:
        ncols, nrows, height_ratios = 1, 1, None
    rows = max(1, int(nrows))
    if _style.figure_width is not None:
        width = float(_style.figure_width)
        if ncols > 1 and _style.figure_layout_mode == "facets":
            width = max(width, width * _style.figure_facet_width * ncols)
        height = _style.figure_row_height * rows
        if height_ratios and _style.figure_lower_panels != "share":
            height *= sum(height_ratios) / height_ratios[0]
        return (width, float(height))
    panel_count = max(1, int(ncols))
    width = _style.figure_base_width + _style.figure_panel_width * (panel_count - 1)
    height = _style.figure_height * rows
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

    # A figure smaller than its margins (a small --width/--aspect) keeps a
    # quarter of each dimension for the panels; the measured layout refines it.
    for low, high in (("left", "right"), ("bottom", "top")):
        if low in margins_normalized and high in margins_normalized:
            taken = margins_normalized[low] + 1 - margins_normalized[high]
            if taken > 0.75:
                scale = 0.75 / taken
                margins_normalized[low] *= scale
                margins_normalized[high] = 1 - (1 - margins_normalized[high]) * scale

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


def create_common_two_panel_figure(ncols=1, height_ratios=None, hspace=None) -> tuple[Any, Any]:
    apply_panel_font_scale(ncols)
    height_ratios = list(height_ratios or lower_height_ratios(1))
    fig = plt.figure(figsize=get_common_figsize(ncols=ncols, height_ratios=height_ratios))
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
    for ax in fig.axes:
        for legend in _axes_legends(ax):
            owner = getattr(legend, "_plotipus_owner", None)
            if owner is not None and legend.get_visible():
                extra.setdefault(owner, []).append(legend.get_window_extent(renderer))
    for cax in fig.axes:
        parents = getattr(cax, "_plotipus_colorbar_of", None)
        if parents and cax.get_visible():
            owner = max(parents, key=lambda a: a.get_position(original=True).x1)
            extra.setdefault(owner, []).append(cax.get_tightbbox(renderer, for_layout_only=True))
    overhangs = {}
    for ax, _, _ in panels:
        # A legend above the axes takes room above them only: wider than its panel, it may reach over the gap
        # (counting its width would widen the gaps and shrink every panel to a sliver).
        above = [lg for lg in _axes_legends(ax) if lg.get_visible() and lg.get_in_layout()
                 and getattr(lg, "_plotipus_placement", {}).get("above")]
        # So does the centred panel title.
        above += [t for t in (ax.title,) if t.get_visible() and t.get_text() and t.get_in_layout()]
        for lg in above:
            lg.set_in_layout(False)
        try:
            tight = ax.get_tightbbox(renderer, for_layout_only=True)
        finally:
            for lg in above:
                lg.set_in_layout(True)
        boxes = [tight, *extra.get(ax, [])]
        for lg in above:
            box = lg.get_window_extent(renderer)
            boxes.append(Bbox([[ax.bbox.x0, box.y0], [ax.bbox.x1, box.y1]]))
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


def _visible_length(text):
    """Rough printed length of ``text``: math (``$...$``) counts a third of
    its source, which is mostly markup."""
    parts = text.split("$")
    return sum(len(part) / 3 if i % 2 else len(part) for i, part in enumerate(parts))


def _break_label(text):
    """``text`` on two lines, broken at the space (outside ``$...$`` math)
    that makes the longer line shortest; None when there is no such space.
    A lone operator ("Events - Bkg") stays at the end of the first line."""
    spaces, math = [], False
    for i, char in enumerate(text):
        if char == "$":
            math = not math
        elif char == " " and not math:
            following = text[i + 1:].split(" ")[0]
            if not (len(following) == 1 and not following.isalnum()):
                spaces.append(i)
    if not spaces or "\n" in text:
        return None
    cut = min(spaces, key=lambda i: max(_visible_length(text[:i]), _visible_length(text[i + 1:])))
    return text[:cut] + "\n" + text[cut + 1:]


def _wrap_long_labels(panels, renderer):
    """Break an axis label or panel title longer than its axes onto two
    lines (once). Returns whether any label changed."""
    changed = False
    for ax, _, _ in panels:
        for label, length in ((ax.yaxis.label, ax.bbox.height), (ax.xaxis.label, ax.bbox.width), (ax.title, ax.bbox.width)):
            text = label.get_text()
            if not text or not label.get_visible():
                continue
            box = label.get_window_extent(renderer)
            extent = box.height if label is ax.yaxis.label else box.width
            if extent > length:
                broken = _break_label(text)
                if broken is not None:
                    label.set_text(broken)
                    changed = True
    return changed


def _measured_layout(fig, iterations):
    found = _layout_panels(fig)
    gridspec, panels = found
    nrows, ncols = gridspec.get_geometry()
    pad = _style.figure_pad_inches
    minimum = _minimum_margins(fig)
    width, height = fig.get_size_inches()
    params = fig.subplotpars
    # The configured spacing is the minimum of every pass: the current one may come from an earlier pass
    # (a legend not yet placed spilling out of its panel) and would only ever grow.
    if not hasattr(gridspec, "_plotipus_spacing"):
        gridspec._plotipus_spacing = (gridspec.wspace if gridspec.wspace is not None else params.wspace,
                                      gridspec.hspace if gridspec.hspace is not None else params.hspace,
                                      gridspec.hspace is not None)
    min_wspace, min_hspace, fixed_hspace = gridspec._plotipus_spacing
    # Upper/lower stacks keep their configured gap; grids of panels are measured.
    fig.align_ylabels([ax for ax, _, _ in panels])

    for _ in range(iterations):
        fig.draw_without_rendering()
        renderer = fig.canvas.get_renderer()
        if _wrap_long_labels(panels, renderer):
            fig.draw_without_rendering()
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
from matplotlib.ticker import Formatter, LogFormatter, LogFormatterMathtext, LogFormatterSciNotation, ScalarFormatter


def apply_tick_formatter(ax, axis="both"):
    """Plain tick numbers with a common power of ten (``ScalarFormatter`` with
    mathtext, limits from the style's ``axes.formatter.limits``) on the linear
    axes of ``ax``; log axes are labelled when saved (:func:`apply_log_labels`). With
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


LOG_LABEL_MODES = ("auto", "sci", "plain")
# auto writes plain numbers when every labelled tick lies in this range.
PLAIN_LOG_RANGE = (1e-3, 1e4)


def _plain_number(x):
    """A log tick value k x 10^n as a decimal number: 200, 0.01, 0.002."""
    digits = max(0, -math.floor(math.log10(x) + 1e-9))
    return rf"$\mathdefault{{{x:.{digits}f}}}$"


class LogTickFormatter(LogFormatterSciNotation):
    """Log-axis tick labels in ``mode``: "sci" (10^n), "plain" (200, 0.01) or
    "auto" (plain when every labelled tick lies in :data:`PLAIN_LOG_RANGE`).
    Which ticks get a label is matplotlib's choice (decades; minor ticks too
    on short ranges). A minor tick is never written as 2x10^2: in sci it is
    unlabelled when two decades are labelled, else written plain."""

    def __init__(self, mode="auto", minor=False):
        super().__init__(labelOnlyBase=False)
        self.mode, self.minor = mode, minor
        self._resolved = None

    def _in_view(self, locs):
        low, high = sorted(self.axis.get_view_interval())
        return [v for v in locs if low * (1 - 1e-9) <= v <= high * (1 + 1e-9) and v > 0]

    def _majors(self):
        return self._in_view(self.axis.get_majorticklocs())

    def resolved_mode(self):
        if self.mode != "auto":
            return self.mode
        majors = self._majors()
        values = majors if len(majors) >= 2 else [*majors, *self._in_view(self.axis.get_minorticklocs())]
        low, high = PLAIN_LOG_RANGE
        plain = all(low * (1 - 1e-9) <= v <= high * (1 + 1e-9) for v in values)
        return "plain" if plain else "sci"

    def set_locs(self, locs=None):
        super().set_locs(locs)
        self._resolved = self.resolved_mode()

    def __call__(self, x, pos=None):
        label = super().__call__(x, pos)
        if not label or x <= 0:
            return label
        mode = self._resolved or self.resolved_mode()
        if mode == "plain":
            return _plain_number(x)
        if math.isclose(math.log10(x), round(math.log10(x)), abs_tol=1e-9):
            return label
        if self.minor and len(self._majors()) >= 2:
            return ""
        return _plain_number(x)


def log_label_modes(value=None):
    """{"x", "y", "z"} -> mode from ``--log_labels`` values ("plain",
    "x=plain", "z=sci"), else the style's ``plot_settings.log_labels`` (a
    mode, or {"x": ..., "y": ..., "z": ...}). "z" is a colorbar's axis."""
    if value is None:
        value = _style.log_labels
    if isinstance(value, dict):
        items = [f"{key}={mode}" for key, mode in value.items()]
    else:
        items = [value] if isinstance(value, str) else list(value)
    modes = dict.fromkeys("xyz", "auto")
    for item in items:
        keys, _, mode = item.rpartition("=")
        for key in keys or "xyz":
            modes[key] = mode
    return modes


def _default_log_formatter(formatter):
    return type(formatter) in (LogFormatter, LogFormatterMathtext, LogFormatterSciNotation, LogTickFormatter)


def apply_log_labels(fig, log_labels=None):
    """Put :class:`LogTickFormatter` on every base-10 log axis of ``fig``
    (colorbars included) that has matplotlib's default log labels; modes
    from :func:`log_label_modes`."""
    modes = log_label_modes(log_labels)
    for ax in fig.axes:
        colorbar = getattr(ax, "_colorbar", None)
        long_axis = None if colorbar is None else ax.yaxis if colorbar.orientation == "vertical" else ax.xaxis
        for name, axis in (("x", ax.xaxis), ("y", ax.yaxis)):
            major, minor = axis.get_major_formatter(), axis.get_minor_formatter()
            if axis.get_scale() != "log" or not _default_log_formatter(major) or getattr(major, "_base", 10) != 10:
                continue
            key = "z" if axis is long_axis else name
            new_major = LogTickFormatter(modes[key])
            new_minor = LogTickFormatter(modes[key], minor=True) if _default_log_formatter(minor) else minor
            if axis is long_axis:
                colorbar.formatter, colorbar.minorformatter = new_major, new_minor
            else:
                axis.set_major_formatter(new_major)
                axis.set_minor_formatter(new_minor)


def finish_tick_labels(fig, sci_in_label=None, log_labels=None):
    """Write every common power of ten as "$\\times10^{n}$" (mathtext) and,
    with ``sci_in_label`` (default: the style's ``plot_settings.sci_in_label``),
    move the offset text of each labelled axis into its label ("Density
    ($\\times10^{-2}$)", "Rate ($\\times10^{-5}$ Hz)") before saving. Log
    axes get labels in the ``log_labels`` modes (:func:`apply_log_labels`)."""
    apply_log_labels(fig, log_labels)
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


# --legend_inside: automatic legends never leave the axes.
_LEGEND_INSIDE = {"on": False}


def keep_legends_inside(on=True):
    """Keep every automatic legend inside its axes, over the data if it
    must (--legend_inside); an explicit --legend_loc above/below/right
    still places it outside."""
    _LEGEND_INSIDE["on"] = bool(on)


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
    # Step outlines drawn with stairs (series with empty bins) show the same
    # box as those drawn by hist, not a line.
    style.setdefault("handler_map", {StepPatch: HandlerPatch()})
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

    # "best" (the style default), "outside"/"above", "below" and "right" are
    # placed when the figure is saved (place_legends), on the finished axes;
    # "none" hides the legend.
    loc = style.get("loc", "best")
    mode = None
    if loc in (None, "best", "auto", *OUTSIDE_LOCATIONS, "none") and "bbox_to_anchor" not in style:
        mode = {"none": "none", **OUTSIDE_LOCATIONS}.get(loc, "auto")
        style["loc"] = "upper right"
    if handles is not None or labels is not None:
        legend = ax.legend(handles=handles, labels=labels, **style)
    else:
        legend = ax.legend(**style)
    if mode == "none":
        legend.set_visible(False)
    elif mode is not None:
        _defer_placement(legend, mode, handles, labels, style)
    return legend


LEGEND_PLACEMENT_CANDIDATES = (
    "upper left",
    "upper right",
    "center left",
    "center right",
    "lower left",
    "lower right",
)
# --legend_loc values placed outside the axes -> placement mode.
OUTSIDE_LOCATIONS = {"outside": "outside", "above": "outside", "below": "below", "right": "right"}
_PLACED_LATER = ("auto", "free", "outside", "below", "right")
# A placement is free when data covers less than this fraction of its box.
LEGEND_FREE_FRACTION = 0.002
# Legends with more entries go above the axes.
LEGEND_MAX_INSIDE_ENTRIES = 6
_LEGEND_PAD_PX = 4.0
_legend_counter = iter(range(1 << 62))


def _defer_placement(legend, mode, handles, labels, style):
    """Mark ``legend`` for :func:`place_legends`; keep what rebuilding it
    (with more columns, above the axes) needs."""
    legend._plotipus_placement = {"mode": mode, "order": next(_legend_counter), "handles": handles,
                                  "labels": labels, "style": dict(style)}


def apply_legend_style_clear_of_data(ax, avoid_boxes=(), candidate_locs=None, pad_px=None,
                                     max_height_fraction=None, **legend_kwargs):
    """A legend placed where it covers the least data (corners first, then
    any free position; see :func:`place_legends`). Legends already on the
    axes are avoided, so ``avoid_boxes`` is no longer needed."""
    legend_kwargs.setdefault("loc", "best")
    return apply_legend_style(ax, **legend_kwargs)


def apply_legend_style_free(ax, **legend_kwargs):
    """Like :func:`apply_legend_style_clear_of_data`, but every free position
    is as good as a corner (--legend_free)."""
    legend = apply_legend_style_clear_of_data(ax, **legend_kwargs)
    if hasattr(legend, "_plotipus_placement"):
        legend._plotipus_placement["mode"] = "free"
    return legend


def apply_legend_pair_clear_of_data(ax, primary_kwargs, secondary_kwargs, candidate_locs=None, pad_px=None,
                                    max_height_fraction=None, primary_loc=None, secondary_loc=None):
    """Two legends on one axes (colour and line style), each where it covers
    the least data and away from the other. Both are returned; the primary
    is kept alive with ``ax.add_artist``."""
    primary = apply_legend_style(ax, **({"loc": primary_loc} if primary_loc else {}), **primary_kwargs)
    ax.add_artist(primary)
    secondary = apply_legend_style(ax, **({"loc": secondary_loc} if secondary_loc else {}), **secondary_kwargs)
    return primary, secondary


def _axes_legends(ax):
    found = [a for a in ax.artists if isinstance(a, Legend)]
    if ax.legend_ is not None and ax.legend_ not in found:
        found.append(ax.legend_)
    return found


def axes_occupancy(ax, renderer=None, extra_boxes=(), exclude=()):
    """Occupancy of ``ax``: a boolean mask over its pixels (row 0 at the
    bottom), True where a data artist (line, patch, collection, image, text)
    draws anything. Filled bars, bands and filled contours count whole.
    ``extra_boxes`` (display boxes, e.g. legends already placed) are marked
    occupied too."""
    from matplotlib.backends.backend_agg import RendererAgg

    fig = ax.figure
    width, height = int(np.ceil(fig.bbox.width)), int(np.ceil(fig.bbox.height))
    agg = RendererAgg(width, height, fig.dpi)
    artists = [*ax.lines, *ax.patches, *ax.collections, *ax.images, *ax.texts,
               *(a for a in ax.artists if not isinstance(a, Legend))]
    for artist in sorted(artists, key=lambda a: a.get_zorder()):
        if artist.get_visible() and not any(artist is skip for skip in exclude):
            artist.draw(agg)
    alpha = np.asarray(agg.buffer_rgba())[::-1, :, 3] > 0  # flip: row 0 at the bottom
    box = ax.bbox
    x0, x1 = max(0, int(np.floor(box.x0))), min(width, int(np.ceil(box.x1)))
    y0, y1 = max(0, int(np.floor(box.y0))), min(height, int(np.ceil(box.y1)))
    mask = alpha[y0:y1, x0:x1].copy()
    for extra in extra_boxes:
        ex0, ex1 = int(extra.x0) - x0, int(np.ceil(extra.x1)) - x0
        ey0, ey1 = int(extra.y0) - y0, int(np.ceil(extra.y1)) - y0
        mask[max(0, ey0):max(0, ey1), max(0, ex0):max(0, ex1)] = True
    return mask, (x0, y0)


class _HideTickValue(Formatter):
    """A y formatter that leaves the label at one tick ``value`` empty and
    otherwise formats like ``inner`` (offsets and all)."""

    def __init__(self, inner, value):
        self.inner, self.value = inner, value

    def _hidden(self, x):
        return math.isclose(x, self.value, rel_tol=1e-9, abs_tol=1e-12)

    def __call__(self, x, pos=None):
        return "" if self._hidden(x) else self.inner(x, pos)

    def format_ticks(self, values):
        labels = self.inner.format_ticks(values)
        return ["" if self._hidden(v) else label for v, label in zip(values, labels)]

    def set_axis(self, axis):
        super().set_axis(axis)
        self.inner.set_axis(axis)

    def set_locs(self, locs):
        self.inner.set_locs(locs)

    def get_offset(self):
        return self.inner.get_offset()


def _edge_tick(ax, renderer, lowest):
    """(value, label box) of the lowest (or highest) labelled y tick drawn
    next to ``ax`` (centred within half a label of its range), or None."""
    found = []
    for tick in ax.yaxis.get_major_ticks():
        label = tick.label1
        if not (label.get_visible() and label.get_text() and tick.get_visible()):
            continue
        box = label.get_window_extent(renderer)
        if ax.bbox.y0 - box.height / 2 <= (box.y0 + box.y1) / 2 <= ax.bbox.y1 + box.height / 2:
            found.append((tick.get_loc(), box))
    if not found:
        return None
    return min(found, key=lambda f: f[1].y0) if lowest else max(found, key=lambda f: f[1].y1)


def separate_panel_tick_labels(fig, pad_px=1.0):
    """Where an upper panel sits on a lower one, the upper panel's lowest y
    tick label and the lower panel's highest can overlap ("0" over "2"):
    the upper one is left empty (the lower panel keeps its scale)."""
    panels = [ax for ax in fig.axes if ax.get_visible() and not hasattr(ax, "_colorbar") and ax.get_subplotspec()]
    if len(panels) < 2:
        return
    fig.draw_without_rendering()
    renderer = fig.canvas.get_renderer()
    for upper in panels:
        top = upper.get_position()
        for lower in panels:
            bottom = lower.get_position()
            touching = (lower is not upper and abs(top.x0 - bottom.x0) < 1e-3 and abs(top.x1 - bottom.x1) < 1e-3
                        and 0 <= top.y0 - bottom.y1 < 0.02)
            if not touching:
                continue
            low, high = _edge_tick(upper, renderer, lowest=True), _edge_tick(lower, renderer, lowest=False)
            if low is not None and high is not None and low[1].y0 < high[1].y1 + pad_px:
                upper.yaxis.set_major_formatter(_HideTickValue(upper.yaxis.get_major_formatter(), low[0]))


def settle_text_backgrounds(fig):
    """Keep the translucent background of notes and reference-line labels
    only where they sit on data; on empty space they are bare text. Run on
    the finished layout (the data under a text depends on the limits)."""
    renderer = None
    for ax in fig.axes:
        texts = [t for t in ax.texts if getattr(t, "_plotipus_background_over_data", False)
                 and t.get_visible() and t.get_bbox_patch() is not None]
        if not texts:
            continue
        renderer = renderer or fig.canvas.get_renderer()
        occupancy = _Occupancy(*axes_occupancy(ax, renderer, exclude=texts))
        for text in texts:
            if occupancy.fraction(text.get_window_extent(renderer), pad=0) <= LEGEND_FREE_FRACTION:
                text.set_bbox(None)


class _Occupancy:
    """Fraction of occupied pixels in any display box (summed-area table)."""

    def __init__(self, mask, origin):
        self.origin = origin
        self.shape = mask.shape
        self.table = np.pad(mask.astype(np.int32).cumsum(0).cumsum(1), ((1, 0), (1, 0)))

    def fraction(self, box, pad=_LEGEND_PAD_PX):
        x0, y0 = self.origin
        h, w = self.shape
        c0, c1 = int(np.clip(box.x0 - pad - x0, 0, w)), int(np.clip(box.x1 + pad - x0, 0, w))
        r0, r1 = int(np.clip(box.y0 - pad - y0, 0, h)), int(np.clip(box.y1 + pad - y0, 0, h))
        area = (c1 - c0) * (r1 - r0)
        if area <= 0:
            return 1.0
        t = self.table
        return float(t[r1, c1] - t[r0, c1] - t[r1, c0] + t[r0, c0]) / area


def _corner_box(ax, loc, width, height, pad):
    """Display box of a legend of the given size at a corner ``loc``."""
    box = ax.bbox
    x0 = box.x0 + pad if "left" in loc else box.x1 - pad - width
    if loc.startswith("upper"):
        y0 = box.y1 - pad - height
    elif loc.startswith("lower"):
        y0 = box.y0 + pad
    else:
        y0 = (box.y0 + box.y1 - height) / 2
    return Bbox.from_bounds(x0, y0, width, height)


def _free_boxes(ax, width, height, pad, grid=9):
    box = ax.bbox
    for fx in np.linspace(0, 1, grid):
        for fy in np.linspace(0, 1, grid):
            x0 = box.x0 + pad + fx * (box.width - width - 2 * pad)
            y0 = box.y0 + pad + fy * (box.height - height - 2 * pad)
            yield Bbox.from_bounds(x0, y0, width, height)


def _best_inside(ax, legend, occupancy, renderer):
    """(fraction, setter) of the best inside position of ``legend``."""
    size = legend.get_window_extent(renderer)
    pad = legend.borderaxespad * legend._fontsize * ax.figure.dpi / 72.0
    if size.width + 2 * pad > ax.bbox.width or size.height + 2 * pad > ax.bbox.height:
        return 1.0, None
    mode = legend._plotipus_placement["mode"]
    corners = [(occupancy.fraction(_corner_box(ax, loc, size.width, size.height, pad)), loc)
               for loc in LEGEND_PLACEMENT_CANDIDATES]
    best_corner = min(corners, key=lambda item: item[0])
    if mode != "free" and best_corner[0] <= LEGEND_FREE_FRACTION:
        return best_corner[0], lambda: _set_corner(legend, best_corner[1])
    free = min(((occupancy.fraction(b), b) for b in _free_boxes(ax, size.width, size.height, pad)),
               key=lambda item: item[0])
    if best_corner[0] <= free[0]:
        return best_corner[0], lambda: _set_corner(legend, best_corner[1])
    return free[0], lambda: _set_anchor(legend, ax, free[1])


def _set_corner(legend, loc):
    legend.set_bbox_to_anchor(None)
    legend.set_loc(loc)


def _set_anchor(legend, ax, box):
    corner = ax.transAxes.inverted().transform((box.x0, box.y1))
    legend.borderaxespad = 0.0
    legend.set_loc("upper left")
    legend.set_bbox_to_anchor(tuple(corner), transform=ax.transAxes)


def _headroom(ax, legend, renderer):
    """Extend the top of the y range by the legend's height (log axes by
    whole decades); False when the range is fixed (--rangey, set limits)."""
    if not ax.get_autoscaley_on() or getattr(ax, "_plotipus_fixed_ylim", False):
        return False
    size = legend.get_window_extent(renderer)
    pad = legend.borderaxespad * legend._fontsize * ax.figure.dpi / 72.0
    fraction = (size.height + 2 * pad) / ax.bbox.height
    if fraction >= 0.6:
        return False
    bottom, top = ax.get_ylim()
    if ax.get_yscale() == "log":
        low, high = np.log10(bottom), np.log10(top)
        ax.set_ylim(bottom, 10 ** np.ceil(low + (high - low) / (1 - fraction)))
    else:
        ax.set_ylim(bottom, bottom + (top - bottom) / (1 - fraction))
    return True


def _has_panel_above(ax):
    """A lower panel: another visible axes sharing x sits right above it."""
    box = ax.get_position()
    return any(other is not ax and other.get_visible() and other.get_position().y0 >= box.y1 - 1e-6
               for other in ax.get_shared_x_axes().get_siblings(ax))


def _place_outside(ax, legend, renderer):
    """Above the axes (and its title), in as many columns as fit. The anchor
    is a fixed offset in points from the axes top, so it stays clear of the
    title when the layout resizes the axes."""
    from matplotlib.transforms import offset_copy

    info = legend._plotipus_placement
    style = dict(info["style"], loc="lower center")
    entries = max(1, len(legend.get_texts()))
    # Above the panel title and any legend already placed above the axes.
    above = [t.get_window_extent(renderer) for t in (ax.title, ax._left_title, ax._right_title)
             if t.get_visible() and t.get_text()]
    above += [lg.get_window_extent(renderer) for lg in _axes_legends(ax)
              if lg is not legend and getattr(lg, "_plotipus_placement", {}).get("outside")]
    # ... and above an experiment header drawn above the axes.
    above += [a.get_window_extent(renderer) for a in ax.artists
              if getattr(a, "_plotipus_header", None) == "above" and a.get_visible()]
    rise = max([0.0, *(b.y1 - ax.bbox.y1 for b in above)]) * 72.0 / ax.figure.dpi
    anchor = offset_copy(ax.transAxes, fig=ax.figure, y=rise, units="points")
    rebuilt = legend
    for ncol in range(entries, 0, -1):
        rebuilt = _rebuild_legend(ax, rebuilt, dict(style, ncol=ncol, bbox_to_anchor=(0.5, 1.0),
                                                    bbox_transform=anchor, borderaxespad=0.2))
        if rebuilt.get_window_extent(renderer).width <= ax.bbox.width or ncol == 1:
            break
    rebuilt._plotipus_placement["above"] = True
    return rebuilt


def stagger_above_legends(fig):
    """On the final layout, a legend above its panel that reaches over a
    neighbouring panel's legend (both wider than their panels) goes above
    it; the larger legend stays. Returns whether any moved."""
    from matplotlib.transforms import offset_copy

    above = [(ax, lg) for ax in fig.axes for lg in _axes_legends(ax)
             if lg.get_visible() and getattr(lg, "_plotipus_placement", {}).get("above")]
    if len(above) < 2:
        return False
    fig.draw_without_rendering()
    renderer = fig.canvas.get_renderer()
    above.sort(key=lambda item: -_area(item[1].get_window_extent(renderer)))
    settled, moved = [], False
    for ax, legend in above:
        box = legend.get_window_extent(renderer)
        clashing = [b for b in settled if b.x0 < box.x1 and box.x0 < b.x1 and b.y0 < box.y1 and box.y0 < b.y1]
        if clashing:
            rise = (max(b.y1 for b in clashing) - ax.bbox.y1) * 72.0 / fig.dpi + 2
            anchor = offset_copy(ax.transAxes, fig=fig, y=rise, units="points")
            info = legend._plotipus_placement
            legend = _rebuild_legend(ax, legend, dict(info["style"], loc="lower center", ncol=legend._ncols,
                                                      bbox_to_anchor=(0.5, 1.0), bbox_transform=anchor,
                                                      borderaxespad=0.2))
            legend._plotipus_placement["above"] = True
            box = legend.get_window_extent(renderer)
            moved = True
        settled.append(box)
    return moved


def _place_beside(ax, legend, renderer, side):
    """Below the axes (under the lowest panel sharing x and its tick and
    axis labels), in as many columns as fit the figure, or right of the axes, aligned
    with its top. Offsets are in points, so they hold when the layout
    resizes the axes; the layout makes room for the legend."""
    from matplotlib.transforms import offset_copy

    info = legend._plotipus_placement
    dpi = ax.figure.dpi
    legend.set_visible(False)  # not part of the boxes measured below
    if side == "right":
        tight = ax.get_tightbbox(renderer, for_layout_only=True)
        shift = (max(tight.x1, ax.bbox.x1) - ax.bbox.x1) * 72.0 / dpi + 4
        anchor = offset_copy(ax.transAxes, fig=ax.figure, x=shift, units="points")
        legend.set_visible(True)
        return _rebuild_legend(ax, legend, dict(info["style"], loc="upper left", bbox_to_anchor=(1.0, 1.0),
                                                bbox_transform=anchor, borderaxespad=0.0))
    stack = [a for a in ax.get_shared_x_axes().get_siblings(ax) if a.get_visible()]
    bottom = min(stack, key=lambda a: a.get_position().y0)
    tight = bottom.get_tightbbox(renderer, for_layout_only=True)
    drop = (bottom.bbox.y0 - min(tight.y0, bottom.bbox.y0)) * 72.0 / dpi + 4
    anchor = offset_copy(bottom.transAxes, fig=ax.figure, y=-drop, units="points")
    legend.set_visible(True)
    entries = max(1, len(legend.get_texts()))
    rebuilt = legend
    for ncol in range(entries, 0, -1):
        rebuilt = _rebuild_legend(ax, rebuilt, dict(info["style"], loc="upper center", ncol=ncol,
                                                    bbox_to_anchor=(0.5, 0.0), bbox_transform=anchor,
                                                    borderaxespad=0.0))
        # As wide as the figure allows: fewer rows leave the axes more height.
        if rebuilt.get_window_extent(renderer).width <= 0.96 * ax.figure.bbox.width or ncol == 1:
            break
    if bottom is not ax:
        # Under a lower panel: the layout counts it with that panel.
        rebuilt.set_in_layout(False)
        rebuilt._plotipus_owner = bottom
    return rebuilt


def _rebuild_legend(ax, legend, style):
    """Replace ``legend`` by a new one with ``style`` (same entries)."""
    info = legend._plotipus_placement
    kept = legend in ax.artists
    zorder = legend.get_zorder()
    legend.remove()
    if kept:
        new = Legend(ax, *_legend_entries(ax, info), **style)
        ax.add_artist(new)
    else:
        if info["handles"] is not None or info["labels"] is not None:
            new = ax.legend(handles=info["handles"], labels=info["labels"], **style)
        else:
            new = ax.legend(**style)
    new.set_zorder(zorder)
    new._plotipus_placement = dict(info, mode="placed", outside=True)
    legend._plotipus_rebuilt = new  # for legends that follow this one
    return new


def follow_legend(legend, leader):
    """Keep ``legend`` right under (or above) ``leader``, on the same side,
    once the figure is laid out (:func:`attach_legends`)."""
    legend._plotipus_follow = leader
    return legend


def attach_legends(fig):
    """Put every following legend next to its leader: under it when the
    leader is in an upper or centre position, above it when it is low."""
    renderer = fig.canvas.get_renderer()
    for ax in fig.axes:
        for legend in _axes_legends(ax):
            leader = getattr(legend, "_plotipus_follow", None)
            while getattr(leader, "_plotipus_rebuilt", None) is not None:
                leader = leader._plotipus_rebuilt
            if leader is None or not legend.get_visible():
                continue
            box = leader.get_window_extent(renderer)
            center = (box.x0 + box.x1) / 2 - ax.bbox.x0
            side = "left" if center < ax.bbox.width / 3 else "right" if center > 2 * ax.bbox.width / 3 else "center"
            low = (box.y0 + box.y1) / 2 < ax.bbox.y0 + ax.bbox.height / 3
            x = {"left": box.x0, "right": box.x1, "center": (box.x0 + box.x1) / 2}[side]
            y = box.y1 if low else box.y0
            point = ax.transAxes.inverted().transform((x, y))
            legend.borderaxespad = 0.0
            legend.set_loc(f"{'lower' if low else 'upper'} {side}")
            legend.set_bbox_to_anchor(tuple(point), transform=ax.transAxes)
            legend._plotipus_placement = {"mode": "placed", "order": -1}


def _legend_entries(ax, info):
    handles, labels = info["handles"], info["labels"]
    if handles is None and labels is None:
        return ax.get_legend_handles_labels()
    if handles is None:
        return ax.get_legend_handles_labels()[0], labels
    return handles, labels if labels is not None else [h.get_label() for h in handles]


def _right_edge_value(handle, ax):
    """y of a legend handle's series at its right-most x in view, or None."""
    from matplotlib.container import Container
    from matplotlib.patches import StepPatch

    if isinstance(handle, Container) and len(handle) and isinstance(handle[0], plt.Line2D):
        handle = handle[0]
    if isinstance(handle, plt.Line2D):
        try:
            x = np.asarray(handle.get_xdata(), dtype=float)
            y = np.asarray(handle.get_ydata(), dtype=float)
        except (TypeError, ValueError):
            return None
        low, high = sorted(ax.get_xlim())
        keep = np.isfinite(x) & np.isfinite(y) & (x >= low) & (x <= high)
        return float(y[keep][np.argmax(x[keep])]) if keep.any() else None
    if isinstance(handle, StepPatch):
        values = np.asarray(handle.get_data().values, dtype=float)
        finite = values[np.isfinite(values)]
        return float(finite[-1]) if finite.size else None
    return None


def order_legend_entries(ax, handles, labels, stacked=False, keep_first=(), keep_last=()):
    """Legend entries in the order of the data: a stack top first, lines by
    the height of their right-hand ends (highest first; entries without a
    value keep their place at the end). Labels in ``keep_first`` (e.g. data)
    stay in front, those in ``keep_last`` (e.g. an uncertainty band) at the
    end, in that order."""
    first = [i for i, label in enumerate(labels) if label in keep_first]
    last = [i for label in keep_last for i, other in enumerate(labels) if other == label and i not in first]
    rest = [i for i in range(len(labels)) if i not in first and i not in last]
    if stacked:
        rest = rest[::-1]
    else:
        values = {i: _right_edge_value(handles[i], ax) for i in rest}
        valued = sorted((i for i in rest if values[i] is not None), key=lambda i: -values[i])
        rest = valued + [i for i in rest if values[i] is None]
    order = first + rest + last
    return [handles[i] for i in order], [labels[i] for i in order]


def _area(box):
    return box.width * box.height


def place_legends(fig):
    """Place every automatic legend of ``fig`` on its finished axes: the
    emptiest corner, else the emptiest free position, else headroom above
    the data, else above the axes (also with more than
    LEGEND_MAX_INSIDE_ENTRIES entries or loc "outside"). Legends placed
    earlier on the same axes are avoided. Returns whether any moved."""
    pending = [(ax, legend) for ax in fig.axes for legend in _axes_legends(ax)
               if getattr(legend, "_plotipus_placement", {}).get("mode") in _PLACED_LATER
               and legend.get_visible()]
    if not pending:
        return False
    # A legend computes its own box from its location, so no full draw is
    # needed; but the view limits may still be stale (autoscaling happens
    # lazily, and fixed_margins skips the layout's draw). Larger legends
    # choose first.
    for ax in {id(ax): ax for ax, _ in pending}.values():
        ax.get_xlim(), ax.get_ylim()
    renderer = fig.canvas.get_renderer()
    pending.sort(key=lambda item: (-_area(item[1].get_window_extent(renderer)), item[1]._plotipus_placement["order"]))
    for ax, legend in pending:
        info = legend._plotipus_placement
        if info["mode"] in ("below", "right"):
            _place_beside(ax, legend, renderer, info["mode"])
            continue
        lower_panel = _has_panel_above(ax)
        inside = _LEGEND_INSIDE["on"] and info["mode"] != "outside"
        if not lower_panel and not inside and (
                info["mode"] == "outside" or len(legend.get_texts()) > LEGEND_MAX_INSIDE_ENTRIES):
            _place_outside(ax, legend, renderer)
            continue
        others = [lg.get_window_extent(renderer) for lg in _axes_legends(ax)
                  if lg is not legend and lg.get_visible()
                  and getattr(lg, "_plotipus_placement", {}).get("mode") not in _PLACED_LATER]
        occupancy = _Occupancy(*axes_occupancy(ax, renderer, others))
        fraction, setter = _best_inside(ax, legend, occupancy, renderer)
        if fraction > LEGEND_FREE_FRACTION and _headroom(ax, legend, renderer):
            occupancy = _Occupancy(*axes_occupancy(ax, renderer, others))
            fraction, setter = _best_inside(ax, legend, occupancy, renderer)
        if lower_panel and setter is not None:
            pass  # nothing above a lower panel but its upper panel: the emptiest place inside
        elif inside:
            # The emptiest place inside, over the data if need be; a legend
            # larger than the axes keeps the upper right corner.
            setter = setter or (lambda: _set_corner(legend, "upper right"))
        elif fraction > LEGEND_FREE_FRACTION or setter is None:
            _place_outside(ax, legend, renderer)
            continue
        setter()
        info["mode"] = "placed"
    return True


# Plot types whose y errors follow --errory_type (bar charts and scatter
# points keep their own error bars).
_ERROR_PLOT_TYPES = ("line", "step", "plot", "errorbar")


def errory_type(args, plot_type):
    """--errory_type, or its default for the plot type: bands for lines and
    steps, bars for points."""
    selected = getattr(args, "errory_type", None)
    if selected in ("bars", "bands"):
        return selected
    # None, or an interval (poisson, clopper_pearson): the errors are drawn the default way.
    return "bars" if plot_type in ("errorbar", "scatter") else "bands"


def _draw_band(ax, x, x_edges, y, errory, color, plot_type, drawstyle=None, alpha=None, **extra):
    """Shade y ± errory (1-D symmetric, or 2xN lower/upper) in the series
    colour: stepwise across the bins for steps. ``extra`` (label, zorder)
    goes to fill_between."""
    y = np.asarray(y, dtype=float)
    errory = np.asarray(errory, dtype=float)
    low, high = (y - errory, y + errory) if errory.ndim == 1 else (y - errory[0], y + errory[1])
    band = dict(color=color, alpha=_style.band_alpha if alpha is None else alpha, edgecolor="none", linewidth=0,
                **extra)
    if plot_type == "step" and x_edges is not None and len(x_edges) == len(y) + 1:
        ax.fill_between(np.asarray(x_edges, dtype=float), np.append(low, low[-1]), np.append(high, high[-1]),
                        step="post", **band)
    elif plot_type == "step":
        ax.fill_between(x, low, high, step="mid", **band)
    elif drawstyle in ("steps", "steps-pre", "steps-mid", "steps-post"):
        ax.fill_between(x, low, high, step=drawstyle.partition("-")[2] or "pre", **band)
    else:
        ax.fill_between(x, low, high, **band)


# Expected-limit band colours of ATLAS arXiv:1207.7214 Fig. 7(a): the vector
# fills of its ±1σ and ±2σ bands are pure green and yellow (ROOT kGreen and
# kYellow, read by examples/famous/extract/extract_atlas_p0_limit.py).
BRAZIL_COLORS = ("#00ff00", "#ffff00")
# Share of the base colour in each graded band, innermost first.
_GRADED_SHARES = (0.45, 0.2)


def band_colors(spec, base, n):
    """Colours of ``n`` nested bands, innermost first (--band_colors):
    ``graded`` mixes ``base`` into the paper colour in steps, ``brazil`` is
    green and yellow, anything else is a list of colours ("c1,c2" or
    separate words); short lists reuse their last colour."""
    spec = [part for item in (spec or ["graded"]) for part in str(item).split(",") if part]
    if spec == ["graded"]:
        shares = np.linspace(*_GRADED_SHARES, n) if n > 1 else _GRADED_SHARES[:1]
        return [_style._mix(base, _style.role("paper"), share) for share in shares]
    colors = list(BRAZIL_COLORS) if spec == ["brazil"] else [_style.resolve_mapped_color(c) for c in spec]
    return [colors[min(i, len(colors) - 1)] for i in range(n)]


def draw_nested_bands(ax, x, x_edges, y, errors, colors, labels, plot_type, drawstyle=None):
    """Shade one opaque band per entry of ``errors`` (innermost first), each
    in its colour and with its legend label (None: no entry). The
    innermost band is drawn on top (by z order, so that the legend lists it
    first), all of them under the lines."""
    n = len(errors)
    for i in range(n):
        label = labels[i] if labels is not None and i < len(labels) else None
        _draw_band(ax, x, x_edges, y, errors[i], colors[i], plot_type, drawstyle, alpha=1.0, label=label,
                   zorder=1.0 + 0.01 * (n - 1 - i))


def sigma_pvalue(n):
    """One-sided p-value of an n σ excess, 1 - Φ(n)."""
    from scipy.stats import norm

    return float(norm.sf(n))


def sigma_lines(sigmas):
    """(p-values, labels) of --sigma_lines: 1σ is at p = 0.1587."""
    return [sigma_pvalue(n) for n in sigmas], [f"{format_ref_value(n)}$\\sigma$" for n in sigmas]


def delta_chi2_lines(values=None, levels=None, dof=1):
    """(Δχ² values, labels) of --delta_chi2_lines (labelled nσ for whole
    √Δχ² with 1 dof, else Δχ² = v) and of --cl_lines (confidence levels in
    percent, at the χ² quantile for ``dof``, labelled "68% CL")."""
    out, labels = [], []
    if not values and not levels:
        return out, labels  # scipy.stats takes a second to import: only when needed
    from scipy.stats import chi2

    for value in values or []:
        root = math.sqrt(value) if value >= 0 else float("nan")
        out.append(float(value))
        if dof == 1 and root == round(root) and root > 0:
            labels.append(f"{int(root)}$\\sigma$")
        else:
            labels.append(f"$\\Delta\\chi^2$ = {format_ref_value(value)}")
    for level in levels or []:
        out.append(float(chi2.ppf(level / 100.0, dof)))
        labels.append(f"{format_ref_value(level)}% CL")
    return out, labels


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
        step_open = hist_kwargs.pop("step_open", False)
        if (
            (step_open or getattr(args, "step_open", False))
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
            # Edge, whiskers and caps in the series colour, the face at alpha
            # 0.6, the median in ink so it reads on the face, fliers as small
            # hollow markers; the legend shows one box.
            kwargs.setdefault("patch_artist", True)
            kwargs.setdefault("boxprops", {"facecolor": to_rgba(color, 0.6), "edgecolor": color, "linewidth": 1.5})
            kwargs.setdefault("medianprops", {"color": _style.role("ink"), "linewidth": 2})
            for key in ("whiskerprops", "capprops"):
                kwargs.setdefault(key, {"color": color, "linewidth": 1.5})
            kwargs.setdefault("flierprops", {"marker": "o", "markersize": 3, "markerfacecolor": "none",
                                             "markeredgecolor": color})
        return ax.boxplot(boxplot_data, label=label, **kwargs)

    if plot_type == "violin":
        # A violin per position: the density in the series colour (face at alpha
        # 0.6), the interquartile range as a thick ink bar and the median as a
        # paper dot on it; the legend shows the body.
        data = kwargs.pop("violin_data", y)
        positions = kwargs.pop("positions", x)
        parts = ax.violinplot(data, positions=positions, widths=kwargs.pop("widths", 0.8), showmeans=False,
                              showmedians=False, showextrema=False)
        for body in parts["bodies"]:
            body.set_facecolor(to_rgba(color, 0.6) if color is not None else None)
            body.set_edgecolor(color)
            body.set_linewidth(1.2)
            body.set_alpha(None)
        if parts["bodies"]:
            parts["bodies"][0].set_label(label)
        q1, median, q3 = (np.array([np.percentile(d, q) for d in data]) for q in (25, 50, 75))
        ax.vlines(positions, q1, q3, color=_style.role("ink"), linewidth=4, zorder=3)
        ax.scatter(positions, median, s=12, color=_style.role("paper"), edgecolors=_style.role("ink"),
                   linewidths=0.8, zorder=4)
        return parts

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
    # the note goes where it covers the least drawn data, clear of fixed
    # legends (automatic legends are placed later, around the note).
    positions = [(0.98, 0.98), (0.02, 0.98), (0.02, 0.02), (0.98, 0.02), (0.98, 0.5), (0.02, 0.5)]
    fig = ax.figure
    fig.draw_without_rendering()
    renderer = fig.canvas.get_renderer()
    legends = [lg.get_window_extent(renderer) for lg in _axes_legends(ax) if lg.get_visible()
               and getattr(lg, "_plotipus_placement", {}).get("mode") not in _PLACED_LATER]
    occupancy = _Occupancy(*axes_occupancy(ax, renderer, legends))

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
        score = occupancy.fraction(probe.get_window_extent(renderer))
        probe.remove()
        if best is None or score < best[0]:
            best = (score, x, y)
    text_obj = place(best[1], best[2])
    text_obj._plotipus_background_over_data = True
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
        _include_in_limits(ax, "x", v, v)
        ax.axvline(v, color=color, linestyle=style, linewidth=1, zorder=5)
        if label:
            text_obj = place_vertical_label(ax, v, label, fontsize=fontsize, avoid=avoid_boxes)
            if text_obj is not None:
                box = _label_avoid_box(text_obj, ax, fontsize)
                if box is not None:
                    avoid_boxes.append(box)


def draw_bands(ax, axis, values, labels=None, colors=None, fontsize=None, alpha=0.18):
    """Shade ``axis`` ("x" or "y") ranges, given as pairs ``[a1, b1, a2,
    b2, ...]``, behind the data (--vertical_band, --horizontal_band). Each
    label is written in its band like a line label, and ``colors`` default to
    the style's muted role; lists shorter than the bands reuse their last item."""
    if not values:
        return
    if len(values) % 2:
        from rich import print as rprint

        rprint(f"[yellow]Warning:[/yellow] --{'vertical' if axis == 'x' else 'horizontal'}_band takes pairs of "
               f"values; the last one ({values[-1]:g}) is ignored.")
    avoid = []
    for i in range(len(values) // 2):
        low, high = sorted(values[2 * i:2 * i + 2])
        color = _ref_line_get(colors, i, _style.role("muted"))
        span = ax.axvspan if axis == "x" else ax.axhspan
        span(low, high, facecolor=color, edgecolor="none", alpha=alpha, zorder=0.5)
        _include_in_limits(ax, axis, low, high)
        label = _ref_line_get(labels, i, None) if labels is not None else None
        if label:
            place = place_vertical_label if axis == "x" else place_horizontal_label
            kwargs = {} if axis == "x" else {"pos": "auto"}
            text_obj = place(ax, 0.5 * (low + high), label, fontsize=fontsize, avoid=avoid, **kwargs)
            if text_obj is not None:
                box = _label_avoid_box(text_obj, ax, fontsize)
                if box is not None:
                    avoid.append(box)


def draw_horizontal_lines(ax, values, labels=None, styles=None, colors=None, fontsize=None, label_pos="right"):
    """Draw one or more horizontal reference lines on *ax*.

    Each positional list (``labels``, ``styles``, ``colors``) is matched to
    ``values`` by index; if shorter than ``values`` the last element is reused
    as a default. ``label_pos`` is the side of the labels (right, left, or
    auto: wherever they cover the least data).

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
        _include_in_limits(ax, "y", v, v)
        ax.axhline(v, color=color, linestyle=style, linewidth=1, zorder=5)
        if label is not None and label:
            text_obj = place_horizontal_label(ax, v, label, fontsize=fontsize, avoid=avoid_boxes, pos=label_pos)
            if text_obj is not None:
                box = _label_avoid_box(text_obj, ax, fontsize)
                if box is not None:
                    avoid_boxes.append(box)


def _include_in_limits(ax, axis, low, high):
    """Widen the x or y limits of *ax* to [low, high], keeping their
    direction (a reversed range such as --rangey 17 10 stays reversed)."""
    get, set_ = (ax.get_xlim, ax.set_xlim) if axis == "x" else (ax.get_ylim, ax.set_ylim)
    first, last = get()
    lo, hi = min(first, last), max(first, last)
    if low < lo or high > hi:
        lo, hi = min(lo, low), max(hi, high)
        set_((lo, hi) if first <= last else (hi, lo))


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

        _include_in_limits(ax, "x", x0, x1e)
        _include_in_limits(ax, "y", y0, y1e)

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
            # On the visually upper edge (the smaller y on a reversed axis).
            bottom, top = ax.get_ylim()
            ax.text(
                (x0 + x1e) / 2,
                y1e if bottom <= top else y0,
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

        _include_in_limits(ax, "x", min(x1, x2), max(x1, x2))
        _include_in_limits(ax, "y", min(y1, y2), max(y1, y2))

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
    text_obj._plotipus_background_over_data = True
    return text_obj


def place_horizontal_label(ax, y_value, label_text, fontsize=None, pad_fraction=0.02, avoid=None, pos="auto"):
    """Place a label next to a horizontal line at `y_value`: just above the
    line (else below it), at its right end, its left end or along it,
    wherever it covers the least drawn data.

    Args:
        avoid: optional list of (x0, x1, y0, y1) data-space boxes (e.g. other
            labels placed earlier in the same batch) the new label should not
            overlap.
        pos: "right" or "left" keeps the label at that end of the line (above
            it, below only when above leaves the axes); "outside" writes it
            in the right margin, level with the line; "auto" tries every
            place.
    """
    if label_text is None or not str(label_text).strip():
        return None

    text_str = str(label_text).strip()

    try:
        y0 = float(y_value)
    except Exception:
        return add_note_to_axes(ax, text_str, fontsize=fontsize)

    fig = ax.figure
    fig.draw_without_rendering()
    renderer = fig.canvas.get_renderer()
    occupancy = _Occupancy(*axes_occupancy(ax, renderer))
    # x along the axes, y on the line (it follows later limit changes), a few points off it.
    offset = max(pad_fraction * ax.bbox.height * 72.0 / fig.dpi, 3.0)

    def place(x, ha, above):
        return ax.annotate(text_str, (x, y0), xycoords=ax.get_yaxis_transform(),
                           xytext=(0, offset if above else -offset), textcoords="offset points", fontsize=fontsize,
                           ha=ha, va="bottom" if above else "top", zorder=100,
                           bbox={"facecolor": _style.role("paper"), "alpha": 0.8, "edgecolor": "none"})

    if pos == "outside":
        text_obj = ax.annotate(text_str, (1.0, y0), xycoords=ax.get_yaxis_transform(), xytext=(offset, 0),
                               textcoords="offset points", fontsize=fontsize, ha="left", va="center",
                               annotation_clip=False, zorder=100)
        return text_obj

    # Right end first, then the left end, then along the line; above the line before below it.
    anchors = [(0.98, "right"), (0.02, "left"), (0.75, "center"), (0.25, "center"), (0.5, "center")]
    if pos in ("right", "left"):
        anchors = [anchors[0] if pos == "right" else anchors[1]]
    best = None
    for above in (True, False):
        for x, ha in anchors:
            probe = place(x, ha, above)
            box = probe.get_window_extent(renderer)
            clash = avoid and any(_rects_overlap(_display_to_data_box(ax, box), other) for other in avoid)
            inside = ax.bbox.y0 <= box.y0 and box.y1 <= ax.bbox.y1
            covered = occupancy.fraction(box, pad=0) if pos == "auto" else 0.0  # a fixed side stays above the line
            score = covered + (1.0 if clash else 0.0) + (0.0 if inside else 2.0)
            probe.remove()
            if best is None or score < best[0] - 1e-9:
                best = (score, x, ha, above)
    text_obj = place(*best[1:])
    text_obj._plotipus_background_over_data = True
    return text_obj


def _display_to_data_box(ax, box):
    """(x0, x1, y0, y1) in data coordinates of a display box."""
    (x0, y0), (x1, y1) = ax.transData.inverted().transform([(box.x0, box.y0), (box.x1, box.y1)])
    return (min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1))


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
    text_obj._plotipus_background_over_data = True
    return text_obj

