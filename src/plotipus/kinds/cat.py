"""cat: one value per category.

Each row carries an array column (``-y``, e.g. counts) binned along another
array column (``--integrate_over``) and a categorical column (``-x``). The
array is reduced to a scalar per row (``--integral_mode integrate``: sum of
y times bin width; ``sum``: plain sum; optionally within
``--integration_range``); rows sharing a category are summed and errors add
in quadrature. One series per ``--hue`` value (colour and marker), one line
style (or bar opacity) per ``--style`` value; ``--kind`` draws points joined
by lines (line), bare points (point) or dodged bars (bar).
"""

import matplotlib.lines as mlines
import numpy as np
from rich import print as rprint

from .. import style
from ..args import add_common_args, map_iterable_color, map_iterable_label, resolve_axis_label
from ..encodings import LINESTYLES
from ..io import import_data, prepare_import
from ..palettes import ColorAllocator
from ..panels import add_title_and_note, create_panels, draw_horizontal_overlay, save
from ..plot import apply_legend_style, plot_data
from ..selection import filter_dataframe
from . import _base

KIND = "cat"
MARKERS = ["o", "s", "^", "D", "v", "P", "X", "*"]


def build_parser():
    parser = _base.make_parser(KIND, "One value per category of -x, one series per --hue value.")
    add_common_args(
        parser,
        [
            "datafile", "configs", "names", "variables", "iterable", "select", "save_values",
            "remove_value", "filename_select", "filename_suffix", "x", "y", "labelx", "labely", "logy",
            "rangey", "title", "output", "subfolder", "horizontal", "horizontal_label",
            "horizontal_style", "horizontal_color", "note", "multiply", "debug", "errory",
        ],
        overrides={
            "datafile": {"required": True},
            "x": {"required": True, "help": "Categorical column (one position per value)"},
            "y": {"required": True, "help": "Array column reduced to one value per row"},
            "iterable": {"required": True, "help": "Column whose values become separate series (colour)"},
            "errory": {"help": "Propagate the {y}Error column (in quadrature) as error bars"},
        },
    )
    add = parser.add_argument
    add("--kind", choices=["line", "point", "bar"], default="line",
        help="Points joined by lines, bare points, or dodged bars.")
    add("--integrate_over", type=str, default=None,
        help="Array column with the bin centres of -y (default: bin index).")
    add("--integration_range", type=float, nargs=2, default=None, metavar=("LO", "HI"),
        help="Only bins whose --integrate_over value lies in [LO, HI].")
    add("--integral_mode", choices=["integrate", "sum"], default="integrate",
        help="'integrate' multiplies each bin by its width (densities -> totals); 'sum' adds raw values.")
    add("--comparable", "--style", "-c", dest="comparable", type=str, default=None,
        help="Column drawn with distinct line styles (bars: opacity).")
    add("--comparable_linestyles", nargs="+", type=str, default=None,
        help="Line styles cycled over the --comparable values (default - -- : -.).")
    add("--comparable_mapping", type=str, default=None, help="Mapping renaming the --comparable values.")
    add("--comparable_title", type=str, default=None, help="Heading of the --comparable legend section.")
    add("--iterable_mapping", "--hue_mapping", dest="iterable_mapping", type=str, default=None,
        help="Mapping renaming the hue values in the legend.")
    add("--iterable_color_mapping", "--hue_color_mapping", dest="iterable_color_mapping", type=str, default=None,
        help="Mapping giving the colour of each hue value.")
    add("--xtick_mapping", type=str, default=None, help="Mapping renaming the categories on the axis.")
    add("--x_order", nargs="+", type=str, default=None, help="Order of the categories (default: first seen).")
    add("--overlay_names", action="store_true", default=False,
        help="All --configs/--names in one figure instead of one figure per pair.")
    _base.add_output_args(parser)
    return parser


def main(argv=None):
    return _base.main(__import__(__name__, fromlist=["run"]), argv)


