"""line: y as a function of x, one series per hue (and style) value.

Each DataFrame row holds a series (``x`` and ``y`` arrays, optionally
``{y}Error``); rows are split into panels by ``--variables`` (the
``Variable`` column, or ``--variable_column``), into colours by ``--hue``
(``--iterable``) and into line styles by ``--style`` (``--comparable``).
One figure is drawn per ``--configs``/``--names`` pair unless
``--overlay_names``; ``--by_config`` instead draws one series per
config/name entry in a single figure, coloured by the config mappings.

Lower panels (``--lower``) show operations between the drawn series, a
stored column or a residual; see :mod:`plotipus.lower`.
"""

import json

import matplotlib
import matplotlib.lines as mlines
import matplotlib.ticker
from matplotlib.colors import to_hex
import numpy as np
import pandas as pd
from rich import print as rprint

from .. import intervals, style
from ..args import (
    add_common_args,
    add_panel_args,
    map_iterable_color,
    map_iterable_label,
    resolve_axis_label,
)
from ..encodings import (
    DATA_STYLE,
    add_encoding_args,
    comparable_legend_title,
    comparable_maps,
    draw_legends,
    fill_options,
    iterable_legend_title,
    legend_selection,
    order_values,
    resolve_linestyle,
    resolve_linewidth,
)
from ..format import _title_case_words, make_config_color_and_style_from_args, make_config_label_from_args, make_subtitle_from_args
from ..io import import_data, prepare_import
from ..lower import (
    DEFAULT_LABELS,
    REFERENCE_LINES,
    group_difference,
    operation_series,
    pairwise,
    parse_lower,
)
from ..palettes import ColorAllocator
from ..panels import (
    add_title_and_note,
    apply_axis_options,
    create_panels,
    draw_horizontal_overlay,
    draw_overlays,
    grow_for_tick_labels,
    rotate_categorical_labels,
    save,
)
from ..plot import (apply_legend_style, apply_legend_style_clear_of_data, apply_tick_formatter, order_legend_entries,
                    errory_type, plot_data)
from ..selection import filter_dataframe
from ..transforms import (
    align_error_column,
    combine,
    edges_from_centers,
    explode,
    extrapolated_segments,
    merge_groups,
    mirror,
    pick_row,
    project,
    rebin_rows,
    scale_cells,
    union_grid,
    y_error_of,
)
from . import _base

KIND = "line"
PLOT_TYPES = ["scatter", "line", "bar", "barh", "step", "stepmid", "plot", "errorbar", "box", "fill"]
EXTRAPOLATED_LINESTYLE = "--"


# --- Arguments ---------------------------------------------------------------------


def build_parser():
    parser = _base.make_parser(KIND, "Series of y against x, coloured by --hue, styled by --style, with optional lower panels.")
    add_common_args(
        parser,
        [
            "datafile", "configs", "names", "variables", "iterable", "select", "save_values",
            "remove_value", "filename_select", "filename_suffix", "x", "y", "reduce", "labelx",
            "labely", "labelz", "logx", "logy", "rangex", "rangey", "plot_style", "plot_type",
            "title", "output", "subfolder", "horizontal", "horizontal_label", "horizontal_style",
            "horizontal_color", "vertical", "vertical_label", "vertical_style", "vertical_color",
            "xtick", "xtick_label", "xtick_height", "xtick_side", "xtick_edge", "ytick",
            "ytick_label", "ytick_height", "ytick_side", "ytick_edge", "square", "square_label",
            "square_style", "square_color", "line", "line_label", "line_style", "line_color",
            "point", "point_label", "note", "multiply", "debug", "errory", "errory_type",
            "confidence_level", "error_label",
        ],
        overrides={
            "datafile": {"required": True},
            "names": {"flags": ["--names"]},
            "y": {"required": True},
            "labelx": {"nargs": "+", "help": "Label for the x axis (one per panel, or one for all)"},
            "plot_type": {
                "choices": PLOT_TYPES,
                "help": "How series are drawn: plot (markers, default), line, step (histogram outline "
                "from bin edges), stepmid (line through steps), errorbar, scatter, bar, barh, fill (each "
                "series a closed, filled shape)",
            },
        },
    )
    add_encoding_args(parser)
    add = parser.add_argument

    group = parser.add_argument_group("series")
    add = group.add_argument
    add("--overlay_names", action="store_true", default=False,
        help="Draw every --configs/--names pair in one figure instead of one figure per pair.")
    add("--overlay_name_all", action="store_true", default=False,
        help="With --overlay_names: name the output after every config/name (default: the first pair).")
    add("--by_config", action="store_true", default=False,
        help="One series per --configs/--names entry in a single figure, coloured/labelled by the "
        "config_color/config_dict/name_dict mappings; --variables are panels in one row.")
    add("--show_configs", nargs="+", type=str, default=None,
        help="With --by_config: configs actually drawn (the others are still combined by --combine_op).")
    add("--exclude_iterable", nargs="+", action="extend", default=None,
        help="Hue values left out of plot and legend.")
    add("--variable_label_map", type=str, default=None, help="JSON {panel value: panel title}.")
    add("--y_row", type=int, default=None, help="For 2D y cells, plot only this row (0-based).")
    add("--errory_column", type=str, default=None,
        help="Column holding the symmetric y error (default {y}Error).")
    add("--errory_bounds", type=str, nargs=2, default=None, metavar=("LOW", "HIGH"),
        help="Columns holding the lower and upper edges of an asymmetric y interval.")
    add("--errory_x", action="store_true", default=False, help="Also draw x error bars (half bin widths).")
    add("--count_column", type=str, default=None, metavar="N",
        help="With --errory_type clopper_pearson: array column with the number of trials of each point "
        "(k = y / --efficiency_scale * N).")
    add("--efficiency_scale", type=float, default=1.0,
        help="Value of y at 100%% efficiency, with --errory_type clopper_pearson (default 1; 100 for percent).")
    add("--extrapolate", action="store_true", default=False,
        help="Draw points flagged in '{y}Extrapolated' as a dashed continuation (dropped otherwise).")
    add("--merge_iterables", nargs="+", default=None, metavar="VALUES=LABEL",
        help="Merge groups of hue values into single summed series, e.g. '1,2=Membrane'.")
    add("--sum_iterables", nargs="+", default=None,
        help="Hue values drawn as one summed series (per style value) instead of individually.")
    add("--sum_label", type=str, default="Combined", help="Legend label of the --sum_iterables series.")
    add("--sum_color", type=str, default=None,
        help="Colour of the --sum_iterables series (default: a palette colour no hue value has).")
    add("--rebin", type=int, default=None, help="Merge every N consecutive points of each series.")
    add("--density", action="store_true", default=False,
        help="Normalise each series to unit area (y / sum of y times the bin width, errors alike), so "
        "samples of different sizes compare as shapes; the y label defaults to Density.")
    add("--rebin_sum", action="store_true", default=False,
        help="With --rebin: sum merged y values (counts) instead of averaging them.")
    add("--mirror", type=str, default=None, help="Config whose series is extended by its reflection.")
    add("--mirror_edge", action="store_true", default=False,
        help="With --mirror: reflect around the upper edge of the last bin.")
    add("--project", nargs="+", type=str, default=None,
        help="With --by_config: configs whose series are also drawn rescaled (x*--project_scale+--project_offset).")
    add("--project_offset", type=float, default=0)
    add("--project_scale", type=float, default=1)
    add("--shift", nargs="+", type=str, default=None, help="Configs/names whose x values are shifted.")
    add("--shift_offset", type=float, default=0, help="Offset added to the x values selected by --shift.")
    add("--combine", type=str, default=None,
        help="With --by_config: merge configs sharing a prefix (value 'prefix': text before the first '_').")
    add("--combine_operation", type=str, default="mean", choices=["mean", "sum"],
        help="How --combine merges values at equal x.")
    add("--combine_op", type=str, default=None, choices=["sum", "squared_sum", "mean"],
        help="With --by_config: also draw the combination of all series.")
    add("--combined_color", type=str, default=None,
        help="Colour of the --combine_op series (default: a palette colour no config has).")
    add("--combined_linestyle", type=str, default="-")
    add("--combined_linewidth", type=float, default=None)
    add("--combined_alpha", type=float, default=1.0)
    add("--combined_label", type=str, default="Combined")
    add("--prefix_by_config", action="store_true", default=False,
        help="With --by_config: start the output name with the config prefix (text before the first '_') "
        "when all drawn configs share it.")
    add("--printy", type=float, default=None, help="Print each series' y at this x.")
    add("--printx", type=float, default=None, help="Print each series' first x reaching this y.")

    group = parser.add_argument_group("drawing")
    add = group.add_argument
    add("--connect", action="store_true", default=False,
        help="Join the points: with steps without --plot_type, with lines for points with error bars.")
    add("--stacked", action="store_true", default=False,
        help="Stack the series: filled histograms over binned x (outlines with --plot_type step, filled steps "
        "with a darker edge with fill, a stacked area with line), bars over categories, with --bar_width or "
        "with --plot_type bar. --overlay values stay out of the stack.")
    add("--data_hue", "--overlay", nargs="+", default=None, metavar="VALUE",
        help="Hue values drawn as data: points with error bars in the ink colour, first in the legend, never "
        "stacked. The other series are drawn as steps (bars with --stacked), with error bands with --errory, and "
        "ratio/subtract/relative_difference lower panels compare the data with their total. The values may "
        "also be --style values: those series are drawn as points in their hue colour, and the style legend "
        "shows a point for them. With --by_config, the values are configs, names or hue values.")
    add("--stack_reverse", action="store_true", default=False, help="Stack in reverse order (first series on top).")
    add("--stack_total_error", action="store_true", default=False,
        help="With --stacked: a hatched band around the stack total, from the stacked series' errors added in "
        "quadrature (also drawn with --overlay and --errory).")
    add("--stack_total_error_column", type=str, default=None, metavar="COL",
        help="Array column with a precomputed error of the stack total (e.g. with systematics), read from the "
        "first stacked series that has it; implies --stack_total_error.")
    add("--overlay_legend", choices=["first", "last"], default="first",
        help="Legend position of the --overlay (--data_hue) entries: before the stack (default) or after it.")
    add("--bar_width", type=str, default=None,
        help="Stack as bars of this width: a number, or 'auto' for the x spacing without edges (default: "
        "filled histograms over binned x, bars of width 0.8 over categories).")
    add("--dodge", type=float, default=0.0,
        help="With --plot_type errorbar: shift each hue value sideways by this amount.")
    add("--step_open", action="store_true", default=False,
        help="Draw --plot_type step outlines without the baseline edges.")
    add("--align", type=str, default="mid", help="Alignment of step outlines (mid, left, right).")
    add("--compact", action="store_true", default=False, help="Hide repeated y labels/ticks on inner panels.")
    add("--vertical_per_variable", type=str, default=None, help="JSON {panel value: [x positions]}.")
    add("--vertical_column_map", type=str, default=None,
        help="JSON {panel value: column}: vertical line per hue value at that column's value, in its colour.")
    add("--vertical_column_style", type=str, default="--")
    add("--mean_band", action="store_true", default=False,
        help="Horizontal line at the mean of all y values with a +-1 std band.")

    group = parser.add_argument_group("lower panels")
    add = group.add_argument
    add("--lower", action="append", default=None,
        help="Lower panel (repeatable): an operation between series (ratio, subtract, relative_difference, "
        "asymmetry, excess, excess_probability, add, multiply, sum, mean, rms), residual/pull, "
        "column:NAME (stored series) or events:PREFIX.")
    add("--lower_across", choices=["hue", "comparable"], default="hue",
        help="Pairwise lower operations compare hue series (default) or, per hue value, style series.")
    add("--reference", type=int, default=0, help="Index of the reference series of pairwise operations.")
    add("--reference_value", type=str, default=None, help="Reference series by hue value (overrides --reference).")
    add("--lower_line_index", type=int, default=1,
        help="With --lower_across comparable: index of the style value compared with the reference.")
    add("--reference_sum", nargs="+", default=None, help="Hue values summed into one series before the operation.")
    add("--reference_sum_label", type=str, default=None)
    add("--reference_sum_color", type=str, default=None,
        help="Colour of the --reference_sum series (default: a palette colour no hue value has).")
    add("--reference_group", nargs="+", default=None,
        help="Hue values summed (weighted) into the left side of a group comparison (with --other_group).")
    add("--reference_group_weights", nargs="+", type=float, default=None)
    add("--reference_group_label", type=str, default=None)
    add("--other_group", nargs="+", default=None, help="Hue values summed into the right side of the comparison.")
    add("--other_group_weights", nargs="+", type=float, default=None)
    add("--other_group_label", type=str, default=None)
    add("--show_stat_error", action="store_true", default=False, help="Group comparison drawn with error bars.")
    add("--group_diff_uncorrelated", action="store_true", default=False,
        help="Combine the two group sums as independent (a shared series does not cancel).")
    add("--group_diff_relative", action="store_true", default=False,
        help="Group difference in percent of the other group's sum.")
    add("--group_significance", action="store_true", default=False,
        help="Per-point S/sqrt(B) of the two group sums instead of their difference.")
    add("--group_significance_min_background", type=float, default=0.0)
    add("--lower_comparable_value", type=str, default=None,
        help="Group comparison only for this style value.")
    add("--lower_label_mapping", type=str, default=None,
        help="Mapping renaming the default lower label (keyed by operation or column).")
    add("--lower_zero_line", action="store_true", default=False, help="Dashed reference line at y=0 on lower panels.")
    add("--lower_zero_color", type=str, default=None,
        help="Colour of the y=0 lines of lower panels (default: the style's muted role; 'red' restores the old look).")
    add("--lower_log_format", choices=["scientific", "plain"], default=None)
    add("--lower_legend_loc", type=str, default=None)
    add("--no_lower_legend", action="store_true", default=False)
    add("--no_lower_plot", action="store_true", default=False, help="Ignore --lower.")
    add("--no_lower_name", action="store_true", default=False,
        help="Leave the lower operation/column out of the output name.")
    add("--lower_series_donor", nargs=2, metavar=("FROM", "TO"), default=None,
        help="Copy the lower column (column:NAME) from the rows of hue FROM onto those of hue TO.")
    add_panel_args(parser, "lower_")
    from ._estimator import add_estimator_args
    from ._events import add_events_args
    from ._fit import add_fit_args

    add_fit_args(parser)
    add_estimator_args(parser)
    add_events_args(parser)
    _add_shape_args(parser)
    _base.add_output_args(parser)
    return parser


