"""Event-marker lower panel of the line kind (``--lower events:PREFIX``).

The first selected row holds an upper series (``x``/``y`` arrays, e.g. a
waveform) and per-event columns named after ``PREFIX``: positions
(``PREFIXTime``/``Peak``/``X``...), values (``PREFIXArea``/``Value``/
``Amplitude``...) and optionally ``PREFIXStart``/``PREFIXEnd`` ranges. The
lower panel shows the events as points (with range bars and guide lines
through both panels) or, with ``--events_style hist``, as a histogram of
their positions over the upper x range.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from rich import print as rprint

from .. import style
from ..format import make_title_from_args
from ..io import normalize_datafiles
from ..panels import create_panels
from ..plot import (
    add_centered_suptitle,
    apply_common_figure_margins,
    apply_legend_style,
    apply_note_to_figure,
    draw_horizontal_lines,
    draw_vertical_lines,
    plot_data,
)
from ..selection import filter_dataframe


def add_events_args(parser):
    group = parser.add_argument_group("event markers (--lower events:PREFIX)")
    add = group.add_argument
    add("--series_label", type=str, default=None, help="Legend label of the upper series.")
    add("--hue_value", type=str, default=None, help="Draw the row of this hue value.")
    add("--events_label", type=str, default=None, help="Legend label of the events (default: the prefix).")
    add("--events_style", choices=["scatter", "hist"], default="scatter", help="Events as points or as a histogram.")
    add("--events_bins", type=int, default=50, help="Histogram bins of --events_style hist.")
    add("--events_density", action="store_true", default=False, help="Histogram divided by bin width.")
    add("--events_range", action="store_true", default=False, help="Range bars from the PREFIXStart/PREFIXEnd columns.")
    add("--events_guides", action="store_true", default=False, help="Guide lines at each event through both panels.")
    add("--show_highlights", action="store_true", default=False,
        help="Shade the PREFIXStart-PREFIXEnd windows on the upper panel.")
    add("--highlight_color", type=str, default="C1")


def _array_or_zero(row, column, length):
    if column is None or column not in row:
        return np.zeros(length, dtype=float)
    values = np.asarray(row[column], dtype=float).ravel()
    if values.size == 0:
        return np.zeros(length, dtype=float)
    if values.size == 1 and length > 1:
        return np.full(length, values[0], dtype=float) if np.isfinite(values[0]) else np.zeros(length, dtype=float)
    if values.size < length:
        padded = np.zeros(length, dtype=float)
        padded[: values.size] = values
        return padded
    return values[:length]


def _prefixed_column(row, prefix, preferred, fallback=()):
    """First column named ``{prefix}{token}[unit]`` (or ``True{prefix}...``)."""
    exact = []
    for token in preferred:
        exact += [f"{prefix}{token}{unit}" for unit in ("", "NS", "PE", "MeV", "GeV")]
    for token in fallback:
        exact += [f"{prefix}{token}{unit}" for unit in ("", "NS", "PE")]
    exact += [f"True{prefix}{token}" for token in preferred]
    for candidate in exact:
        if candidate in row:
            return candidate
    if prefix in row:
        return prefix
    lowered = prefix.lower()
    for column in row.index:
        text = str(column).lower()
        if not (text.startswith(lowered) or text.startswith(f"true{lowered}")):
            continue
        if any(t.lower() in text for t in preferred) or any(t.lower() in text for t in fallback):
            return str(column)
    return None


def event_columns(row, prefix):
    """(position, value, start, end, centre) column names of the events."""
    x = _prefixed_column(row, prefix, ("Time", "Peak", "X", "Position"), ("TimeNS", "PeakNS", "X"))
    y = _prefixed_column(row, prefix, ("Area", "Count", "Value", "Amplitude", "Y"), ("AreaPE", "Count", "Y"))
    start = _prefixed_column(row, prefix, ("Start",), ("Start",))
    end = _prefixed_column(row, prefix, ("End",), ("End",))
    centre = _prefixed_column(row, prefix, ("Peak", "Center", "Time", "X"), ("Peak", "Center", "X"))
    return x, (None if y == x else y), start, end, centre


def draw_lower_events(ax, spec, row, args, top_ax=None, x_range=None):
    """Draw the events of ``row`` (prefix ``spec.name``) on ``ax``."""
    x_column, y_column, start, end, _ = event_columns(row, spec.name)
    if x_column is None or x_column not in row:
        return
    x = np.asarray(row[x_column], dtype=float).ravel()
    if x.size == 0:
        return
    label = args.events_label or spec.name
    if args.events_style == "hist":
        counts, edges = np.histogram(x, bins=args.events_bins, range=x_range)
        values = counts.astype(float)
        if args.events_density:
            widths = np.diff(edges)
            values = values / np.where(widths > 0.0, widths, 1.0)
        ax.plot((edges[:-1] + edges[1:]) / 2.0, values, drawstyle="steps-mid", linewidth=1.5, color="C1", label=label)
        return

    y = _array_or_zero(row, y_column, x.size)
    ax.scatter(x, y, color="C1", s=26, marker="o", label=label)
    if args.events_guides and top_ax is not None:
        for value in x:
            for target in (ax, top_ax):
                target.axvline(value, color="C1", linestyle="--", linewidth=0.8, alpha=0.55, zorder=0)
    if not args.events_range or start is None or end is None or start not in row or end not in row:
        return
    starts = np.asarray(row[start], dtype=float).ravel()
    ends = np.asarray(row[end], dtype=float).ravel()
    n = min(x.size, y.size, starts.size, ends.size)
    if n == 0:
        return
    xerr = np.vstack([np.clip(x[:n] - starts[:n], 0.0, None), np.clip(ends[:n] - x[:n], 0.0, None)])
    ax.errorbar(x[:n], y[:n], xerr=xerr, fmt="none", ecolor="C1", elinewidth=1.0, alpha=0.85, capsize=0)


def _highlights(ax, row, prefix, args):
    _, _, start, end, centre = event_columns(row, prefix)
    if not args.events_range:
        start = end = None
    if None in (start, end, centre) or any(c not in row for c in (start, end, centre)):
        return
    starts = np.asarray(row[start], dtype=float).ravel()
    ends = np.asarray(row[end], dtype=float).ravel()
    peaks = np.asarray(row[centre], dtype=float).ravel()
    for i in range(min(starts.size, ends.size, peaks.size)):
        ax.axvspan(starts[i], ends[i], color=args.highlight_color, alpha=0.14, zorder=1)
        ax.axvline(peaks[i], color=args.highlight_color, linestyle="--", linewidth=0.8, alpha=0.8, zorder=2)


def _output_name(args, row, prefix):
    """``<datafile>_<hue value|data>_<prefix>[_<variables>]_<style>_line_scatter_panel.png``."""
    datafile = Path("_".join(normalize_datafiles(args.datafile)))
    hue = str(row[args.iterable]) if args.iterable is not None and args.iterable in row and pd.notna(row[args.iterable]) else "data"
    parts = [datafile.stem if datafile.suffix else datafile.name, hue, prefix,
             "_".join(args.variables) if args.variables else None, args.events_style, "line_scatter_panel"]
    return "_".join(p.replace(" ", "_").replace("/", "_") for p in parts if p) + ".png"


def run_events(df, args, spec):
    """One figure from the first selected row: upper series + event panel."""
    if args.iterable is not None and args.iterable in df.columns or args.variables is not None or args.select is not None:
        df = filter_dataframe(df, args)
    if args.hue_value is not None and args.iterable is not None and args.iterable in df.columns:
        df = df[df[args.iterable].astype(str) == args.hue_value]
    if df.empty:
        raise ValueError("No rows match the selection")
    if len(df) > 1 and args.hue_value is None:
        rprint("[yellow]Warning:[/yellow] Multiple rows found; using the first one.")
    row = df.iloc[0]

    x = np.asarray(row[args.x], dtype=float).ravel()
    y = _array_or_zero(row, args.y, x.size)
    x_column = event_columns(row, spec.name)[0]
    available = x_column is not None and x_column in row
    lower = not args.no_lower_plot
    fig, upper, lowers, _ = create_panels(1, n_lower=1 if lower else 0)
    ax_top = upper[0]
    ax_top.tick_params(labelbottom=True)
    ax_bottom = lowers[0][0] if lower else None
    target = ax_bottom if ax_bottom is not None else (ax_top if available else None)

    label = args.series_label
    if label is None:
        label = str(row[args.iterable]) if args.iterable is not None and args.iterable in row else (
            " ".join(args.variables) if args.variables else "Line")
    plot_data(args, ax_top, x, y=y, label=label, color="C0", linestyle=args.plot_style, plot_type="plot")
    if args.show_highlights:
        _highlights(ax_top, row, spec.name, args)
    if target is not None:
        draw_lower_events(target, spec, row, args, top_ax=ax_top, x_range=(float(np.min(x)), float(np.max(x))))

    ax_top.set_ylabel(args.labely if args.labely is not None else args.y, fontsize=style.ysublabelfontsize)
    ax_top.grid(alpha=0.25)
    draw_vertical_lines(ax_top, args.vertical, labels=args.vertical_label, styles=args.vertical_style,
                        colors=args.vertical_color, fontsize=style.linelabelfontsize)
    if ax_bottom is not None:
        draw_vertical_lines(ax_bottom, args.vertical, fontsize=style.linelabelfontsize)
    draw_horizontal_lines(ax_top, args.horizontal, labels=args.horizontal_label, styles=args.horizontal_style,
                          colors=args.horizontal_color, fontsize=style.linelabelfontsize)
    apply_legend_style(ax_top, title=args.labelz, capitalize_labels=args.capitalize_legend)

    xlabel = args.labelx[0] if isinstance(args.labelx, list) else (args.labelx if args.labelx is not None else args.x)
    if ax_bottom is not None:
        ax_bottom.set_ylabel(args.lower_labely if args.lower_labely is not None else spec.name,
                             fontsize=style.ysublabelfontsize)
        ax_bottom.set_xlabel(xlabel, fontsize=style.xlabelfontsize)
        ax_bottom.grid(alpha=0.25)
        if ax_bottom.get_legend_handles_labels()[0]:
            apply_legend_style(ax_bottom, capitalize_labels=args.capitalize_legend)
    else:
        ax_top.set_xlabel(xlabel, fontsize=style.xlabelfontsize)

    if args.rangex is not None:
        ax_top.set_xlim(args.rangex)
        if ax_bottom is not None:
            ax_bottom.set_xlim(args.rangex)
    if args.rangey is not None:
        ax_top.set_ylim(args.rangey)
    if ax_bottom is not None and args.rangey is None and not args.logy:
        low, high = ax_bottom.get_ylim()
        if args.events_style == "hist":
            ax_bottom.set_ylim(0.0, high)
        elif high - low < 1.0:
            # All event values (nearly) equal, e.g. zero.
            mid = (low + high) / 2.0
            ax_bottom.set_ylim(mid - 0.5, mid + 1.5)
        else:
            margin = 0.15 * (high - low)
            ax_bottom.set_ylim(low - margin, high + margin)
    if args.logx:
        ax_top.set_xscale("log")
        if ax_bottom is not None:
            ax_bottom.set_xscale("log")
    if args.logy:
        ax_top.set_yscale("log")
        if ax_bottom is not None:
            ax_bottom.set_yscale("log")

    add_centered_suptitle(fig, make_title_from_args(args), fontsize=style.titlefontsize)
    apply_common_figure_margins(fig)
    apply_note_to_figure(fig, args.note)
    from ..io import save_figure_to_paths
    from ..panels import apply_figure_hooks

    name = _output_name(args, row, spec.name)
    apply_figure_hooks(fig, args)
    save_figure_to_paths(fig, args.output, name, subfolder=args.subfolder, sci_in_label=getattr(args, "sci_in_label", None))
    plt.close(fig)
    return name
