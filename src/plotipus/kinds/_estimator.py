"""Binned-estimator mode of the line kind (``--binned``).

Rows hold raw per-event arrays (``x`` and ``y`` of equal length). x is
binned (unit bins for integer x, else ``--bins`` equal bins; ``--threshold``
makes every bin cumulative, x >= edge) and y is reduced per bin with
``--estimator`` (mean, sum, max, min) -- seaborn's ``lineplot(estimator=)``.
``--plot_type box`` draws a box per bin instead. ``--panels`` draws one x
column per panel; with ``--compact`` the panels share one axis, their
``--panel_rangex`` ranges stitched side by side.
"""

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import MaxNLocator
from rich import print as rprint

from .. import style
from ..args import map_iterable_color, map_iterable_label, resolve_axis_label, resolve_plot_kwargs
from ..format import make_subtitle_from_args, make_title_from_args
from ..io import prepare_import
from ..panel_lines import add_panel_line_args, draw_panel_lines, panel_rangex, resolve_panel_lines
from ..panels import add_title_and_note, create_panels, draw_overlays, save
from ..plot import (
    add_centered_suptitle,
    apply_common_figure_margins,
    apply_legend_style,
    apply_note_to_figure,
    apply_scientific_threshold_formatter,
    get_common_figsize,
    plot_data,
)
from ..selection import filter_dataframe
from ..transforms import bin_reduce, reduction_bins

ESTIMATORS = ("mean", "average", "sum", "max", "min")
SUFFIXES = {"scatter_points": "scatter", "scatter": "scatter"}


def add_estimator_args(parser):
    group = parser.add_argument_group("binned estimator (--binned)")
    add = group.add_argument
    add("--binned", action="store_true", default=False,
        help="Bin raw per-event x/y arrays and draw y reduced per x bin with --estimator.")
    add("--estimator", type=str, default=None, choices=ESTIMATORS,
        help="Reduction of y per bin (default: project setting default_operation, else mean).")
    add("--bins", "-b", type=int, default=None, help="Number of bin edges for non-integer x (default: style nbins).")
    add("--threshold", action="store_true", default=False, help="Cumulative bins: every point with x >= edge.")
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


def _reduce_cell(x, y, args, error=None):
    """(centres, values, errors) or None; scalar cells are already reduced."""
    estimator = _estimator(args)
    if np.ndim(x) != 0 and np.ndim(y) == 0:
        rprint(f"[yellow]Warning:[/yellow] x is an array but '{args.y}' is a single value; skipping.")
        return None
    if np.ndim(x) == 0:
        centres = np.asarray([float(x)])
        if np.ndim(y) == 0:
            return centres, np.asarray([float(y)]), None if error is None else np.asarray([float(error)])
        reduced_error = None if error is None else np.asarray([_reduce_all(error, estimator)])
        return centres, np.asarray([_reduce_all(y, estimator)]), reduced_error
    if x.size == 0:
        rprint("[yellow]Warning:[/yellow] No x values found. Skipping.")
        return None
    edges, centres = reduction_bins(x, args.bins if args.bins is not None else style.nbins, args.reduce)
    values = bin_reduce(x, y, edges, estimator, cumulative=args.threshold)
    errors = bin_reduce(x, error, edges, estimator, cumulative=args.threshold) if error is not None else None
    return centres, values, errors


def _reduce_all(values, estimator):
    values = np.asarray(values)
    return {"mean": values.mean, "average": values.mean, "sum": values.sum, "max": values.max, "min": values.min}[estimator.lower()]()


