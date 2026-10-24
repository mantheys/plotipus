"""hist: 1D histograms of per-event arrays.

Each DataFrame row holds the values of one sample (array cells); the first
row of every (panel, hue) selection is histogrammed. Several ``-x`` columns
are first combined point by point with ``--hist_combine`` (sum, mean,
subtract, relative = (a - b) / last, absolute_relative, rms). Panels come
from ``--variables``, colours from ``--hue``; ``--hue Config``/``Name`` draws
the loaded configs/names together with the config mappings. Every hue of a
panel shares one set of bin edges, spanning all of them; entries outside
(``--rangex``, ``--percentile``) are reported and, with ``--flow``, hinted at
or added to the edge bins.
"""

import numpy as np
from matplotlib.transforms import offset_copy
from rich import print as rprint

from .. import style
from ..args import add_common_args, map_iterable_color, map_iterable_label, resolve_axis_label
from ..encodings import add_legend_args
from ..format import make_config_color_and_style_from_args, make_config_label_from_args, make_subtitle_from_args
from ..io import import_data, prepare_import
from ..palettes import ColorAllocator
from ..panel_lines import add_panel_line_args, draw_panel_lines, panel_rangex, resolve_panel_lines
from ..panels import add_title_and_note, create_panels, draw_overlays, save
from ..plot import _resolve_plot_style, apply_legend_style, apply_scientific_threshold_formatter
from ..selection import filter_dataframe
from . import _base

KIND = "hist"
COMBINE = ["sum", "mean", "subtract", "relative", "absolute_relative", "rms"]
FLOW = ["none", "hint", "show"]


def build_parser():
    parser = _base.make_parser(KIND, "1D histograms of array columns, one line per --hue value.")
    add_common_args(
        parser,
        [
            "datafile", "configs", "names", "variables", "x", "iterable", "reduce", "select",
            "save_values", "remove_value", "filename_select", "filename_suffix", "bins", "percentile",
            "labelx", "labely", "labelz", "logx", "logy", "rangex", "rangey", "title", "output",
            "subfolder", "horizontal", "horizontal_label", "horizontal_style", "horizontal_color",
            "vertical", "vertical_label", "vertical_style", "vertical_color", "point", "point_label",
            "note", "debug", "density",
        ],
        overrides={
            "datafile": {"required": True},
            "x": {"nargs": "+", "required": True, "help": "Array column(s) histogrammed (several are combined)"},
            "density": {"help": "Normalise each histogram to unit area (also when --labely is 'Density')"},
        },
    )
    add = parser.add_argument
    add("--hist_combine", type=str, default=None, choices=COMBINE,
        help="How several -x columns are combined point by point.")
    add("--weight", "-w", type=str, default=None, help="Array column of per-entry weights.")
    add("--flow", type=str, default="none", choices=FLOW,
        help="Entries outside the range: none (dropped), hint (a marker beyond the outer edge), "
             "show (added to the first/last bin). Their number is printed in every mode.")
    add("--iterable_mapping", "--hue_mapping", dest="iterable_mapping", type=str, default=None,
        help="Mapping renaming the hue values in the legend.")
    add("--iterable_color_mapping", "--hue_color_mapping", dest="iterable_color_mapping", type=str, default=None,
        help="Mapping giving the colour of each hue value.")
    add("--iterable_order", nargs="+", type=str, default=None,
        help="Draw/legend order of the hue values (listed first, others keep data order).")
    add_legend_args(parser)
    add_panel_line_args(parser, horizontal=False)
    _base.add_output_args(parser)
    return parser


def main(argv=None):
    return _base.main(__import__(__name__, fromlist=["run"]), argv)


def combined_values(subset, args):
    """Values of the first row, the -x columns combined by --hist_combine."""
    x = np.asarray(subset[args.x[0]].values[0], dtype=float)
    if len(args.x) == 1:
        return x
    op = args.hist_combine or "subtract"
    for column in args.x[1:]:
        other = np.asarray(subset[column].values[0], dtype=float)
        if op in ("mean", "sum"):
            x = x + other
        elif op in ("subtract", "relative", "absolute_relative"):
            x = x - other
        elif op == "rms":
            x = x**2 + other**2
    last = np.asarray(subset[args.x[-1]].values[0], dtype=float)
    if op == "mean":
        x = x / len(args.x)
    elif op == "relative":
        x = x / last
    elif op == "absolute_relative":
        x = np.abs(x) / last
    elif op == "rms":
        x = np.sqrt(x / len(args.x))
    return x


