"""map: two-dimensional data as a colour map, optionally with contours.

Three inputs, one row per panel (panels from ``--variables`` or ``--hue``):

* raw points: ``x`` and ``y`` arrays per row, binned into a 2D histogram
  (integer-valued data gets one bin per integer; ``--norm`` normalises rows,
  columns or the whole map; ``--percentile`` sets the range);
* a gridded map: ``-z`` names a 2D array cell drawn on the ``x``/``y`` grid
  with a colour bar;
* contours (``--contour``): gridded maps (Δχ² or significance) of every
  ``--configs``/``--names`` entry drawn as confidence contours (2-dof Δχ²
  levels by default, ``--contour_dof``), lines or graded filled bands, with
  the best fit (a point with its 1-sigma profile intervals on a Delta-chi2
  map, else a ``+``) and an optional background image, optionally combined
  bin by bin (``--combine_op squared_sum``) and projected to another exposure
  (``--project``). Defaults come from the style's ``contours`` section.

Colours given as ``cycle`` (the matplotlib colour cycle) or as the name of a
list/dict style mapping are palettes: successive contour levels take
successive palette colours.
"""

import copy
import json
import os

import matplotlib.pyplot as plt
from matplotlib import patheffects
import numpy as np
import pandas as pd
from matplotlib.colors import LogNorm, Normalize, PowerNorm, to_rgb, to_rgba
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.path import Path
from matplotlib.ticker import MaxNLocator
from rich import print as rprint

from .. import posterior, style
from ..args import add_common_args, map_iterable_color, map_iterable_label, parse_plot_label, resolve_axis_label
from ..format import _title_case_words, make_config_label_from_args, make_subtitle_from_args
from ..io import import_data, normalize_datafiles, prepare_import
from ..hue_colors import hue_color
from ..palettes import ColorAllocator
from ..panels import add_colorbar, add_title_and_note, create_panels, draw_overlays, save
from ..plot import (
    apply_legend_style,
    apply_legend_style_clear_of_data,
    apply_tick_formatter,
    draw_horizontal_lines,
    draw_lines,
    draw_squares,
    draw_vertical_lines,
    place_point_label,
    plot_data,
)
from ..args import (
    normalize_line_labels,
    normalize_point_labels,
    normalize_square_labels,
    parse_line_segments,
    parse_point_pairs,
    parse_square_quads,
)
from ..selection import filter_dataframe
from . import _base

KIND = "map"
NORM_LABELS = {
    "global": "Normalized Counts",
    "horizontal": "Normalized Counts (Rows)",
    "vertical": "Normalized Counts (Columns)",
    "combined": "Normalized Counts (Rows + Columns)",
}
# Contour sets draw at zorder 5-6.5 and best-fit markers at 7.
OVERLAY_ZORDER = 6.9
# One-off notices already printed by this process.
_NOTICES_SHOWN = set()


# --- Arguments ---------------------------------------------------------------------


def build_parser():
    parser = _base.make_parser(KIND, "2D histogram or gridded map, optionally with sigma contours.")
    add_common_args(
        parser,
        [
            "datafile", "configs", "names", "variables", "x", "y", "z", "percentile", "iterable",
            "select", "save_values", "remove_value", "filename_select", "bins", "labelx", "labely",
            "labelz", "rangex", "rangey", "rangez", "logx", "logy", "logz", "density", "norm", "zoom", "matchx",
            "matchy", "horizontal", "horizontal_label", "horizontal_style", "horizontal_color", "horizontal_label_pos",
            "vertical", "vertical_label", "vertical_style", "vertical_color", "square",
            "vertical_band", "vertical_band_label", "vertical_band_color", "horizontal_band",
            "horizontal_band_label", "horizontal_band_color",
            "square_label", "square_style", "square_color", "line", "line_label", "line_style",
            "line_color", "title", "output", "subfolder", "point", "point_label", "note",
            "multiply", "debug",
        ],
        overrides={
            "datafile": {"required": True},
            "x": {"help": "Column of the x values (required unless --corner)"},
            "y": {"help": "Column of the y values (required unless --corner)"},
            "bins": {"default": None, "help": "Number of bins of the 2D histogram (default: style nbins)"},
            "percentile": {"default": [0, 100], "help": "Percentile range of the histogram axes"},
            "density": {"help": "Normalise the histogram (or each contour map) to unit sum"},
            "zoom": {"help": "Restrict the histogram range to the overlap of the panels' ranges"},
            "multiply": {"help": "Multiply every -z value by this factor"},
        },
    )
    add = parser.add_argument
    add("--map_type", default="hist2d", choices=["hist2d", "hexbin"],
        help="Binning of raw points: rectangular bins (hist2d) or hexagons (hexbin, --bins hexagons across x); "
        "both take --logz, --rangez, --cmap, --zpower and the colorbar options.")
    add("--corner", nargs="+", default=None, metavar="VARIABLE",
        help="Corner plot of these array columns (instead of -x/-y): an N x N grid with the 2D histogram of each "
        "pair below the diagonal, the histogram of each variable on the diagonal and the upper triangle empty. "
        "With --contour, a posterior corner plot: credible regions (--contour_sigmas) and marginal densities "
        "with their median and 68.3%% interval, one colour per --contour_hue value.")
    add("--corner_labels", nargs="+", type=parse_plot_label, default=None, metavar="LABEL",
        help="Axis label of each --corner variable (default: the column names).")
    add("--corner_truth", nargs="+", type=float, default=None, metavar="VALUE",
        help="Reference value of each --corner variable (the injected or true value; 'nan' for none): a line "
        "across its panels and a marker where two meet.")
    add("--corner_truth_label", type=parse_plot_label, default="Truth", help="Legend label of the --corner_truth lines.")
    add("--no_corner_titles", action="store_true", default=False,
        help="With --corner --contour: do not write the median and 68.3%% interval above each diagonal panel.")
    add("--weight", type=str, default=None, metavar="COLUMN",
        help="With --corner --contour: column of per-point weights (weighted posterior samples).")
    add("--corner_levels", nargs="+", type=float, default=None, metavar="PERCENT",
        help="With --corner --contour: content of the credible regions in percent (68 90), instead of the "
        "--contour_sigmas levels; the marginals then carry the interval of the first level.")
    add("--corner_interval", default=None, choices=["quantile", "hdi", "limit"],
        help="Interval of each marginal: the central one around the median (quantile), the highest-density one "
        "around the mode, in pieces when the marginal has several peaks (hdi), or a one-sided limit for every "
        "variable with a --corner_bound (limit). Default: quantile, a limit where the marginal is highest at its "
        "bound, and hdi for a --corner_cyclic variable.")
    add("--corner_cyclic", nargs="+", action="append", default=None, metavar="VARIABLE [LOW HIGH]",
        help="A periodic --corner variable (a phase; repeatable): its panels span one period (default [-pi, pi] or "
        "[0, 2 pi], whichever holds the draws), regions and intervals run across the end of the axis.")
    add("--corner_bound", nargs=3, action="append", default=None, metavar=("VARIABLE", "LOW", "HIGH"),
        help="Hard bounds of a --corner variable ('nan' for none; repeatable): nothing is smoothed across them, and a "
        "marginal that is highest at one gets a one-sided limit holding the outermost level.")
    add("--corner_split", nargs="+", action="append", default=None, metavar="VARIABLE VALUE | COLUMN",
        help="Posterior probability of the two sides of a value of a --corner variable, or of each value of a label "
        "column (one label per draw or per row; repeatable): written in the legend with its Monte Carlo error and the "
        "posterior odds, a dotted line at the value.")
    add("--corner_split_marginals", action="store_true", default=False,
        help="With --corner_split: draw the share of each part of the first split in every diagonal panel, one line "
        "style each.")
    add("--prior_odds", type=float, default=None, metavar="ODDS",
        help="With --corner_split: prior odds of the first part against the second; the legend then gives the Bayes "
        "factor (posterior odds / prior odds) instead of the posterior odds.")
    add("--corner_upper", default=None, choices=["profile", "corr"],
        help="With --corner --contour, the upper triangle: the profile likelihood of each pair and over each marginal "
        "(profile, needs --loglike; one sample) or the correlation coefficient of each pair with its Monte Carlo "
        "error (corr). The legend then goes above the grid.")
    add("--loglike", type=str, default=None, metavar="COLUMN",
        help="With --corner_upper profile: column of the log-likelihood of each draw (not the log-posterior).")
    add("--corner_mc_error", nargs="?", type=int, const=30, default=None, metavar="N",
        help="With --corner --contour: the outermost region's outline for N (default 30) resamplings of the draws at "
        "their effective sample size, as hairlines: the Monte Carlo uncertainty of the region.")
    add("--corner_prior", type=str, default=None, metavar="VALUE",
        help="With --corner --contour --contour_hue: the value of that column whose rows hold draws from the prior. It "
        "is drawn as a dashed outline in the neutral colour (its marginals, and its outermost region in the pairs), "
        "never filled, and is left out of the ranges, the titles and the other statistics.")
    add("--corner_shrinkage", action="store_true", default=False,
        help="With --corner_prior and one posterior sample: under each title, the posterior's width over the prior's "
        "and the shift of its median in prior widths (widths: half the central 68.3%% interval).")
    add("--corner_block", nargs="+", default=None, metavar="COLUMN",
        help="With --corner --contour and four or more variables: array columns that are not in the grid (derived "
        "parameters), drawn as marginals in the top-right block of the upper triangle, with their interval and, with "
        "--corner_prior, the prior they inherit. The legend then goes above the grid.")
    add("--corner_block_labels", nargs="+", type=parse_plot_label, default=None, metavar="LABEL",
        help="Axis label of each --corner_block column (default: the column names).")
    add("--corner_band", nargs="+", action="append", default=None, metavar="VARIABLE LOW HIGH [LABEL]",
        help="With --corner --contour: an outside constraint on one variable, a hatched band across its panels "
        "(repeatable); with a LABEL it is named in the legend.")
    add("--diagonal", action="store_true", default=False, help="Draw the y = x line.")
    add("--cmap", type=str, default=None,
        help="Matplotlib colour map of -z images; 'diverging' is the style's map for signed values "
        "(RdBu_r, berlin on dark backgrounds).")
    add("--colorbar", default=None, choices=["shared", "each", "none"],
        help="One colorbar and colour scale for the row of panels (shared, the default unless --norm), "
        "one per panel (each) or none.")
    add("--annotate", nargs="?", const=".3g", default=None, metavar="FORMAT",
        help="Write each cell's value in it (-z grids and 2D histograms), with a Python format: '.2f', "
        "'.0%%' (default .3g); the text is dark on light cells and light on dark ones.")
    add("--matrix", action="store_true", default=False,
        help="Matrix layout for -z grids (confusion matrices, correlation tables): the first y value at the top.")
    add("--zpower", type=float, default=None, metavar="GAMMA",
        help="Power-law colour scale, value**GAMMA (0.5: square root); the colorbar is ticked at powers of ten.")
    add("--zmin", type=float, default=None, metavar="VALUE",
        help="Bottom of the colour scale; lower values take --zunder (default: blank on a log or power scale).")
    add("--zunder", type=str, default=None, metavar="COLOUR",
        help="Colour of the values below --zmin (e.g. black for the sparsest bins).")
    add("--panel_title", nargs="+", type=parse_plot_label, default=None, help="Title of each panel.")
    add("--compact", action="store_true", default=None,
        help="Panels side by side share their y range and only the first shows the y label and tick labels "
        "(default with several panels; --no-compact gives each panel its own y axis).")
    add("--no-compact", dest="compact", action="store_false")
    add("--iterable_mapping", type=str, default=None,
        help="Mapping renaming each overlaid contour variant in the legend (its datafile, or its --contour_hue value).")
    add("--iterable_color_mapping", type=str, default=None,
        help="Mapping giving the colour of each overlaid contour variant (by datafile, or by --contour_hue value).")
    add("--iterable_label_map", type=str, default=None, help="JSON {hue value: label} applied to the panel values.")

    group = parser.add_argument_group("contours")
    add = group.add_argument
    add("--contour", action="store_true", default=False,
        help="Contour mode: sigma contours of each config/name map (-z) over a background image; without -z, "
        "the regions holding the sigma fractions of the points over their 2D histogram.")
    add("--contour_hue", type=str, default=None, metavar="COLUMN",
        help="With -z: overlay the map of each value of COLUMN in every panel, one colour and legend entry each "
        "(several datasets in one file, as several --configs would be); --combine_op adds them up.")
    add("--contour_sigmas", nargs="+", type=float, default=[1.0, 2.0, 3.0], help="Sigma levels drawn.")
    add("--contour_level_mode", default="sigma_probability", choices=["z_values", "sigma_probability"],
        help="z_values: maps are significances, contours at the sigmas; sigma_probability: maps are "
        "delta-chi2, contours at the delta-chi2 of each sigma's coverage (see --contour_dof).")
    add("--contour_dof", type=int, default=None, choices=[1, 2],
        help="Degrees of freedom of the sigma_probability levels: 2 (default; joint region of the two "
        "parameters, delta-chi2 = 2.30, 6.18, 11.83) or 1 (delta-chi2 = sigma^2, the old levels). "
        "Default: style contours.dof, else 2.")
    add("--contour_label", default=None, choices=["cl", "sigma"],
        help="Level labels: coverage ('68.3%% CL', default) or significance ('1σ', '1σ (2 dof)'). "
        "Default: style contours.label.")
    add("--contour_linestyles", nargs="+", type=str, default=None,
        help="Line style per sigma level (default: style contours.linestyles, solid, dashed, dotted).")
    add("--contour_linewidth", type=float, default=2.0)
    add("--contour_labels", action="store_true", default=False,
        help="Write each level's label (68.3%% CL, 1 sigma, ...) on its contour line instead of in the legend.")
    add("--contour_label_pos", nargs="+", type=float, default=None, metavar="X Y",
        help="Place the level labels at these points instead (data coordinates, one X Y pair per level, innermost "
        "first); implies --contour_labels.")
    add("--contour_label_leader", action="store_true", default=False,
        help="With --contour_label_pos: a thin line from each label to its contour.")
    add("--contour_alpha", type=float, default=0.95)
    add("--contour_smoothing_sigma", type=float, default=0.0, help="Gaussian smoothing of the maps before contouring "
        "(in bins; without -z, default 1).")
    add("--background_smoothing_sigma", type=float, default=0.0, help="Gaussian smoothing of the background image.")
    add("--contour_min_vertices", type=int, default=0, help="Drop contour pieces with fewer vertices.")
    add("--background", default=None, choices=["all", "combined", "first", "none"],
        help="Background image: sum of all maps, the combined map, the first map or none (default: style "
        "contours.background, none). Delta-chi2 backgrounds are clipped at the outermost level.")
    add("--no_best_fit", action="store_true", default=False, help="Do not mark the best fit (the map minimum).")
    add("--nan_fill", default="interpolate", choices=["interpolate", "nearest", "zero", "none"],
        help="How NaN map cells are filled.")
    add("--nan_interp_method", default="linear", choices=["cubic", "linear"])
    add("--fill_contours", action="store_true", default=False,
        help="Filled sigma bands: one hue per map mixed with the paper colour (style contours.fill_mix), "
        "darkest at the best fit, lighter outwards, unfilled outside.")
    add("--fill_alpha", type=float, default=None, help="Opacity of the bands (of the innermost one, default 1).")
    add("--fill_outer_alpha", type=float, default=None,
        help="Opacity of the outermost band (default: --fill_alpha); the bands between are interpolated.")
    add("--fill_inner_alpha", type=float, default=0.0,
        help="Opacity above the highest level, outside the outermost contour (default 0, unfilled).")
    add("--fill_outline_linewidth", type=float, default=None,
        help="Width of the lines on the band edges (default: --contour_linewidth).")
    add("--combine_op", default=None, choices=["squared_sum"],
        help="Combine the maps bin by bin (delta-chi2 sum, or quadrature sum of significances).")
    add("--combined_contours_only", action="store_true", default=False, help="Draw only the combined contour.")
    add("--combined_color", type=str, default=None,
        help="Colour of the combined contour (default: the style's ink role), or a palette: 'cycle' or a list/dict style mapping name.")
    add("--combined_linestyle", type=str, default=None,
        help="One line style for every level of the combined contour (default: per-level styles).")
    add("--combined_linewidth", type=float, default=None)
    add("--combined_alpha", type=float, default=1.0)
    add("--combined_label", type=str, default="Combined")
    add("--unified_colors", action="store_true", default=False,
        help="Start every panel at the first palette colour (default: shifted per panel).")
    add("--project", nargs="+", type=str, default=None,
        help="Configs added again as extra maps, rescaled to --project_scale times their exposure.")
    add("--project_datafile", type=str, default=None, help="Datafile of the --project maps (default: first --datafile).")
    add("--project_scale", type=float, default=1, help="Exposure scale of the --project maps.")
    add("--project_reference", type=str, default=None,
        help="Datafile at another exposure: per-bin power law delta-chi2 ~ T^k instead of k = 1.")
    add("--project_label", type=str, default=None, help="Legend suffix of projected contours.")
    _base.add_output_args(parser)
    return parser


def main(argv=None):
    return _base.main(__import__(__name__, fromlist=["run"]), argv)


# --- Histogram / image panels ------------------------------------------------------------


NORM_SUFFIX = {"global": "normalized", "horizontal": "per row", "vertical": "per column",
               "combined": "per row + column"}


def _categorical(values):
    """(positions, names) of an axis: strings become 0, 1, ... with their
    names (in order of first appearance), numbers stay (names None)."""
    values = np.asarray(values)
    if values.ndim != 1 or values.dtype.kind in "biuf":
        return values, None
    try:
        return values.astype(float), None
    except (TypeError, ValueError):
        names = list(dict.fromkeys(str(v) for v in values))
        return np.array([names.index(str(v)) for v in values], dtype=float), names