def integrate_row(row, args):
    """(value, error) of one row: -y reduced over --integrate_over."""
    y = np.asarray(row[args.y], dtype=float)
    error_column = f"{args.y}Error"
    yerr = None
    if args.errory and error_column in row.index and row[error_column] is not None:
        yerr = np.asarray(row[error_column], dtype=float)
    grid = row[args.integrate_over] if args.integrate_over and args.integrate_over in row.index else None
    grid = np.arange(len(y), dtype=float) if grid is None or np.ndim(grid) == 0 else np.asarray(grid, dtype=float)
    widths = np.gradient(grid) if args.integral_mode == "integrate" and len(grid) > 1 else np.ones_like(grid)

    mask = np.isfinite(y)
    if args.integration_range is not None:
        lo, hi = args.integration_range
        mask &= (grid >= lo) & (grid <= hi)
    value = float(np.sum(y[mask] * widths[mask]))
    error = float(np.sqrt(np.sum((yerr[mask] * widths[mask]) ** 2))) if yerr is not None and len(yerr) == len(y) else None
    if args.multiply is not None:
        value *= args.multiply
        error = None if error is None else error * args.multiply
    return value, error


def _ordered_unique(values, explicit=None):
    seen = list(dict.fromkeys(values))
    if explicit:
        return [v for v in explicit if v in seen] + [v for v in seen if v not in explicit]
    return seen


def draw_figure(rows, args, kdx, comparable):
    categories = _ordered_unique(rows[args.x].tolist(), args.x_order)
    hues = _ordered_unique(rows[args.iterable].tolist())
    comparables = _ordered_unique(rows[comparable].dropna().tolist()) if comparable else [None]
    linestyles = args.comparable_linestyles or LINESTYLES
    positions = np.arange(len(categories), dtype=float)
    fig, axes, _, _ = create_panels(1)
    ax = axes[0]

    colors = ColorAllocator()
    colors.reserve(hues, lambda hue: map_iterable_color(hue, args.iterable_color_mapping, args.iterable))
    hue_handles, style_handles = [], []
    for idx, hue in enumerate(hues):
        # Hue values past the palette repeat a colour but keep their own marker.
        color = colors.color_for(hue)
        marker = MARKERS[idx % len(MARKERS)]
        hue_handles.append(mlines.Line2D([], [], color=color, linestyle="-", marker=marker,
                                         label=map_iterable_label(hue, args.iterable, args.iterable_mapping)))
        for cdx, value in enumerate(comparables):
            subset = rows[rows[args.iterable] == hue]
            if value is not None:
                subset = subset[subset[comparable] == value]
            if subset.empty:
                continue
            linestyle = linestyles[cdx % len(linestyles)]
            xs, ys, es = [], [], []
            for position, category in zip(positions, categories):
                category_rows = subset[subset[args.x] == category]
                if category_rows.empty:
                    continue
                totals = [integrate_row(row, args) for _, row in category_rows.iterrows()]
                errors = [e for _, e in totals if e is not None]
                xs.append(position)
                ys.append(sum(v for v, _ in totals))
                es.append(float(np.sqrt(np.sum(np.square(errors)))) if errors else np.nan)
            if not xs:
                continue
            xs, ys, es = np.asarray(xs), np.asarray(ys), np.asarray(es)
            rprint(f"\tValues for {args.iterable}={hue}" + (f", {comparable}={value}" if value is not None else "") + ": "
                   + ", ".join(f"{categories[int(i)]}={v:.3g}" for i, v in zip(xs, ys)))
            if args.kind == "bar":
                width = 0.8 / max(1, len(hues))
                ax.bar(xs + (idx - (len(hues) - 1) / 2) * width, ys, width=width, color=color,
                       alpha=0.9 if cdx == 0 else 0.5)
            else:
                plot_type = "line" if args.kind == "line" else "scatter"
                kwargs = {"marker": marker} if args.kind == "line" else {}
                if args.errory and np.isfinite(es).any():
                    ax.errorbar(xs, ys, yerr=np.nan_to_num(es), color=color,
                                linestyle=linestyle if args.kind == "line" else "none", capsize=3, **kwargs)
                else:
                    plot_data(args, ax, xs, y=ys, color=color, plot_type=plot_type, linestyle=linestyle, **kwargs)
            if value is not None and cdx >= len(style_handles):
                style_handles.append(mlines.Line2D([], [], color="black", linestyle=linestyle,
                                                   label=map_iterable_label(value, comparable, args.comparable_mapping)))

    ax.set_xticks(positions)
    ax.set_xticklabels([map_iterable_label(c, args.x, args.xtick_mapping) for c in categories],
                       rotation=20, ha="right", rotation_mode="anchor")
    ax.set_xlabel(resolve_axis_label(args.labelx, args.x, rows))
    ylabel = args.labely
    if ylabel is None:
        unit_column = f"{args.y}Unit"
        unit = rows[unit_column].iloc[0] if unit_column in rows.columns else None
        if unit and args.integral_mode == "integrate" and "/ MeV" in str(unit):
            unit = str(unit).replace(" / MeV", "")
        ylabel = f"Integrated {args.y}" + (f" ({unit})" if unit else "")
    ax.set_ylabel(ylabel)
    if args.logy:
        ax.set_yscale("log")
    if args.rangey is not None:
        ax.set_ylim(args.rangey)
    ax.set_xlim(-0.5, len(categories) - 0.5)
    ax.grid(True, axis="y", alpha=0.3)
    draw_horizontal_overlay(ax, args)

    handles = list(hue_handles)
    if style_handles:
        title = args.comparable_title if args.comparable_title is not None else comparable
        handles.append(mlines.Line2D([], [], color="none", label=f"$\\bf{{{title}}}$" if title else ""))
        handles += style_handles
    apply_legend_style(ax, handles=handles, capitalize_labels=args.capitalize_legend, loc=args.legend_loc or "lower left")

    add_title_and_note(fig, args)
    fig.subplots_adjust(bottom=0.22)
    return save(fig, args, kdx, suffix="cat.png")


