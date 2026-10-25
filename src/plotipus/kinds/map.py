"""map: two-dimensional data as a colour map, optionally with contours.

Three inputs, one row per panel (panels from ``--variables`` or ``--hue``):

* raw points: ``x`` and ``y`` arrays per row, binned into a 2D histogram
  (integer-valued data gets one bin per integer; ``--norm`` normalises rows,
  columns or the whole map; ``--percentile`` sets the range);
* a gridded map: ``-z`` names a 2D array cell drawn on the ``x``/``y`` grid
  with a colour bar;
* contours (``--contour``): gridded maps (Δχ² or significance) of every
  ``--configs``/``--names`` entry drawn as confidence contours (2-dof Δχ²
  levels by default, ``--contour_dof``), lines or graded filled bands, with a
  ``+`` at the best fit and an optional background image, optionally combined
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
from matplotlib.colors import LogNorm, Normalize, to_rgb, to_rgba
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.path import Path
from rich import print as rprint

from .. import style
from ..args import add_common_args, map_iterable_color, map_iterable_label, parse_plot_label, resolve_axis_label
from ..format import _title_case_words, make_config_label_from_args, make_subtitle_from_args
from ..io import import_data, normalize_datafiles, prepare_import
from ..palettes import ColorAllocator
from ..panels import add_colorbar, add_title_and_note, create_panels, draw_overlays, save
from ..plot import (
    apply_legend_style,
    apply_scientific_threshold_formatter,
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
            "labelz", "rangex", "rangey", "rangez", "logz", "density", "norm", "zoom", "matchx",
            "matchy", "horizontal", "horizontal_label", "horizontal_style", "horizontal_color",
            "vertical", "vertical_label", "vertical_style", "vertical_color", "square",
            "square_label", "square_style", "square_color", "line", "line_label", "line_style",
            "line_color", "title", "output", "subfolder", "point", "point_label", "note",
            "multiply", "debug",
        ],
        overrides={
            "datafile": {"required": True},
            "x": {"required": True},
            "y": {"required": True},
            "bins": {"default": None, "help": "Number of bins of the 2D histogram (default: style nbins)"},
            "percentile": {"default": [0, 100], "help": "Percentile range of the histogram axes"},
            "density": {"help": "Normalise the histogram (or each contour map) to unit sum"},
            "zoom": {"help": "Restrict the histogram range to the overlap of the panels' ranges"},
            "multiply": {"help": "Multiply every -z value by this factor"},
        },
    )
    add = parser.add_argument
    add("--diagonal", action="store_true", default=False, help="Draw the y = x line.")
    add("--cmap", type=str, default=None, help="Matplotlib colour map of -z images.")
    add("--colorbar", default=None, choices=["shared", "each"],
        help="One colorbar and colour scale for the row of panels (shared, the default unless --norm) "
        "or one per panel (each).")
    add("--panel_title", nargs="+", type=parse_plot_label, default=None, help="Title of each panel.")
    add("--compact", action="store_true", default=False, help="Hide repeated y ticks on inner panels.")
    add("--iterable_mapping", type=str, default=None,
        help="Mapping renaming the datafile of each overlaid contour variant in the legend.")
    add("--iterable_color_mapping", type=str, default=None,
        help="Mapping giving the colour of each overlaid contour variant (by datafile).")
    add("--iterable_label_map", type=str, default=None, help="JSON {hue value: label} applied to the panel values.")

    group = parser.add_argument_group("contours")
    add = group.add_argument
    add("--contour", action="store_true", default=False,
        help="Contour mode: sigma contours of each config/name map over a background image (needs -z).")
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
    add("--contour_alpha", type=float, default=0.95)
    add("--contour_smoothing_sigma", type=float, default=0.0, help="Gaussian smoothing of the maps before contouring.")
    add("--background_smoothing_sigma", type=float, default=0.0, help="Gaussian smoothing of the background image.")
    add("--contour_min_vertices", type=int, default=0, help="Drop contour pieces with fewer vertices.")
    add("--background", default=None, choices=["all", "combined", "first", "none"],
        help="Background image: sum of all maps, the combined map, the first map or none (default: style "
        "contours.background, none). Delta-chi2 backgrounds are clipped at the outermost level.")
    add("--no_best_fit", action="store_true", default=False, help="Do not mark the map minimum with a '+'.")
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

        x_range = [np.percentile(x, args.percentile[0]), np.percentile(x, args.percentile[1])]
        y_range = [np.percentile(y, args.percentile[0]), np.percentile(y, args.percentile[1])]
        if ranges is None or not args.zoom:
            ranges = [list(x_range), list(y_range)]
        else:
            ranges = [[max(ranges[0][0], x_range[0]), min(ranges[0][1], x_range[1])],
                      [max(ranges[1][0], y_range[0]), min(ranges[1][1], y_range[1])]]

        if z is not None:
            mappable = plot_data(args, ax, x, y=y, plot_type="image", z=z,
                                 **({"cmap": args.cmap} if args.cmap is not None else {}))
            if args.logz:
                mappable.set_array(np.ma.masked_less_equal(mappable.get_array(), 0))
            if args.rangez is not None:
                mappable.set_clim(*args.rangez)
                if args.logz:
                    # Bins below the log floor stay blank instead of taking the lowest colour.
                    mappable.set_cmap(mappable.get_cmap().with_extremes(under="none"))
            colorbars.append((ax, mappable, resolve_axis_label(args.labelz, args.z, subset)))
        else:
            kwargs = {"range": (x_range, y_range), "bins": args.bins or style.nbins}
            if is_integer_valued(x) and is_integer_valued(y):
                kwargs["bins"] = [integer_bin_edges(*x_range), integer_bin_edges(*y_range)]
            hist = plot_data(args, ax, x, y=y, plot_type="hist2d", **kwargs)
            mesh = hist[3]
            if args.norm is not None:
                mesh.set_array(normalize_hist2d(hist[0], args.norm).T)
            # Empty bins are blank on linear and log scales alike.
            mesh.set_array(np.ma.masked_less_equal(mesh.get_array(), 0))
            if args.logz:
                mesh.autoscale()  # vmin at the smallest non-empty bin
            else:
                mesh.set_clim(0, mesh.get_array().max())
            if args.rangez is not None:
                mesh.set_clim(*args.rangez)
            label = args.labelz or (NORM_LABELS[args.norm] if args.norm else "Density" if args.density else "Counts")
            colorbars.append((ax, mesh, label))

        if args.diagonal:
            ax.plot(x_range, x_range, color=style.role("ink") if args.logz else style.role("paper"), linestyle="--")
            ax.set_xlim(ranges[0])
            ax.set_ylim(ranges[0])

    draw_colorbars(fig, colorbars, args)

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
        apply_scientific_threshold_formatter(ax, threshold=0.1, axis="both")
        draw_overlays(ax, args)

    add_title_and_note(fig, args)
    return save(fig, args, kdx, suffix="hist2d.png")


def colorbar_mode(args):
    """shared or each: panels share one colorbar unless --norm normalises
    each panel on its own scale (or --colorbar each asks for one per panel)."""
    return args.colorbar or ("each" if args.norm else "shared")


def draw_colorbars(fig, entries, args):
    """Colorbars of ``entries`` [(ax, mappable, label)]: one per panel, or a
    shared one right of the row when the panels show the same quantity (one
    label), with one norm spanning every panel."""
    if not entries:
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


def _smooth(z, sigma):
    z = np.asarray(z, dtype=float)
    if sigma <= 0:
        return z
    from scipy.ndimage import gaussian_filter

    return gaussian_filter(z, sigma=sigma)


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


def draw_outlines(ax, x, y, image, levels, hues, linestyles, width, alpha, args, zorder):
    lines = ax.contour(x, y, image, levels=levels, colors=hues, linestyles=linestyles,
                       linewidths=width, alpha=alpha, zorder=zorder)
    _filter_vertices(lines, args.contour_min_vertices)


def draw_best_fit(ax, x, y, image, color, zorder):
    """A '+' at the grid minimum, haloed in the paper colour so it shows on
    a fill of its own hue."""
    image = np.asarray(image, dtype=float)
    if not np.isfinite(image).any():
        return
    i, j = np.unravel_index(np.nanargmin(image), image.shape)
    xa, ya = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    bx = xa[i, j] if xa.ndim == 2 else xa[j]
    by = ya[i, j] if ya.ndim == 2 else ya[i]
    size, width = 2.5 * plt.rcParams["lines.markersize"], max(1.5, plt.rcParams["lines.linewidth"])
    ax.plot([bx], [by], linestyle="none", marker="+", color=color, markersize=size, markeredgewidth=width,
            zorder=zorder, path_effects=[patheffects.withStroke(linewidth=width + 2, foreground=_paper())])


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
    """(index, config, name, datafile, rows, projected) per contour."""
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
        # Several --datafile variants of one config: one contour each.
        if "_Datafile" in rows.columns and rows["_Datafile"].nunique() > 1:
            groups = list(rows.groupby("_Datafile", sort=False))
        else:
            groups = [(None, rows)]
        items += [(cdx, config, name, label, group, False) for label, group in groups]
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
    for cdx, config, name, datafile, rows, is_projected in _items(subset, projected, args, configs, names):
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
        elif datafile is not None:
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
    sets = []
    smooth = lambda z: _smooth(_smooth(z, args.background_smoothing_sigma), args.contour_smoothing_sigma)  # noqa: E731

    def draw_set(x, y, image, color, label, linestyle, width, alpha, zorder, offset=0, palette_colors=False):
        hues = band_hues(color, len(levels), offset)
        styles = level_linestyles(args, len(levels), linestyle)
        fills = None
        if args.fill_contours:
            fills = draw_filled(ax, x, y, image, levels, color, args, zorder, offset)
            width, alpha = args.fill_outline_linewidth if args.fill_outline_linewidth is not None else width, 1.0
        draw_outlines(ax, x, y, image, levels, hues, styles, width, alpha, args, zorder + 0.5)
        if not args.no_best_fit:
            draw_best_fit(ax, x, y, image, hues[0], zorder=7)
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

    labels = sigma_labels(levels, args.contour_sigmas, args.contour_level_mode, args.contour_dof, args.contour_label)
    handles = contour_legend(sets, labels)
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
                if args.matchy:
                    matched[1] = [min(matched[1][0], y_range[0]), max(matched[1][1], y_range[1])]
            contour_artists = set(ax.get_children())
            if args.diagonal:
                span = [min(x_range[0], y_range[0]), max(x_range[1], y_range[1])]
                ax.plot(span, span, color=line_color, linestyle="--")
            draw_horizontal_lines(ax, args.horizontal, labels=args.horizontal_label, styles=args.horizontal_style,
                                  colors=args.horizontal_color or [line_color], fontsize=style.linelabelfontsize)
            draw_vertical_lines(ax, args.vertical, labels=args.vertical_label, styles=args.vertical_style,
                                colors=args.vertical_color or [line_color], fontsize=style.linelabelfontsize)
            draw_contour_shapes(ax, args, line_color)
            # Reference overlays sit above the contours, below the best-fit markers.
            for artist in set(ax.get_children()) - contour_artists:
                artist.set_zorder(OVERLAY_ZORDER)
            if ncols > 1:
                ax.set_title(make_subtitle_from_args(args, hues, plot_type="hist2d", idx=hdx), fontsize=style.subtitlefontsize)
            ax.set_xlabel(resolve_axis_label(args.labelx, args.x, subset))
            if panel_idx == 0:
                ax.set_ylabel(resolve_axis_label(args.labely, args.y, subset))
            else:
                ax.set_ylabel("")
                if args.compact:
                    ax.tick_params(labelleft=False)
            ax.set_xlim(matched[0] if args.matchx else x_range)
            ax.set_ylim(matched[1] if args.matchy else y_range)
            if args.rangex is not None:
                ax.set_xlim(args.rangex)
            if args.rangey is not None:
                ax.set_ylim(args.rangey)
            apply_scientific_threshold_formatter(ax, threshold=0.1, axis="both")
            points = parse_point_pairs(args.point)
            point_labels, warning = normalize_point_labels(args.point_label, len(points))
            if warning:
                rprint(f"[yellow]Warning:[/yellow] {warning}")
            for i, (px, py) in enumerate(points):
                ax.scatter(px, py, color=line_color, edgecolors=style.role("ink") if on_image else style.role("paper"),
                           linewidths=1.0, s=85, zorder=100)
                if point_labels is not None:
                    place_point_label(ax, px, py, point_labels[i], fontsize=style.linelabelfontsize)
            handles = getattr(ax, "_contour_handles", [])
            if handles:
                apply_legend_style(ax, handles=handles, capitalize_labels=args.capitalize_legend).set_zorder(10)

    draw_colorbars(fig, [(ax, *ax._background_colorbar) for ax in axes if hasattr(ax, "_background_colorbar")], args)
    add_title_and_note(fig, args)
    if args.compact and ncols > 1:
        fig.tight_layout()
    return save(fig, args, None, suffix="contour.png")


# --- Entry point -------------------------------------------------------------------------


def run(args):
    df = import_data(args)
    if df.empty:
        rprint("[yellow]Warning:[/yellow] No datafiles found. Exiting...")
        return []
    if args.variables is not None and args.iterable is not None:
        rprint("[red]Error:[/red] Both --variables and --iterable were given; use only one.")
        return []
    if args.variables is not None and "None" in args.variables and "Variable" in df.columns:
        df["Variable"] = df["Variable"].fillna("None")
    if args.contour:
        if args.z is None:
            rprint("[red]Error:[/red] --contour needs -z (the map column).")
            return []
        if args.combined_color is None:
            args.combined_color = style.role("ink")
        return [draw_contour_figure(df, args)]
    if args.multiply is not None and args.z is not None:
        df[args.z] = df[args.z].apply(lambda v: np.asarray(v) * args.multiply if v is not None else v)
    outputs = []
    for kdx, config, name, rows in _base.figure_groups(df, args):
        print(f"Plotting for Config: {config}, Name: {name}")
        outputs.append(draw_histogram_figure(rows, args, kdx))
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