def _histogram_range(samples, args, idx):
    """Range of one panel: --panel_rangex, --rangex, else --percentile or the
    extremes of all its hue samples together."""
    rangex = panel_rangex(args, idx)
    if rangex is not None:
        return tuple(rangex)
    if args.rangex is not None:
        return tuple(args.rangex)
    x = np.concatenate(samples)
    if args.percentile is None:
        return float(np.min(x)), float(np.max(x))
    return float(np.percentile(x, args.percentile[0])), float(np.percentile(x, args.percentile[1]))


def histogram(x, edges, weights=None, density=False, flow="none"):
    """(counts, underflow, overflow) of *x* in *edges*. ``flow="show"`` adds the
    outside weights to the first/last bin; density normalises what is drawn."""
    weights = np.ones_like(x) if weights is None else weights
    counts, _ = np.histogram(x, bins=edges, weights=weights)
    counts = counts.astype(float)
    under = float(np.sum(weights[x < edges[0]]))
    over = float(np.sum(weights[x > edges[-1]]))
    if flow == "show":
        counts[0] += under
        counts[-1] += over
    if density:
        total = np.sum(counts)
        if total > 0:
            counts = counts / (total * np.diff(edges))
    return counts, under, over


def _draw_flow_hints(ax, counts, edges, under, over, color):
    """Small arrows just outside the outer edges, at the edge bins' height
    (mplhep's flow="hint")."""
    for outside, x, y, marker, dx in ((under, edges[0], counts[0], "<", -4), (over, edges[-1], counts[-1], ">", 4)):
        if outside > 0:
            ax.plot([x], [y], marker=marker, markersize=5, linestyle="none", color=color, clip_on=False,
                    transform=offset_copy(ax.transData, fig=ax.figure, x=dx, units="points"))


def _series_style(args, value, name):
    """(label, mapped colour or None, line style or None) of one hue value."""
    if args.iterable == "Config":
        label = make_config_label_from_args(args, config=value, name=name)
        color, linestyle = make_config_color_and_style_from_args(args, config=value, name=name)
        return label, color, linestyle
    label = None if value is None else f"{value}"
    color = None
    if args.iterable_mapping is not None:
        label = map_iterable_label(value, args.iterable, args.iterable_mapping)
    if args.iterable_color_mapping is not None:
        color = map_iterable_color(value, args.iterable_color_mapping) or color
    return label, color, None