def run(args):
    df = import_data(args)
    if df.empty:
        rprint("[yellow]Warning:[/yellow] No datafiles found. Exiting...")
        return []
    for column in (args.x, args.y, args.iterable):
        if column not in df.columns:
            rprint(f"[red]Error:[/red] Column '{column}' not found. Available: {', '.join(map(str, df.columns))}")
            return []
    comparable = args.comparable if args.comparable in df.columns else None
    if args.comparable is not None and comparable is None:
        rprint(f"[yellow]Warning:[/yellow] Column '{args.comparable}' not found; one series per hue value.")

    configs, names = prepare_import(args)
    pairs = list(zip(configs, names)) if configs is not None and not args.overlay_names else [(None, None)]
    outputs = []
    for kdx, (config, name) in enumerate(pairs):
        rows = df
        if config is not None:
            rows = rows[rows["Config"] == config]
        if name is not None:
            rows = rows[rows["Name"] == name]
        rows = filter_dataframe(rows, args)
        rows = rows[rows[args.iterable].notna()]
        if rows.empty:
            rprint(f"[yellow]Warning:[/yellow] No data for Config={config}, Name={name}. Skipping.")
            continue
        outputs.append(draw_figure(rows, args, None if args.overlay_names else kdx, comparable))
    return outputs


# --- Legacy command lines ----------------------------------------------------------------


def _legacy_integral(tokens):
    from ..legacy import has, option_values, rename

    plot_type = (option_values(tokens, "--plot_type") or ["line"])[0]
    tokens = rename(tokens, {"--plot_type": None})
    tokens += ["--kind", {"scatter": "point"}.get(plot_type, plot_type)]
    if not has(tokens, "--integrate_over"):
        tokens += ["--integrate_over", "Energy"]
    return tokens + ["--output_suffix", "integral.png"]


LEGACY = {"script_compare_integral": _legacy_integral}