def _add_shape_args(parser):
    group = parser.add_argument_group("shapes (per-series styling from the data)")
    add = group.add_argument
    add("--color_column", default=None,
        help="Column giving each series its colour (face of --plot_type fill, else the line colour); "
        "matplotlib colours, rgb(...) or role:NAME. Wins over the palette; an --iterable_color_mapping "
        "entry still wins over the data.")
    add("--edgecolor_column", default=None, help="Column giving each filled shape its edge colour ('none' for no edge).")
    add("--linewidth_column", default=None, help="Column giving each series its line (or edge) width.")
    add("--plot_type_column", default=None,
        help="Column giving each series its plot type (any --plot_type value), e.g. fill for shapes and "
        "line for strokes in one figure.")
    add("--facecolor", default=None, help="One face colour for every filled shape (overrides --color_column).")
    add("--edgecolor", default=None,
        help="One colour for every edge of a filled shape and every line (overrides the data).")
    add("--axis", nargs="+", choices=["equal", "off"], default=None,
        help="equal: one data unit is as long on x as on y; off: no frame, ticks or labels.")


def _check_args(args, parser):
    if args.binned:
        from ._estimator import resolve_estimator_args

        resolve_estimator_args(args, parser)
    elif args.y is None:
        parser.error("the following arguments are required: -y")


def main(argv=None):
    return _base.main(__import__(__name__, fromlist=["run"]), argv)


def parse(argv=None):
    """Parse (and check) line arguments."""
    parser = build_parser()
    args = parser.parse_args(argv)
    _check_args(args, parser)
    return args


# --- Loading -----------------------------------------------------------------------


def _lower_specs(args):
    if getattr(args, "no_lower_plot", False):
        return []
    return [parse_lower(spec) for spec in (args.lower or [])]


def _donate_lower_column(df, args):
    donor = getattr(args, "lower_series_donor", None)
    columns = [s.name for s in _lower_specs(args) if s.kind == "column"]
    if not donor or not columns or args.iterable not in df.columns:
        return df
    source, target = donor
    copy_cols = [c for name in columns for c in (name, f"{name}Error") if c in df.columns]
    keys = [c for c in ("Config", "Name", "SpectrumType", "Study", "Variable") if c in df.columns]
    for index in df.index[df[args.iterable].astype(str) == target]:
        match = df[df[args.iterable].astype(str) == source]
        for key in keys:
            match = match[match[key] == df.at[index, key]]
        if len(match):
            for column in copy_cols:
                df.at[index, column] = match.iloc[0][column]
    return df


def load(args):
    """Load the frame and apply the row transforms (y row, rebin, error
    columns, panel column, scaling, merged hue groups)."""
    df = import_data(args)
    if df.empty:
        return df
    df = _donate_lower_column(df, args)

    y = args.y
    if args.y_row is not None:
        df[y] = df[y].apply(lambda v: pick_row(v, args.y_row))

    # Error columns: 'Error' (symmetric) or 'ErrorLow'/'ErrorHigh' (sizes).
    if args.errory_bounds is not None:
        low, high = args.errory_bounds
        df["ErrorLow"] = [np.asarray(v, dtype=float) - np.asarray(lo, dtype=float) for v, lo in zip(df[y], df[low])]
        df["ErrorHigh"] = [np.asarray(hi, dtype=float) - np.asarray(v, dtype=float) for v, hi in zip(df[y], df[high])]
    elif args.errory_column is not None:
        df["Error"] = df[args.errory_column]
    elif f"{y}Error" in df.columns:
        df["Error"] = df[f"{y}Error"]
    elif f"{y}Error+" in df.columns and f"{y}Error-" in df.columns:
        df["ErrorLow"] = df[f"{y}Error-"]
        df["ErrorHigh"] = df[f"{y}Error+"]

    error_columns = [c for c in ("Error", "ErrorLow", "ErrorHigh") if c in df.columns]
    # --by_config rebins its concatenated series itself (summing y).
    if args.rebin and args.rebin > 1 and args.x in df.columns and not args.by_config:
        df = rebin_rows(df, args.x, y, args.rebin, sum_y=args.rebin_sum, error_columns=error_columns)

    if args.multiply is not None:
        df = scale_cells(df, [y, *error_columns], args.multiply)
    if args.merge_iterables and args.iterable in df.columns:
        df = merge_groups(df, args.iterable, y, args.merge_iterables, error_columns=[c for c in ("Error",) if c in df.columns])
    # NaN panel values are dropped unless --variables asks for "None".
    if args.variables is not None and "None" in args.variables and "Variable" in df.columns:
        df["Variable"] = df["Variable"].fillna("None")
    return df


# --- Series ------------------------------------------------------------------------


class Series:
    """One drawn series and its encodings."""

    def __init__(self, x, y, error=None, x_edges=None, extrapolated=None, categorical=False, rows=None):
        self.x = x
        self.y = y
        self.error = error
        self.x_edges = x_edges
        self.extrapolated = extrapolated if extrapolated is not None else np.zeros(len(x), dtype=bool)
        self.categorical = categorical
        self.rows = rows
        self.hue = None
        self.hue_label = None
        self.comparable = None
        self.comparable_index = 0
        self.color = None
        self.edgecolor = None
        self.linestyle = None
        self.linewidth = None
        self.fill_alpha = None
        self.fill_hatch = None
        self.label = None
        self.is_sum = False
        self.is_data = False
        self.interval = None  # poisson / clopper_pearson errors


def extract(subset, args, x_column=None, y_column=None):
    """Explode the rows of one series into a :class:`Series` (None when
    empty). Non-numeric x gives a categorical series."""
    x_column = x_column or args.x
    y_column = y_column or args.y
    columns = [x_column, y_column]
    for error_column in ("Error", "ErrorLow", "ErrorHigh"):
        if error_column in subset.columns:
            subset = align_error_column(subset, y_column, error_column)
            columns.append(error_column)
    extrapolated_column = f"{y_column}Extrapolated"
    points = explode(subset, columns)
    if points.empty:
        return None

    raw_extrapolated = points[extrapolated_column].to_numpy() if extrapolated_column in points.columns else None
    try:
        y = points[y_column].astype(float).to_numpy()
    except (ValueError, TypeError):
        return None
    try:
        x = points[x_column].astype(float).to_numpy()
    except (ValueError, TypeError):
        x = points[x_column].astype(str).to_numpy()
        return Series(x, y, error=y_error_of(points), categorical=True, rows=subset)

    error = y_error_of(points)
    mask = ~np.isnan(x) & ~np.isnan(y)
    x, y = x[mask], y[mask]
    if error is not None:
        error = error[..., mask]
    extrapolated = (
        pd.array(raw_extrapolated[mask], dtype="boolean").fillna(False).to_numpy(dtype=bool)
        if raw_extrapolated is not None
        else np.zeros(len(x), dtype=bool)
    )
    if extrapolated.any() and not args.extrapolate:
        keep = ~extrapolated
        x, y = x[keep], y[keep]
        if error is not None:
            error = error[..., keep]
        extrapolated = np.zeros(len(x), dtype=bool)
    if len(x) == 0:
        return None
    return Series(x, y, error=error, x_edges=edges_from_centers(x), extrapolated=extrapolated, rows=subset)


def _sum_series(series_list):
    """Point-by-point sum of equally long series (others are skipped)."""
    total = None
    for s in series_list:
        if s is None or s.categorical:
            continue
        if total is None:
            total = Series(s.x, np.array(s.y, dtype=float), x_edges=s.x_edges, rows=s.rows)
        elif len(s.y) == len(total.y):
            total.y = total.y + s.y
    return total


