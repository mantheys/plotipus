"""Binned-estimator mode of the line kind (``--binned``).

Rows hold raw per-event arrays (``x`` and ``y`` of equal length). x is
binned (unit bins for integer x, else ``--bins`` equal bins; ``--threshold``
makes every bin cumulative, x >= edge) and y is reduced per bin with
``--estimator`` (mean, sum, max, min, median, std, rms) -- seaborn's ``lineplot(estimator=)``.
Each bin carries the standard error of its statistic (``--estimator_error``;
stored per-event errors from ``--errory`` are propagated, see
:func:`plotipus.transforms.estimate`) and bins with fewer than
``--min_count`` entries are dropped.
``--plot_type box`` draws a box per bin (per category for non-numeric x)
instead, the hues dodged side by side within each bin. ``--panels`` draws one x
column per panel; with ``--compact`` the panels share one axis, their
``--panel_rangex`` ranges stitched side by side.
"""

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FixedFormatter, FixedLocator, MaxNLocator, NullLocator
from rich import print as rprint

from .. import style
from ..args import map_iterable_color, map_iterable_label, resolve_axis_label, resolve_plot_kwargs
from ..format import make_subtitle_from_args, make_title_from_args
from ..io import prepare_import
from ..panel_lines import add_panel_line_args, draw_panel_lines, panel_rangex, resolve_panel_lines
from ..palettes import ColorAllocator
from ..panels import add_title_and_note, create_panels, draw_overlays, save
from ..plot import (
    add_centered_suptitle,
    apply_common_figure_margins,
    apply_legend_style,
    apply_note_to_figure,
    apply_tick_formatter,
    get_common_figsize,
    plot_data,
)
from ..selection import filter_dataframe
from ..transforms import _ESTIMATORS, bin_estimate, bin_reduce, edges_from_centers, estimate, reduction_bins

ESTIMATORS = tuple(_ESTIMATORS)
SUFFIXES = {"scatter_points": "scatter", "scatter": "scatter"}
ERROR_MODES = ("sem", "std", "none")
BOX_TICK_LABELS = ("axis", "centres", "ranges")
# Most box tick labels on one axis (centres, ranges); past it, every k-th
# bin is labelled.
_MAX_BOX_TICKS = {"centres": 12, "ranges": 6}


def add_estimator_args(parser):
    group = parser.add_argument_group("binned estimator (--binned)")
    add = group.add_argument
    add("--binned", action="store_true", default=False,
        help="Bin raw per-event x/y arrays and draw y reduced per x bin with --estimator.")
    add("--estimator", type=str, default=None, choices=ESTIMATORS,
        help="Reduction of y per bin (default: project setting default_operation, else mean).")
    add("--bins", "-b", type=int, default=None, help="Number of bin edges for non-integer x (default: style nbins).")
    add("--threshold", action="store_true", default=False, help="Cumulative bins: every point with x >= edge.")
    add("--estimator_error", type=str, default="sem", choices=ERROR_MODES,
        help="Error drawn per bin: sem the standard error of the statistic (stored --errory errors propagated), "
             "std the bin's spread σ, none no error (default: sem).")
    add("--min_count", type=int, default=5,
        help="Drop bins with fewer entries than this (default: 5; 1 draws every non-empty bin).")
    add("--no_error_label", action="store_true", default=False,
        help="Do not append the error description, e.g. '(mean ± s.e.m.)', to the y label.")
    add("--whis", nargs="+", type=float, default=[1.5],
        help="With --plot_type box: whisker reach in IQRs past the box, or two percentiles, e.g. 5 95 "
             "(default: 1.5).")
    add("--box_tick_labels", type=str, default="axis", choices=BOX_TICK_LABELS,
        help="With --plot_type box and numeric bins: a plain numeric axis over the bin edges (axis, default), "
             "a tick at each bin centre (centres) or [a, b) ranges (ranges).")
    add("--no_fliers", action="store_true", default=False,
        help="With --plot_type box: do not draw the points past the whiskers.")
    add("--panels", nargs="+", type=str, default=None, help="x columns, one per panel (replaces -x).")
    add_panel_line_args(parser)