def _panel_figure(df, args, kdx, config, name):
    n_panels = len(args.panels) if args.panels is not None else (len(args.variables) if args.variables else 1)
    fig, axes, _, _ = create_panels(n_panels, grid=False)
    group = _group_rows(df, args, config, name)
    variables = [None] * len(args.panels) if args.panels is not None else (args.variables or [None])
    hues = group[args.iterable].unique() if args.iterable is not None else [None]
    first_subset = {}

    for idx, variable in enumerate(variables):
        ax = axes[idx]
        for hue in hues:
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
                if np.ndim(x) == 0:
                    if np.ndim(y) == 0:
                        rprint("[yellow]Warning:[/yellow] box plots need array data; skipping.")
                        continue
                    data, centres, widths = [y], np.asarray([float(x)]), None
                else:
                    edges, centres = reduction_bins(x, args.bins if args.bins is not None else style.nbins, args.reduce)
                    data = bin_reduce(x, y, edges, None, cumulative=args.threshold)
                    widths = np.diff(edges) * 0.8 if np.issubdtype(np.asarray(x).dtype, np.integer) else None
                plot_data(args, ax, centres, y=data, label=f"Median {args.y}", plot_type="boxplot",
                          positions=centres, widths=widths, showfliers=False)
                continue

            reduced = _reduce_cell(x, y, args, error)
            if reduced is None:
                continue
            centres, values, errors = reduced
            plot_type = args.plot_type or ("errorbar" if errors is not None else "scatter_points")
            if variable is not None:
                label = f"{args.y}: {variable}"
            elif args.iterable is not None:
                label = map_iterable_label(hue, args.iterable, args.iterable_mapping, len(hues))
            else:
                label = f"{args.y} vs {args.x}"
            color = map_iterable_color(hue, args.iterable_color_mapping) if args.iterable is not None else None
            plot_data(args, ax, centres, y=values, errory=errors, label=label, color=color,
                      marker="o" if plot_type == "scatter_points" else None, **resolve_plot_kwargs(plot_type))

    for idx, _ in enumerate(variables):
        ax = axes[idx]
        if n_panels > 1:
            title = args.panel_title[idx] if args.panels is not None and args.panel_title is not None else make_subtitle_from_args(args, None, idx=idx)
            ax.set_title(title, fontsize=style.subtitlefontsize)
        subset = first_subset.get(idx, df)
        x_col = args.panels[idx] if args.panels is not None else args.x
        ax.set_xlabel(resolve_axis_label(_first(args.labelx), x_col, subset))
        if idx == 0:
            ax.set_ylabel(resolve_axis_label(args.labely, args.y, subset))
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
        apply_scientific_threshold_formatter(ax, threshold=0.1, axis="both")
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


def _first(value):
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def _compact_figure(df, args, kdx, config, name):
    """--panels on one shared axis, each panel's range shifted after the previous."""
    ranges = [panel_rangex(args, i) for i in range(len(args.panels))]
    widths = [hi - lo for lo, hi in ranges]
    offsets = list(np.concatenate([[0.0], np.cumsum(widths)[:-1]]))
    plot_type = args.plot_type or "scatter_points"
    plot_kwargs = resolve_plot_kwargs(plot_type)
    cycle = plt.rcParams["axes.prop_cycle"].by_key().get("color", ["C0"])

    fig, ax = plt.subplots(nrows=1, ncols=1, figsize=get_common_figsize(ncols=1, nrows=1), constrained_layout=False)
    apply_common_figure_margins(fig)
    # Room for the per-panel x label row under the tick labels.
    fig.subplots_adjust(bottom=fig.subplotpars.bottom + 0.42 / fig.get_figheight())

    group = _group_rows(df, args, config, name)
    hues = group[args.iterable].unique() if args.iterable is not None else [None]
    colors = {hue: map_iterable_color(hue, args.iterable_color_mapping) or cycle[j % len(cycle)] for j, hue in enumerate(hues)}
    tick_positions, tick_labels = [], []

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
            if isinstance(x, list):
                continue
            if integer is None and np.ndim(x) != 0:
                integer = bool(np.issubdtype(np.asarray(x).dtype, np.integer))
            reduced = _reduce_cell(x, y, args)
            if reduced is None:
                continue
            centres, values, _ = reduced
            keep = (centres >= lo) & (centres <= hi)
            if not keep.any():
                continue
            label = map_iterable_label(hue, args.iterable, args.iterable_mapping, len(hues)) if args.iterable is not None and pidx == 0 else None
            plot_data(args, ax, centres[keep] - lo + offset, y=values[keep], label=label, color=colors[hue],
                      marker="o" if plot_type == "scatter_points" else None, **plot_kwargs)

        locator = MaxNLocator(nbins=4 if args.reduce else 6, integer=bool(integer), steps=[1, 2, 2.5, 5, 10])
        ticks = locator.tick_values(lo, hi)
        for tick in ticks[(ticks >= lo) & (ticks <= hi)]:
            tick_positions.append(tick - lo + offset)
            tick_labels.append(str(int(round(tick))) if integer else f"{tick:g}")
        if pidx > 0:
            ax.axvline(offset, color="black", linewidth=1.4, zorder=10)

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
            color = args.panel_horizontal_color[pidx] if args.panel_horizontal_color is not None else "gray"
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
    ax.set_ylabel(resolve_axis_label(args.labely, args.y, group))
    if args.rangey is not None:
        ax.set_ylim(args.rangey[0], args.rangey[1])
    # y only: the x ticks carry the per-panel values set above.
    apply_scientific_threshold_formatter(ax, threshold=0.1, axis="y")
    if args.logy:
        ax.semilogy()
    if not args.no_legend:
        apply_legend_style(ax, title=args.labelz if args.labelz is not None else args.iterable,
                           capitalize_labels=args.capitalize_legend)
    draw_overlays(ax, args)
    title = make_title_from_args(args)
    if title:
        add_centered_suptitle(fig, title, fontsize=style.titlefontsize)
    apply_note_to_figure(fig, args.note)
    return save(fig, args, kdx, suffix=_suffix(args))