# --- Drawing -----------------------------------------------------------------------


def _resolved_plot_type(args, prefix=""):
    return getattr(args, f"{prefix}plot_type", None) or args.plot_type


def _bar_width(x):
    try:
        values = np.unique(np.asarray(x, dtype=float))
    except (TypeError, ValueError):
        return 0.8
    steps = np.diff(values)
    steps = steps[steps > 0]
    return float(np.min(steps)) if steps.size else 0.8


def _error_kwargs(s, args):
    if s.error is None or not (args.errory or getattr(s, "show_error", False)):
        return {}
    symmetric = np.ndim(s.error) == 1
    return {"errory": s.error, "errory_sym": "symmetric" if symmetric else "asymmetric"}


_DENSITY_WARNED = set()


def _to_density(s, args):
    """Scale series ``s`` (and its errors) to unit area (--density). Stacked
    series keep their counts: a stack needs one factor for all its parts."""
    if args.stacked:
        if "stacked" not in _DENSITY_WARNED:
            _DENSITY_WARNED.add("stacked")
            rprint("[yellow]Warning:[/yellow] --density is ignored with --stacked.")
        return
    if s.categorical or s.x_edges is None:
        return
    area = float(np.nansum(np.asarray(s.y, dtype=float) * np.diff(s.x_edges)))
    if not np.isfinite(area) or area == 0:
        return
    s.y = np.asarray(s.y, dtype=float) / area
    if s.error is not None:
        s.error = np.asarray(s.error, dtype=float) / area


def _interval_errors(s, args):
    """Replace the errors of ``s`` by an interval: --errory_type poisson
    (Garwood, y as counts; also the default for --overlay data without an
    error column) or clopper_pearson (y an efficiency of --count_column
    trials). Stored as 2xN (below, above) distances, never crossing 0 (or
    100% for efficiencies)."""
    kind = args.errory_type if args.errory_type in ("poisson", "clopper_pearson") else None
    if kind is None and s.is_data and s.error is None and not s.categorical:
        kind = "poisson"
    if kind is None:
        return
    y = np.asarray(s.y, dtype=float)
    if kind == "poisson":
        low, high = intervals.garwood(y, args.confidence_level)
    else:
        if not args.count_column or s.rows is None or args.count_column not in s.rows.columns:
            rprint("[yellow]Warning:[/yellow] --errory_type clopper_pearson needs --count_column (the trials); "
                   "the stored errors are kept.")
            return
        counts = extract(s.rows, args, y_column=args.count_column)
        if counts is None or len(counts.y) != len(y):
            rprint(f"[yellow]Warning:[/yellow] {args.count_column} does not align with {args.y}; no interval drawn.")
            return
        total = np.asarray(counts.y, dtype=float)
        passed = np.round(y / args.efficiency_scale * total)
        low, high = intervals.clopper_pearson(passed, total, args.confidence_level)
        low, high = low * args.efficiency_scale, high * args.efficiency_scale
    s.error = np.vstack([np.clip(y - low, 0, None), np.clip(high - y, 0, None)])
    s.interval = kind


def _is_data(hue, args):
    """Whether hue value ``hue`` is drawn as data (--data_hue)."""
    return bool(args.data_hue) and not isinstance(hue, _SumSlot) and str(hue) in {str(v) for v in args.data_hue}


def draw_series(ax, s, args, plot_type=None, stack_bottom=None, dodge_shift=0.0):
    """Draw one series with the plot type rules of the line kind: without
    --plot_type, markers (error bars with --errory, a line with
    --errory_type bands, steps with --connect, lines for styled series).
    Error bars on points are joined only with --connect. Plot type "data"
    draws points with their error bars whatever --errory_type says."""
    stacking = args.stacked and stack_bottom is not None and s.x_edges is not None and not s.categorical
    if plot_type == "fill" and not stacking:  # closed shapes; stacked, fill is filled steps (below)
        face = _shape_color(args.facecolor) or s.color
        edge = _shape_color(args.edgecolor) or s.edgecolor or "none"
        width = s.linewidth if s.linewidth is not None else (style.default_linewidth if edge != "none" else 0)
        ax.fill(s.x, s.y, facecolor=face, edgecolor=edge, linewidth=width, joinstyle="round", label=s.label)
        return
    if args.edgecolor:
        s.color = _shape_color(args.edgecolor)  # strokes take the edge colour too
    common = dict(label=s.label, color=s.color)
    if plot_type == "band":
        # Only the shaded y ± error, stepwise over the bins (a reference band).
        error = np.asarray(s.error, dtype=float)
        ax.stairs(s.y + error, s.x_edges, baseline=s.y - error, fill=True, color=s.color, alpha=style.band_alpha,
                  linewidth=0, label=s.label)
        return
    if plot_type == "data":
        xerr = np.diff(s.x_edges) / 2 if args.errory_x and s.x_edges is not None else None
        plot_data(args, ax, s.x, y=s.y, plot_type="errorbar", yerr=s.error, xerr=xerr, fmt="o", zorder=3, **common)
        return
    lw = {} if s.linewidth is None else {"linewidth": s.linewidth}
    fill = {}
    if s.fill_alpha is not None:
        fill = {"fill_alpha": s.fill_alpha, "fill_hatch": s.fill_hatch, "fill_hatch_color": args.fill_hatch_color}
    linestyle = s.linestyle if s.linestyle is not None else args.plot_style

    if stacking and (plot_type in ("step", "fill", "line") or (plot_type is None and args.bar_width is None)):
        # Binned series stack in data space: each one from the running total up (bars with --bar_width or
        # --plot_type bar).
        bottom = np.array(stack_bottom, dtype=float)  # a copy: the running stack grows in place
        top = bottom + np.asarray(s.y, dtype=float)
        if plot_type == "line":
            ax.fill_between(s.x, bottom, top, linewidth=0, **common)
        elif plot_type == "step":
            # Each outline is its top and its two outer sides: a closed outline would draw its bottom edge
            # over the top of the series below.
            line = dict(color=s.color, linestyle=linestyle,
                        linewidth=s.linewidth if s.linewidth is not None else style.default_linewidth)
            outline = ax.stairs(top, s.x_edges, baseline=None, label=s.label, **line)
            outline.sticky_edges.y.append(0)  # the axis starts at 0, as for filled stacks
            ax.vlines([s.x_edges[0], s.x_edges[-1]], [bottom[0], bottom[-1]], [top[0], top[-1]], **line)
        elif plot_type == "fill":
            ax.stairs(top, s.x_edges, baseline=bottom, fill=True, facecolor=s.color,
                      edgecolor=style._mix(s.color, style.role("ink"), 0.7), linewidth=1, label=s.label)
        else:
            ax.stairs(top, s.x_edges, baseline=bottom, fill=True, **common)
        return
    if args.stacked and stack_bottom is not None and plot_type in (None, "bar"):
        width = {}
        if args.bar_width == "auto":
            width = {"width": _bar_width(s.x), "edgecolor": "none", "linewidth": 0}
        elif args.bar_width is not None:
            width = {"width": float(args.bar_width)}
        plot_data(args, ax, s.x, y=s.y, plot_type="bar", bottom=stack_bottom, **width, **common)
        return

    if plot_type is None:
        if s.error is not None and args.errory:
            if errory_type(args, "errorbar") == "bands":
                plot_data(args, ax, s.x, y=s.y, plot_type="line", linestyle=linestyle, **common,
                          **_error_kwargs(s, args), **lw)
            else:
                plot_data(args, ax, s.x, y=s.y, plot_type="errorbar", errory=s.error, fmt="o", linestyle=linestyle,
                          **common)
        elif args.connect:
            plot_data(args, ax, s.x, x_edges=s.x_edges, y=s.y, plot_type="step", linestyle=linestyle, **common, **fill, **lw)
        elif s.comparable is not None:
            plot_data(args, ax, s.x, y=s.y, plot_type="line", linestyle=linestyle, **common)
        else:
            plot_data(args, ax, s.x, y=s.y, plot_type="plot", marker="o", linestyle="None", **common)
        return

    if plot_type == "line":
        if s.extrapolated.any():
            x_norm, y_norm, x_ext, y_ext = extrapolated_segments(s.x, s.y, s.extrapolated)
            plot_data(args, ax, x_norm, y=y_norm, plot_type="line", linestyle=linestyle, **common, **lw)
            plot_data(args, ax, x_ext, y=y_ext, plot_type="line", linestyle=EXTRAPOLATED_LINESTYLE, color=s.color, **lw)
        else:
            plot_data(args, ax, s.x, y=s.y, plot_type="line", linestyle=linestyle, **common, **_error_kwargs(s, args), **lw)
    elif plot_type == "step":
        plot_data(args, ax, s.x, x_edges=s.x_edges, y=s.y, plot_type="step", linestyle=linestyle, **common, **fill,
                  **_error_kwargs(s, args), **lw)
    elif plot_type == "stepmid":
        plot_data(args, ax, s.x, y=s.y, plot_type="plot", drawstyle="steps-mid", linestyle=linestyle, **common, **fill,
                  **_error_kwargs(s, args), **lw)
    elif plot_type == "errorbar":
        x = s.x
        if dodge_shift:
            x = np.asarray(s.x, dtype=float) + dodge_shift if not s.categorical else s.x
        xerr = None
        if args.errory_x and s.x_edges is not None:
            xerr = np.diff(s.x_edges) / 2
        plot_data(args, ax, x, y=s.y, errorx=xerr, plot_type="errorbar", fmt="o", linestyle=linestyle, **common,
                  **_error_kwargs(s, args))
    elif plot_type == "scatter":
        plot_data(args, ax, s.x, y=s.y, errory=s.error, plot_type="scatter", fmt="o", **common)
    elif plot_type in ("bar", "barh"):
        plot_data(args, ax, s.x, y=s.y, plot_type=plot_type, **common)
    else:
        plot_data(args, ax, s.x, y=s.y, plot_type="plot", marker="o", linestyle=linestyle, **common, **lw)