def _category_ticks(ax, x_names, y_names):
    """One tick per category name; long x names are rotated."""
    if x_names is not None:
        ax.set_xticks(range(len(x_names)), x_names, rotation=45 if max(map(len, x_names)) > 4 else 0,
                      ha="right" if max(map(len, x_names)) > 4 else "center")
        ax.tick_params(axis="x", which="minor", bottom=False, top=False)
    if y_names is not None:
        ax.set_yticks(range(len(y_names)), y_names)
        ax.tick_params(axis="y", which="minor", left=False, right=False)


def annotate_cells(ax, mappable, x, y, values, fmt, skip_masked=None):
    """--annotate: each finite cell value (``values[j, i]`` at x[i], y[j]) in
    its cell, formatted with ``fmt``, dark on light cells and light on dark."""
    fontsize = style.linelabelfontsize

    def luminance(color):
        red, green, blue = to_rgb(color)
        return 0.299 * red + 0.587 * green + 0.114 * blue

    # The style's ink or paper colour, whichever stands out more from the cell.
    ink, paper = style.role("ink"), style.role("paper")
    for j, yj in enumerate(y):
        for i, xi in enumerate(x):
            value = values[j, i]
            if not np.isfinite(value) or (skip_masked is not None and skip_masked[j, i]):
                continue
            cell = luminance(mappable.cmap(mappable.norm(value))[:3])
            color = ink if abs(luminance(ink) - cell) >= abs(luminance(paper) - cell) else paper
            text = format(value, fmt) if "{" not in fmt else fmt.format(value)
            ax.text(xi, yj, text, ha="center", va="center", fontsize=fontsize, color=color, zorder=OVERLAY_ZORDER)


def _colour_scale(mappable, args):
    """--zpower (a power-law norm), --zmin and --zunder on one image or
    histogram."""
    if args.zpower is None and args.zmin is None and args.zunder is None:
        return
    low, high = mappable.get_clim()
    low = args.zmin if args.zmin is not None else max(low, 0) if args.zpower is not None else low
    if args.zpower is not None:
        mappable.set_norm(PowerNorm(args.zpower, vmin=low, vmax=high))
    else:
        mappable.set_clim(low, high)
    if args.zunder is not None:
        mappable.set_cmap(mappable.get_cmap().with_extremes(under=args.zunder))


def _power_ticks(mappable, args):
    """On a --zpower colorbar, ticks at the powers of ten (linear ticks crowd
    its top), dropping a decade within 6% of the bar of the one above."""
    colorbar = getattr(mappable, "colorbar", None)
    if args.zpower is None or colorbar is None:
        return
    low, high = mappable.norm.vmin, mappable.norm.vmax
    decades = 10.0 ** np.arange(np.ceil(np.log10(max(low, 1e-12))), np.floor(np.log10(high)) + 1)
    kept = []
    for value in decades[::-1]:
        if not kept or mappable.norm(kept[-1]) - mappable.norm(value) >= 0.06:
            kept.append(value)
    colorbar.set_ticks(kept[::-1], labels=[f"{d:g}" for d in kept[::-1]])
    colorbar.ax.minorticks_off()


def normalize_hist2d(h, mode):
    """Normalise a (nx, ny) histogram: global, horizontal (each y slice),
    vertical (each x slice) or combined (row + column totals)."""
    if mode is None:
        return h
    h = h.astype(float)
    if mode == "global":
        total = h.sum()
        return h / total if total != 0 else h
    if mode == "horizontal":
        sums = h.sum(axis=0, keepdims=True)
    elif mode == "vertical":
        sums = h.sum(axis=1, keepdims=True)
    elif mode == "combined":
        sums = h.sum(axis=0, keepdims=True) + h.sum(axis=1, keepdims=True)
    else:
        raise ValueError(f"Unknown norm mode: {mode}")
    sums[sums == 0] = 1
    return h / sums


def is_integer_valued(values):
    if np.issubdtype(values.dtype, np.integer):
        return values.size > 0
    finite = values[np.isfinite(values)]
    return finite.size > 0 and np.allclose(finite, np.round(finite))


def integer_bin_edges(vmin, vmax):
    """One bin per integer between vmin and vmax."""
    return np.arange(int(np.floor(vmin)), int(np.ceil(vmax)) + 2) - 0.5


def _panels(df, args):
    """[(variable, hue)] panels and the hue values."""
    hues = filter_dataframe(df, args)[args.iterable].unique() if args.iterable is not None else [None]
    variables = args.variables if args.variables is not None else [None]
    return [(v, h) for v in variables for h in hues], list(hues)


def _panel_rows(df, args, variable, hue):
    if variable is not None:
        return df[df["Variable"] == variable]
    if hue is not None:
        return df[df[args.iterable] == hue]
    return df


def draw_histogram_figure(rows, args, kdx):
    panels, hues = _panels(rows, args)
    fig, axes, _, _ = create_panels(len(panels), grid=False)
    ranges = None
    colorbars = []  # (ax, mappable, label) per panel
    subsets = []
    regions = {}  # panel -> legend handles of its --contour sample regions
    for pdx, (variable, hue) in enumerate(panels):
        ax = axes[pdx]
        subset = filter_dataframe(_panel_rows(rows, args, variable, hue), args)
        subsets.append(subset)
        if len(subset[args.x].values) > 1:
            rprint(f"[red]Error:[/red] Multiple entries found for {variable if variable is not None else f'{args.iterable}={hue}'}")
            plt.close(fig)
            return None
        x = np.array(subset[args.x].values[0])
        y = np.array(subset[args.y].values[0])
        z = np.array(subset[args.z].values[0]) if args.z is not None else None
        if z is None:
            valid = np.isfinite(x) & np.isfinite(y)
            if not valid.all():
                rprint(f"[yellow]Warning:[/yellow] Dropping {(~valid).sum()} non-finite entries out of {len(valid)}")
            x, y = x[valid], y[valid]

        x_names = y_names = None
        if z is not None:
            # String axes of a grid (classes, samples) are categories: one tick per name.
            x, x_names = _categorical(x)
            y, y_names = _categorical(y)
        x_range = [np.percentile(x, args.percentile[0]), np.percentile(x, args.percentile[1])]
        y_range = [np.percentile(y, args.percentile[0]), np.percentile(y, args.percentile[1])]
        if ranges is None or not args.zoom:
            ranges = [list(x_range), list(y_range)]
        else:
            ranges = [[max(ranges[0][0], x_range[0]), min(ranges[0][1], x_range[1])],
                      [max(ranges[1][0], y_range[0]), min(ranges[1][1], y_range[1])]]

        if z is not None:
            if args.norm is not None:
                # A grid is z[y, x]: rows are y slices.
                z = normalize_hist2d(np.asarray(z, dtype=float).T, args.norm).T
            mappable = plot_data(args, ax, x, y=y, plot_type="image", z=z,
                                 **({"cmap": args.cmap} if args.cmap is not None else {}))
            if args.logz:
                mappable.set_array(np.ma.masked_less_equal(mappable.get_array(), 0))
            if args.rangez is not None:
                mappable.set_clim(*args.rangez)
                if args.logz:
                    # Bins below the log floor stay blank instead of taking the lowest colour.
                    mappable.set_cmap(mappable.get_cmap().with_extremes(under="none"))
            _colour_scale(mappable, args)
            label = resolve_axis_label(args.labelz, args.z, subset)
            if args.norm is not None and args.labelz is None:
                label = f"{label} ({NORM_SUFFIX[args.norm]})"
            colorbars.append((ax, mappable, label))
            ax._plotipus_categories = (x_names, y_names)
            if args.annotate is not None and np.ndim(x) == 1 and np.ndim(y) == 1:
                cells = np.ma.filled(np.ma.asarray(mappable.get_array(), dtype=float), np.nan)
                annotate_cells(ax, mappable, x, y, cells.reshape(len(y), len(x)), args.annotate)
            if args.matrix:
                ax._plotipus_matrix = True
        else:
            label = args.labelz or (NORM_LABELS[args.norm] if args.norm else "Density" if args.density else "Counts")
            if args.map_type == "hexbin":
                colorbars.append((ax, draw_hexbin(ax, x, y, x_range, y_range, args), label))
            else:
                hist, mesh = draw_hist2d(ax, x, y, x_range, y_range, args)
                colorbars.append((ax, mesh, label))
                if args.annotate is not None:
                    centres = [0.5 * (edges[1:] + edges[:-1]) for edges in (hist[1], hist[2])]
                    shape = (len(centres[1]), len(centres[0]))
                    annotate_cells(ax, mesh, *centres, np.ma.getdata(mesh.get_array()).reshape(shape), args.annotate,
                                   skip_masked=np.ma.getmaskarray(mesh.get_array()).reshape(shape))
                if args.contour:
                    regions[pdx] = draw_sample_regions(ax, hist[0], hist[1], hist[2], args)

        if args.diagonal:
            _diagonal(ax, x_range, color=style.role("ink") if args.logz else style.role("paper"))
            ax.set_xlim(ranges[0])
            ax.set_ylim(ranges[0])

    draw_colorbars(fig, colorbars, args)
    for _, mappable, _ in colorbars:
        _power_ticks(mappable, args)

    for pdx, ((variable, hue), ax) in enumerate(zip(panels, axes)):
        hue_index = hues.index(hue) if hue in hues else 0
        variable_index = (args.variables or [None]).index(variable) if args.variables else 0
        if len(panels) > 1:
            if args.panel_title is not None and hue_index < len(args.panel_title):
                title = args.panel_title[hue_index]
            else:
                # The panel's variable (with several --variables), then its hue value.
                parts = [_title_case_words(variable)] if variable is not None and len(args.variables or []) > 1 else []
                parts.append(make_subtitle_from_args(args, hues, plot_type="hist2d", idx=hue_index))
                title = " - ".join(part for part in parts if part)
            ax.set_title(title, fontsize=style.subtitlefontsize)
        xlabel = resolve_axis_label(args.labelx, args.x, subsets[pdx])
        ax.set_xlabel(r"Time ($\mu$s)" if xlabel == "Time" else xlabel)
        if variable_index == 0:
            ax.set_ylabel(resolve_axis_label(args.labely, args.y, subsets[pdx]))
        if args.matchx:
            ax.set_xlim(ranges[0])
        if args.matchy:
            ax.set_ylim(ranges[1])
        if args.rangex is not None:
            ax.set_xlim(args.rangex)
        if args.rangey is not None:
            ax.set_ylim(args.rangey)
        if args.logx:
            ax.set_xscale("log")
        if args.logy:
            ax.set_yscale("log")
        if getattr(ax, "_plotipus_matrix", False):
            low, high = sorted(ax.get_ylim())
            ax.set_ylim(high, low)
        apply_tick_formatter(ax, axis="both")
        _category_ticks(ax, *getattr(ax, "_plotipus_categories", (None, None)))
        draw_overlays(ax, args)
    if compact(args, len(panels)) and len(panels) > 1:
        # One y range spanning every panel's, then shared.
        low = min(ax.get_ylim()[0] for ax in axes[:len(panels)])
        high = max(ax.get_ylim()[1] for ax in axes[:len(panels)])
        share_rows(axes[:len(panels)], args)
        axes[0].set_ylim(low, high)
    handle_lists = [regions.get(pdx, []) for pdx in range(len(panels))]
    for pdx in legend_panels(handle_lists):
        handles = handle_lists[pdx]
        apply_legend_style_clear_of_data(axes[pdx], handles=handles, labels=[h.get_label() for h in handles])

    add_title_and_note(fig, args)
    return save(fig, args, kdx, suffix="hist2d.png")


def corner_edges(values, args):
    """Bin edges of one --corner variable over its --percentile range,
    --bins wide (integer-aligned for integer-valued data, never narrower than
    one unit)."""
    low, high = np.percentile(values, args.percentile[0]), np.percentile(values, args.percentile[1])
    nbins = args.bins or style.nbins
    nbins = nbins[0] if isinstance(nbins, (list, tuple)) else int(nbins)
    if is_integer_valued(values):
        width = max(1, int(np.ceil((np.ceil(high) - np.floor(low) + 1) / nbins)))
        return np.arange(np.floor(low), np.ceil(high) + width + 1, width) - 0.5
    if high <= low:
        low, high = low - 0.5, high + 0.5
    return np.linspace(low, high, nbins + 1)


def corner_figure_size(n, posterior_mode=False):
    """The medium's width for two facets side by side (one plot's width with
    --layout panels, as on paper), at one plot's aspect: every panel keeps
    the proportions of a single plot. A posterior corner plot in a medium
    that keeps side-by-side panels at one plot's width (paper) is drawn at
    the style's 'double' width instead, unless a --width was given: its
    panels, titles and legend do not fit one column."""
    from ..plot import get_common_figsize

    width, height = get_common_figsize()
    wide = get_common_figsize(ncols=min(n, 2))[0]
    double = style.widths.get("double")
    given = style._CONFIG.get("cli_geometry", {}).get("width") is not None
    if posterior_mode and double is not None and style.figure_width is not None and not given \
            and style.figure_layout_mode == "panels" and not style.figure_single_panel:
        double = float(double["width"] if isinstance(double, dict) else double)
        if double > wide:
            _notice("corner-double", f"a posterior corner plot is drawn at the double-column width ({double:g} in) in this "
                    "medium; --width single keeps one column")
            wide = double
    return wide, height * wide / width


def draw_corner_diagonal(ax, values, edges):
    """Histogram of one variable: a step outline in ink over its Garwood
    (68.3%) band."""
    from .. import intervals

    counts, _ = np.histogram(values, bins=edges)
    low, high = intervals.garwood(counts)
    ink = style.role("ink")
    ax.stairs(high, edges, baseline=low, fill=True, color=ink, alpha=0.2, linewidth=0)
    ax.stairs(counts, edges, color=ink, linewidth=1.2)
    ax.set_ylim(0, 1.1 * high.max())


# The central 68.3% interval of a marginal: the 1 sigma quantiles around the median.
CREDIBLE_QUANTILES = (0.15865525393145707, 0.5, 0.8413447460685429)
CREDIBLE_LEVEL = CREDIBLE_QUANTILES[2] - CREDIBLE_QUANTILES[0]


def weighted_quantiles(values, weights, quantiles):
    """Quantiles of weighted values (unit weights for None): the weighted
    ECDF taken at each value's mid-weight, interpolated."""
    return posterior.weighted_quantiles(values, weights, quantiles)


def _notice(key, message):
    """Print a warning once per process."""
    if key not in _NOTICES_SHOWN:
        _NOTICES_SHOWN.add(key)
        rprint(f"[yellow]Warning:[/yellow] {message}")


def corner_samples(subset, args):
    """The samples of a corner plot, each a dict (label, color, columns,
    weights, and for posteriors lengths, loglike and labels): the one row of
    arrays; with --contour and --contour_hue, one sample per value of that
    column (its rows joined, each row a chain), overlaid in the panels. None,
    after an error message, when the rows do not fit."""
    hue = args.contour_hue if args.contour else None
    if hue is None and len(subset) != 1:
        rprint(f"[red]Error:[/red] --corner needs one row of arrays, found {len(subset)} "
               f"(narrow it with --select or --configs/--names"
               + (", or overlay the rows with --contour_hue COLUMN)" if args.contour else ")"))
        return None
    groups = [(None, subset)] if hue is None else [(value, subset[subset[hue] == value]) for value in pd.unique(subset[hue])]
    join = lambda cells: np.concatenate([np.asarray(cell, dtype=float).ravel() for cell in cells])  # noqa: E731
    label_columns = [entry[0] for entry in getattr(args, "corner_split", None) or [] if len(entry) == 1]
    loglike = getattr(args, "loglike", None) if getattr(args, "corner_upper", None) == "profile" else None
    block_columns = list(getattr(args, "corner_block", None) or []) if args.contour else []
    prior_value = getattr(args, "corner_prior", None) if hue is not None else None
    is_prior = lambda value: prior_value is not None and str(value) == str(prior_value)  # noqa: E731
    allocator = ColorAllocator()
    if hue is not None:  # the prior takes the neutral colour, not one of the palette
        allocator.reserve([value for value, _ in groups if not is_prior(value)], lambda value: hue_color(value, args, hue))
    samples, dropped, total = [], 0, 0
    for value, frame in groups:
        columns = [join(frame[variable].values) for variable in args.corner]
        weights = join(frame[args.weight].values) if args.weight else None
        extra = join(frame[loglike].values) if loglike else None
        lengths = [np.asarray(cell).size for cell in frame[args.corner[0]].values]
        # A label per draw (an array cell) or per row (a scalar cell, repeated over the row's draws).
        labels = {name: np.concatenate([np.asarray(cell, dtype=object).ravel() if np.ndim(cell) else np.full(size, cell, dtype=object)
                                        for cell, size in zip(frame[name].values, lengths)]) for name in label_columns}
        block = {name: join(frame[name].values) for name in block_columns}
        sizes = {len(c) for c in columns} | {len(a) for a in (weights, extra, *labels.values(), *block.values()) if a is not None}
        if len(sizes) != 1:
            names = [*args.corner, *(n for n in (args.weight, loglike, *label_columns, *block_columns) if n)]
            rprint(f"[red]Error:[/red] --corner: the arrays of {', '.join(names)} differ in length"
                   + (f" for {hue} = {value}" if hue is not None else ""))
            return None
        valid = np.logical_and.reduce([np.isfinite(c) for c in columns]
                                      + [np.isfinite(a) for a in (weights, extra, *block.values()) if a is not None])
        dropped, total = dropped + int((~valid).sum()), total + len(valid)
        if not valid.any():
            continue
        bounds = np.r_[0, np.cumsum(lengths)]
        samples.append({
            "label": None if value is None else map_iterable_label(value, hue, args.iterable_mapping),
            "color": style.role("muted") if is_prior(value) else allocator.color_for(value if hue is not None else "sample"),
            "prior": is_prior(value),
            "block": {name: array[valid] for name, array in block.items()},
            "columns": [c[valid] for c in columns],
            "weights": weights[valid] if weights is not None else None,
            "loglike": extra[valid] if extra is not None else None,
            "labels": {name: array[valid] for name, array in labels.items()},
            "lengths": [int(valid[a:b].sum()) for a, b in zip(bounds[:-1], bounds[1:])],
        })
    if dropped:
        rprint(f"[yellow]Warning:[/yellow] Dropping {dropped} non-finite entries out of {total}")
    if not samples:
        rprint("[red]Error:[/red] --corner: no finite entries to draw")
        return None
    return samples