def resolve_estimator_args(args, parser):
    if args.panels is None and args.x is None:
        parser.error("the following arguments are required: -x (or use --panels)")
    resolve_panel_lines(args, parser, n_panels=len(args.panels) if args.panels else None, unit="--panels entry")
    if args.compact and args.panels is None:
        parser.error("--compact requires --panels")
    if args.compact and args.panel_rangex is None:
        parser.error("--compact requires --panel_rangex")


def _estimator(args):
    from ..project import load_project

    name = args.estimator or load_project().settings.get("default_operation") or "mean"
    if name.lower() not in ESTIMATORS:
        raise ValueError(f"Invalid estimator {name}; use one of {', '.join(ESTIMATORS)}.")
    return name


def _first_row_with(subset, column):
    """Index of the first row whose ``column`` holds data, not a NaN placeholder."""
    for i, value in enumerate(subset[column].values):
        if isinstance(value, (list, np.ndarray)) or not (isinstance(value, float) and np.isnan(value)):
            return i
    return 0


def _group_rows(df, args, config, name):
    if config is not None and name is None and args.iterable != "Config":
        return df[df["Config"] == config]
    if config is None and name is not None and args.iterable != "Name":
        return df[df["Name"] == name]
    if config is not None and name is not None:
        return df[(df["Config"] == config) & (df["Name"] == name)]
    return df.copy()


def _suffix(args):
    if args.plot_type == "box":
        return "box.png"
    plot_type = args.plot_type or "scatter_points"
    return f"{SUFFIXES.get(plot_type, plot_type)}.png"


def run_estimator(df, args):
    configs, names = prepare_import(args)
    configs = configs if (configs is not None and args.iterable != "Config") else [None]
    names = names if (names is not None and args.iterable != "Name") else [None]
    if args.compact:
        return [_compact_figure(df, args, kdx, config, name) for kdx, (config, name) in enumerate(zip(configs, names))]
    return [_panel_figure(df, args, kdx, config, name) for kdx, (config, name) in enumerate(zip(configs, names))]


def _shared_span(group, args, variable, x_col):
    """(min, max) that every hue of one panel is binned over: --rangex, else
    the range of all their raw x arrays, so the hues share bin edges."""
    rangex = getattr(args, "rangex", None)
    if rangex is not None and len(rangex) == 2:
        return float(rangex[0]), float(rangex[1])
    rows = group if variable is None else group[group["Variable"] == variable]
    if x_col not in rows.columns:
        return None
    try:
        arrays = [np.asarray(v, dtype=float).ravel() for v in filter_dataframe(rows, args)[x_col]
                  if not isinstance(v, list) and np.ndim(v) != 0 and np.size(v)]
    except (TypeError, ValueError):
        return None  # categorical x
    values = np.concatenate(arrays) if arrays else np.empty(0)
    values = values[np.isfinite(values)]
    return (float(values.min()), float(values.max())) if values.size else None


def _reduce_cell(x, y, args, error=None, span=None):
    """(centres, values, errors) or None; scalar cells are already reduced.
    errors is None when no bin has one; bins under --min_count are dropped."""
    estimator = _estimator(args)
    mode = getattr(args, "estimator_error", "sem")
    if np.ndim(x) != 0 and np.ndim(y) == 0:
        rprint(f"[yellow]Warning:[/yellow] x is an array but '{args.y}' is a single value; skipping.")
        return None
    if np.ndim(x) == 0:
        centres = np.asarray([float(x)])
        if np.ndim(y) == 0:
            return centres, np.asarray([float(y)]), None if error is None else np.asarray([float(error)])
        # A single stored error cannot be shared out over the events.
        value, value_error = estimate(y, estimator, error if np.ndim(error) != 0 else None, mode)
        values, errors, counts = np.asarray([value]), np.asarray([value_error]), np.asarray([np.size(y)])
    elif x.size == 0:
        rprint("[yellow]Warning:[/yellow] No x values found. Skipping.")
        return None
    else:
        edges, centres = reduction_bins(x, args.bins if args.bins is not None else style.nbins, args.reduce, span)
        values, errors, counts = bin_estimate(x, y, edges, estimator, cumulative=args.threshold, errors=error,
                                              error_mode=mode)
    min_count = max(getattr(args, "min_count", 1), 1)
    keep = counts >= min_count
    dropped = int(np.count_nonzero((counts > 0) & ~keep))
    if dropped:
        rprint(f"[yellow]Note:[/yellow] '{args.y}': dropped {dropped} of {np.count_nonzero(counts)} bins "
               f"with fewer than {min_count} entries (--min_count).")
    centres, values, errors = centres[keep], values[keep], errors[keep]
    return centres, values, errors if np.isfinite(errors).any() else None