def _shape_color(value):
    """A colour from the data or the command line (``role:NAME`` and ``rgb(...)`` too)."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    return style.resolve_mapped_color(str(value))


def _row_value(s, column):
    """The value of ``column`` in the first row of series ``s`` (None if absent)."""
    if column is None or s.rows is None or column not in s.rows.columns or s.rows.empty:
        return None
    value = s.rows[column].iloc[0]
    return None if value is None or (isinstance(value, float) and np.isnan(value)) else value


def _dodge_categorical(ax, s, shift):
    """Place a categorical series at integer category positions + ``shift``."""
    categories = getattr(ax, "_dodge_categories", [])
    categories += [v for v in s.x if v not in categories]
    ax._dodge_categories = categories
    positions = np.array([categories.index(v) for v in s.x], dtype=float) + shift
    ax.set_xticks(range(len(categories)), categories)
    ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_xlim(-0.5, len(categories) - 0.5)
    return positions


# --- Figure (hue/style series) ------------------------------------------------------


def _panel_rows(rows, variable):
    if variable is None or "Variable" not in rows.columns:
        return rows
    return rows[rows["Variable"] == variable]


def _hue_values(filtered, args):
    if args.iterable is None:
        return [None]
    values = list(filtered[args.iterable].dropna().unique()) if args.iterable in filtered.columns else []
    exclude = {str(v) for v in (args.exclude_iterable or [])}
    values = [v for v in values if str(v) not in exclude]
    return order_values(values, args)


def _with_sum_slot(values, args):
    """Insert the --sum_iterables label among the hue values: at its position
    in --iterable_color_mapping when listed there, else last."""
    if not args.sum_iterables:
        return values
    sum_set = {str(s) for s in args.sum_iterables}
    values = [v for v in values if str(v) not in sum_set]
    label = args.sum_label
    mapping = style.get_mapping_dict(args.iterable_color_mapping)
    if mapping is not None and label in mapping:
        keys = list(mapping.keys())
        position = len(values)
        for i, v in enumerate(values):
            if str(v) in mapping and keys.index(str(v)) > keys.index(label):
                position = i
                break
        return values[:position] + [_SumSlot(label)] + values[position:]
    return values + [_SumSlot(label)]


class _SumSlot(str):
    """Marker for the summed --sum_iterables series in the hue order."""


def draw_figure(rows, args, kdx=None):
    """Draw (and save) one figure of hue/style series with optional lower panels."""
    variables = args.variables if args.variables is not None else [None]
    specs = _lower_specs(args)
    fig, upper, lower, (nrows, ncols) = create_panels(len(variables), n_lower=len(specs))
    n_panels = len(variables)

    rows = rows[rows[args.iterable].notna()] if args.iterable is not None and args.iterable in rows.columns else rows
    filtered = filter_dataframe(rows, args)
    hue_values = _with_sum_slot(_hue_values(filtered, args), args)
    regular = [v for v in hue_values if not isinstance(v, _SumSlot)]
    reduce_active = args.reduce and len(hue_values) > 8
    drawn_hues = [v for j, v in enumerate(hue_values) if not (reduce_active and j % 2 == 1)]
    style_index = {v: i for i, v in enumerate(v for v in drawn_hues if not isinstance(v, _SumSlot))}
    n_style = len(style_index) + (1 if args.sum_iterables else 0)

    comparable = args.comparable if args.comparable is not None and args.comparable in rows.columns else None
    # --hue X --style X: one series per value, drawn in its own colour and line style under one legend.
    same_column = comparable is not None and comparable == args.iterable
    if same_column:
        comparable = None
    comparable_values = list(filtered[comparable].dropna().unique()) if comparable else []
    if args.comparable_order_reverse:
        comparable_values = comparable_values[::-1]
    invert = args.invert_style and not same_column
    # --data_hue naming --style values: those series are data, drawn first; the line styles go to the rest.
    data_styles = [v for v in comparable_values if _is_data(v, args)] if not invert else []
    if data_styles:
        comparable_values = data_styles + [v for v in comparable_values if v not in data_styles]
    # Colours from the data or one --facecolor: only mapped values are allocated (no overflow warning).
    allocated = [v for v in drawn_hues if not _is_data(v, args)]
    if args.facecolor:
        allocated = []
    elif args.color_column:
        allocated = [v for v in allocated if map_iterable_color(v, args.iterable_color_mapping) is not None]
    colors = _allocate_colors(allocated, comparable_values, args, invert)

    style_map, alpha_map = ({}, {}) if invert else comparable_maps(comparable_values, comparable, args)
    if data_styles:
        model_styles = [v for v in comparable_values if v not in data_styles]
        style_map = {
            map_iterable_label(v, comparable, args.comparable_mapping):
                DATA_STYLE if v in data_styles else resolve_linestyle(model_styles.index(v), args, n_total=len(model_styles))
            for v in comparable_values
        }
        alpha_map = {}
    iterable_style_map = {}
    if invert and n_style > 1:
        for value, index in style_index.items():
            label = map_iterable_label(value, args.iterable, args.iterable_mapping, len(hue_values))
            iterable_style_map[label] = resolve_linestyle(index, args, n_total=n_style, reverse=args.iterable_reverse)
        if args.sum_iterables:
            iterable_style_map[args.sum_label] = resolve_linestyle(len(style_index), args, n_total=n_style, reverse=args.iterable_reverse)

    legend_panel = args.legend_panel % n_panels
    labeled = set()
    drawn = {i: [] for i in range(n_panels)}  # panel -> [Series]
    last_x = np.array([])
    extrapolated_axes = {}
    vertical_map = json.loads(args.vertical_column_map) if args.vertical_column_map else {}
    sum_set = {str(s) for s in (args.sum_iterables or [])}

    for idx, variable in enumerate(variables):
        ax = upper[idx]
        panel_rows = _panel_rows(rows, variable)
        stack_bottoms = {}
        ordered = drawn_hues[::-1] if args.stacked and args.stack_reverse else drawn_hues
        # Data first: first in the legend, drawn above the rest by its zorder.
        ordered = [v for v in ordered if _is_data(v, args)] + [v for v in ordered if not _is_data(v, args)]
        for jdx, hue in enumerate(ordered):
            hue_rows = panel_rows if hue is None else panel_rows[panel_rows[args.iterable] == hue] if not isinstance(hue, _SumSlot) else None
            for sdx, comparable_value in enumerate(comparable_values or [None]):
                if isinstance(hue, _SumSlot):
                    members = []
                    for member in args.sum_iterables:
                        member_rows = panel_rows[panel_rows[args.iterable].astype(str) == str(member)]
                        if comparable_value is not None:
                            member_rows = member_rows[member_rows[comparable] == comparable_value]
                        members.append(extract(filter_dataframe(member_rows, args), args))
                    s = _sum_series(members)
                    if s is None:
                        continue
                    s.is_sum = True
                else:
                    subset = hue_rows if comparable_value is None else hue_rows[hue_rows[comparable] == comparable_value]
                    s = extract(filter_dataframe(subset, args), args)
                    if s is None:
                        rprint(f"[yellow]Warning:[/yellow] No data for {args.iterable}={hue}"
                               + (f", {comparable}={comparable_value}" if comparable_value is not None else "")
                               + f", Variable={variable}. Skipping.")
                        continue
                s.hue = hue
                s.is_data = _is_data(hue, args) or comparable_value in data_styles
                s.data_by_style = comparable_value in data_styles
                _interval_errors(s, args)
                if args.density:
                    _to_density(s, args)
                s.comparable = comparable_value
                s.comparable_index = sdx
                _encode(s, args, hue_values, colors, style_index, n_style, comparable, comparable_values, invert,
                        same_column)
                key = s.comparable if invert and comparable_value is not None else hue
                if idx == legend_panel and key not in labeled and not (invert and s.is_sum and comparable_value is not None):
                    s.label = s.comparable_label if invert and comparable_value is not None else s.hue_label
                    if s.is_sum and sdx != 0 and not invert:
                        s.label = None
                    else:
                        labeled.add(key)

                plot_type = _row_value(s, args.plot_type_column) or _resolved_plot_type(args)
                if s.is_data:
                    plot_type = "data"
                elif plot_type is None and args.data_hue and not args.stacked:
                    plot_type = "step"
                bottom = None
                if args.stacked and not s.is_data:
                    bottom = stack_bottoms.setdefault(comparable_value, np.zeros(len(s.y), dtype=float))
                    if len(bottom) != len(s.y):
                        bottom = None
                if s.categorical and plot_type == "errorbar" and args.dodge and len(regular) > 1:
                    shift = (jdx - (len(regular) - 1) / 2) * args.dodge
                    s.x = _dodge_categorical(ax, s, shift)
                    draw_series(ax, s, args, plot_type)
                else:
                    shift = (jdx - (len(regular) - 1) / 2) * args.dodge if args.dodge and len(regular) > 1 else 0.0
                    draw_series(ax, s, args, (plot_type or "line") if s.is_sum else plot_type,
                                stack_bottom=bottom, dodge_shift=shift)
                if bottom is not None:
                    bottom += s.y
                if s.extrapolated.any() and plot_type == "line":
                    extrapolated_axes.setdefault(ax, []).append((s.label or s.hue_label, s.color))
                vertical_column = vertical_map.get(str(variable))
                if vertical_column and s.rows is not None and vertical_column in s.rows.columns:
                    for value in pd.to_numeric(s.rows[vertical_column], errors="coerce").dropna().unique():
                        ax.axvline(float(value), color=s.color, linestyle=args.vertical_column_style,
                                   linewidth=1.2, alpha=0.85, zorder=1)
                drawn[idx].append(s)
                last_x = s.x

    if args.stacked and (args.stack_total_error or args.stack_total_error_column or (args.data_hue and args.errory)):
        for idx, series in drawn.items():
            _draw_stack_error(upper[idx], series, args)

    if not any(drawn.values()):
        rprint("[yellow]Warning:[/yellow] No valid series to plot.")
        matplotlib.pyplot.close(fig)
        return None

    for idx, specs_axes in enumerate(lower):
        for spec, lower_ax in zip(specs, specs_axes):
            _draw_lower(lower_ax, spec, drawn[idx], args, comparable, comparable_values, colors)

    _finish_upper(fig, upper, lower, drawn, rows, args, variables, last_x, hue_values, comparable,
                  style_map, alpha_map, iterable_style_map, extrapolated_axes, nrows, ncols)

    suffix = "stacked_line.png" if args.stacked else "line.png"
    return save(fig, args, kdx, suffix=suffix)


_SUM_KEY = ("sum",)


def _stack_total_error(stacked, args):
    """Error of the stack total: --stack_total_error_column of the first
    stacked series that has it, else the stacked errors in quadrature (None
    when one is missing)."""
    column = getattr(args, "stack_total_error_column", None)
    if column:
        for s in stacked:
            if s.rows is not None and column in s.rows.columns:
                value = s.rows[column].iloc[0]
                if np.ndim(value) == 1 and len(value) == len(s.y):
                    return np.asarray(value, dtype=float)
        rprint(f"[yellow]Warning:[/yellow] No stacked series has a {column} array of matching length; "
               "using the stacked errors.")
    if any(s.error is None or np.ndim(s.error) != 1 for s in stacked):
        return None
    return np.sqrt(np.sum([np.square(np.asarray(s.error, dtype=float)) for s in stacked], axis=0))


def _draw_stack_error(ax, series, args):
    """Hatched band of the stacked simulation's total ± its error (--stack_total_error, or --overlay with
    --errory), styled by the style file's plot_settings.stack_error (label, hatch, color)."""
    stacked = [s for s in series if not s.is_data and not s.is_sum and not s.categorical]
    if not stacked or any(len(s.y) != len(stacked[0].y) for s in stacked):
        return
    total = np.sum([np.asarray(s.y, dtype=float) for s in stacked], axis=0)
    error = _stack_total_error(stacked, args)
    if error is None:
        rprint("[yellow]Warning:[/yellow] The stack total error needs an error for every stacked series; "
               "no band drawn.")
        return
    band = style.role_colors(style.stack_error)
    ax.stairs(total + error, stacked[0].x_edges, baseline=total - error, fill=False, hatch=band["hatch"] or None,
              color=band["color"], linewidth=0, label=band["label"], zorder=2.5)