def corner_variable_info(args, samples):
    """What --corner_cyclic and --corner_bound say of each --corner variable:
    [{"cyclic": (low, high) or None, "bound": (low, high)}] (NaN: no bound).
    Draws of a cyclic variable outside its range are wrapped into it. None,
    after an error message, for a variable that is not drawn or a range that
    cannot be read."""
    info = [{"cyclic": None, "bound": (np.nan, np.nan)} for _ in args.corner]

    def position(name, option):
        if name not in args.corner:
            rprint(f"[red]Error:[/red] {option} {name}: not one of the --corner variables ({', '.join(args.corner)})")
            return None
        return args.corner.index(name)

    for entry in args.corner_cyclic or []:
        index = position(entry[0], "--corner_cyclic")
        if index is None:
            return None
        values = np.concatenate([s["columns"][index] for s in samples])
        try:
            given = [float(v) for v in entry[1:]]
        except ValueError:
            given = [np.nan]
        if len(given) == 2 and given[0] < given[1]:
            low, high = given
        elif not given and values.min() >= -np.pi and values.max() <= np.pi:
            low, high = -np.pi, np.pi
        elif not given and values.min() >= 0 and values.max() <= 2 * np.pi:
            low, high = 0.0, 2 * np.pi
        else:
            rprint(f"[red]Error:[/red] --corner_cyclic {entry[0]}: give its range as LOW HIGH "
                   f"(the draws span {values.min():.4g} to {values.max():.4g}, neither [-pi, pi] nor [0, 2 pi])")
            return None
        outside = int(((values < low) | (values > high)).sum())
        if outside:
            rprint(f"[yellow]Warning:[/yellow] --corner_cyclic {entry[0]}: {outside} draws outside [{low:.4g}, {high:.4g}] "
                   "are wrapped into it")
            for sample in samples:
                sample["columns"][index] = low + np.mod(sample["columns"][index] - low, high - low)
        info[index]["cyclic"] = (low, high)
    for name, low, high in args.corner_bound or []:
        index = position(name, "--corner_bound")
        if index is None:
            return None
        try:
            low, high = float(low), float(high)
        except ValueError:
            rprint(f"[red]Error:[/red] --corner_bound {name}: LOW and HIGH are numbers ('nan' for no bound)")
            return None
        values = np.concatenate([s["columns"][index] for s in samples])
        outside = int(((values < low) | (values > high)).sum())  # comparisons with NaN are False
        if outside:
            rprint(f"[yellow]Warning:[/yellow] --corner_bound {name}: {outside} draws lie outside the bounds and are not drawn")
        info[index]["bound"] = (low, high)
    return info


def corner_posterior_edges(values, args, info):
    """Bin edges of a posterior's variable: one period of a cyclic variable;
    else :func:`corner_edges`, which stop at a --corner_bound and start from
    it when the draws come within a tenth of the range of it."""
    nbins = args.bins or style.nbins
    nbins = nbins[0] if isinstance(nbins, (list, tuple)) else int(nbins)
    if info["cyclic"] is not None:
        return np.linspace(*info["cyclic"], nbins + 1)
    edges = corner_edges(values, args)
    low, high = edges[0], edges[-1]
    bound_low, bound_high = info["bound"]
    if np.isfinite(bound_low) and low - bound_low < 0.1 * (high - low):
        low = bound_low
    if np.isfinite(bound_high) and bound_high - high < 0.1 * (high - low):
        high = bound_high
    return edges if (low, high) == (edges[0], edges[-1]) else np.linspace(low, high, nbins + 1)


def credible_fractions(args):
    """Content of the regions of sampled points, innermost first:
    --corner_levels (in percent), else that of the --contour_sigmas levels
    (68.3, 95.4 and 99.7% with 2 dof; 39.3, 86.5 and 98.9% with --contour_dof 1)."""
    from scipy.stats import chi2

    levels = getattr(args, "corner_levels", None)
    if levels:
        return sorted(set(float(p) / 100.0 for p in levels if 0 < p < 100))
    sigmas = sorted(set(float(s) for s in args.contour_sigmas if np.isfinite(s)))
    return [float(chi2.cdf(level, 2)) for level in contour_levels(sigmas, "sigma_probability", args.contour_dof)]


def level_text(fraction, args):
    """'68.3%' ('90%' for a --corner_levels value)."""
    return f"{100 * fraction:g}%" if getattr(args, "corner_levels", None) else f"{100 * fraction:.1f}%"


def _contour_grid(density, xedges, yedges, pads=(None, None)):
    """(x, y, density) to contour: the bin centres, with one more column or
    row past each end named in ``pads`` (per axis, (low, high) of 'wrap' for
    a cyclic axis, 'edge' for a hard bound, None), so that a region reaches
    the end of the axis instead of stopping half a bin short of it."""
    grids = []
    for axis, (edges, pad) in enumerate(zip((xedges, yedges), pads)):
        centres = 0.5 * (edges[1:] + edges[:-1])
        low, high = pad if pad is not None else (None, None)
        step = edges[1] - edges[0]
        for side, kind in (("low", low), ("high", high)):
            if kind is None:
                continue
            take = (-1 if side == "low" else 0) if kind == "wrap" else (0 if side == "low" else -1)
            extra = np.take(density, [take], axis=axis)
            density = np.concatenate([extra, density] if side == "low" else [density, extra], axis=axis)
            centres = np.r_[centres[0] - step, centres] if side == "low" else np.r_[centres, centres[-1] + step]
        grids.append(centres)
    return grids[0], grids[1], density


def corner_pads(info, edges):
    """Per variable, how its contouring grid continues past the ends of its axis (see :func:`_contour_grid`)."""
    pads = []
    for entry, edge in zip(info, edges):
        if entry["cyclic"] is not None:
            pads.append(("wrap", "wrap"))
        else:
            low, high = entry["bound"]
            pads.append(("edge" if np.isfinite(low) and np.isclose(edge[0], low) else None,
                         "edge" if np.isfinite(high) and np.isclose(edge[-1], high) else None))
    return pads


def draw_corner_regions(ax, sample, c, r, xedges, yedges, fractions, args, alpha, modes=("reflect", "reflect"),
                        pads=(None, None)):
    """Credible regions of one sample in the (c, r) panel: the smallest
    regions holding each fraction of its (weighted) points, from the 2D
    histogram smoothed by --contour_smoothing_sigma bins (default 1; around
    the end of a cyclic axis with the mode 'wrap'), filled from the sample's
    colour (innermost) towards the paper, with outlines. With
    --corner_mc_error, the outermost outline of that many resamplings of the
    histogram at the effective sample size, as hairlines."""
    counts, _, _ = np.histogram2d(sample["columns"][c], sample["columns"][r], bins=[xedges, yedges], weights=sample["weights"])
    sigma = args.contour_smoothing_sigma or 1.0
    density = _smooth(counts, sigma, modes)
    thresholds = sample_region_thresholds(density, fractions)
    levels = sorted(set(t for t in thresholds if np.isfinite(t) and 0 < t < density.max()))  # outermost first
    if not levels:
        return
    xc, yc, drawn = _contour_grid(density, xedges, yedges, pads)
    bands = sample["bands"][:len(levels)][::-1]
    ax.contourf(xc, yc, drawn.T, levels=levels + [np.inf], colors=bands, alpha=alpha, zorder=2)
    ax.contour(xc, yc, drawn.T, levels=levels, colors=[sample["color"]], linewidths=0.6 * args.contour_linewidth,
               linestyles="solid", zorder=2.5)
    if args.corner_mc_error:
        rng = np.random.default_rng(1000 * c + r)  # the same hairlines every time the figure is drawn
        total = float(np.sum(sample["weights"])) if sample["weights"] is not None else float(len(sample["columns"][c]))
        for _ in range(int(args.corner_mc_error)):
            resampled = _smooth(posterior.resampled_counts(counts, total, sample["ess"], rng), sigma, modes)
            (level,) = sample_region_thresholds(resampled, fractions[-1:])
            if np.isfinite(level) and 0 < level < resampled.max():
                ax.contour(xc, yc, _contour_grid(resampled, xedges, yedges, pads)[2].T, levels=[level], colors=[sample["color"]], linewidths=0.25 * args.contour_linewidth,
                           alpha=0.45, zorder=2.6)


def corner_summary(sample, index, edges, info, args, level, outer):
    """How the marginal of one variable is summarised: a dict with ``kind``
    ('interval', 'pieces' or 'limit'), ``pieces`` [(low, high)] to shade,
    ``centre`` (the median or the mode; the limit), ``method`` (for the
    legend) and ``error``, the Monte Carlo error of the centre.

    * the central interval around the median (default), at ``level``;
    * with --corner_interval hdi, and always for a cyclic variable, the
      highest-density region: one interval around the mode (past the end of
      a cyclic axis when it wraps) or several pieces, never merged;
    * for a variable with a --corner_bound whose highest-density region
      touches the bound (and for every bounded one with --corner_interval
      limit), a one-sided limit holding ``outer`` of the marginal."""
    values, weights = sample["columns"][index], sample["weights"]
    percent, mode = level_text(level, args), args.corner_interval
    cyclic, bound = info["cyclic"], info["bound"]
    error = posterior.quantile_error(values, weights, 0.5, sample["ess"])
    bounded = np.isfinite(bound).any() and cyclic is None
    if cyclic is not None or mode == "hdi" or (bounded and mode in (None, "limit")):
        fine, density = posterior.fine_density(values, weights, edges, cyclic is not None, bound)
        pieces, peak = posterior.density_pieces(fine, density, level, cyclic is not None)
        step = fine[1] - fine[0]
        at_low = np.isfinite(bound[0]) and pieces and pieces[0][0] <= bound[0] + 1.5 * step
        at_high = np.isfinite(bound[1]) and pieces and pieces[-1][1] >= bound[1] - 1.5 * step
        if bounded and mode == "limit" and not (at_low or at_high):
            at_low = np.isfinite(bound[0]) and (not np.isfinite(bound[1]) or peak - bound[0] < bound[1] - peak)
            at_high = not at_low
        if bounded and mode in (None, "limit") and (at_low or at_high):
            lower_side = bool(at_low and not (at_high and density[-1] > density[0]))
            (limit,) = weighted_quantiles(values, weights, [outer if lower_side else 1 - outer])
            pieces = [(bound[0], float(limit))] if lower_side else [(float(limit), bound[1])]
            return {"kind": "limit", "pieces": pieces, "centre": float(limit), "side": "<" if lower_side else ">",
                    "method": f"{level_text(outer, args)} limit", "error": error, "auto": mode is None}
        if cyclic is not None or mode == "hdi":
            if cyclic is not None and mode != "hdi":
                _notice(("cyclic", args.corner[index]),
                        f"{args.corner[index]} is cyclic: its interval is the highest-density one (a central interval "
                        "depends on where the axis is cut)")
            if cyclic is not None and pieces and peak < pieces[-1][0] and pieces[-1][1] > cyclic[1]:
                peak += cyclic[1] - cyclic[0]  # the mode lies in the part of the wrapped piece past the end
            return {"kind": "interval" if len(pieces) == 1 else "pieces", "pieces": pieces, "centre": float(peak),
                    "method": f"mode, {percent} HDI", "error": error}
    tail = 0.5 * (1 - level)
    low, median, high = weighted_quantiles(values, weights, [tail, 0.5, 1 - tail])
    return {"kind": "interval", "pieces": [(float(low), float(high))], "centre": float(median),
            "method": f"median, central {percent}", "error": error}


def draw_corner_marginal(ax, sample, index, edges, summary=None, period=None):
    """Marginal of one variable: the (weighted) density as a step outline in
    the sample's colour; with a ``summary`` (a single sample), shaded over
    its pieces (a piece past the end of a cyclic axis continues from its
    start), with a line at the median, the mode or the limit. Returns the
    peak density."""
    values, weights, color = sample["columns"][index], sample["weights"], sample["color"]
    density, _ = np.histogram(values, bins=edges, weights=weights, density=True)
    density = np.nan_to_num(density)
    height = lambda x: density[np.clip(np.searchsorted(edges, x, side="right") - 1, 0, len(density) - 1)]  # noqa: E731
    if summary is not None:
        shown = []
        for low, high in summary["pieces"]:
            low = edges[0] if not np.isfinite(low) else low
            high = edges[-1] if not np.isfinite(high) else high
            if period is not None and high > edges[-1]:
                shown += [(low, edges[-1]), (edges[0], high - period)]
            else:
                shown.append((low, high))
        for low, high in shown:
            inside = np.linspace(max(low, edges[0]), min(high, edges[-1]), 400)
            ax.fill_between(inside, height(inside), color=color, alpha=0.25, linewidth=0)
        if summary["kind"] != "pieces":
            centre = summary["centre"] - period if period is not None and summary["centre"] > edges[-1] else summary["centre"]
            ax.plot([centre, centre], [0, float(height(centre))], color=color, linewidth=1.0)
    ax.stairs(density, edges, color=color, linewidth=1.2)
    return float(density.max())


def _split_unit(label):
    """('E', 'GeV') for 'E (GeV)' or 'E [GeV]'; (label, None) without a unit."""
    import re

    match = re.match(r"^(.*\S)\s*[(\[]([^()\[\]]+)[)\]]\s*$", label or "")
    return (match.group(1), match.group(2)) if match else (label, None)


def _decimals(value, digits=2):
    """Decimals that show ``digits`` significant figures of ``value``."""
    return int(np.clip(digits - 1 - np.floor(np.log10(abs(value))), 0, 6)) if value and np.isfinite(value) else 2


def credible_text(low, median, high, mc_error=None):
    """'$1.20^{+0.10}_{-0.11}$': the median with the distances to the
    interval's ends, to two significant figures of the smaller one, with a
    common power of ten for very small or large values. With ``mc_error``
    (the Monte Carlo error of the median), no digit past its leading one."""
    up, down = high - median, median - low
    scale = max(abs(median), up, down)
    exponent = int(np.floor(np.log10(scale))) if scale > 0 and not 1e-3 <= scale < 1e4 else 0
    median, up, down = (v / 10.0**exponent for v in (median, up, down))
    sides = [s for s in (up, down) if s > 0]
    decimals = int(np.clip(1 - np.floor(np.log10(min(sides))), 0, 6)) if sides else 2
    if mc_error and np.isfinite(mc_error) and mc_error > 0:
        decimals = min(decimals, max(0, int(-np.floor(np.log10(mc_error / 10.0**exponent)))))
    text = f"{median:.{decimals}f}^{{+{up:.{decimals}f}}}_{{-{down:.{decimals}f}}}"
    return f"$({text}) \\times 10^{{{exponent}}}$" if exponent else f"${text}$"


def summary_text(summary, label, args, outer):
    """The title of a diagonal panel: 'm = 124.95 +0.25 -0.25 GeV', the
    pieces of a highest-density region as a union, or a limit with its
    content."""
    name, unit = _split_unit(label)
    unit = f" {unit}" if unit else ""
    if summary["kind"] == "limit":
        value = summary["centre"]
        return f"{name} ${summary['side']}$ ${value:.{_decimals(value)}f}${unit} ({level_text(outer, args)})"
    if summary["kind"] == "pieces":
        decimals = _decimals(min(high - low for low, high in summary["pieces"]))
        union = " $\\cup$ ".join(f"[${low:.{decimals}f}$, ${high:.{decimals}f}$]" for low, high in summary["pieces"])
        return f"{name} $\\in$ {union}{unit}"
    (low, high), centre = summary["pieces"][0], summary["centre"]
    text = credible_text(low, centre, high, summary["error"])
    if text != credible_text(low, centre, high):
        _notice(("digits", label), f"{name}: the Monte Carlo error of its estimate ({summary['error']:.2g}) is larger than "
                "the last digit of its interval; the title is rounded to it")
    return f"{name} = {text}{unit}"


def corner_truths(args, n):
    """--corner_truth as one value per variable (NaN: none)."""
    values = list(args.corner_truth or [])
    if len(values) > n:
        rprint(f"[yellow]Warning:[/yellow] --corner_truth: {len(values)} values for {n} variables; the last ones are ignored")
    return [values[i] if i < len(values) else np.nan for i in range(n)]


def corner_bands(args):
    """--corner_band as [(variable index, low, high, label or None)]; None after an error message."""
    bands = []
    for entry in args.corner_band or []:
        try:
            index, low, high = args.corner.index(entry[0]), float(entry[1]), float(entry[2])
        except (ValueError, IndexError):
            rprint("[red]Error:[/red] --corner_band takes VARIABLE LOW HIGH [LABEL], the variable one of --corner "
                   f"({', '.join(args.corner)})")
            return None
        bands.append((index, min(low, high), max(low, high), parse_plot_label(" ".join(entry[3:])) if len(entry) > 3 else None))
    return bands


def corner_splits(args, samples, labels):
    """--corner_split as [{"index" (a drawn variable, or None), "value",
    "parts": per sample [(text, mask)]}]: the two sides of a value of a drawn
    variable, or the values of a label column. None after an error message."""
    splits = []
    for entry in args.corner_split or []:
        if len(entry) == 2 and entry[0] in args.corner:
            index = args.corner.index(entry[0])
            try:
                value = float(entry[1])
            except ValueError:
                rprint(f"[red]Error:[/red] --corner_split {entry[0]} {entry[1]}: the value is a number")
                return None
            name = _split_unit(labels[index])[0]
            parts = [[(f"{name} $>$ {value:g}", s["columns"][index] > value), (f"{name} $<$ {value:g}", s["columns"][index] < value)]
                     for s in samples]
            splits.append({"index": index, "value": value, "parts": parts})
        elif len(entry) == 1:
            values = list(pd.unique(np.concatenate([s["labels"][entry[0]] for s in samples])))
            if len(values) > 6:
                rprint(f"[red]Error:[/red] --corner_split {entry[0]}: {len(values)} values; a split takes a column of a few labels")
                return None
            parts = [[(f"{entry[0]} = {value}", s["labels"][entry[0]] == value) for value in values] for s in samples]
            splits.append({"index": None, "value": None, "parts": parts})
        else:
            rprint("[red]Error:[/red] --corner_split takes VARIABLE VALUE (a --corner variable) or one label COLUMN")
            return None
    return splits