def _error_label(args, propagated):
    """'(mean ± s.e.m.)' and the like, for the y label of drawn errors."""
    name = {"average": "mean", "rms": "RMS"}.get(_estimator(args).lower(), _estimator(args).lower())
    if getattr(args, "estimator_error", "sem") == "std":
        return f"({name} $\\pm$ $\\sigma$)"
    if propagated:
        return f"({name} $\\pm$ propagated error)"
    return f"({name} $\\pm$ s.e.m.)" if name == "mean" else f"({name} $\\pm$ s.e.)"


def _ylabel(args, subset, errors_drawn, propagated):
    label = resolve_axis_label(args.labely, args.y, subset)
    if errors_drawn and args.note is None and not getattr(args, "no_error_label", False):
        label = f"{label} {_error_label(args, propagated)}" if label else _error_label(args, propagated)
    return label


def _panel_figure(df, args, kdx, config, name):
    n_panels = len(args.panels) if args.panels is not None else (len(args.variables) if args.variables else 1)
    fig, axes, _, _ = create_panels(n_panels, grid=False)
    group = _group_rows(df, args, config, name)
    variables = [None] * len(args.panels) if args.panels is not None else (args.variables or [None])
    # Hue values left by --select and friends: the boxes dodge over these only.
    hues = filter_dataframe(group, args)[args.iterable].unique() if args.iterable is not None else [None]
    if getattr(args, "data_hue", None) and args.iterable is not None:
        # Data first: drawn (and listed in the legend) before the samples it is compared with.
        data_values = {str(v) for v in args.data_hue}
        hues = sorted(hues, key=lambda hue: str(hue) not in data_values)
    first_subset = {}
    errors_drawn = propagated = False
    box_colors = ColorAllocator()
    box_colors.reserve(hues, lambda hue: map_iterable_color(hue, args.iterable_color_mapping))
    box_ticks = {}  # panel -> (centres, edges, categories) of the boxes

    for idx, variable in enumerate(variables):
        ax = axes[idx]
        span = _shared_span(group, args, variable, args.panels[idx] if args.panels is not None else args.x)
        categories = None
        for jdx, hue in enumerate(hues):
            rows = group
            if variable is not None:
                rows = rows[rows["Variable"] == variable]
            if hue is not None:
                rows = rows[rows[args.iterable] == hue]
            subset = filter_dataframe(rows, args)
            first_subset.setdefault(idx, subset)
            if subset.empty:
                continue
            x_col = args.panels[idx] if args.panels is not None else args.x
            row = _first_row_with(subset, x_col)
            x, y = subset[x_col].values[row], subset[args.y].values[row]
            # 'Error' is {y}Error as loaded (and rescaled by --multiply).
            error = subset["Error"].values[row] if args.errory and "Error" in subset.columns else None
            if isinstance(x, list):
                continue

            if args.plot_type == "box":
                if np.ndim(x) == 0 and np.ndim(y) == 0:
                    rprint("[yellow]Warning:[/yellow] box plots need array data; skipping.")
                    continue
                if categories is None and np.ndim(x) != 0 and not np.issubdtype(np.asarray(x).dtype, np.number):
                    categories = _shared_categories(group, args, variable, x_col)
                data, centres, edges = _box_groups(x, y, args, span, categories)
                bin_widths = np.diff(edges) if edges is not None else np.ones(len(centres))
                width = 0.8 * bin_widths / len(hues)
                keep = np.array([np.size(d) > 0 for d in data], dtype=bool)
                label = map_iterable_label(hue, args.iterable, args.iterable_mapping, len(hues)) \
                    if args.iterable is not None else None
                if keep.any():
                    plot_data(args, ax, centres, y=[d for d, k in zip(data, keep) if k], label=label,
                              plot_type="boxplot", color=box_colors.color_for(hue),
                              positions=(centres + (jdx - (len(hues) - 1) / 2) * width)[keep], widths=width[keep],
                              whis=args.whis[0] if len(args.whis) == 1 else tuple(args.whis[:2]),
                              showfliers=not args.no_fliers, manage_ticks=False)
                box_ticks.setdefault(idx, (centres, edges, categories))
                continue

            reduced = _reduce_cell(x, y, args, error, span)
            if reduced is None:
                continue
            centres, values, errors = reduced
            plot_type = args.plot_type or ("errorbar" if errors is not None else "scatter_points")
            if errors is not None:
                errors_drawn = True
                propagated = propagated or error is not None
            if variable is not None:
                label = f"{args.y}: {variable}"
            elif args.iterable is not None:
                label = map_iterable_label(hue, args.iterable, args.iterable_mapping, len(hues))
            else:
                label = f"{args.y} vs {args.x}"
            if hue is not None and args.plot_type is None and getattr(args, "data_hue", None):
                # --data_hue: data as ink points, the other samples as steps with error bands.
                if str(hue) in {str(v) for v in args.data_hue}:
                    plot_data(args, ax, centres, y=values, errory=errors, label=label, color=style.role("ink"),
                              plot_type="errorbar", fmt="o", ls="none", zorder=3)
                else:
                    plot_data(args, ax, centres, x_edges=edges_from_centers(centres), y=values, errory=errors,
                              label=label, color=box_colors.color_for(hue), plot_type="step", step_open=True)
                continue
            color = map_iterable_color(hue, args.iterable_color_mapping) if args.iterable is not None else None
            plot_data(args, ax, centres, y=values, errory=errors, label=label, color=color,
                      **_marker_kwargs(args, plot_type), **resolve_plot_kwargs(plot_type))

    for idx, _ in enumerate(variables):
        ax = axes[idx]
        if n_panels > 1:
            title = args.panel_title[idx] if args.panels is not None and args.panel_title is not None else make_subtitle_from_args(args, None, idx=idx)
            ax.set_title(title, fontsize=style.subtitlefontsize)
        subset = first_subset.get(idx, df)
        x_col = args.panels[idx] if args.panels is not None else args.x
        ax.set_xlabel(resolve_axis_label(_first(args.labelx), x_col, subset))
        if idx == 0:
            ax.set_ylabel(_ylabel(args, subset, errors_drawn, propagated))
        if len(ax.get_xticks()) > 10 and args.reduce:
            ticks = ax.get_xticks()
            ax.set_xticks(ticks[:: max(1, len(ticks) // 10)])
        span = panel_rangex(args, idx) if args.panels is not None else None
        if span is not None:
            ax.set_xlim(*span)
        elif args.rangex is not None:
            ax.set_xlim(args.rangex[0], args.rangex[1])
        else:
            ax.set_xlim(None)
        if args.rangey is not None:
            ax.set_ylim(args.rangey[0], args.rangey[1])
        apply_tick_formatter(ax, axis="both")
        if idx in box_ticks:
            _set_box_ticks(ax, *box_ticks[idx], args)
        if args.logy:
            ax.semilogy()
        if args.logx:
            ax.semilogx()
        if idx == n_panels - 1 and not args.no_legend:
            apply_legend_style(ax, title=args.labelz if args.labelz is not None else args.iterable,
                               capitalize_labels=args.capitalize_legend)
        draw_overlays(ax, args)
        if args.panels is not None:
            draw_panel_lines(ax, args, idx)

    if args.panels is not None and args.panel_title is not None and args.title is None:
        apply_note_to_figure(fig, args.note)
    else:
        add_title_and_note(fig, args)
    return save(fig, args, kdx, suffix=_suffix(args))


def _shared_categories(group, args, variable, x_col):
    """Sorted values of a non-numeric x column over every hue of one panel,
    so the hues share the box positions."""
    rows = group if variable is None else group[group["Variable"] == variable]
    values = [np.asarray(v).ravel() for v in filter_dataframe(rows, args)[x_col] if np.ndim(v) != 0]
    return sorted({str(v) for array in values for v in array})


def _box_groups(x, y, args, span, categories):
    """(per-box y arrays, centres, edges) of one series: per x bin, per
    category (edges None, centres 0..n-1), or one box for a scalar x."""
    if np.ndim(x) == 0:
        return [np.asarray(y)], np.asarray([float(x)]), None
    if categories is not None:
        x, y = np.asarray(x).astype(str), np.asarray(y)
        return [y[x == c] for c in categories], np.arange(len(categories), dtype=float), None
    edges, centres = reduction_bins(x, args.bins if args.bins is not None else style.nbins, args.reduce, span)
    return bin_reduce(x, y, edges, None, cumulative=args.threshold), np.asarray(centres, dtype=float), edges


def _tick_number(values, step):
    """Formatter of ``values`` to the precision of the bin width ``step``,
    one more digit when that makes them exact (centres of unit bins at .5)."""
    digits = max(0, -int(np.floor(np.log10(step)))) if step > 0 else 0
    if not np.allclose(np.round(values, digits), values) and np.allclose(np.round(values, digits + 1), values):
        digits += 1

    def number(value):
        text = f"{value:.{digits}f}"
        return text.lstrip("-") if float(text) == 0 else text

    return number


def _set_box_ticks(ax, centres, edges, categories, args):
    """Ticks at the box centres: the category names, else the bin centres
    (or [a, b) ranges with --box_tick_labels ranges) to the bins' precision;
    with --box_tick_labels axis, a plain numeric axis over the bin edges."""
    if categories is None and args.box_tick_labels == "axis":
        if edges is not None and len(edges) > 1 and args.rangex is None:
            ax.set_xlim(edges[0], edges[-1])
        return
    if categories is not None:
        labels = list(categories)
    else:
        step = float(np.min(np.diff(edges))) if edges is not None and len(edges) > 1 else 1.0
        if args.box_tick_labels == "ranges" and edges is not None:
            number = _tick_number(edges, step)
            labels = [f"$\\geq${number(lo)}" if args.threshold else f"[{number(lo)}, {number(hi)})"
                      for lo, hi in zip(edges[:-1], edges[1:])]
        else:
            labels = [_tick_number(centres, step)(c) for c in centres]
    every = 1 if categories is not None else int(np.ceil(len(centres) / _MAX_BOX_TICKS[args.box_tick_labels]))
    ax.xaxis.set_major_locator(FixedLocator(list(centres)[::every]))
    ax.xaxis.set_major_formatter(FixedFormatter(labels[::every]))
    ax.xaxis.set_minor_locator(NullLocator())


def _marker_kwargs(args, plot_type):
    """Markers for scatter points; the default error bars sit on markers, not joined."""
    if plot_type == "scatter_points":
        return {"marker": "o"}
    if plot_type == "errorbar" and args.plot_type is None:
        return {"ls": "none"}
    return {}


def _first(value):
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def _compact_figure(df, args, kdx, config, name):
    """--panels on one shared axis, each panel's range shifted after the previous."""
    ranges = [panel_rangex(args, i) for i in range(len(args.panels))]
    widths = [hi - lo for lo, hi in ranges]
    offsets = list(np.concatenate([[0.0], np.cumsum(widths)[:-1]]))
    cycle = plt.rcParams["axes.prop_cycle"].by_key().get("color", ["C0"])

    fig, ax = plt.subplots(nrows=1, ncols=1, figsize=get_common_figsize(ncols=1, nrows=1), constrained_layout=False)
    apply_common_figure_margins(fig)
    # Room for the per-panel x label row under the tick labels.
    fig.subplots_adjust(bottom=fig.subplotpars.bottom + 0.42 / fig.get_figheight())

    group = _group_rows(df, args, config, name)
    # Hue values left by --select and friends: the boxes dodge over these only.
    hues = filter_dataframe(group, args)[args.iterable].unique() if args.iterable is not None else [None]
    colors = {hue: map_iterable_color(hue, args.iterable_color_mapping) or cycle[j % len(cycle)] for j, hue in enumerate(hues)}
    tick_positions, tick_labels = [], []
    errors_drawn = propagated = False

    for pidx, x_col in enumerate(args.panels):
        lo, hi = ranges[pidx]
        offset = offsets[pidx]
        integer = None
        for hue in hues:
            rows = group if hue is None else group[group[args.iterable] == hue]
            subset = filter_dataframe(rows, args)
            if subset.empty:
                continue
            row = _first_row_with(subset, x_col)
            x, y = subset[x_col].values[row], subset[args.y].values[row]
            error = subset["Error"].values[row] if args.errory and "Error" in subset.columns else None
            if isinstance(x, list):
                continue
            if integer is None and np.ndim(x) != 0:
                integer = bool(np.issubdtype(np.asarray(x).dtype, np.integer))
            reduced = _reduce_cell(x, y, args, error)
            if reduced is None:
                continue
            centres, values, errors = reduced
            keep = (centres >= lo) & (centres <= hi)
            if not keep.any():
                continue
            plot_type = args.plot_type or ("errorbar" if errors is not None else "scatter_points")
            if errors is not None:
                errors_drawn = True
                propagated = propagated or error is not None
            label = map_iterable_label(hue, args.iterable, args.iterable_mapping, len(hues)) if args.iterable is not None and pidx == 0 else None
            plot_data(args, ax, centres[keep] - lo + offset, y=values[keep],
                      errory=None if errors is None else errors[keep], label=label, color=colors[hue],
                      **_marker_kwargs(args, plot_type), **resolve_plot_kwargs(plot_type))

        locator = MaxNLocator(nbins=4 if args.reduce else 6, integer=bool(integer), steps=[1, 2, 2.5, 5, 10])
        ticks = locator.tick_values(lo, hi)
        for tick in ticks[(ticks >= lo) & (ticks <= hi)]:
            tick_positions.append(tick - lo + offset)
            tick_labels.append(str(int(round(tick))) if integer else f"{tick:g}")
        if pidx > 0:
            ax.axvline(offset, color=style.role("ink"), linewidth=1.4, zorder=10)

        vertical = args.panel_vertical
        if vertical is not None and vertical[pidx] is not None:
            from ..plot import draw_vertical_lines

            draw_vertical_lines(
                ax, [v - lo + offset for v in vertical[pidx]],
                labels=args.panel_vertical_label[pidx] if args.panel_vertical_label is not None else None,
                styles=args.panel_vertical_style[pidx] if args.panel_vertical_style is not None else None,
                colors=args.panel_vertical_color[pidx] if args.panel_vertical_color is not None else None,
                fontsize=style.linelabelfontsize,
            )
        horizontal = args.panel_horizontal
        if horizontal is not None and horizontal[pidx] is not None:
            color = args.panel_horizontal_color[pidx] if args.panel_horizontal_color is not None else style.role("muted")
            line_style = args.panel_horizontal_style[pidx] if args.panel_horizontal_style is not None else "--"
            # Only this panel's segment of the shared axis.
            ax.hlines(horizontal[pidx], offset, offset + widths[pidx], colors=color, linestyles=line_style,
                      linewidth=1, zorder=5)
            label = args.panel_horizontal_label[pidx] if args.panel_horizontal_label is not None else None
            if label:
                ax.text(offset + widths[pidx] * 0.97, horizontal[pidx], label, ha="right", va="bottom",
                        fontsize=style.linelabelfontsize, color=color, clip_on=True)

        if args.panel_labelx is not None:
            text = args.panel_labelx[pidx]
        elif args.labelx is not None:
            text = _first(args.labelx)
        else:
            text = resolve_axis_label(None, x_col, group)
        ax.text(offset + widths[pidx] / 2, -0.11, text, transform=ax.get_xaxis_transform(), ha="center",
                va="top", fontsize=style.xsublabelfontsize, clip_on=False)

    ax.set_xlim(0, sum(widths))
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels)
    ax.set_xlabel("")
    ax.set_ylabel(_ylabel(args, group, errors_drawn, propagated))
    if args.rangey is not None:
        ax.set_ylim(args.rangey[0], args.rangey[1])
    # y only: the x ticks carry the per-panel values set above.
    apply_tick_formatter(ax, axis="y")
    if args.logy:
        ax.semilogy()
    # Without --hue no series is labelled; an empty legend fails on matplotlib >= 3.11.
    if not args.no_legend and ax.get_legend_handles_labels()[0]:
        apply_legend_style(ax, title=args.labelz if args.labelz is not None else args.iterable,
                           capitalize_labels=args.capitalize_legend)
    draw_overlays(ax, args)
    title = make_title_from_args(args)
    if title:
        add_centered_suptitle(fig, title, fontsize=style.titlefontsize)
    apply_note_to_figure(fig, args.note)
    return save(fig, args, kdx, suffix=_suffix(args))