def _allocate_colors(hue_values, comparable_values, args, invert):
    """The figure's :class:`ColorAllocator` with the hue values (with
    --invert_style, the comparable values) assigned in draw order: mapped
    colours first, the palette for the rest (from its end with
    --iterable_reverse/--comparable_reverse), the sum series after them."""
    colors = ColorAllocator()
    if invert and comparable_values:
        values, reverse = list(comparable_values), args.comparable_reverse
    else:
        values, reverse = [v for v in hue_values if not isinstance(v, _SumSlot)], args.iterable_reverse
    colors.reserve(values, lambda value: map_iterable_color(value, args.iterable_color_mapping))
    for value in values[::-1] if reverse else values:
        colors.color_for(value)
    if args.sum_iterables and not (invert and comparable_values):
        colors.color_for(_SUM_KEY, args.sum_color or map_iterable_color(args.sum_label, args.iterable_color_mapping))
    return colors


def _encode(s, args, hue_values, colors, style_index, n_style, comparable, comparable_values, invert, same_column=False):
    """Colour, line style, width and fill of a series."""
    n_comparable = len(comparable_values)
    sdx = s.comparable_index
    if s.is_sum:
        s.hue_label = args.sum_label
    else:
        s.hue_label = map_iterable_label(s.hue, args.iterable, args.iterable_mapping, len(hue_values)) if args.iterable else None
    s.comparable_label = (
        map_iterable_label(s.comparable, comparable, args.comparable_mapping) if s.comparable is not None else None
    )

    if invert and s.comparable is not None:
        s.color = (args.sum_color if s.is_sum else None) or colors.color_for(s.comparable)
        index = len(style_index) if s.is_sum else style_index.get(s.hue, 0)
        s.linestyle = resolve_linestyle(index, args, n_total=n_style, reverse=args.iterable_reverse)
    elif s.is_data and not getattr(s, "data_by_style", False):
        s.color = map_iterable_color(s.hue, args.iterable_color_mapping) or style.role("ink")
    elif s.is_data:
        s.color = colors.color_for(s.hue)  # data told apart by --style: in its hue colour
    else:
        from_data = args.facecolor or (_row_value(s, args.color_column) is not None
                                       and map_iterable_color(s.hue, args.iterable_color_mapping) is None)
        s.color = None if from_data else colors.color_for(_SUM_KEY if s.is_sum else s.hue)
        if s.comparable is not None:
            model = [v for v in comparable_values if not _is_data(v, args)]
            if len(model) < n_comparable and s.comparable in model:
                s.linestyle = resolve_linestyle(model.index(s.comparable), args, n_total=len(model))
            else:
                s.linestyle = resolve_linestyle(sdx, args, n_total=n_comparable)
        elif same_column:
            # Line style by position: with 10 colours and 4 styles, distinct pairs for up to 20 values.
            index = len(style_index) if s.is_sum else style_index.get(s.hue, 0)
            s.linestyle = resolve_linestyle(index, args, n_total=n_style)
        else:
            s.linestyle = None

    if s.comparable is not None:
        s.linewidth = resolve_linewidth(sdx, args, n_total=n_comparable)
        s.fill_alpha, s.fill_hatch = fill_options(sdx, args, n_comparable)
    elif args.fill:
        s.fill_alpha, s.fill_hatch = fill_options(0, args, 1)

    # Styling stored in the data (--color_column and friends) wins over the palette; a
    # --iterable_color_mapping entry still wins over the data.
    data_color = _shape_color(_row_value(s, args.color_column))
    if data_color is not None and map_iterable_color(s.hue, args.iterable_color_mapping) is None:
        s.color = data_color
    s.edgecolor = _shape_color(_row_value(s, args.edgecolor_column))
    width = _row_value(s, args.linewidth_column)
    if width is not None:
        s.linewidth = float(width)


# --- Lower panels ------------------------------------------------------------------


def _lower_label(spec, args):
    mapping = style.get_mapping_dict(args.lower_label_mapping)
    if mapping and spec.name in mapping:
        return str(mapping[spec.name])
    if args.lower_across == "comparable" and spec.kind == "operation":
        return "Residual"
    return spec.label if spec.kind == "operation" else spec.name


def _aligned(series):
    """Series sharing the x values of the first one (others are skipped)."""
    reference, out = None, []
    for s in series:
        if s.categorical:
            continue
        if reference is None:
            reference = s.x
        elif len(s.x) != len(reference) or not np.allclose(s.x, reference, equal_nan=True):
            rprint(f"[yellow]Warning:[/yellow] Skipping {s.hue_label} in the lower panel: x values are not aligned.")
            continue
        out.append(s)
    return reference, out


def _lower_series(x, y, error, color, linestyle, label, linewidth=None, x_edges=None):
    s = Series(x, y, error=error, x_edges=x_edges if x_edges is not None else edges_from_centers(x))
    s.color, s.linestyle, s.label, s.linewidth = color, linestyle, label, linewidth
    s.show_error = True  # lower series show their errors whenever they have them
    return s


def _draw_lower(ax, spec, series, args, comparable, comparable_values, colors):
    """Compute and draw one lower panel from the series of its upper panel."""
    plot_type = _resolved_plot_type(args, "lower_")
    label = _lower_label(spec, args)
    out = []  # Series to draw
    regular = [s for s in series if not s.is_sum]
    by_comparable = {}
    for s in regular:
        by_comparable.setdefault(s.comparable, []).append(s)

    if spec.kind == "events":
        from . import _events

        if series and series[0].rows is not None and not series[0].rows.empty:
            _events.draw_lower_events(ax, spec, series[0].rows.iloc[0], args, top_ax=None)
        _finish_lower(ax, spec, args, label, has_content=True)
        return

    if spec.name == "group" or (args.reference_group and args.other_group):
        if not (args.reference_group and args.other_group):
            rprint("[yellow]Warning:[/yellow] --lower group needs --reference_group and --other_group.")
            _finish_lower(ax, spec, args, label, has_content=False)
            return
        group_kwargs = dict(
            reference_group=args.reference_group,
            reference_group_weights=args.reference_group_weights,
            reference_group_label=args.reference_group_label,
            other_group=args.other_group,
            other_group_weights=args.other_group_weights,
            other_group_label=args.other_group_label,
            correlated=not args.group_diff_uncorrelated,
            relative=args.group_diff_relative,
            significance=args.group_significance,
            significance_min_background=args.group_significance_min_background,
        )
        for sdx, (value, members) in enumerate(by_comparable.items()):
            if args.lower_comparable_value is not None and str(value) != args.lower_comparable_value:
                continue
            x, aligned = _aligned(members)
            if not aligned:
                continue
            labels = [s.hue_label for s in aligned]
            arrays = [s.y for s in aligned]
            errors = [None if s.error is None or np.ndim(s.error) != 1 else s.error for s in aligned]
            for diff_label, values, errors_out in group_difference(labels, arrays, errors, **group_kwargs):
                if args.show_stat_error:
                    color = args.reference_sum_color or colors.next_free(("group", value))
                    lower_s = _lower_series(x, values, errors_out, color, None,
                                            f"{diff_label} ({aligned[0].comparable_label})" if value is not None else diff_label)
                    lower_s.forced_type = "errorbar"
                else:
                    color = args.reference_sum_color or colors.next_free(("group",))
                    lower_s = _lower_series(x, values, None, color, aligned[0].linestyle,
                                            diff_label if sdx == 0 else None, aligned[0].linewidth)
                out.append(lower_s)
    elif spec.kind == "column":
        first = True
        for s in regular:
            if s.rows is None or spec.name not in s.rows.columns:
                continue
            rows = s.rows[s.rows[spec.name].notna()]
            if rows.empty:
                continue
            error_rows = rows.drop(columns=[c for c in ("Error", "ErrorLow", "ErrorHigh") if c in rows.columns])
            if f"{spec.name}Error" in error_rows.columns:
                error_rows = error_rows.assign(Error=error_rows[f"{spec.name}Error"])
            column_series = extract(error_rows, args, y_column=spec.name)
            if column_series is None:
                continue
            lower_s = _lower_series(column_series.x, column_series.y, column_series.error, s.color, s.linestyle,
                                    label if first else None, s.linewidth, column_series.x_edges)
            if s.is_data:
                lower_s.forced_type = "data"  # points, like the data above
            out.append(lower_s)
            first = False
    elif spec.name in ("residual", "pull"):
        from . import _fit

        out.extend(_fit.lower_model_series(spec, regular, args, label))
    elif args.lower_across == "comparable":
        hues = {}
        for s in regular:
            hues.setdefault(s.hue, []).append(s)
        for hdx, (hue, members) in enumerate(hues.items()):
            members = sorted(members, key=lambda s: s.comparable_index)
            if len(members) < 2 or args.lower_line_index >= len(members):
                continue
            reference = members[min(args.reference, len(members) - 1)]
            other = members[args.lower_line_index]
            values = pairwise(reference.y, other.y, spec.name)
            linestyle = resolve_linestyle(hdx, args, n_total=len(hues))
            out.append(_lower_series(reference.x, values, None, other.color, linestyle,
                                     label if hdx == 0 else None, resolve_linewidth(hdx, args, len(hues))))
    else:
        for value, members in by_comparable.items():
            x, aligned = _aligned(members)
            if not aligned:
                continue
            if (any(s.is_data for s in aligned) and spec.name in DATA_COMPARISONS
                    and args.reference_value is None and not args.reference_sum):
                # The y label names the comparison; no legend over the points.
                out.extend(_data_lower(x, aligned, spec.name, None, args))
                ax.axhline(REFERENCE_LINES[spec.name], color=style.role("muted"), linestyle="--", linewidth=1, zorder=1)
                continue
            labels = [str(s.hue_label) for s in aligned]
            reference_index = args.reference
            if args.reference_value is not None:
                try:
                    reference_index = [str(s.hue) for s in aligned].index(str(args.reference_value))
                except ValueError:
                    rprint(f"[yellow]Warning:[/yellow] reference value '{args.reference_value}' not found; using index {args.reference}.")
            series_colors = {str(s.hue_label): s.color for s in aligned}
            reference_label = labels[max(0, min(reference_index, len(labels) - 1))]
            if args.reference_sum:
                sum_label = str(args.reference_sum_label or " + ".join(map(str, args.reference_sum)))
                series_colors[sum_label] = args.reference_sum_color or colors.next_free(("reference_sum", sum_label))
            for out_label, values in operation_series(labels, [s.y for s in aligned], spec.name, reference_index,
                                                      args.reference_sum, args.reference_sum_label):
                # A sum/mean/rms of every series is a new series: it takes a colour of its own.
                if spec.name in ("sum", "mean", "rms"):
                    color = colors.next_free((spec.name,))
                else:
                    color = series_colors.get(out_label)
                entry = label if spec.name in ("sum", "mean", "rms") else _pair_label(out_label, reference_label, spec.name)
                out.append(_lower_series(x, values, None, color, aligned[0].linestyle, entry, aligned[0].linewidth))

    for s in out:
        draw_series(ax, s, args, getattr(s, "forced_type", None) or plot_type or "line")
    # Lower series in the colours of the upper ones need no legend: the y
    # label says what is shown.
    upper_colors = {to_hex(s.color) for s in series if s.color is not None}
    new_colors = any(s.color is None or to_hex(s.color) not in upper_colors for s in out if s.label)
    _finish_lower(ax, spec, args, label, has_content=bool(out) and new_colors)