def _probability_text(p, error):
    decimals = int(np.clip(-np.floor(np.log10(error)), 2, 5)) if np.isfinite(error) and error > 0 else 3
    return f"{p:.{decimals}f} $\\pm$ {error:.{decimals}f}"


# The profile-likelihood regions are lighter than a sample's: they are the second view, in the neutral colour.
PROFILE_FILL = 0.55
SPLIT_LINESTYLES = ["--", ":", "-.", (0, (1, 3)), (0, (5, 1)), (0, (3, 1, 1, 1))]


def split_entries(splits, samples, args):
    """Legend entries (handle, text) of the splits: the probability of each
    part with its error, and for a split in two the odds of the first part
    against the second (the Bayes factor with --prior_odds). With
    --corner_split_marginals the entries of the first split carry the line
    styles of its parts in the diagonal panels."""
    entries = []
    blank = lambda: Line2D([], [], linestyle="none")  # noqa: E731
    for number, split in enumerate(splits):
        drawn = args.corner_split_marginals and number == 0
        for sample, parts in zip(samples, split["parts"]):
            prefix = f"{sample['label']}: " if sample["label"] is not None and len(samples) > 1 else ""
            results = posterior.split_probabilities([mask for _, mask in parts], sample["weights"], sample["ess"])
            binary = len(parts) == 2
            for k, ((text, _), (p, error)) in enumerate(zip(parts, results)):
                if binary and k == 1 and not drawn:
                    continue  # the second side of two is one minus the first
                handle = Line2D([], [], color=sample["color"], linewidth=1.0, linestyle=SPLIT_LINESTYLES[k]) \
                    if drawn else blank()
                entries.append((handle, f"{prefix}$P$({text}) = {_probability_text(p, error)}"))
            if binary and 0 < results[0][0] < 1:
                p, error = results[0]
                odds, odds_error = p / (1 - p), error / (1 - p) ** 2
                if args.prior_odds:
                    odds, odds_error = odds / args.prior_odds, odds_error / args.prior_odds
                    name = f"Bayes factor (prior odds {args.prior_odds:g})"
                else:
                    name = "posterior odds"
                decimals = _decimals(odds_error, 1) if np.isfinite(odds_error) and odds_error > 0 else 2
                entries.append((blank(), f"{prefix}{name} {odds:.{decimals}f} $\\pm$ {odds_error:.{decimals}f}"))
    return entries


def draw_split_marginals(ax, sample, parts, index, edges):
    """The parts of a split in a diagonal panel: the density of each part
    scaled by its share, so that the parts add up to the marginal."""
    weights = np.ones(len(sample["columns"][index])) if sample["weights"] is None else sample["weights"]
    width = np.diff(edges)
    for k, (_, mask) in enumerate(parts):
        counts, _ = np.histogram(sample["columns"][index][mask], bins=edges, weights=weights[mask])
        ax.stairs(counts / (weights.sum() * width), edges, color=sample["color"], linewidth=0.9, linestyle=SPLIT_LINESTYLES[k])


def draw_corner_profile(ax, sample, c, r, xedges, yedges, fractions, args, pads=(None, None)):
    """The profile likelihood of the (c, r) pair in its mirrored cell: the
    regions where -2 ln L, minimised over the draws of each bin, lies within
    the delta-chi2 of each fraction (2 dof) of the best draw, in the neutral
    colour with dashed outlines, and the best draw as a star. Bins with fewer
    than posterior.PROFILE_MIN_DRAWS draws are left out. Returns (bins with
    draws, bins left out)."""
    from scipy.stats import chi2 as chi2_law

    chi2 = -2.0 * sample["loglike"]
    best, counts = posterior.profile_grid(chi2, [posterior.bin_index(sample["columns"][c], xedges),
                                                 posterior.bin_index(sample["columns"][r], yedges)],
                                          (len(xedges) - 1, len(yedges) - 1))
    levels = [float(chi2_law.ppf(f, 2)) for f in fractions]
    thin = (counts > 0) & (counts < posterior.PROFILE_MIN_DRAWS)
    delta = np.where(counts >= posterior.PROFILE_MIN_DRAWS, best - chi2.min(), np.inf)
    delta = _smooth(np.minimum(delta, 3 * levels[-1]), 0.5 * (args.contour_smoothing_sigma or 1.0))
    xc, yc, delta = _contour_grid(delta, xedges, yedges, pads)
    muted, ink = style.role("muted"), style.role("ink")
    mix = [PROFILE_FILL * m for m in fill_mix(len(levels))]
    ax.contourf(xc, yc, delta.T, levels=[-np.inf] + levels, colors=[mix_paper(muted, m) for m in mix], zorder=2)
    ax.contour(xc, yc, delta.T, levels=levels, colors=[ink], linewidths=0.6 * args.contour_linewidth, linestyles="dashed", zorder=2.5)
    at = int(np.argmin(chi2))
    ax.plot([sample["columns"][c][at]], [sample["columns"][r][at]], marker="*", markersize=7, color=ink, linestyle="none",
            zorder=OVERLAY_ZORDER)
    return int((counts > 0).sum()), int(thin.sum())


def draw_marginal_profile(ax, sample, index, edges, peak):
    """The 1D profile likelihood over a marginal: exp(-delta chi2 / 2) of
    the best draw of each bin, scaled to the marginal's peak, dashed in ink."""
    chi2 = -2.0 * sample["loglike"]
    best, counts = posterior.profile_grid(chi2, [posterior.bin_index(sample["columns"][index], edges)], (len(edges) - 1,))
    shown = counts >= posterior.PROFILE_MIN_DRAWS
    centres = 0.5 * (edges[1:] + edges[:-1])
    ax.plot(centres[shown], peak * np.exp(-0.5 * (best[shown] - chi2.min())), color=style.role("ink"), linewidth=1.0,
            linestyle="dashed")