def draw_figure(df, args, kdx, config, name):
    variables = args.variables if args.variables is not None else [None]
    n_panels = len(variables)
    fig, axes, _, _ = create_panels(n_panels, grid=False)
    ranges = {}  # panel -> histogram range (panels may have very different scales)

    if args.iterable is not None:
        values = list(df[args.iterable].unique())
        if args.iterable_order:
            values = [v for v in args.iterable_order if v in values] + [v for v in values if v not in args.iterable_order]
    else:
        values = [None]
    colors = ColorAllocator()
    colors.reserve(values, lambda value: _series_style(args, value, name)[1])
    density = args.density or args.labely == "Density"

    for idx, variable in enumerate(variables):
        ax = axes[idx]
        series = []  # (value, x, weights) of every hue drawn in this panel
        for jdx, value in enumerate(values):
            if args.iterable is not None and len(values) > 8 and args.reduce and jdx % 2 == 1:
                continue
            rows = df
            if variable is not None:
                rows = rows[rows["Variable"] == variable]
            if value is not None:
                rows = rows[rows[args.iterable] == value]
            subset = filter_dataframe(rows, args)
            if subset.empty:
                rprint(f"[yellow]Warning:[/yellow] No data for {args.iterable}={value}, Variable={variable}. Skipping.")
                continue
            weights = np.asarray(subset[args.weight].values[0], dtype=float) if args.weight is not None else None
            series.append((value, combined_values(subset, args), weights))
        if not series:
            continue
        ranges[idx] = _histogram_range([x for _, x, _ in series], args, idx)
        edges = np.histogram_bin_edges(ranges[idx], bins=args.bins, range=ranges[idx])  # the same edges for every hue

        for value, x, weights in series:
            counts, under, over = histogram(x, edges, weights, density=density, flow=args.flow)
            label, mapped, linestyle = _series_style(args, value, name)
            color = colors.color_for(value, mapped)
            outside = int(np.sum(x < edges[0]) + np.sum(x > edges[-1]))
            if outside:
                what = f"{args.iterable}={value}" if value is not None else "the sample"
                rprint(f"[yellow]Warning:[/yellow] {outside} of {len(x)} entries of {what} (Variable={variable}) "
                       f"fall outside [{edges[0]:g}, {edges[-1]:g}] (--flow {args.flow}).")
            ax.stairs(counts, edges, label=label, color=color, linestyle=_resolve_plot_style(linestyle) or "-",
                      linewidth=style.default_linewidth)
            if args.flow == "hint":
                _draw_flow_hints(ax, counts, edges, under, over, color)

    for idx, variable in enumerate(variables):
        ax = axes[idx]
        if n_panels > 1:
            title = args.panel_title[idx] if args.panel_title is not None else make_subtitle_from_args(args, None, idx=idx)
            ax.set_title(title, fontsize=style.subtitlefontsize)
        default_x = args.labelx if args.labelx is not None else " ".join(args.x)
        ax.set_xlabel(args.panel_labelx[idx] if args.panel_labelx is not None else resolve_axis_label(default_x, None, df))
        if idx == 0:
            default_y = args.labely if args.labely is not None else ("Density" if density else "Counts")
            ax.set_ylabel(resolve_axis_label(default_y, None, df))
        rangex = panel_rangex(args, idx)
        if rangex is not None:
            ax.set_xlim(*rangex)
        elif args.rangex is None:
            ax.set_xlim(ranges.get(idx))
        else:
            ax.set_xlim(args.rangex[0], args.rangex[1])
        if args.rangey is not None:
            ax.set_ylim(args.rangey[0], args.rangey[1])
        apply_scientific_threshold_formatter(ax, threshold=0.1, axis="both")
        if args.logy:
            ax.semilogy()
        if args.logx:
            ax.semilogx()
        # A single series without --hue needs no legend.
        if idx == n_panels - 1 and args.iterable is not None and not args.no_legend and args.draw_legend != "none":
            apply_legend_style(ax, title=args.labelz or args.iterable, capitalize_labels=args.capitalize_legend)
        draw_overlays(ax, args)
        draw_panel_lines(ax, args, idx)

    add_title_and_note(fig, args)
    return save(fig, args, kdx, suffix="hist.png")


def _project_relative(path):
    """Relative file paths are read from the project root."""
    from pathlib import Path

    from ..project import load_project

    if path is None or Path(path).expanduser().is_absolute() or Path(path).exists():
        return path
    return str(load_project().root / path)


def run(args):
    args.panel_vertical_file = _project_relative(args.panel_vertical_file)
    resolve_panel_lines(args, n_panels=len(args.variables) if args.variables is not None else None, unit="--variables entry")
    df = import_data(args)
    if df.empty:
        rprint("[yellow]Warning:[/yellow] No datafiles found. Exiting...")
        return []
    if args.variables is not None and "None" in args.variables and "Variable" in df.columns:
        df["Variable"] = df["Variable"].fillna("None")

    configs, names = prepare_import(args)
    configs = configs if configs is not None and args.iterable != "Config" else [None]
    names = names if names is not None and args.iterable != "Name" else [None]
    outputs = []
    for kdx, (config, name) in enumerate(zip(configs, names)):
        rprint(f"Plotting for Config: {config}, Name: {name}")
        rows = df
        if config is not None and args.iterable != "Config":
            rows = rows[rows["Config"] == config]
        if name is not None and args.iterable != "Name":
            rows = rows[rows["Name"] == name]
        outputs.append(draw_figure(rows, args, kdx, config, name))
    return outputs


# --- Legacy command lines ----------------------------------------------------------------


def _legacy_hist1d(tokens):
    from ..legacy import has, rename

    tokens = rename(tokens, {"--operation": "--hist_combine", "-p": "--percentile"})
    if not has(tokens, "--hist_combine"):
        tokens += ["--hist_combine", "subtract"]  # the old default, part of the output name
    if not has(tokens, "--labelx"):
        tokens += ["--labelx", r"Time ($\mu$s)"]
    if not has(tokens, "--labely"):
        tokens += ["--labely", "Density"]
    return tokens + ["--output_suffix", "hist1d.png"]


LEGACY = {"script_compare_hist1d": _legacy_hist1d}