def _pair_label(value, reference, operation):
    """Legend entry of a lower series compared with the reference series."""
    symbol = {"ratio": "/", "subtract": "\u2212"}.get(operation)
    return f"{value} {symbol} {reference}" if symbol else f"{value} vs {reference}"


DATA_COMPARISONS = ("ratio", "subtract", "relative_difference")


def _data_lower(x, aligned, operation, label, args=None):
    """--data_hue lower panel: each data series against the total of the
    other series, as points with the data errors over a band of the total's
    error (in the colour of the total when it is one series)."""
    data = [s for s in aligned if s.is_data]
    model = [s for s in aligned if not s.is_data]
    if not model:
        return []
    total = np.sum([np.asarray(s.y, dtype=float) for s in model], axis=0)
    total_error = _stack_total_error(model, args)

    def scaled(error):
        # Error of the comparison for an error on the compared values.
        with np.errstate(divide="ignore", invalid="ignore"):
            if operation == "subtract":
                return np.asarray(error, dtype=float)
            return (100.0 if operation == "relative_difference" else 1.0) * np.asarray(error, dtype=float) / total

    out = []
    if total_error is not None:
        centre = np.full_like(total, 1.0 if operation == "ratio" else 0.0)
        color = model[0].color if len(model) == 1 else style.role("muted")
        band = _lower_series(x, np.where(total > 0, centre, np.nan), scaled(total_error), color, None, None)
        band.forced_type = "band"
        out.append(band)
    for s in data:
        error = s.error if s.error is not None and np.ndim(s.error) == 1 else None
        points = _lower_series(x, pairwise(total, s.y, operation), None if error is None else scaled(error),
                               s.color, None, label)
        points.forced_type = "data"
        out.append(points)
        label = None
    return out


def _finish_lower(ax, spec, args, label, has_content):
    ax.set_ylabel(str(args.lower_labely if args.lower_labely is not None else label), fontsize=style.ysublabelfontsize)
    apply_axis_options(ax, args, prefix="lower_", x=False)
    if getattr(args, "logx", False):
        ax.set_xscale("log")
    if args.lower_zero_line:
        ax.axhline(y=0, color=args.lower_zero_color or style.role_colors(style.zero_line_color), linestyle="--",
                   zorder=-1)
    draw_horizontal_overlay(ax, args, prefix="lower_")
    if args.vertical:
        from ..plot import draw_vertical_lines

        draw_vertical_lines(ax, args.vertical, fontsize=style.linelabelfontsize)
    if args.lower_log_format == "scientific":
        from matplotlib.ticker import ScalarFormatter

        ax.yaxis.set_major_formatter(ScalarFormatter(useMathText=True))
        ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
    if has_content and not args.no_lower_legend and ax.get_legend_handles_labels()[0]:
        kwargs = dict(capitalize_labels=args.capitalize_legend)
        if args.lower_legend_loc:
            apply_legend_style(ax, loc=args.lower_legend_loc, **kwargs)
        else:
            apply_legend_style_clear_of_data(ax, **kwargs)


# --- Upper axes, legends ---------------------------------------------------------------


def _finish_upper(fig, upper, lower, drawn, rows, args, variables, last_x, hue_values, comparable,
                  style_map, alpha_map, iterable_style_map, extrapolated_axes, nrows, ncols):
    n_panels = len(variables)
    label_map = json.loads(args.variable_label_map) if args.variable_label_map else None
    vertical_per_variable = json.loads(args.vertical_per_variable) if args.vertical_per_variable else None
    invert = args.invert_style
    primary_title = comparable_legend_title(args) if invert else iterable_legend_title(args)
    secondary_title = iterable_legend_title(args) if invert else comparable_legend_title(args)
    secondary_style_map = iterable_style_map if invert else style_map
    secondary_alpha_map = {} if invert else alpha_map

    categorical = any(s.categorical for panel in drawn.values() for s in panel[-1:])
    rotated = categorical and args.plot_type != "barh"
    categorical_y = categorical and args.plot_type == "barh"
    legend_panel = args.legend_panel % n_panels
    comparable_panel = args.comparable_legend_panel % n_panels if args.comparable_legend_panel is not None else legend_panel
    base_selection = legend_selection(args)

    for idx, variable in enumerate(variables):
        ax = upper[idx]
        panel_rows = _panel_rows(rows, variable)
        has_lower = bool(lower[idx])
        if n_panels > 1:
            subtitle = _title_case_words(variable) if variable is not None else ""
            if label_map is not None and variable in label_map:
                subtitle = label_map[variable]
            ax.set_title(subtitle, fontsize=style.subtitlefontsize)

        labelx = _panel_labelx(args, idx, n_panels)
        if args.plot_type == "barh":
            ax.set_xlabel(resolve_axis_label(args.labely, args.y, panel_rows))
            ylabel = resolve_axis_label(labelx, args.x, panel_rows)
        else:
            xlabel = resolve_axis_label(labelx, args.x, panel_rows)
            if has_lower:
                lower[idx][-1].set_xlabel(xlabel)
            else:
                ax.set_xlabel(xlabel)
            ylabel = resolve_axis_label(args.labely if args.labely is not None or not args.density else "Density",
                                        args.y, panel_rows)
            kinds = {getattr(s, "interval", None) for s in drawn.get(idx, [])} - {None}
            show = args.error_label if args.error_label is not None else style.error_label
            if show and len(kinds) == 1 and ylabel:
                ylabel = f"{ylabel}, {intervals.label(kinds.pop(), args.confidence_level)}"
        if rotated:
            ax.tick_params(axis="x", labelrotation=45)

        if not args.compact or idx % ncols == 0:
            ax.set_ylabel(ylabel, **({"fontsize": style.ysublabelfontsize} if has_lower else {}))
        else:
            ax.set_ylabel("")
            ax.tick_params(labelleft=False)

        if args.y == "Efficiency" or args.labely == "Efficiency (%)":
            ax.set_ylim(0, 105)
            ax.axhline(100, color=style.role("muted"), linestyle="--", linewidth=1)
        apply_axis_options(ax, args)
        if args.axis and "equal" in args.axis:
            ax.set_aspect("equal", adjustable="box")
        if args.axis and "off" in args.axis:
            ax.set_axis_off()
        for lower_ax in lower[idx]:
            if args.rangex is not None:
                lower_ax.set_xlim(args.rangex)

        show_legend = len([v for v in hue_values]) > 1 or args.single_legend or (
            base_selection == "comparable" and secondary_style_map
        ) or bool(lower[idx])
        if show_legend and idx in (legend_panel, comparable_panel) and base_selection != "none":
            selection = _panel_selection(base_selection, idx, legend_panel, comparable_panel)
            handles, labels = ax.get_legend_handles_labels()
            # matplotlib lists error bars after lines and patches: --data_hue entries go first.
            data_labels = {s.label for series in drawn.values() for s in series if s.is_data and s.label}
            if args.legend_order == "data":
                order = sorted(range(len(labels)), key=lambda i: labels[i] not in data_labels)
                handles, labels = [handles[i] for i in order], [labels[i] for i in order]
            else:
                band_label = style.stack_error.get("label") if args.stacked else None
                overlay_last = args.overlay_legend == "last"
                handles, labels = order_legend_entries(
                    ax, handles, labels, stacked=args.stacked, keep_first=() if overlay_last else data_labels,
                    keep_last=([band_label] if band_label else []) + (sorted(data_labels) if overlay_last else []))
            for label, color in extrapolated_axes.get(ax, []):
                handles.append(mlines.Line2D([], [], color=color, linestyle=EXTRAPOLATED_LINESTYLE, linewidth=1))
                labels.append(f"{label} Extrapolated")
            loc = {"loc": args.legend_loc} if args.stacked and args.legend_loc else {}
            draw_legends(ax, args, primary_title, handles, labels, secondary_title, secondary_style_map,
                         secondary_alpha_map, selection=selection, **loc)

        if args.mean_band:
            values = pd.to_numeric(filter_dataframe(rows, args)[args.y], errors="coerce").dropna().to_numpy()
            if len(values):
                mean, std = float(np.mean(values)), float(np.std(values))
                decimals = max(0, 1 - int(np.floor(np.log10(std)))) if std > 0 else 2
                ax.axhspan(mean - std, mean + std, color=style.role("muted"), alpha=0.2, linewidth=0, zorder=0)
                from ..plot import draw_horizontal_lines

                draw_horizontal_lines(ax, [mean], labels=[f"Average {mean:.{decimals}f} $\\pm$ {std:.{decimals}f}"],
                                      styles=["--"], colors=[style.role("muted")], fontsize=style.linelabelfontsize)
        vertical = vertical_per_variable.get(variable) if vertical_per_variable and variable in vertical_per_variable else None
        draw_overlays(ax, args, vertical=vertical)

    if rotated:
        rotate_categorical_labels(fig)
    if nrows == 1:
        grow_for_tick_labels(fig, rotated_x=rotated, categorical_y=categorical_y)
    add_title_and_note(fig, args, tight_rows=nrows)
    if args.compact and ncols > 1:
        fig.tight_layout()


def _panel_labelx(args, idx, n_panels):
    labels = args.labelx
    if not labels:
        return None
    if isinstance(labels, str):
        return labels
    return labels[idx] if len(labels) == n_panels else labels[0]


def _panel_selection(base, idx, legend_panel, comparable_panel):
    on_primary, on_comparable = idx == legend_panel, idx == comparable_panel
    if on_primary and on_comparable:
        return base
    if on_primary:
        return "iterable" if base in ("both", "iterable") else "none"
    if on_comparable:
        return "comparable" if base in ("both", "comparable") else "none"
    return "none"


# --- One series per config/name (--by_config) ---------------------------------------


def _config_rows(df, config, name, occurrence):
    mask = df["Config"] == config if "Config" in df.columns else pd.Series(True, index=df.index)
    if name is not None and "Name" in df.columns:
        mask &= df["Name"] == name
    if occurrence is not None and "_Occurrence" in df.columns:
        mask &= df["_Occurrence"] == occurrence
    return df[mask]