def draw_corner_correlation(ax, samples, c, r, cyclic):
    """The correlation coefficient of the (c, r) pair in its mirrored cell,
    with its Monte Carlo error: one sample on a tint of the diverging map,
    several as one line each in their colours. Empty for a pair with a cyclic
    variable. Returns the texts."""
    ax.set_xticks([]), ax.set_yticks([])
    ax.tick_params(which="both", length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    if cyclic:
        _notice("corr-cyclic", "--corner_upper corr: no coefficient for a pair with a cyclic variable (a linear "
                "correlation does not describe it); its cell is empty")
        return []
    texts = []
    for k, sample in enumerate(samples):
        rho, error = posterior.correlation(sample["columns"][c], sample["columns"][r], sample["weights"], sample["ess"])
        decimals = int(np.clip(-np.floor(np.log10(error)), 2, 3)) if np.isfinite(error) and error > 0 else 2
        value = f"{rho:+.{decimals}f} \\pm {error:.{decimals}f}" if np.isfinite(error) else f"{rho:+.2f}"
        y = 0.5 + (0.5 * (len(samples) - 1) - k) * 0.22
        texts.append(ax.text(0.5, y, f"$\\rho = {value}$", ha="center", va="center", transform=ax.transAxes,
                             color=sample["color"] if len(samples) > 1 else style.role("ink")))
        if len(samples) == 1:
            ax.set_facecolor(mix_paper(plt.get_cmap(style.diverging_cmap)(0.5 + 0.5 * rho), 0.55))
            ax._plotipus_rho = (rho, error)
    return texts


PRIOR_REGION_MAX = 0.8
SHRINKAGE_LEGEND = r"$\sigma/\sigma_0$, $\Delta/\sigma_0$: width, shift in prior widths"


def draw_prior_marginal(ax, values, weights, edges):
    """The prior of a marginal: its density as a dashed step in the neutral colour, never filled."""
    density, _ = np.histogram(values, bins=edges, weights=weights)
    total = float(np.sum(weights)) if weights is not None else float(len(values))
    ax.stairs(density / (total * np.diff(edges)), edges, color=style.role("muted"), linewidth=1.0, linestyle="dashed")


def draw_prior_region(ax, prior, c, r, xedges, yedges, fraction, args, modes, pads):
    """The prior in a pair panel: the outline of its outermost region, dashed
    in the neutral colour. A prior whose region fills more than
    PRIOR_REGION_MAX of the panel (flat over it) has none: its outline would
    be the noise of its histogram."""
    counts, _, _ = np.histogram2d(prior["columns"][c], prior["columns"][r], bins=[xedges, yedges], weights=prior["weights"])
    density = _smooth(counts, args.contour_smoothing_sigma or 1.0, modes)
    (level,) = sample_region_thresholds(density, [fraction])
    if np.isfinite(level) and 0 < level < density.max() and (density >= level).mean() <= PRIOR_REGION_MAX:
        xc, yc, drawn = _contour_grid(density, xedges, yedges, pads)
        ax.contour(xc, yc, drawn.T, levels=[level], colors=[style.role("muted")], linewidths=0.5 * args.contour_linewidth,
                   linestyles="dashed", zorder=2.4)


def prior_shrinkage(values, weights, prior_values, prior_weights):
    """(posterior width / prior width, shift of the median in prior widths),
    a width being half the central 68.3% interval."""
    low, median, high = weighted_quantiles(values, weights, CREDIBLE_QUANTILES)
    prior_low, prior_median, prior_high = weighted_quantiles(prior_values, prior_weights, CREDIBLE_QUANTILES)
    width = 0.5 * (prior_high - prior_low)
    if not width > 0:
        return np.nan, np.nan
    return float(0.5 * (high - low) / width), float((median - prior_median) / width)


def shrinkage_text(shrinkage):
    """The second line of a title: the width and the shift in prior widths."""
    if shrinkage is None or not np.isfinite(shrinkage[0]):
        return ""
    ratio, shift = shrinkage
    return f"\n$\\sigma/\\sigma_0$ = {ratio:.2f}, $\\Delta/\\sigma_0$ = ${shift:+.2f}$"


def corner_block_cells(args, n):
    """The cells of the block of --corner_block: the top-right n//2 x n//2
    cells, which touch no diagonal panel; empty below four variables."""
    size = n // 2
    if not args.corner_block or n < 4:
        return set()
    return {(r, c) for r in range(size) for c in range(n - size, n)}


def draw_corner_block(fig, grid, n, samples, prior, args, level, outer):
    """--corner_block: the marginal of each column in the block, side by
    side in a holder that spans it, each with its own x axis, its interval
    and title (a single sample) and its prior. The panels are inset by the
    room their tick labels, axis label and title take, in inches, so that
    they stay inside the block at every figure size. Returns the panels."""
    from matplotlib.font_manager import FontProperties

    size = n // 2
    holder = fig.add_subplot(grid[0:size, n - size:n])
    holder.set_axis_off()
    names = list(args.corner_block)
    labels = list(args.corner_block_labels or [])
    labels = [labels[i] if i < len(labels) else name for i, name in enumerate(names)]
    box = holder.get_position()
    width, height = box.width * fig.get_figwidth(), box.height * fig.get_figheight()
    line = FontProperties(size=plt.rcParams["axes.labelsize"]).get_size_in_points() / 72.0
    left, gap = min(0.3, 1.5 * line / width), min(0.2, 1.5 * line / width)
    bottom, top = min(0.45, 3.4 * line / height), min(0.3, 1.8 * line / height)
    each = (1.0 - left - gap * (len(names) - 1)) / len(names)
    panels = []
    for k, (name, label) in enumerate(zip(names, labels)):
        ax = holder.inset_axes([left + k * (each + gap), bottom, each, 1.0 - bottom - top])
        edges = corner_edges(np.concatenate([s["block"][name] for s in samples]), args)
        views = [dict(s, columns=[s["block"][name]]) for s in samples]
        summary = None
        if len(samples) == 1:
            summary = corner_summary(views[0], 0, edges, {"cyclic": None, "bound": (np.nan, np.nan)}, args, level, outer)
        peaks = [draw_corner_marginal(ax, view, 0, edges, summary) for view in views]
        if prior is not None:
            draw_prior_marginal(ax, prior["block"][name], prior["weights"], edges)
        ax.set_ylim(0, 1.1 * max(peaks))
        ax.set_xlim(edges[0], edges[-1])
        ax.set_xlabel(label)
        ax.tick_params(which="both", labelleft=False)
        apply_tick_formatter(ax, axis="both")
        ax.xaxis.set_major_locator(MaxNLocator(nbins=5, steps=[1, 2, 2.5, 5, 10]))
        if summary is not None and not args.no_corner_titles:
            ax.set_title(summary_text(summary, label, args, outer), fontsize=plt.rcParams["xtick.labelsize"])
        panels.append(ax)
    return panels


def draw_corner_figure(rows, args, kdx):
    """--corner X1 ... XN: an N x N grid, the pair (Xc, Xr) at row r, column c
    below the diagonal, Xr alone on the diagonal, the upper triangle empty.
    Panels share x down each column and y along each row; labels on the outer
    panels only.

    * Histograms (default): the 2D histogram of each pair on one colour scale
      with one colorbar, the counts of each variable (with their Garwood
      band) on the diagonal, which keeps its counts axis.
    * Posterior samples (--contour): the credible regions of each pair
      (--contour_sigmas or --corner_levels), the marginal density of each
      variable on the diagonal, for a single sample with its interval shaded
      and written above it (:func:`corner_summary`), --contour_hue samples
      overlaid in their colours, --corner_truth lines and --corner_band
      bands. The legend names what the regions and the intervals hold and the
      number of draws, with the probabilities of --corner_split; it takes the
      top-right cell, or goes above the grid when --corner_upper fills the
      upper triangle with the profile likelihood (profile) or the
      correlation coefficients (corr) of each pair."""
    from ..plot import apply_common_figure_margins, apply_panel_font_scale

    variables = args.corner
    subset = filter_dataframe(rows, args)
    samples = corner_samples(subset, args)
    if samples is None:
        return None
    n = len(variables)
    posterior_mode = args.contour
    prior = None
    if posterior_mode and args.corner_prior is not None:
        priors = [sample for sample in samples if sample.get("prior")]
        if len(priors) != 1 or len(samples) < 2:
            rprint(f"[red]Error:[/red] --corner_prior {args.corner_prior}: "
                   + ("no such value of " + args.contour_hue if not priors else "no other sample to draw with the prior"))
            return None
        prior = priors[0]
    everything = samples
    samples = [sample for sample in samples if sample is not prior]
    info = corner_variable_info(args, everything) if posterior_mode else None
    bands = corner_bands(args) if posterior_mode else []
    if posterior_mode and (info is None or bands is None):
        return None
    if posterior_mode:
        edges = [corner_posterior_edges(np.concatenate([s["columns"][i] for s in samples]), args, info[i]) for i in range(n)]
    else:
        edges = [corner_edges(np.concatenate([s["columns"][i] for s in samples]), args) for i in range(n)]
    labels = list(args.corner_labels or [])
    labels = [labels[i] if i < len(labels) else resolve_axis_label(None, v, subset) for i, v in enumerate(variables)]
    upper = args.corner_upper if posterior_mode else None
    splits, block = [], set()
    if posterior_mode:
        cyclic = [i["cyclic"] for i in info]
        for sample in everything:
            sample["size"] = len(sample["columns"][0])
            sample["ess"] = posterior.sample_ess(sample["columns"], sample["weights"], sample["lengths"], cyclic)
        block = corner_block_cells(args, n)
        splits = corner_splits(args, samples, labels)
        if splits is None:
            return None
        if upper == "profile" and len(samples) > 1:
            rprint("[red]Error:[/red] --corner_upper profile draws the profile of one sample; narrow --contour_hue to one "
                   "value with --select")
            return None

    apply_panel_font_scale(1)
    fig = plt.figure(figsize=corner_figure_size(n, posterior_mode))
    # Rows as far apart as the measured layout puts the columns (its pad), close enough to read as one figure.
    rows_height = 0.75 * fig.get_figheight()
    gap = style.figure_pad_inches / (rows_height / n) if style.compact_gap() else 0.0
    row_gap, titles_between = gap, bool(upper) and len(samples) == 1 and not args.no_corner_titles
    if titles_between:
        # The title of a diagonal panel needs its line between the rows when the cell above it is drawn: the
        # measured layout sets the row gap from the titles (two lines when they wrap); this is its minimum.
        from matplotlib.font_manager import FontProperties

        title_inches = 1.5 * FontProperties(size=plt.rcParams["xtick.labelsize"]).get_size_in_points() / 72.0
        row_gap = (style.figure_pad_inches + title_inches) / (rows_height / n)
    grid = fig.add_gridspec(n, n, wspace=gap, hspace=None if titles_between else gap)
    apply_common_figure_margins(fig, hspace=row_gap)
    axes = [[None] * n for _ in range(n)]
    for r in range(n):
        for c in range(r + 1):
            sharex = axes[c][c] if r > c else None
            sharey = axes[r][0] if 0 < c < r else None
            axes[r][c] = fig.add_subplot(grid[r, c], sharex=sharex, sharey=sharey)
    if upper:
        for r in range(n):
            for c in range(r + 1, n):
                if (r, c) in block:
                    continue
                if upper == "profile":  # the pair of (c, r) with its axes exchanged: x of its column, y of its row
                    sharey = axes[r][0] if r > 0 else axes[0][1] if c > 1 else None
                    axes[r][c] = fig.add_subplot(grid[r, c], sharex=axes[c][c], sharey=sharey)
                else:
                    axes[r][c] = fig.add_subplot(grid[r, c])

    mappables, fractions, summaries = [], [], {}
    if posterior_mode:
        fractions = credible_fractions(args)
        if not fractions:
            rprint("[red]Error:[/red] --corner: no region to draw (--corner_levels takes percentages between 0 and 100)")
            plt.close(fig)
            return None
        level = fractions[0] if args.corner_levels else CREDIBLE_LEVEL
        mix = fill_mix(len(fractions))
        for sample in samples:
            sample["bands"] = [mix_paper(sample["color"], m) for m in mix]
        alpha = 1.0 if len(samples) == 1 else 0.6  # overlaid samples show through each other
        modes = ["wrap" if i["cyclic"] is not None else "reflect" for i in info]
        pads = corner_pads(info, edges)
        corner_sample_warnings(samples, fractions, args)
    blanked = [0, 0]
    shrinkage = {}
    for r in range(n):
        for c in range(n if upper else r + 1):
            ax = axes[r][c]
            if ax is None:
                continue  # a cell of the block
            if c > r and upper == "profile":
                seen, thin = draw_corner_profile(ax, samples[0], c, r, edges[c], edges[r], fractions, args, (pads[c], pads[r]))
                blanked = [blanked[0] + seen, blanked[1] + thin]
            elif c > r:
                draw_corner_correlation(ax, samples, c, r, info[c]["cyclic"] is not None or info[r]["cyclic"] is not None)
            elif r == c and posterior_mode:
                single = len(samples) == 1
                period = info[r]["cyclic"][1] - info[r]["cyclic"][0] if info[r]["cyclic"] is not None else None
                if single:
                    summaries[r] = corner_summary(samples[0], r, edges[r], info[r], args, level, fractions[-1])
                peaks = [draw_corner_marginal(ax, sample, r, edges[r], summaries.get(r), period) for sample in samples]
                if prior is not None:
                    draw_prior_marginal(ax, prior["columns"][r], prior["weights"], edges[r])
                    if single and args.corner_shrinkage and summaries[r]["kind"] == "interval" and period is None:
                        shrinkage[r] = prior_shrinkage(samples[0]["columns"][r], samples[0]["weights"], prior["columns"][r],
                                                       prior["weights"])
                for split in splits[:1] if args.corner_split_marginals else []:  # one split: its styles name its parts
                    for sample, parts in zip(samples, split["parts"]):
                        draw_split_marginals(ax, sample, parts, r, edges[r])
                if upper == "profile":
                    draw_marginal_profile(ax, samples[0], r, edges[r], max(peaks))
                ax.set_ylim(0, 1.1 * max(peaks))
                if single and not args.no_corner_titles:
                    ax.set_title(summary_text(summaries[r], labels[r], args, fractions[-1]) + shrinkage_text(shrinkage.get(r)),
                                 fontsize=plt.rcParams["xtick.labelsize"])
            elif r == c:
                draw_corner_diagonal(ax, samples[0]["columns"][r], edges[r])
            elif posterior_mode:
                for sample in samples:
                    draw_corner_regions(ax, sample, c, r, edges[c], edges[r], fractions, args, alpha, (modes[c], modes[r]),
                                        (pads[c], pads[r]))
                if prior is not None:
                    draw_prior_region(ax, prior, c, r, edges[c], edges[r], fractions[-1], args, (modes[c], modes[r]),
                                      (pads[c], pads[r]))
            else:
                x, y = samples[0]["columns"][c], samples[0]["columns"][r]
                x_range, y_range = (edges[c][0], edges[c][-1]), (edges[r][0], edges[r][-1])
                if args.map_type == "hexbin":
                    mappables.append(draw_hexbin(ax, x, y, x_range, y_range, args, gridsize=len(edges[c]) - 1))
                else:
                    mappables.append(draw_hist2d(ax, x, y, x_range, y_range, args, bins=[edges[c], edges[r]])[1])
    if blanked[1]:
        rprint(f"[yellow]Warning:[/yellow] --corner_upper profile: {blanked[1]} of the {blanked[0]} bins with draws hold fewer "
               f"than {posterior.PROFILE_MIN_DRAWS} and are left out of the profile (fewer --bins, or more draws, fill them)")
    for index, (ratio, _) in shrinkage.items():
        if ratio > 0.9:
            rprint(f"[yellow]Warning:[/yellow] {variables[index]}: the posterior is {ratio:.2f} times as wide as the prior; "
                   "the data hardly constrain it")
    block_axes = []
    if posterior_mode and args.corner_block:
        if not block:
            rprint(f"[yellow]Warning:[/yellow] --corner_block needs four or more --corner variables (the block is the "
                   f"top-right {max(n // 2, 1)} x {max(n // 2, 1)} cells of the upper triangle); with {n} it is not drawn")
        else:
            block_axes = draw_corner_block(fig, grid, n, samples, prior, args, level, fractions[-1])
    for index, summary in summaries.items():
        if summary["kind"] == "limit" and summary.get("auto"):
            rprint(f"[yellow]Warning:[/yellow] {variables[index]}: the marginal is highest at its bound, so a one-sided limit "
                   f"holding {level_text(fractions[-1], args)} replaces the interval (--corner_interval quantile or hdi keeps it)")

    truths = corner_truths(args, n)
    ink, muted = style.role("ink"), style.role("muted")
    data_panels = [(r, c) for r in range(n) for c in range(n if upper == "profile" else r + 1) if axes[r][c] is not None]
    for r, c in data_panels:
        ax = axes[r][c]
        for index, low, high, _ in bands:
            if index == c:
                ax.axvspan(low, high, facecolor="none", edgecolor=muted, hatch="////", linewidth=0.0, zorder=2.8)
            if index == r and r != c:
                ax.axhspan(low, high, facecolor="none", edgecolor=muted, hatch="////", linewidth=0.0, zorder=2.8)
        for split in splits:
            if split["index"] == c:
                ax.axvline(split["value"], color=muted, linewidth=0.9, linestyle="dotted", zorder=OVERLAY_ZORDER - 0.1)
            if split["index"] == r and r != c:
                ax.axhline(split["value"], color=muted, linewidth=0.9, linestyle="dotted", zorder=OVERLAY_ZORDER - 0.1)
        if np.isfinite(truths[c]):
            ax.axvline(truths[c], color=ink, linewidth=0.9, zorder=OVERLAY_ZORDER)
        if r != c and np.isfinite(truths[r]):
            ax.axhline(truths[r], color=ink, linewidth=0.9, zorder=OVERLAY_ZORDER)
            if np.isfinite(truths[c]):
                ax.plot([truths[c]], [truths[r]], marker="s", markersize=3.5, color=ink, linestyle="none", zorder=OVERLAY_ZORDER)

    for r, c in data_panels:
        ax = axes[r][c]
        ax.set_xlim(edges[c][0], edges[c][-1])
        if r != c:
            ax.set_ylim(edges[r][0], edges[r][-1])
        if r == n - 1:
            ax.set_xlabel(labels[c])
        else:
            ax.tick_params(which="both", labelbottom=False)
        if c > r:
            # A mirrored panel reads its y axis on the right, on the last column only.
            ax.tick_params(which="both", labelleft=False, labelright=c == n - 1)
            if c == n - 1:
                ax.yaxis.set_label_position("right")
                ax.set_ylabel(labels[r])
        elif c == 0 and r > 0:
            ax.set_ylabel(labels[r])
        elif r == c:
            # The counts of a diagonal panel are not the row's variable: unlabelled, except the first
            # (a posterior's density has no scale worth reading: never labelled).
            if r == 0 and n > 1 and not posterior_mode:
                ax.set_ylabel("Counts")
            else:
                ax.tick_params(which="both", labelleft=False)
        else:
            ax.tick_params(which="both", labelleft=False)
        apply_tick_formatter(ax, axis="both")
        if posterior_mode:
            # Small panels of narrow ranges: few ticks, so that "124.75" and "125.00" do not touch.
            for axis in (ax.xaxis, ax.yaxis) if r != c else (ax.xaxis,):
                axis.set_major_locator(MaxNLocator(nbins=5, steps=[1, 2, 2.5, 5, 10]))

    if mappables and colorbar_mode(args) != "none":
        for mappable in mappables:
            mappable.autoscale_None()
        norm = mappables[0].norm
        norm = type(norm)(vmin=min(m.norm.vmin for m in mappables), vmax=max(m.norm.vmax for m in mappables)) \
            if not args.rangez else norm
        for mappable in mappables:
            mappable.set_norm(norm)
        label = args.labelz or (NORM_LABELS["global"] if args.norm else "Density" if args.density else "Counts")
        # Right of the grid, as tall as it, and as wide as the bar of a single plot (the panels are 1/n of the
        # figure, which is two plots wide: a bar of one panel's share would be a hairline).
        add_colorbar(fig, mappables[0], [axes[r][c] for r in range(n) for c in range(r + 1)], label, width=n / 2)
        _power_ticks(mappables[0], args)

    handles = []
    if posterior_mode or np.isfinite(truths).any():
        methods = list(dict.fromkeys(s["method"] for s in summaries.values())) if not args.no_corner_titles or summaries else []
        handles = corner_legend_handles(samples, fractions, truths, args, methods=methods, bands=bands,
                                        entries=split_entries(splits, samples, args) if splits else [], profile=upper == "profile",
                                        prior=prior, shrinkage=bool(shrinkage))
    if posterior_mode and len(samples) == 1 and not args.no_corner_titles:
        from ..plot import apply_measured_layout

        apply_measured_layout(fig)  # the panels at their final width, before the titles are fitted to them
        _fit_corner_titles(fig, [axes[i][i] for i in range(n)])
    holder = None
    if handles:
        # The empty upper triangle holds the legend, in a panel of its own so that the layout moves it with the grid.
        holder = fig.add_subplot(grid[0, n - 1])
        holder.set_axis_off()
        legend = holder.legend(handles=handles, loc="upper right", borderaxespad=0.0, frameon=False)
        if upper or block_axes or not _legend_fits_upper_triangle(fig, legend, axes, n):
            handles = _legend_above_handles(fig, legend, handles, axes[0][0])
            holder.remove()
            holder = None
    if handles and holder is None:
        # Every cell is taken, or the legend is larger than the empty ones: it goes above the grid, centred on it.
        from ..plot import apply_legend_style

        apply_legend_style(axes[0][0], handles=handles, labels=[h.get_label() for h in handles], loc="top center")
    if upper == "corr":
        _fit_correlation_texts(fig, [axes[r][c] for r in range(n) for c in range(r + 1, n) if axes[r][c] is not None])

    add_title_and_note(fig, args)
    return save(fig, args, kdx, suffix="corner.png")


def _legend_fits_upper_triangle(fig, legend, axes, n):
    """Whether the legend of the top-right cell stays inside the empty
    upper triangle: right of the diagonal panel of the first column it
    reaches, and above the title of the diagonal panel under it."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    box = legend.get_window_extent(renderer)
    for column in range(1, n):
        if box.x0 >= axes[column - 1][column - 1].bbox.x1:
            below = axes[column][column]
            floor = max(below.bbox.y1, below.title.get_window_extent(renderer).y1 if below.title.get_text() else 0.0)
            return box.y0 >= floor
    return False


def _legend_above_handles(fig, legend, handles, first):
    """The handles of a legend that goes above the grid, where it is laid
    out in as many columns as fit the figure. The layout gives the top of a
    figure at most 3/8 of its height, shared with the figure title and the
    title of the first panel (``first``); text is never scaled to fit. So
    when the legend's rows need more than what is left, the entries without
    a handle (the number of draws, the odds) are printed instead of drawn;
    when the rest is still too tall, the whole legend is printed and the
    caption has to name what is drawn. Each step warns."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    box = legend.get_window_extent(renderer)
    texts = legend.get_texts()
    widths = [t.get_window_extent(renderer).width for t in texts]
    handle = box.width - max(widths)
    line = box.height / len(texts)
    taken = sum(t.get_window_extent(renderer).height for t in (first.title, fig._suptitle) if t is not None and t.get_text())
    room = 0.9 * (0.375 * fig.bbox.height - taken - 4 * style.figure_pad_inches * fig.dpi)

    def height(kept):
        # The columns must fit the width of the panels, about 0.7 of a small figure's.
        columns = max(1, int(0.7 * fig.bbox.width // (max(widths[i] for i in kept) + 1.5 * handle)))
        return np.ceil(len(kept) / columns) * line

    plain = lambda text: text.replace("$", "").replace("\\pm", "+-").replace("\\,", " ").replace("\\Delta", "Delta")  # noqa: E731
    advice = "a wider figure (--width double on paper) has room for it"
    everything = list(range(len(handles)))
    if height(everything) <= room:
        return handles
    drawn = [i for i in everything if not (isinstance(handles[i], Line2D) and handles[i].get_linestyle() == "None"
                                             and handles[i].get_marker() in ("None", "", None))]
    if drawn and len(drawn) < len(everything) and height(drawn) <= room:
        rprint(f"[yellow]Warning:[/yellow] --corner: the legend does not fit above the grid at this size, so these entries "
               f"are left out of it; {advice}:")
        for i in everything:
            if i not in drawn:
                rprint("  " + plain(handles[i].get_label()))
        return [handles[i] for i in drawn]
    rprint(f"[yellow]Warning:[/yellow] --corner: the legend does not fit above the grid at this size and is not drawn; "
           f"{advice}. The caption has to say:")
    for handle_ in handles:
        rprint("  " + plain(handle_.get_label()))
    return []


def _fit_corner_titles(fig, diagonal):
    """Keep the titles of the diagonal panels inside the figure: one wider
    than its panel is broken onto two lines, and when it is still wider, the
    title of the last column ends at its panel's right edge and the title of
    the first starts at its left edge."""
    from ..plot import _break_label

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for index, ax in enumerate(diagonal):
        title = ax.title
        if not title.get_text() or title.get_window_extent(renderer).width <= ax.bbox.width:
            continue
        broken = _break_label(title.get_text())
        if broken is not None:
            title.set_text(broken)
        if title.get_window_extent(renderer).width > ax.bbox.width:
            if index == len(diagonal) - 1:
                title.set_ha("right"), title.set_x(1.0)
            elif index == 0:
                title.set_ha("left"), title.set_x(0.0)


def _fit_correlation_texts(fig, cells):
    """Drop the numbers of the correlation cells when one does not fit its
    cell at the medium's type size (the tint stays), with a warning."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    texts = [(ax, text) for ax in cells for text in ax.texts]
    if any(text.get_window_extent(renderer).width > 0.95 * ax.bbox.width for ax, text in texts):
        for _, text in texts:
            text.set_visible(False)
        rprint("[yellow]Warning:[/yellow] --corner_upper corr: the coefficients do not fit their cells at this medium's "
               "type size, so only the tint is drawn (fewer variables, or a wider --width, show them)")


# The effective sample size is written when it is below this share of the draws (its estimate scatters by a few
# percent for independent draws).
ESS_SHOWN_BELOW = 0.8


def _count_text(value):
    """'40\\,000' for mathtext: thousands apart by a thin space."""
    return f"{int(round(value)):,}".replace(",", "\\,")


def corner_sample_warnings(samples, fractions, args):
    """Say when a sample cannot support a region: fewer than
    posterior.MIN_DRAWS_OUTSIDE effective draws outside it; and that
    --contour_dof 1 regions hold less than their sigma suggests."""
    if args.contour_dof == 1 and not args.corner_levels:
        rprint("[yellow]Warning:[/yellow] --contour_dof 1 on samples: the regions hold "
               + ", ".join(level_text(f, args) for f in fractions)
               + " of the points, not the coverage of 1, 2, ... sigma intervals (the legend states their content)")
    for sample in samples:
        name = f"{sample['label']}: " if sample["label"] is not None else ""
        for fraction in fractions:
            outside = sample["ess"] * (1 - fraction)
            if outside < posterior.MIN_DRAWS_OUTSIDE:
                rprint(f"[yellow]Warning:[/yellow] {name}the {level_text(fraction, args)} region rests on about "
                       f"{max(outside, 0):.0f} effective draws outside it (ESS = {sample['ess']:.0f} of {sample['size']} draws): "
                       "its outline is uncertain (--corner_mc_error shows by how much)")


def corner_legend_handles(samples, fractions, truths, args, methods=(), bands=(), entries=(), profile=False, prior=None,
                          shrinkage=False):
    """One patch per overlaid sample; one per credible level, named with its
    content (in the single sample's colour, or in the muted colour when
    several share them); the interval of the marginals; the resampled
    outline; the profile likelihood's levels and best fit; the bands and the
    truth line; the number of draws of a single sample (with its effective
    size when that is smaller) and the split probabilities."""
    from scipy.stats import chi2

    handles = []
    if len(samples) > 1:
        handles += [Patch(facecolor=s["bands"][0], edgecolor=s["color"], label=s["label"]) for s in samples]
    base = samples[0]["color"] if len(samples) == 1 else style.role("muted")
    if fractions:
        handles += [Patch(facecolor=mix_paper(base, m), edgecolor=base, label=f"{level_text(f, args)} (2D region)")
                    for f, m in zip(fractions, fill_mix(len(fractions)))]
        if args.corner_mc_error:
            handles.append(Line2D([0], [0], color=base, linewidth=0.25 * args.contour_linewidth, alpha=0.6,
                                  label=f"{level_text(fractions[-1], args)}, {int(args.corner_mc_error)} resamplings"))
    handles += [Patch(facecolor=to_rgba(base, 0.25), edgecolor="none", label=method) for method in methods]
    if profile:
        muted, ink = style.role("muted"), style.role("ink")
        for k, (f, m) in enumerate(zip(fractions, fill_mix(len(fractions)))):
            label = f"Profile, $-2\\Delta\\ln L <$ {chi2.ppf(f, 2):.2f}"
            handles.append(Patch(facecolor=mix_paper(muted, PROFILE_FILL * m), edgecolor=ink, linestyle="dashed", label=label))
        handles.append(Line2D([0], [0], color=ink, marker="*", markersize=7, linestyle="none", label="Best draw"))
    muted = style.role("muted")
    if prior is not None:
        handles.append(Line2D([0], [0], color=muted, linewidth=1.0, linestyle="dashed", label=prior["label"]))
    if shrinkage:
        handles.append(Line2D([], [], linestyle="none", label=SHRINKAGE_LEGEND))
    handles += [Patch(facecolor="none", edgecolor=muted, hatch="////", linewidth=0.0, label=label) for *_, label in bands if label]
    if np.isfinite(truths).any():
        handles.append(Line2D([0], [0], color=style.role("ink"), linewidth=0.9, marker="s", markersize=3.5, label=args.corner_truth_label))
    if fractions and len(samples) == 1:
        size, ess = samples[0]["size"], samples[0]["ess"]
        text = f"$N = {_count_text(size)}$"
        if ess < ESS_SHOWN_BELOW * size:
            text += f", ESS = ${_count_text(float(f'{ess:.2g}'))}$"
        handles.append(Line2D([], [], linestyle="none", label=text))
    for handle, text in entries:
        handle.set_label(text)
        handles.append(handle)
    return handles


def draw_hist2d(ax, x, y, x_range, y_range, args, bins=None):
    """2D histogram of the points (one bin per integer when both are
    integer-valued, unless ``bins`` gives the edges), empty bins blank, on
    the --norm/--logz/--rangez/--cmap colour scale. Returns
    (the hist2d tuple, its mesh)."""
    if bins is None:
        bins = args.bins or style.nbins
        if is_integer_valued(x) and is_integer_valued(y):
            bins = [integer_bin_edges(*x_range), integer_bin_edges(*y_range)]
    hist = plot_data(args, ax, x, y=y, plot_type="hist2d", range=(x_range, y_range), bins=bins)
    mesh = hist[3]
    if args.norm is not None:
        mesh.set_array(normalize_hist2d(hist[0], args.norm).T)
    # Empty bins are blank on linear and log scales alike.
    mesh.set_array(np.ma.masked_less_equal(mesh.get_array(), 0))
    _finish_scale(mesh, args)
    return hist, mesh


def draw_hexbin(ax, x, y, x_range, y_range, args, gridsize=None):
    """--map_type hexbin: hexagonal bins (``gridsize`` or --bins across x)
    over the ranges, empty hexagons blank, counts normalised to unit sum by
    --norm global and to a density (per unit area) by --density. Returns the
    collection."""
    gridsize = gridsize or args.bins or style.nbins
    if isinstance(gridsize, (list, tuple)):
        gridsize = gridsize[0]
    inside = (x >= x_range[0]) & (x <= x_range[1]) & (y >= y_range[0]) & (y <= y_range[1])
    x, y = x[inside], y[inside]
    scales = {"xscale": "log" if args.logx else "linear", "yscale": "log" if args.logy else "linear"}
    extent = [*x_range, *y_range]
    if args.logx:
        extent[:2] = np.log10(x_range)
    if args.logy:
        extent[2:] = np.log10(y_range)
    hexes = ax.hexbin(x, y, gridsize=int(gridsize), extent=extent, mincnt=1, linewidths=0.2, edgecolors="face",
                      norm=LogNorm() if args.logz else None, **scales)
    counts = np.asarray(hexes.get_array(), dtype=float)
    if args.norm == "global" and counts.sum() > 0:
        hexes.set_array(counts / counts.sum())
    elif args.density and counts.sum() > 0:
        # Each hexagon covers half a cell of the two offset lattices.
        nx = int(gridsize)
        ny = max(1, int(nx / np.sqrt(3)))
        area = (extent[1] - extent[0]) / nx * (extent[3] - extent[2]) / ny / 2
        hexes.set_array(counts / (len(x) * area))
    _finish_scale(hexes, args)
    return hexes


def _finish_scale(mappable, args):
    """Colour scale of binned points: from 0 (linear) or the smallest
    non-empty bin (--logz), then --rangez, --cmap, --zpower/--zmin/--zunder."""
    if args.logz:
        mappable.autoscale()  # vmin at the smallest non-empty bin
    else:
        mappable.set_clim(0, np.ma.max(mappable.get_array()))
    if args.rangez is not None:
        mappable.set_clim(*args.rangez)
    if args.cmap is not None:
        mappable.set_cmap(args.cmap)
    _colour_scale(mappable, args)


def sample_region_thresholds(density, fractions):
    """Density thresholds of the smallest regions holding each fraction of
    the entries: the bins are filled from the densest down."""
    flat = np.sort(np.asarray(density, dtype=float).ravel())[::-1]
    total = flat.sum()
    if total <= 0:
        return [np.nan] * len(fractions)
    cumulative = np.cumsum(flat) / total
    return [float(flat[min(np.searchsorted(cumulative, f), flat.size - 1)]) for f in fractions]


def draw_sample_regions(ax, counts, xedges, yedges, args):
    """--contour without -z: outlines of the regions holding the --contour_sigmas
    fractions of the entries (68.3/95.4/99.7% with 2 dof, the content of the
    2-parameter delta-chi2 levels; 39.3/86.5/98.9% with 1 dof), from the 2D
    histogram smoothed by --contour_smoothing_sigma bins (default 1). Returns
    the legend handles."""
    from scipy.stats import chi2

    sigmas = sorted(set(float(s) for s in args.contour_sigmas if np.isfinite(s)))
    levels = contour_levels(sigmas, "sigma_probability", args.contour_dof)
    fractions = [float(chi2.cdf(level, 2)) for level in levels]
    density = _smooth(counts, args.contour_smoothing_sigma or 1.0)
    thresholds = sample_region_thresholds(density, fractions)
    if args.contour_label == "cl":
        labels = [f"{100 * f:.1f}%" for f in fractions]
    else:
        labels = sigma_labels(levels, sigmas, "sigma_probability", args.contour_dof, "sigma")
    xc, yc = 0.5 * (xedges[1:] + xedges[:-1]), 0.5 * (yedges[1:] + yedges[:-1])
    ink, width = style.role("ink"), args.contour_linewidth
    halo = [patheffects.withStroke(linewidth=width + 2, foreground=_paper())]  # reads on any bin colour
    handles = []
    for threshold, label, linestyle in zip(thresholds, labels, level_linestyles(args, len(levels))):
        if not np.isfinite(threshold) or threshold <= 0 or threshold >= density.max():
            continue
        lines = ax.contour(xc, yc, density.T, levels=[threshold], colors=[ink], linestyles=[linestyle],
                           linewidths=width, zorder=3)
        lines.set_path_effects(halo)
        handles.append(level_handle(label, ink, linestyle, width))
    return handles


def compact(args, ncols):
    """Whether panels side by side share one y axis (--compact; the default
    with several panels)."""
    if style.figure_layout_mode == "panels":
        return True  # one plot split in parts: always one y axis
    return args.compact if args.compact is not None else ncols > 1


def first_column(ax):
    """Whether ``ax`` is in the first column of its grid (an inset is)."""
    spec = ax.get_subplotspec()
    return spec is None or spec.colspan.start == 0


def share_rows(axes, args):
    """--compact: the panels share the first one's y range and drop the inner
    y labels; they move close unless each has its own colorbar between them."""
    for ax in axes[1:]:
        ax.sharey(axes[0])
        if not first_column(ax):  # a wrapped row keeps the labels of its first panel
            ax.set_ylabel("")
            ax.tick_params(which="both", labelleft=False)  # minor labels too (log axes label some)
    if colorbar_mode(args) in ("shared", "none"):
        axes[0].get_gridspec().update(wspace=style.compact_gap())


def colorbar_mode(args):
    """shared, each or none: panels share one colorbar unless --norm
    normalises each panel on its own scale (or --colorbar each asks for one
    per panel)."""
    return args.colorbar or ("each" if args.norm else "shared")


def draw_colorbars(fig, entries, args):
    """Colorbars of ``entries`` [(ax, mappable, label)]: one per panel, or a
    shared one right of the row when the panels show the same quantity (one
    label), with one norm spanning every panel."""
    if not entries or colorbar_mode(args) == "none":
        return
    labels = {label for _, _, label in entries}
    if colorbar_mode(args) == "shared" and len(entries) > 1 and len(labels) == 1:
        mappables = [mappable for _, mappable, _ in entries]
        for mappable in mappables:
            mappable.autoscale_None()
        norm = type(mappables[0].norm)(vmin=min(m.norm.vmin for m in mappables),
                                       vmax=max(m.norm.vmax for m in mappables))
        for mappable in mappables:
            mappable.set_norm(norm)
        add_colorbar(fig, mappables[0], [ax for ax, _, _ in entries], labels.pop())
        return
    for ax, mappable, label in entries:
        add_colorbar(fig, mappable, ax, label)


# --- Contours: maps ------------------------------------------------------------------------


def palette(color):
    """Colour list named by ``color`` ('cycle' or a list/dict style mapping), else None."""
    key = str(color).strip()
    if key.lower() == "cycle":
        return list(plt.rcParams["axes.prop_cycle"].by_key()["color"])
    mapping = style.mappings.get(key)
    if isinstance(mapping, list):
        return [style.resolve_mapped_color(c) for c in mapping]
    if isinstance(mapping, dict):
        return [style.resolve_mapped_color(c) for c in mapping.values()]
    return None


def _shade(color, factor):
    """Blend toward white (factor > 0) or black (factor < 0)."""
    r, g, b = to_rgb(color)
    if factor > 0:
        return (r + (1 - r) * factor, g + (1 - g) * factor, b + (1 - b) * factor)
    if factor < 0:
        return (r * (1 + factor), g * (1 + factor), b * (1 + factor))
    return (r, g, b)


def band_hues(color, count, offset=0):
    """``count`` colours: the palette from ``offset`` (repeated trips around
    it alternately lightened/darkened), or ``color`` repeated."""
    colors = palette(color)
    if not colors:
        return [color] * count
    hues = []
    for i in range(count):
        slot = i + offset
        base = colors[slot % len(colors)]
        cycle = slot // len(colors)
        if cycle == 0:
            hues.append(base)
        else:
            step, sign = (cycle + 1) // 2, 1 if cycle % 2 else -1
            hues.append(_shade(base, sign * min(0.25 * step, 0.7)))
    return hues


def _smooth(z, sigma, mode="reflect"):
    """Gaussian smoothing by ``sigma`` bins; ``mode`` is scipy's rule at the edges (one per axis: 'wrap' for a
    cyclic axis)."""
    z = np.asarray(z, dtype=float)
    if sigma <= 0:
        return z
    from scipy.ndimage import gaussian_filter

    return gaussian_filter(z, sigma=sigma, mode=mode)


def fill_nan(z, x, y, strategy, method):
    z = np.asarray(z, dtype=float)
    if not np.isnan(z).any() or strategy == "none":
        return z
    if strategy == "zero":
        return np.nan_to_num(z, nan=0.0)
    filled = None
    if strategy == "interpolate":
        try:
            from scipy.interpolate import griddata

            xa, ya = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
            xx, yy = np.meshgrid(xa, ya) if xa.ndim == 1 and ya.ndim == 1 else (xa, ya)
            valid = np.isfinite(z)
            if not valid.any():
                return np.zeros_like(z)
            points, values = np.column_stack((xx[valid], yy[valid])), z[valid]
            query = np.column_stack((xx[~valid], yy[~valid]))
            interp = griddata(points, values, query, method=method)
            for fallback in ("linear", "nearest"):
                if np.isnan(interp).any():
                    interp = np.where(np.isnan(interp), griddata(points, values, query, method=fallback), interp)
            filled = z.copy()
            filled[~valid] = interp
        except Exception:
            frame = pd.DataFrame(z).interpolate(axis=0, limit_direction="both").interpolate(axis=1, limit_direction="both")
            filled = frame.ffill(axis=0).bfill(axis=0).ffill(axis=1).bfill(axis=1).to_numpy(dtype=float)
    else:
        filled = pd.DataFrame(z).ffill(axis=0).bfill(axis=0).ffill(axis=1).bfill(axis=1).to_numpy(dtype=float)
    return np.nan_to_num(filled, nan=0.0)


def _grid(row, args):
    x, y, z = (np.asarray(row[c], dtype=float) for c in (args.x, args.y, args.z))
    if z.ndim != 2:
        raise ValueError(f"{args.z} must be a 2D array, got shape {z.shape}.")
    if x.ndim == 1 and y.ndim == 1:
        if z.shape != (y.size, x.size):
            raise ValueError(f"Grid mismatch: {args.z}.shape {z.shape} != (len({args.y}), len({args.x})) {(y.size, x.size)}.")
    elif not (x.ndim == 2 and y.ndim == 2 and x.shape == z.shape and y.shape == z.shape):
        raise ValueError(f"{args.x} and {args.y} must both be 1D axes or 2D grids shaped like {args.z}.")
    return x, y, z


def _same_grid(a, b):
    return a[0].shape == b[0].shape and a[1].shape == b[1].shape and np.allclose(a[0], b[0]) and np.allclose(a[1], b[1])


def aggregate_grid(rows, args):
    """Sum the maps of the rows (delta-chi2 sums re-centred on their minimum)."""
    reference, total = None, None
    for _, row in rows.iterrows():
        x, y, z = _grid(row, args)
        z = fill_nan(z, x, y, args.nan_fill, args.nan_interp_method)
        if args.density:
            s = np.nansum(z)
            z = z / s if s > 0 else z
        if reference is None:
            reference, total = (x, y), z.copy()
        elif not _same_grid(reference, (x, y)):
            raise ValueError("All grids for a given selection must share the same x/y coordinates.")
        else:
            total = total + z
    if reference is None:
        return None
    if len(rows) > 1 and args.contour_level_mode == "sigma_probability":
        minimum = np.nanmin(total)
        if np.isfinite(minimum) and minimum > 0:
            total = total - minimum
    return {"x": reference[0], "y": reference[1], "z": total}


def _exposure(rows, label):
    if "Exposure" not in rows.columns:
        return None
    values = pd.to_numeric(rows["Exposure"], errors="coerce").dropna().unique()
    if len(values) != 1:
        raise ValueError(f"{label}: expected one Exposure value, found {list(values)}.")
    return float(values[0])


def project_grid(rows, args):
    """Rescale one map to --project_scale times its exposure in delta-chi2:
    chi2 * scale^k with k = 1, or per bin k = ln(chi2_ref/chi2)/ln(T_ref/T)
    (clipped to [0, 1]) with --project_reference."""
    base_name = args.project_datafile or normalize_datafiles(args.datafile)[0]
    base_rows = rows[rows["_Datafile"] == base_name]
    grid = aggregate_grid(base_rows, args)
    if grid is None:
        return None, None
    in_sigma = args.contour_level_mode == "z_values"
    chi2 = np.square(grid["z"]) if in_sigma else grid["z"]
    scale = float(args.project_scale)
    base_exposure = _exposure(base_rows, base_name)
    target = base_exposure * scale if base_exposure is not None else None
    exponent = np.ones_like(chi2)
    if args.project_reference is not None:
        ref_rows = rows[rows["_Datafile"] == args.project_reference]
        ref = aggregate_grid(ref_rows, args)
        if ref is None:
            raise ValueError(f"No {args.project_reference} map for the projection reference.")
        if not _same_grid((grid["x"], grid["y"]), (ref["x"], ref["y"])):
            raise ValueError("--project_reference grid does not match the --project_datafile grid.")
        ref_exposure = _exposure(ref_rows, args.project_reference)
        if base_exposure is None or ref_exposure is None or ref_exposure == base_exposure:
            raise ValueError("--project_reference needs an Exposure column that differs from the base datafile's.")
        if not min(base_exposure, ref_exposure) <= target <= max(base_exposure, ref_exposure):
            rprint(f"[yellow]Warning:[/yellow] Projected exposure {target:g} yr lies outside "
                   f"[{base_exposure:g}, {ref_exposure:g}] yr; the power law is extrapolated.")
        chi2_ref = np.square(ref["z"]) if in_sigma else ref["z"]
        valid = (chi2 > 1e-6) & (chi2_ref > 1e-6)
        exponent[valid] = np.log(chi2_ref[valid] / chi2[valid]) / np.log(ref_exposure / base_exposure)
        exponent = np.clip(exponent, 0.0, 1.0)
    projected = chi2 * np.power(scale, exponent)
    grid["z"] = np.sqrt(projected) if in_sigma else projected
    return grid, target


def load_projected(args, configs, names):
    if not args.project:
        return pd.DataFrame()
    name_by_config = dict(zip(configs, names))
    proj = copy.copy(args)
    proj.configs = list(args.project)
    proj.names = None if names[0] is None else [name_by_config.get(c, names[0]) for c in args.project]
    proj.datafile = [args.project_datafile or normalize_datafiles(args.datafile)[0]]
    if args.project_reference is not None:
        proj.datafile.append(args.project_reference)
    proj.path = normalize_datafiles(getattr(args, "path", None))[:1] or None
    proj.name_columns = False
    df = import_data(proj)
    if df.empty:
        rprint("[yellow]Warning:[/yellow] No data found for the --project configs.")
    return df


# --- Contours: drawing -------------------------------------------------------------------


def contour_levels(sigmas, mode, dof=2):
    """Contour levels of the sigmas: the significances themselves (z_values),
    or the delta-chi2 whose chi2(dof) CDF is each sigma's two-sided Gaussian
    coverage (sigma_probability; sigma^2 for 1 dof)."""
    finite = [float(s) for s in sigmas if np.isfinite(s)]
    if mode == "z_values":
        return sorted(set(finite))
    if dof == 1:
        return sorted(set(s**2 for s in finite))
    from scipy.stats import chi2

    return sorted(set(float(chi2.ppf(chi2.cdf(s**2, 1), dof)) for s in finite))


def coverage_label(sigma):
    """'68.3% CL' for 1 sigma: the two-sided Gaussian coverage, with as many
    decimals as it takes not to round to 100%."""
    from scipy.stats import chi2

    percent = 100 * chi2.cdf(sigma**2, 1)
    decimals = 1
    while decimals < 6 and round(percent, decimals) >= 100:
        decimals += 1
    return f"{percent:.{decimals}f}% CL"


def sigma_labels(levels, sigmas, mode, dof=2, label="cl"):
    ordered = sorted(set(float(s) for s in sigmas if np.isfinite(s)))
    if len(ordered) != len(levels):
        return [f"Level {level:.3g}" for level in levels]
    if label == "cl":
        return [coverage_label(s) for s in ordered]
    # 1 dof levels (sigma^2) read as sigmas; 2 dof ones are named.
    suffix = f" ({dof} dof)" if mode == "sigma_probability" and dof != 1 else ""
    return [f"${s:g}\\sigma${suffix}" for s in ordered]


def _per_level(values, count):
    values = list(values)
    if count <= 0 or not values:
        return values
    return values[:count] if len(values) >= count else values + [values[-1]] * (count - len(values))


def level_linestyles(args, count, single=None):
    """Line style per level: --contour_linestyles, else ``single`` for every
    level (an explicit per-map style), else style contours.linestyles."""
    if args.contour_linestyles:
        return _per_level(args.contour_linestyles, count)
    if single is not None:
        return [single] * count
    return _per_level(style.contours.get("linestyles") or ["-"], count)


def fill_mix(count):
    """Hue fraction of each band from the best fit outwards (style
    contours.fill_mix, halved past its end)."""
    mix = [float(m) for m in style.contours.get("fill_mix") or [1.0]]
    return [mix[i] if i < len(mix) else mix[-1] * 0.5 ** (i - len(mix) + 1) for i in range(count)]


def _paper():
    color = to_rgba(plt.rcParams["axes.facecolor"])
    return color[:3] if color[3] > 0 else (1.0, 1.0, 1.0)


def mix_paper(color, fraction):
    """``fraction`` of ``color`` mixed with the paper (axes background) colour."""
    paper, rgb = _paper(), to_rgb(color)
    return tuple(fraction * c + (1 - fraction) * p for c, p in zip(rgb, paper))


def _diagonal(ax, span, color):
    """The y = x line across the whole visible axes (also where --matchx/--matchy
    widen them past this panel's data), through two points of ``span``."""
    low, high = (float(v) for v in span)
    if low <= 0 < high and "log" in (ax.get_xscale(), ax.get_yscale()):
        low = high / 10.0  # a point a log axis can show
    if not low < high:
        return
    ax.axline((low, low), (high, high), color=color, linestyle="--")


def band_colors(color, count, args, offset=0):
    """RGBA fill of the ``count`` bands from the best fit outwards, plus the
    fill outside the outermost level (None when unfilled)."""
    hues = band_hues(color, count + 1, offset)
    mix = fill_mix(count + 1)
    inner = 1.0 if args.fill_alpha is None else args.fill_alpha
    outer = inner if args.fill_outer_alpha is None else args.fill_outer_alpha
    alphas = np.linspace(inner, outer, count) if count > 1 else [inner]
    bands = [to_rgba(mix_paper(h, m), alpha=float(a)) for h, m, a in zip(hues, mix, alphas)]
    outside = to_rgba(mix_paper(hues[-1], mix[-1]), alpha=args.fill_inner_alpha) if args.fill_inner_alpha else None
    return bands, outside


def _filter_vertices(contour_set, minimum):
    if minimum <= 0:
        return
    paths = []
    for path in contour_set.get_paths():
        pieces = [Path(p) for p in path.to_polygons(closed_only=False) if len(p) >= minimum]
        paths.append(Path.make_compound_path(*pieces) if pieces else Path(np.empty((0, 2))))
    contour_set.set_paths(paths)


def draw_filled(ax, x, y, image, levels, color, args, zorder, offset=0):
    """contourf bands from the best fit (below the lowest level) outwards;
    returns the band colours."""
    bands, outside = band_colors(color, len(levels), args, offset)
    edges = [-np.inf] + list(levels) + ([np.inf] if outside is not None else [])
    ax.contourf(x, y, image, levels=edges, colors=bands + ([outside] if outside is not None else []), zorder=zorder)
    return bands


def draw_outlines(ax, x, y, image, levels, hues, linestyles, width, alpha, args, zorder, labels=None):
    """Contour lines of one set; with --contour_labels each level's label is
    written on its line (``labels``, one per level)."""
    lines = ax.contour(x, y, image, levels=levels, colors=hues, linestyles=linestyles,
                       linewidths=width, alpha=alpha, zorder=zorder)
    _filter_vertices(lines, args.contour_min_vertices)
    if args.contour_labels and labels and args.contour_label_pos:
        _placed_contour_labels(ax, lines, labels, hues, args, zorder)
    elif args.contour_labels and labels:
        texts = ax.clabel(lines, lines.levels, inline=True, fontsize=style.linelabelfontsize,
                          fmt=dict(zip(lines.levels, labels)))
        for text in texts:
            text.set_zorder(zorder + 0.1)
    return lines


def _placed_contour_labels(ax, lines, labels, hues, args, zorder):
    """--contour_label_pos: level i's label at the i-th X Y (data
    coordinates), in its colour; with --contour_label_leader a thin line to
    the nearest point of its contour."""
    positions = args.contour_label_pos
    paths = lines.get_paths()
    for i, label in enumerate(labels):
        if 2 * i + 1 >= len(positions):
            break
        x, y = positions[2 * i], positions[2 * i + 1]
        color = hues[min(i, len(hues) - 1)]
        text = ax.text(x, y, label, color=color, fontsize=style.linelabelfontsize, ha="center", va="center",
                       zorder=zorder + 0.2)
        text._plotipus_background_over_data = True
        if args.contour_label_leader and i < len(paths) and len(paths[i].vertices):
            vertices = paths[i].vertices
            nearest = vertices[np.argmin(np.hypot(vertices[:, 0] - x, vertices[:, 1] - y))]
            ax.annotate("", xy=tuple(nearest), xytext=(x, y),
                        arrowprops=dict(arrowstyle="-", color=color, linewidth=0.6, shrinkA=6, shrinkB=0),
                        zorder=zorder + 0.1)


def _profile_interval(values, delta):
    """(low, high) where the profile ``delta`` (Delta-chi2, minimum 0) stays
    within 1, interpolated linearly between grid points; None if unbounded."""
    inside = np.flatnonzero(np.isfinite(delta) & (delta <= 1.0))
    if not inside.size:
        return None
    first, last = inside[0], inside[-1]

    def crossing(a, b):
        # Where the profile crosses 1 between grid points a (inside) and b (outside).
        if not (0 <= b < len(values)) or not np.isfinite(delta[b]) or delta[b] == delta[a]:
            return values[a]
        return values[a] + (1.0 - delta[a]) / (delta[b] - delta[a]) * (values[b] - values[a])

    return crossing(first, first - 1), crossing(last, last + 1)


def best_fit_point(x, y, image):
    """(bx, by, xerr, yerr) of the grid minimum. On a Delta-chi2 map the
    errors are the 1-sigma profile intervals of each parameter (the Delta-chi2
    <= 1 region projected on each axis, as (minus, plus)); else None."""
    image = np.asarray(image, dtype=float)
    if not np.isfinite(image).any():
        return None
    i, j = np.unravel_index(np.nanargmin(image), image.shape)
    xa, ya = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    xs = xa[0, :] if xa.ndim == 2 else xa
    ys = ya[:, 0] if ya.ndim == 2 else ya
    bx, by = xs[j], ys[i]
    delta = image - np.nanmin(image)
    with np.errstate(all="ignore"):
        profile_x, profile_y = np.nanmin(delta, axis=0), np.nanmin(delta, axis=1)
    errors = []
    for values, profile, best in ((xs, profile_x, bx), (ys, profile_y, by)):
        interval = _profile_interval(values, profile)
        errors.append(None if interval is None else (abs(best - min(interval)), abs(max(interval) - best)))
    return bx, by, errors[0], errors[1]


def draw_best_fit(ax, x, y, image, color, zorder, errors=False):
    """The best fit: with ``errors`` (a Delta-chi2 map), a point with its
    1-sigma profile intervals as error bars; else a '+' at the grid minimum.
    Both are haloed in the paper colour so they show on a fill of their own
    hue. Returns the error-bar container (a legend handle) or None."""
    point = best_fit_point(x, y, image)
    if point is None:
        return None
    bx, by, xerr, yerr = point
    halo = [patheffects.withStroke(linewidth=max(1.5, plt.rcParams["lines.linewidth"]) + 2, foreground=_paper())]
    if errors:
        container = ax.errorbar([bx], [by], xerr=None if xerr is None else [[xerr[0]], [xerr[1]]],
                                yerr=None if yerr is None else [[yerr[0]], [yerr[1]]], fmt="o", color=color,
                                zorder=zorder, label="Best fit")
        for artist in container.get_children():
            artist.set_path_effects(halo)
        return container
    size, width = 2.5 * plt.rcParams["lines.markersize"], max(1.5, plt.rcParams["lines.linewidth"])
    ax.plot([bx], [by], linestyle="none", marker="+", color=color, markersize=size, markeredgewidth=width,
            zorder=zorder, path_effects=[patheffects.withStroke(linewidth=width + 2, foreground=_paper())])
    return None


def level_handle(label, color, linestyle, width, fill=None):
    """Legend handle of one level: its line style, and its fill when filled."""
    if fill is None:
        return Line2D([0], [0], color=color, linestyle=linestyle, linewidth=width, label=label)
    return Patch(facecolor=fill, edgecolor=color, linestyle=linestyle, linewidth=width, label=label)


def _combined_width(args):
    return args.combined_linewidth if args.combined_linewidth is not None else args.contour_linewidth + 0.5


def draw_background(ax, fig, x, y, z, args, rows, levels):
    """The background image. Delta-chi2 maps are clipped at the outermost
    level (blank beyond it) and their colour bar is labelled delta-chi2. The
    colorbar is drawn with the figure's others (:func:`draw_colorbars`)."""
    image = _smooth(z, args.background_smoothing_sigma)
    if args.logz:
        image = np.ma.masked_less_equal(image, 0)
    rangez = args.rangez
    delta_chi2 = args.contour_level_mode == "sigma_probability" and bool(levels)
    if rangez is None and delta_chi2:
        rangez = [None, max(levels)]
    if args.logz:
        norm = LogNorm(vmin=rangez[0], vmax=rangez[1]) if rangez is not None else LogNorm()
    else:
        norm = Normalize(vmin=rangez[0], vmax=rangez[1]) if rangez is not None else None
    mesh = ax.pcolormesh(x, y, image, shading="auto", norm=norm, **({"cmap": args.cmap} if args.cmap else {}))
    if delta_chi2 and args.rangez is None:
        # Cells outside the outermost contour stay blank.
        mesh.set_cmap(mesh.get_cmap().with_extremes(over="none"))
    if args.labelz is not None:
        label = args.labelz
    elif args.density:
        label = "Density"
    elif delta_chi2:
        label = r"$\Delta\chi^2$"
    else:
        label = resolve_axis_label(None, args.z, rows)
    ax._background_colorbar = (mesh, label)


def _handle_signature(handle):
    """What a legend entry shows: its label, colours and line style."""
    parts = [handle.get_label()]
    for getter in ("get_facecolor", "get_edgecolor", "get_color", "get_linestyle", "get_hatch"):
        value = getattr(handle, getter, None)
        if value is not None:
            value = value()
            parts.append(tuple(np.ravel(value)) if isinstance(value, (np.ndarray, list, tuple)) else value)
    return tuple(parts)


def legend_panels(handle_lists):
    """Indices of the panels that draw their legend: each panel with
    entries, or only the last of them when every panel shows the same
    entries (one legend says it for all)."""
    filled = [pdx for pdx, handles in enumerate(handle_lists) if handles]
    signatures = {tuple(_handle_signature(h) for h in handle_lists[pdx]) for pdx in filled}
    if len(filled) > 1 and len(signatures) == 1:
        return filled[-1:]
    return filled


def contour_legend(sets, labels):
    """Legend handles. A lone contour set gets one handle per level. Several
    get one handle per set (its colour) and one per level (its line style and
    fill, in the text colour); a set coloured by a palette keeps one handle
    per level, prefixed with its label."""
    if not sets:
        return []
    count = len(labels)

    def per_level(s, prefix=None, hues=None):
        fills = s["fills"] or [None] * count
        return [level_handle(f"{prefix} {label}" if prefix else label, hue, ls, s["width"], fill)
                for label, hue, ls, fill in zip(labels, hues or s["hues"], s["styles"], fills)]

    if len(sets) == 1:
        return per_level(sets[0])
    handles = []
    for s in sets:
        if s["palette"]:
            handles += per_level(s, prefix=s["label"])
        else:
            fill = s["fills"][0] if s["fills"] else None
            handles.append(level_handle(s["label"], s["hues"][0], s["styles"][0], s["width"], fill))
    neutral = plt.rcParams["text.color"]
    reference = next((s for s in sets if not s["palette"]), sets[0])
    filled = dict(reference, fills=[mix_paper(neutral, m) for m in fill_mix(count)] if reference["fills"] else None)
    return handles + per_level(filled, hues=[neutral] * count)


def _first_notice(key):
    """True the first time ``key`` is noticed in this run: once per process, or
    once per command list under ``plotipus run`` (which shares a marker
    directory, PLOTIPUS_NOTICE_DIR, between its commands)."""
    if key in _NOTICES_SHOWN:
        return False
    _NOTICES_SHOWN.add(key)
    folder = os.environ.get("PLOTIPUS_NOTICE_DIR")
    if not folder:
        return True
    try:
        os.close(os.open(os.path.join(folder, key), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except FileExistsError:
        return False
    except OSError:
        return True
    return True


def resolve_contour_options(args):
    """Fill --contour_dof, --contour_label and --background from the style's
    contours section; print the one-off notice about the 2-dof default."""
    settings = style.contours
    if args.contour_dof is None:
        args.contour_dof = int(settings.get("dof", 2))
        if "dof" not in settings and args.contour_level_mode == "sigma_probability" and _first_notice("contour_dof"):
            levels = ", ".join(f"{level:.2f}" for level in contour_levels(args.contour_sigmas, args.contour_level_mode, 2))
            rprint(f"[yellow]Notice:[/yellow] contour levels now use 2 dof (Δχ² = {levels}); "
                   "pass --contour_dof 1 for the previous levels")
    if args.contour_label is None:
        args.contour_label = settings.get("label", "cl")
    if args.background is None:
        args.background = settings.get("background", "none")


def _item_label(args, config, name, hue):
    if args.configs is None and args.names is None:
        label = "Selection"
        return f"{label}, {hue}" if hue is not None else label
    if len(set(args.configs or [])) <= 1 and len(set(args.names or [])) <= 1:
        # A single contour names both its config and its name.
        both = copy.copy(args)
        both.configs, both.names = [config, None], [name, None]
        return make_config_label_from_args(both, config=config, name=name, iterable=hue)
    return make_config_label_from_args(args, config=config, name=name, iterable=hue)


def _items(subset, projected, args, configs, names):
    """(index, config, name, variant, rows, projected) per contour; the
    variant is ("datafile", label), ("hue", --contour_hue value) or None."""
    items = []
    for cdx, (config, name) in enumerate(zip(configs, names)):
        rows = subset
        if config is not None:
            rows = rows[rows["Config"] == config]
        if name is not None:
            rows = rows[rows["Name"] == name]
        if "_Occurrence" in rows.columns:
            rows = rows[rows["_Occurrence"] == cdx]
        if rows.empty:
            continue
        # Several datasets of one config (--contour_hue values, or --datafile variants): one contour each.
        if args.contour_hue is not None:
            groups = [(("hue", value), group) for value, group in rows.groupby(args.contour_hue, sort=False)]
        elif "_Datafile" in rows.columns and rows["_Datafile"].nunique() > 1:
            groups = [(("datafile", label), group) for label, group in rows.groupby("_Datafile", sort=False)]
        else:
            groups = [(None, rows)]
        items += [(cdx, config, name, variant, group, False) for variant, group in groups]
    if not projected.empty:
        for pdx, config in enumerate(args.project):
            rows = projected[projected["Config"] == config]
            if rows.empty:
                rprint(f"[yellow]Warning:[/yellow] No --project data for Config={config}. Skipping.")
                continue
            name = rows["Name"].iloc[0] if "Name" in rows.columns else None
            items.append((len(configs) + pdx, config, name, None, rows, True))
    return items


def draw_contour_panel(ax, fig, panel_idx, subset, projected, args, configs, names, hue, colors):
    """Draw one contour panel; returns its (x, y) extent or None. ``colors``
    is the figure's :class:`ColorAllocator`."""
    config_color = style.get_mapping_dict("config_color") or {}
    config_line = style.get_mapping_dict("config_line") or {}
    payloads, reference, background, combined = [], None, None, None
    needs_shared = args.background in ("all", "combined") or args.combine_op == "squared_sum"
    for cdx, config, name, variant, rows, is_projected in _items(subset, projected, args, configs, names):
        try:
            grid, exposure = project_grid(rows, args) if is_projected else (aggregate_grid(rows, args), None)
        except ValueError as error:
            rprint(f"[red]Error:[/red] {error}")
            continue
        if grid is None:
            continue
        x, y, z = grid["x"], grid["y"], grid["z"]
        term = z if args.contour_level_mode == "sigma_probability" else np.square(z)
        if reference is None:
            reference, background, combined = (x, y), z.copy(), term.copy()
        elif _same_grid(reference, (x, y)):
            background, combined = background + z, combined + term
        elif needs_shared:
            rprint("[red]Error:[/red] Configuration grids do not share the same x/y coordinates, so they cannot be combined on one contour plot.")
            continue

        if is_projected:
            color = colors.color_for(("projected", config), style.resolve_mapped_color(config_color.get(config)))
            linestyle = None
            suffix = args.project_label or (f"Projected, {exposure:g} yr" if exposure is not None else "Projected")
            label = f"{_item_label(args, config, name, hue)} ({suffix})"
        elif variant is not None and variant[0] == "hue":
            value = variant[1]
            color = colors.color_for(("contour_hue", value),
                                     hue_color(value, args, args.contour_hue))
            linestyle = None
            label = map_iterable_label(value, args.contour_hue, args.iterable_mapping)
            if len(configs) > 1 or len(names) > 1:  # the datasets of several configs: say which config
                label = f"{_item_label(args, config, name, hue)}, {label}"
        elif variant is not None:
            datafile = variant[1]
            color = colors.color_for(("datafile", cdx, datafile), map_iterable_color(datafile, args.iterable_color_mapping))
            linestyle = None
            label = f"{_item_label(args, config, name, hue)}, {map_iterable_label(datafile, '_Datafile', args.iterable_mapping)}"
        else:
            color = colors.color_for(("config", cdx), style.resolve_mapped_color(config_color.get(config)))
            linestyle = config_line.get(config)
            label = _item_label(args, config, name, hue)
        payloads.append({"x": x, "y": y, "z": z, "color": color, "linestyle": linestyle, "label": label})

    if not payloads or reference is None:
        return None
    if args.combine_op == "squared_sum":
        if args.contour_level_mode == "sigma_probability":
            # Re-centre the summed delta-chi2 on the joint best fit.
            minimum = np.nanmin(combined)
            if np.isfinite(minimum) and minimum > 0:
                combined = combined - minimum
        else:
            combined = np.sqrt(combined)
    else:
        combined = background

    bx, by = reference
    levels = contour_levels(args.contour_sigmas, args.contour_level_mode, args.contour_dof)
    if args.background == "all":
        draw_background(ax, fig, bx, by, background, args, subset, levels)
    elif args.background == "first":
        draw_background(ax, fig, payloads[0]["x"], payloads[0]["y"], payloads[0]["z"], args, subset, levels)
    elif args.background == "combined":
        draw_background(ax, fig, bx, by, combined, args, subset, levels)

    # Each contour set: filled bands (best fit outwards), outlines per level, a '+' at the minimum.
    sets, best = [], []
    labels = sigma_labels(levels, args.contour_sigmas, args.contour_level_mode, args.contour_dof, args.contour_label)
    smooth = lambda z: _smooth(_smooth(z, args.background_smoothing_sigma), args.contour_smoothing_sigma)  # noqa: E731

    def draw_set(x, y, image, color, label, linestyle, width, alpha, zorder, offset=0, palette_colors=False):
        hues = band_hues(color, len(levels), offset)
        styles = level_linestyles(args, len(levels), linestyle)
        fills = None
        if args.fill_contours:
            fills = draw_filled(ax, x, y, image, levels, color, args, zorder, offset)
            width, alpha = args.fill_outline_linewidth if args.fill_outline_linewidth is not None else width, 1.0
        draw_outlines(ax, x, y, image, levels, hues, styles, width, alpha, args, zorder + 0.5, labels)
        if not args.no_best_fit:
            # On a Delta-chi2 map the best fit is a point with its 1-sigma intervals: in ink for one
            # contour set, in the set's colour when several share the panel.
            delta_chi2 = args.contour_level_mode == "sigma_probability"
            single = len(payloads) == 1 and args.combine_op != "squared_sum"
            best.append(draw_best_fit(ax, x, y, image, style.role("ink") if delta_chi2 and single else hues[0],
                                      zorder=7, errors=delta_chi2))
        sets.append({"label": label, "hues": hues, "styles": styles, "width": width, "fills": fills,
                     "palette": palette_colors})

    if not args.combined_contours_only and levels:
        for p in payloads:
            draw_set(p["x"], p["y"], smooth(p["z"]), p["color"], p["label"], p["linestyle"],
                     args.contour_linewidth, args.contour_alpha, zorder=5)

    if args.combine_op == "squared_sum" and levels:
        colors = palette(args.combined_color)
        # Shift the palette per panel so panels do not all start at one colour.
        offset = 0 if args.unified_colors or not colors else panel_idx % len(colors)
        draw_set(bx, by, smooth(combined), args.combined_color, args.combined_label, args.combined_linestyle,
                 _combined_width(args), args.combined_alpha, zorder=6, offset=offset, palette_colors=bool(colors))

    if args.contour_labels:
        # The levels are written on the lines: the legend only tells several sets apart.
        handles = [level_handle(s["label"], s["hues"][0], s["styles"][0], s["width"], (s["fills"] or [None])[0])
                   for s in sets] if len(sets) > 1 else []
    else:
        handles = contour_legend(sets, labels)
    marks = [b for b in best if b is not None]
    if len(marks) == 1:
        handles = handles + marks  # "Best fit": a point with error bars
    ax._contour_handles = handles
    xs, ys = np.asarray(bx, dtype=float), np.asarray(by, dtype=float)
    return [float(np.nanmin(xs)), float(np.nanmax(xs))], [float(np.nanmin(ys)), float(np.nanmax(ys))]


def draw_contour_shapes(ax, args, color):
    """--square rectangles and --line segments of a contour panel, in
    ``color`` unless given. Drawn before the panel limits are set, so the
    grid (or --rangex/--rangey) keeps the frame."""
    for parse, normalize, draw, key in ((parse_square_quads, normalize_square_labels, draw_squares, "square"),
                                        (parse_line_segments, normalize_line_labels, draw_lines, "line")):
        shapes = parse(getattr(args, key, None))
        if not shapes:
            continue
        labels, warning = normalize(getattr(args, f"{key}_label", None), len(shapes))
        if warning:
            rprint(f"[yellow]Warning:[/yellow] {warning}")
        draw(ax, shapes, labels=labels, styles=getattr(args, f"{key}_style", None),
             colors=getattr(args, f"{key}_color", None) or [color], fontsize=style.linelabelfontsize)


def draw_contour_figure(df, args):
    if args.iterable is not None and args.iterable not in df.columns:
        rprint(f"[yellow]Warning:[/yellow] Iterable key '{args.iterable}' not found in dataframe columns. Ignoring --iterable filtering.")
        args.iterable = None
    if args.select is not None:
        keep = [i for i, key in enumerate(args.select) if key in df.columns]
        for i, key in enumerate(args.select):
            if i not in keep:
                rprint(f"[yellow]Warning:[/yellow] Selected key '{key}' not found in dataframe columns. Skipping this filter key.")
        args.save_values = [args.save_values[i] for i in keep if i < len(args.save_values)] or None if args.save_values else None
        args.remove_value = [args.remove_value[i] for i in keep if i < len(args.remove_value)] or None if args.remove_value else None
        args.select = [args.select[i] for i in keep] or None
        if args.select is None:
            args.save_values = args.remove_value = None
    if args.density and args.contour_level_mode == "sigma_probability":
        rprint("[red]Error:[/red] --density destroys the delta-chi2 scale of --contour_level_mode sigma_probability.")
        return None
    resolve_contour_options(args)
    if args.combined_contours_only and args.combine_op != "squared_sum":
        rprint("[yellow]Warning:[/yellow] --combined_contours_only requires --combine_op squared_sum; ignoring the flag.")
        args.combined_contours_only = False

    configs, names = prepare_import(args)
    configs = configs if configs is not None else [None]
    names = names if names is not None else [None]
    filtered = filter_dataframe(df, args)
    projected = load_projected(args, configs, names)
    if not projected.empty:
        projected = filter_dataframe(projected, args)
    if args.iterable is not None and args.iterable_label_map is not None:
        label_map = json.loads(args.iterable_label_map)

        def remap(frame):
            if args.iterable not in frame.columns:
                return frame
            frame = frame.copy()
            frame[args.iterable] = frame[args.iterable].astype(str).map(lambda v: label_map.get(str(v), str(v)))
            return frame

        filtered, projected = remap(filtered), remap(projected)

    hues = list(filtered[args.iterable].unique()) if args.iterable is not None else [None]
    variables = args.variables if args.variables is not None else [None]
    # One panel per hue value left by the selection (not per value anywhere in the file).
    ncols = len(variables) if args.variables is not None else len(hues) if args.iterable is not None else 1
    fig, axes, _, _ = create_panels(ncols, grid=False)
    # Compact panels share one y range (the union of theirs).
    match_y = args.matchy or (compact(args, ncols) and ncols > 1)
    # One colour per config in every panel; config_color entries are reserved first.
    colors = ColorAllocator()
    config_color = style.get_mapping_dict("config_color") or {}
    colors.reserve([("config", cdx) for cdx in range(len(configs))],
                   lambda key: style.resolve_mapped_color(config_color.get(configs[key[1]])))
    matched = [None, None]
    # Overlays in the paper colour only on a linear background image that fills the panel (a delta-chi2
    # background is blank beyond the outermost level unless --rangez is given); else in ink.
    full_image = args.background != "none" and (args.contour_level_mode == "z_values" or args.rangez is not None)
    on_image = full_image and not args.logz
    line_color = style.role("paper") if on_image else style.role("ink")
    for vdx, variable in enumerate(variables):
        for hdx, hue in enumerate(hues):
            panel_idx = vdx if args.variables is not None else hdx
            ax = axes[panel_idx]
            subset = _panel_rows(filtered, args, variable, hue)
            if subset.empty:
                rprint(f"[yellow]Warning:[/yellow] No data for {variable if variable is not None else hue}. Skipping...")
                continue
            proj = projected
            if not proj.empty:
                if variable is not None:
                    proj = proj[proj["Variable"] == variable]
                if hue is not None and args.iterable in proj.columns:
                    proj = proj[proj[args.iterable] == hue]
            extent = draw_contour_panel(ax, fig, panel_idx, subset, proj, args, configs, names, hue, colors)
            if extent is None:
                continue
            x_range, y_range = extent
            if matched[0] is None:
                matched = [list(x_range), list(y_range)]
            else:
                if args.matchx:
                    matched[0] = [min(matched[0][0], x_range[0]), max(matched[0][1], x_range[1])]
                if match_y:
                    matched[1] = [min(matched[1][0], y_range[0]), max(matched[1][1], y_range[1])]
            contour_artists = set(ax.get_children())
            if args.diagonal:
                _diagonal(ax, [min(x_range[0], y_range[0]), max(x_range[1], y_range[1])], color=line_color)
            draw_horizontal_lines(ax, args.horizontal, labels=args.horizontal_label, styles=args.horizontal_style,
                                  colors=args.horizontal_color or [line_color], fontsize=style.linelabelfontsize,
                                  label_pos=getattr(args, "horizontal_label_pos", "right"))
            draw_vertical_lines(ax, args.vertical, labels=args.vertical_label, styles=args.vertical_style,
                                colors=args.vertical_color or [line_color], fontsize=style.linelabelfontsize)
            draw_contour_shapes(ax, args, line_color)
            # Reference overlays sit above the contours, below the best-fit markers.
            for artist in set(ax.get_children()) - contour_artists:
                artist.set_zorder(OVERLAY_ZORDER)
            if ncols > 1:
                ax.set_title(make_subtitle_from_args(args, hues, plot_type="hist2d", idx=hdx), fontsize=style.subtitlefontsize)
            ax.set_xlabel(resolve_axis_label(args.labelx, args.x, subset))
            if first_column(ax):
                ax.set_ylabel(resolve_axis_label(args.labely, args.y, subset))
            else:
                ax.set_ylabel("")
            ax.set_xlim(matched[0] if args.matchx else x_range)
            ax.set_ylim(matched[1] if match_y else y_range)
            if args.rangex is not None:
                ax.set_xlim(args.rangex)
            if args.rangey is not None:
                ax.set_ylim(args.rangey)
            apply_tick_formatter(ax, axis="both")
            points = parse_point_pairs(args.point)
            point_labels, warning = normalize_point_labels(args.point_label, len(points))
            if warning:
                rprint(f"[yellow]Warning:[/yellow] {warning}")
            for i, (px, py) in enumerate(points):
                ax.scatter(px, py, color=line_color, edgecolors=style.role("ink") if on_image else style.role("paper"),
                           linewidths=1.0, s=85, zorder=100)
                if point_labels is not None:
                    place_point_label(ax, px, py, point_labels[i], fontsize=style.linelabelfontsize)

    handle_lists = [getattr(ax, "_contour_handles", []) for ax in axes]
    for pdx in legend_panels(handle_lists):
        apply_legend_style(axes[pdx], handles=handle_lists[pdx], capitalize_labels=args.capitalize_legend).set_zorder(10)

    if compact(args, ncols) and ncols > 1:
        limits = axes[0].get_ylim()
        share_rows(axes[:ncols], args)
        axes[0].set_ylim(limits)
    draw_colorbars(fig, [(ax, *ax._background_colorbar) for ax in axes if hasattr(ax, "_background_colorbar")], args)
    add_title_and_note(fig, args)
    return save(fig, args, None, suffix="contour.png")


# --- Entry point -------------------------------------------------------------------------


def run(args):
    if args.contour_label_pos:
        args.contour_labels = True
    if args.cmap == "diverging":
        args.cmap = style.diverging_cmap
    df = import_data(args)
    if df.empty:
        rprint("[yellow]Warning:[/yellow] No datafiles found. Exiting...")
        return []
    if args.variables is not None and args.iterable is not None:
        rprint("[red]Error:[/red] Both --variables and --iterable were given; use only one.")
        return []
    if args.corner is not None:
        missing = [v for v in args.corner if v not in df.columns]
        if len(args.corner) < 2 or missing:
            rprint("[red]Error:[/red] --corner needs two or more columns of the data"
                   + (f"; not found: {', '.join(missing)}" if missing else ""))
            return []
        if args.z is not None or args.variables is not None or args.iterable is not None:
            rprint("[red]Error:[/red] --corner draws raw points only; drop -z, --variables and --iterable.")
            return []
        if args.contour_hue is not None and (not args.contour or args.contour_hue not in df.columns):
            rprint("[red]Error:[/red] --corner overlays the values of --contour_hue, a column of the data, with --contour.")
            return []
    posterior_only = {"--corner_levels": args.corner_levels, "--corner_interval": args.corner_interval,
                      "--corner_cyclic": args.corner_cyclic, "--corner_bound": args.corner_bound,
                      "--corner_split": args.corner_split, "--corner_upper": args.corner_upper,
                      "--corner_mc_error": args.corner_mc_error, "--corner_band": args.corner_band,
                      "--corner_prior": args.corner_prior, "--corner_shrinkage": args.corner_shrinkage,
                      "--corner_block": args.corner_block}
    given = [name for name, value in posterior_only.items() if value]
    if given and not (args.corner and args.contour):
        rprint(f"[red]Error:[/red] {', '.join(given)} apply to a posterior corner plot (--corner ... --contour).")
        return []
    if args.corner_upper == "profile" and (args.loglike is None or args.loglike not in df.columns):
        rprint("[red]Error:[/red] --corner_upper profile needs --loglike COLUMN, the log-likelihood of each draw.")
        return []
    if args.corner_prior is not None and args.contour_hue is None:
        rprint("[red]Error:[/red] --corner_prior names a value of --contour_hue COLUMN, whose rows hold the prior draws.")
        return []
    if args.corner_shrinkage and args.corner_prior is None:
        rprint("[red]Error:[/red] --corner_shrinkage compares with the prior: name its rows with --corner_prior VALUE.")
        return []
    absent = [name for name in args.corner_block or [] if name not in df.columns]
    if absent or (args.corner_block and args.corner_upper == "profile"):
        rprint("[red]Error:[/red] --corner_block takes array columns of the data"
               + (f"; not found: {', '.join(absent)}" if absent else " and shares the upper triangle with --corner_upper corr "
                  "only (the profile likelihood fills every cell)"))
        return []
    missing = [entry[0] for entry in args.corner_split or [] if len(entry) == 1 and entry[0] not in df.columns]
    if missing:
        rprint(f"[red]Error:[/red] --corner_split: no column {', '.join(missing)} (a label column, or VARIABLE VALUE).")
        return []
    if args.weight is not None and not (args.corner and args.contour and args.weight in df.columns):
        rprint("[red]Error:[/red] --weight takes a column of the data and applies to --corner --contour.")
        return []
    if args.corner is None and (args.x is None or args.y is None):
        rprint("[red]Error:[/red] map needs -x and -y (or --corner X1 X2 ...).")
        return []
    if args.map_type == "hexbin" and (args.z is not None or args.contour or args.annotate is not None
                                      or args.norm not in (None, "global")):
        rprint("[red]Error:[/red] --map_type hexbin bins raw points: no -z, --contour or --annotate, "
               "and only --norm global.")
        return []
    if args.variables is not None and "None" in args.variables and "Variable" in df.columns:
        df["Variable"] = df["Variable"].fillna("None")
    if args.contour_hue is not None and args.corner is None and not (args.contour and args.z is not None):
        rprint("[red]Error:[/red] --contour_hue overlays -z maps: it needs --contour and -z.")
        return []
    if args.contour_hue is not None and args.contour_hue not in df.columns:
        rprint(f"[red]Error:[/red] --contour_hue: no column '{args.contour_hue}' in the data.")
        return []
    if args.contour and args.z is None:
        # Without a map: the sigma regions of the sampled points, over their 2D histogram.
        resolve_contour_options(args)
    elif args.contour:
        if args.combined_color is None:
            args.combined_color = style.role("ink")
        return [draw_contour_figure(df, args)]
    if args.multiply is not None and args.z is not None:
        df[args.z] = df[args.z].apply(lambda v: np.asarray(v) * args.multiply if v is not None else v)
    outputs = []
    for kdx, config, name, rows in _base.figure_groups(df, args):
        print(f"Plotting for Config: {config}, Name: {name}")
        outputs.append(draw_corner_figure(rows, args, kdx) if args.corner else draw_histogram_figure(rows, args, kdx))
    return outputs


# --- Legacy command lines ----------------------------------------------------------------


def _legacy_hist2d(tokens):
    return tokens + ["--output_suffix", "hist2d.png"]


def _legacy_contour(tokens):
    from ..legacy import rename

    tokens = rename(tokens, {"--operation": "--combine_op"})
    out = []
    for i, token in enumerate(tokens):
        if i > 0 and tokens[i - 1] == "--combined_color" and token.strip().upper() == "DUNE":
            token = "cycle"
        out.append(token)
    # The legacy scripts drew 1-dof levels (delta-chi2 = sigma^2).
    return out + ["--contour", "--contour_dof", "1", "--output_suffix", "contour.png"]


LEGACY = {
    "script_compare_hist2d": _legacy_hist2d,
    "script_compare_contour": _legacy_contour,
}