def _xy_of_rows(rows, args):
    """Concatenated numeric x/y of the rows (scalar cells broadcast)."""
    xs, ys = [], []
    for _, row in rows.iterrows():
        try:
            x = np.atleast_1d(np.asarray(row[args.x])).astype(float)
            y = np.atleast_1d(np.asarray(row[args.y])).astype(float)
        except (TypeError, ValueError, KeyError):
            continue
        if x.size == 1 and y.size > 1:
            x = np.full(y.shape, float(x[0]))
        elif y.size == 1 and x.size > 1:
            y = np.full(x.shape, float(y[0]))
        elif x.size != y.size:
            continue
        xs.append(x)
        ys.append(y)
    if not xs:
        return None, None
    return np.concatenate(xs), np.concatenate(ys)


def _errors_of_rows(rows):
    def _cat(column):
        arrays = []
        for value in rows[column].tolist():
            try:
                arrays.append(np.atleast_1d(np.asarray(value)).astype(float))
            except (TypeError, ValueError):
                continue
        return np.concatenate(arrays) if arrays else None

    if "ErrorLow" in rows.columns and "ErrorHigh" in rows.columns:
        low, high = _cat("ErrorLow"), _cat("ErrorHigh")
        return [low, high] if low is not None and high is not None else None
    if "Error" in rows.columns:
        return _cat("Error")
    return None


def _combine_by_prefix(rows, configs, names, args):
    """--combine prefix: merge the configs sharing the text before the first
    '_' (values at equal x averaged, or summed)."""
    grouped = {}
    for occurrence, (config, name) in enumerate(zip(configs, names)):
        prefix = str(config).split("_")[0]
        x, y = _xy_of_rows(_config_rows(rows, config, name, occurrence), args)
        if x is None:
            continue
        entry = grouped.setdefault(prefix, {"config": config, "name": name, "values": {}})
        for xv, yv in zip(x, y):
            entry["values"].setdefault(float(xv), []).append(float(yv))
    out_rows, out_configs, out_names = [], [], []
    how = np.sum if args.combine_operation == "sum" else np.mean
    for prefix, entry in grouped.items():
        xs = np.array(sorted(entry["values"]), dtype=float)
        out_rows.append({"Config": entry["config"], "Name": entry["name"], args.x: xs,
                         args.y: np.array([how(entry["values"][v]) for v in xs], dtype=float), "_Prefix": prefix})
        out_configs.append(entry["config"])
        out_names.append(entry["name"])
    return pd.DataFrame(out_rows), out_configs, out_names


def _print_crossings(args, x, y, label):
    if args.printy is not None and min(x) <= args.printy <= max(x):
        rprint(f"[green]PrintY:[/green] At x={args.printy:.2f}, y={np.interp(args.printy, x, y, left=np.nan, right=np.nan):.4f} for {label}")
    if args.printx is not None and min(y) <= args.printx <= max(y):
        above = np.where(y >= args.printx)[0]
        if len(above) and above[0] > 0:
            i = above[0]
            x1, x2, y1, y2 = x[i - 1], x[i], y[i - 1], y[i]
            x_at = x1 + (args.printx - y1) * (x2 - x1) / (y2 - y1) if y2 != y1 else x1
        else:
            x_at = x[above[0]] if len(above) else x[-1]
        rprint(f"[green]PrintX:[/green] At y={args.printx:.2f}, x={x_at:.4f} for {label}")


def _is_shifted(config, name, args):
    return bool(args.shift) and ((config is not None and config in args.shift) or (name is not None and name in args.shift))


def _config_label(args, config, name):
    mapping = args.iterable_mapping
    if mapping is None:
        return make_config_label_from_args(args, config=config, name=name)
    label = map_iterable_label(config, "Config", mapping)
    if name is not None:
        label += ", " + map_iterable_label(name, "Name", mapping)
    return label


def run_by_config(df, args):
    """One series per --configs/--names entry, all in one figure."""
    ncols = len(args.variables) if args.variables is not None else 1
    fig, upper, _, _ = create_panels(ncols, grid=False)
    filtered_all = filter_dataframe(df, args)
    variables = args.variables if args.variables is not None else [None]
    exclude = {str(v) for v in (args.exclude_iterable or [])}
    iterables = (
        [v for v in filtered_all[args.iterable].unique() if str(v) not in exclude] if args.iterable is not None else [None]
    )
    # One colour per (hue value, config/name) in every panel; mapped colours are reserved first.
    colors = ColorAllocator()
    if args.combine != "prefix":
        configs, names = prepare_import(args)
        pairs = list(enumerate(zip(configs if configs is not None else [None], names if names is not None else [None])))
        for iterable in iterables:
            colors.reserve([(iterable, ldx, config, name) for ldx, (config, name) in pairs],
                           lambda key: make_config_color_and_style_from_args(args, config=key[2], name=key[3])[0])
    linestyles, line_colors = {}, {}  # per series, so every panel draws it alike
    plotted = set()
    data_labels = set()  # --data_hue series, first in the legend
    for idx, variable in enumerate(variables):
        ax = upper[idx]
        for iterable in iterables:
            subset = _panel_rows(filtered_all, variable)
            if iterable is not None:
                subset = subset[subset[args.iterable] == iterable]
            configs, names = prepare_import(args)
            configs = configs if configs is not None else [None]
            names = names if names is not None else [None]
            if args.combine == "prefix":
                subset, configs, names = _combine_by_prefix(subset, configs, names, args)
            prefixes = [str(c).split("_")[0] if c is not None else "" for c in configs]
            pending = []  # (x, y, error) for --combine_op
            grids = []
            if args.combine_op is not None:
                for occurrence, (config, name) in enumerate(zip(configs, names)):
                    x, _ = _xy_of_rows(_config_rows(subset, config, name, occurrence), args)
                    if x is not None:
                        grids.append(x + args.shift_offset if _is_shifted(config, name, args) else x)
            grid = union_grid(grids)
            last_edges = None
            for ldx, (prefix, config, name) in enumerate(zip(prefixes, configs, names)):
                rows = _config_rows(subset, config, name, ldx)
                if rows.empty:
                    rprint(f"[yellow]Warning:[/yellow] No data for Config: {config}" + (f", Name: {name}" if name else "") + ". Skipping...")
                    continue
                # --data_hue names a config, name or hue value; data always shows its errors.
                is_data = any(_is_data(value, args) for value in (config, name, iterable) if value is not None)
                with_errors = args.errory or is_data
                columns = [args.x, args.y] + ([c for c in ("Error", "ErrorLow", "ErrorHigh") if c in rows.columns] if with_errors else [])
                if len(rows) == 1:
                    try:
                        rows = rows.explode(column=columns)
                    except ValueError:
                        pass
                rows = rows.dropna(subset=columns)
                x, y = _xy_of_rows(rows, args)
                if x is None:
                    rprint(f"[yellow]Warning:[/yellow] Could not parse x/y for Config: {config}, Name: {name}. Skipping...")
                    continue
                error = _errors_of_rows(rows) if with_errors else None
                label = prefix.upper() if args.combine == "prefix" else _config_label(args, config, name)
                if iterable is not None:
                    iterable_label = map_iterable_label(iterable, args.iterable, args.iterable_mapping)
                    if args.iterable_mapping is not None:
                        label = str(iterable_label)
                    elif str(iterable_label) not in {p.strip() for p in label.split(",")}:
                        label = f"{label}, {iterable_label}"
                _print_crossings(args, x, y, label)
                if _is_shifted(config, name, args):
                    x = x + args.shift_offset
                plotted.add(prefix)

                projected = None
                if args.project is not None and config in args.project:
                    projected, _ = project(x, y, x, args.project_scale, args.project_offset)
                if args.combine_op is not None and not is_data:
                    pending.append((x, y, error))
                    if projected is not None:
                        pending.append((x * args.project_scale + args.project_offset, y, error))

                if args.rebin and args.rebin > 1:
                    k = int(args.rebin)
                    n = len(x) // k * k
                    x = x[:n].reshape(-1, k).mean(axis=1)
                    y = y[:n].reshape(-1, k).sum(axis=1)

                    def _rebin_error(e):
                        e = np.asarray(e, dtype=float)
                        return np.sqrt(np.sum(e[:n].reshape(-1, k) ** 2, axis=1)) if e.shape[0] >= n else None

                    if isinstance(error, list):
                        error = [_rebin_error(e) for e in error] if all(e is not None for e in error) else None
                    elif error is not None:
                        error = _rebin_error(error)
                if len(x) < 2:
                    rprint("[red]Error:[/red] Only found one x value. Skipping...")
                    continue
                if len(x) > 2 and not np.allclose(np.diff(x), x[1] - x[0]):
                    rprint(f"[yellow]Warning:[/yellow] Bins have different widths for Config: {config}, Name: {name}.")
                edges = edges_from_centers(x)
                if config == args.mirror:
                    x, y = mirror(x, y, at_edge=args.mirror_edge)
                    edges = np.linspace(x[0] - (x[1] - x[0]) / 2, x[-1] + (x[1] - x[0]) / 2, len(x) + 1)
                if not np.all(np.diff(edges) > 0):
                    x, y, edges = x[::-1], y[::-1], edges[::-1]
                    if error is not None and not isinstance(error, list):
                        error = error[::-1]
                if not np.all(np.diff(edges) > 0):
                    unique = np.unique(np.sort(x))
                    edges = edges_from_centers(unique) if len(unique) > 1 else np.array([unique[0] - 0.5, unique[0] + 0.5])
                last_edges = edges

                if is_data:
                    if args.show_configs is None or config in args.show_configs:
                        xerr = np.diff(edges) / 2 if args.errory_x else None
                        plot_data(args, ax, x, y=y, plot_type="errorbar", yerr=error, xerr=xerr, fmt="o", zorder=3,
                                  label=label if idx == ncols - 1 else None, color=style.role("ink"))
                        data_labels.add(label)
                    continue

                key = (iterable, ldx, config, name)
                mapped, base_linestyle = make_config_color_and_style_from_args(args, config=config, name=name)
                color = colors.color_for(key, mapped)
                if key not in linestyles:
                    many = len(set(prefixes)) > 1 or len(args.configs or []) > 1 or len(args.names or []) > 2
                    used = list(line_colors.values())
                    if mapped is not None and color in used and many:
                        # The same mapped colour again: tell the lines apart by style.
                        linestyles[key] = {1: "--", 2: ":", 3: "-."}.get(used.count(color), base_linestyle or "-")
                    else:
                        linestyles[key] = "-"
                    line_colors[key] = color
                linestyle = linestyles[key]

                if args.show_configs is None or config in args.show_configs:
                    y_drawn = y
                    if projected is not None:
                        y_drawn = np.sqrt(y**2 + projected**2) if args.combine_op == "squared_sum" else y + projected
                        label = f"{label} (Projected)"
                    plot_data(args, ax, x, edges, y_drawn, error, "symmetric" if not isinstance(error, list) else "asymmetric",
                              label if idx == ncols - 1 else None, color, linestyle, plot_type=args.plot_type or "step")

            if args.combine_op is not None and pending:
                grid = grid if grid is not None else pending[0][0]
                values, error = combine(pending, grid, how=args.combine_op)
                _print_crossings(args, grid, values, "Combined")
                kwargs = {"alpha": args.combined_alpha}
                if args.combined_linewidth is not None:
                    kwargs["linewidth"] = args.combined_linewidth
                plot_data(args, ax, grid, edges_from_centers(grid), values, error,
                          "asymmetric" if np.ndim(error) == 2 else "symmetric",
                          args.combined_label if idx == ncols - 1 else None,
                          args.combined_color or colors.next_free(("combined", iterable)),
                          args.combined_linestyle, plot_type=args.plot_type or "step", **kwargs)

        if ncols > 1:
            ax.set_title(make_subtitle_from_args(args, None, idx=idx), fontsize=style.subtitlefontsize)
        ax.set_xlabel(resolve_axis_label(_panel_labelx(args, idx, ncols), args.x, filtered_all))
        if idx == 0:
            ax.set_ylabel(resolve_axis_label(args.labely or None, args.y, filtered_all))
        if args.rangex is not None:
            ax.set_xlim(args.rangex[0], args.rangex[1])
        if args.y == "Efficiency":
            ax.set_ylim(0, 110)
            ax.axhline(100, color=style.role("muted"), linestyle="--", linewidth=1)
        elif args.y == "RMS":
            ax.set_ylim(0, 0.5)
        if args.rangey is not None:
            ax.set_ylim(args.rangey[0], args.rangey[1])
        apply_tick_formatter(ax, axis="both")
        draw_overlays(ax, args)
        if args.logy:
            ax.set_yscale("log")
        if args.logx:
            ax.set_xscale("log")
        if idx == ncols - 1 and not args.no_legend:
            handles, labels = ax.get_legend_handles_labels()
            order = sorted(range(len(labels)), key=lambda i: labels[i] not in data_labels)
            apply_legend_style(ax, title=args.labelz, handles=[handles[i] for i in order],
                               labels=[labels[i] for i in order], capitalize_labels=args.capitalize_legend)

    add_title_and_note(fig, args)
    if not plotted:
        rprint("[yellow]Warning:[/yellow] No data survived filtering. Exiting without saving a plot.")
        matplotlib.pyplot.close(fig)
        return None
    prefix = None if len(plotted) > 1 else next(iter(plotted))
    return save(fig, args, None, suffix="comparison.png", prefix=prefix if getattr(args, "prefix_by_config", False) else None)


# --- Entry point -------------------------------------------------------------------------


def run(args):
    _check_args(args, build_parser())
    if args.errory_type in ("poisson", "clopper_pearson"):
        args.errory = True  # an interval is an error to draw
    df = load(args)
    if df.empty:
        rprint("[yellow]Warning:[/yellow] No datafiles found. Exiting...")
        return []
    # Events mode keeps its layout with --no_lower_plot (events drawn on the upper panel).
    events = [spec for spec in map(parse_lower, args.lower or []) if spec.kind == "events"]
    if events:
        from ._events import run_events

        return [run_events(df, args, events[0])]
    if args.fit:
        from ._fit import run_fit

        return run_fit(df, args)
    if args.binned:
        from ._estimator import run_estimator

        return run_estimator(df, args)
    if args.by_config:
        return [run_by_config(df, args)]
    if args.iterable is not None and args.iterable not in df.columns:
        rprint(f"[red]Error:[/red] Hue column '{args.iterable}' was not found. Available columns: {', '.join(map(str, df.columns))}")
        return []
    for spec in [] if args.no_lower_name else _lower_specs(args):
        # The lower operation/column is part of the output name.
        if spec.kind == "operation" and spec.name != "group" and getattr(args, "operation", None) is None:
            args.operation = spec.name
        elif spec.kind == "column":
            args.lower_series_data = spec.name
    outputs = []
    for kdx, config, name, rows in _base.figure_groups(df, args, overlay=args.overlay_names):
        rprint(f"Plotting for Config: {config}, Name: {name}")
        outputs.append(draw_figure(rows, args, kdx))
    return outputs


# --- Legacy command lines ----------------------------------------------------------------

_OPERATION_RENAMES = {
    "--bottom_labely": "--lower_labely",
    "--bottom_rangey": "--lower_rangey",
    "--bottom_plot_type": "--lower_plot_type",
    "--bottom_logy": "--lower_logy",
    "--bottom_log_format": "--lower_log_format",
    "--bottom_legend_loc": "--lower_legend_loc",
    "--bottom_label_mapping": "--lower_label_mapping",
    "--bottom_zero_line": "--lower_zero_line",
    "--no_bottom_legend": "--no_lower_legend",
    "--bottom_comparable_value": "--lower_comparable_value",
    "--comparable_reference_index": "--reference",
    "--comparable_operation_line_index": "--lower_line_index",
    "--no_stack_reverse": None,
    "--stack_reverse": None,
}


def _legacy_scan(tokens):
    return tokens + ["--output_suffix", "scan.png"]


def _legacy_line_operation(tokens):
    from ..legacy import has, option_values, rename, replace_value
    from ..project import load_project

    lower = []
    operation = option_values(tokens, "--operation")
    column = option_values(tokens, "--lower_series_data")
    comparable_operation = option_values(tokens, "--comparable_operation")
    default = option_values(tokens, "--default_operation")
    stack_reverse = has(tokens, "--stacked") and not has(tokens, "--no_stack_reverse")

    tokens = rename(tokens, {"--operation": None, "--lower_series_data": None, "--comparable_operation": None,
                             "--default_operation": None, **_OPERATION_RENAMES})
    if comparable_operation:
        lower = ["--lower", comparable_operation[0], "--lower_across", "comparable", "--no_lower_name"]
    elif column:
        lower = ["--lower", f"column:{column[0]}"]
    elif operation:
        lower = ["--lower", operation[0]]
    elif not has(tokens, "--reference_group"):
        behaviour = (default or [None])[0] or load_project().settings.get("default_operation") or "relative_difference"
        from ..lower import OPERATIONS

        lower = ["--lower", behaviour if behaviour in OPERATIONS else f"column:{behaviour}"]
        if not default:
            lower.append("--no_lower_name")
    else:
        lower = ["--lower", "group"]

    plot_type = (option_values(tokens, "--plot_type") or ["step"])[0]
    plot_type = "stepmid" if plot_type == "step" else plot_type
    tokens = rename(tokens, {"--plot_type": None})
    tokens = replace_value(tokens, "--lower_plot_type", "step", "stepmid")
    if has(tokens, "--stacked"):
        # Stacked series are always bars; the plot type only shapes the lower panel.
        if not has(tokens, "--lower_plot_type"):
            tokens += ["--lower_plot_type", plot_type]
    else:
        tokens += ["--plot_type", plot_type]
    if not has(tokens, "--labelx"):
        tokens += ["--labelx", "True Neutrino Energy (MeV)"]
    if stack_reverse:
        tokens.append("--stack_reverse")
    if has(tokens, "--stacked"):
        tokens += ["--bar_width", "auto"]
    if has(tokens, "--overlay_names"):
        tokens.append("--overlay_name_all")
    suffix = "stacked_line_operation.png" if has(tokens, "--stacked") else "line_operation.png"
    return tokens + lower + ["--output_suffix", suffix]


def _legacy_configuration(tokens):
    from ..legacy import has, rename, replace_value
    from ..project import load_project

    tokens = rename(tokens, {"--operation": "--combine_op", "-c": None, "--comparable": None})
    tokens = replace_value(tokens, "--combine", "Geometry", "prefix")
    if not has(tokens, "-x"):
        tokens += ["-x", "Values"]
    if not has(tokens, "--configs", "--config"):
        default_configs = load_project().settings.get("legacy_default_configs")
        if default_configs:
            tokens += ["--configs", *default_configs]
    if not has(tokens, "--plot_type"):
        tokens += ["--plot_type", "step"]
    return tokens + ["--by_config", "--prefix_by_config", "--output_suffix", "comparison.png"]


def _legacy_line_fit(tokens):
    from ..legacy import has, rename

    tokens = rename(tokens, {"--bottom_labely": "--lower_labely"})
    for flag, default in (("--datafile", "NHit_Distributions"), ("-x", "Values"), ("-y", "Density")):
        if not has(tokens, flag):
            tokens += [flag, default]
    return tokens + ["--fit", "--lower", "residual", "--output_suffix", "fit.png"]


def _legacy_reduction(tokens):
    from ..legacy import has, rename

    tokens = rename(tokens, {"--operation": "--estimator", "--default_operation": None,
                             "--percentile": None, "-p": None, "--boxplot": ["--plot_type", "box"]})
    if has(tokens, "--plot_type") and tokens.count("--plot_type") > 1:
        # --boxplot wins over an explicit --plot_type, as in the old script.
        i = next(i for i, t in enumerate(tokens) if t == "--plot_type" and tokens[i + 1] != "box")
        del tokens[i:i + 2]
    return tokens + ["--binned"]


_EVENTS_RENAMES = {
    "--line_label": "--series_label",
    "--line-label": "--series_label",
    "--lower_series_label": "--events_label",
    "--lower_plot_style": "--events_style",
    "--lower-plot-style": "--events_style",
    "--lower_hist_bins": "--events_bins",
    "--lower-hist-bins": "--events_bins",
    "--lower_series_density": "--events_density",
    "--lower-series-density": "--events_density",
    "--lower_series_range": "--events_range",
    "--lower-series-range": "--events_range",
    "--lower_show_range_bars": "--events_range",
    "--lower-show-range-bars": "--events_range",
    "--lower_vertical_lines": "--events_guides",
    "--lower-vertical-lines": "--events_guides",
    "--show-highlights": "--show_highlights",
    "--highlight-color": "--highlight_color",
    "--iterable_value": "--hue_value",
    "--iterable-value": "--hue_value",
    "--lower-labely": "--lower_labely",
    "--lower_label": "--lower_labely",
    "--lower-label": "--lower_labely",
    "--highlight_start_column": None,
    "--highlight-start-column": None,
    "--highlight_end_column": None,
    "--highlight-end-column": None,
    "--highlight_center_column": None,
    "--highlight-center-column": None,
}


def _legacy_line2scatter(tokens):
    from ..legacy import has, option_values, rename

    series = (option_values(tokens, "--lower_series") or option_values(tokens, "--lower-series") or ["OpHit"])[0]
    tokens = rename(tokens, {"--lower_series": None, "--lower-series": None, **_EVENTS_RENAMES})
    for flag, default in (("-x", "TimeNS"), ("-y", "UpperY"), ("--labelx", "Time [ns]"),
                          ("--labely", "Amplitude"), ("--lower_labely", "Scatter value")):
        if not has(tokens, flag):
            tokens += [flag, default]
    return tokens + ["--lower", f"events:{series}"]


LEGACY = {
    "script_line_fit": _legacy_line_fit,
    "script_compare_reduction": _legacy_reduction,
    "script_comapre_line2scatter": _legacy_line2scatter,
    "script_compare_line2scatter": _legacy_line2scatter,
    "script_iterable_scan": _legacy_scan,
    "script_compare_line_operation": _legacy_line_operation,
    "script_compare_configuration": _legacy_configuration,
}
