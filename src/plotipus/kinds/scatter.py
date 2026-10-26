"""scatter: points that are observations (both coordinates measured).

Two ways to get the points:

* **paired rows** (``--x_from COL=A --y_from COL=B``): the rows with
  ``COL == A`` give x and those with ``COL == B`` give y, matched on the
  ``-x`` column (e.g. energy bins); ``-y`` holds the values and
  ``--error_column`` their errors. ``--aggregate`` collapses each series to
  one (weighted) mean point. One series per --configs/--names pair (colour)
  and per hue value (marker shape when several pairs are drawn).
* **points** (default): array cells are exploded into one point per entry;
  ``-y`` (and ``-z``) are drawn against ``-x`` in side-by-side panels.
  Colour by ``--hue`` or a continuous ``--colorby`` column, size by
  ``--sizeby``, marker by ``--markerby`` (two values: hollow vs filled).
"""

import re

import matplotlib.lines as mlines
import numpy as np
import pandas as pd
from matplotlib.colors import LogNorm
from matplotlib.ticker import MaxNLocator
from rich import print as rprint

from .. import style
from ..args import add_common_args, map_iterable_color, map_iterable_label, resolve_axis_label
from ..encodings import add_legend_args
from ..format import make_config_color_and_style_from_args, make_config_label_from_args
from ..io import import_data, prepare_import
from ..palettes import ColorAllocator
from ..panels import add_colorbar, add_title_and_note, create_panels, save
from ..plot import add_centered_suptitle, apply_legend_style, apply_note_to_figure
from ..selection import filter_dataframe
from . import _base

KIND = "scatter"
MARKERS = ["o", "s", "^", "D", "v", "P", "X", "*", "h", "p"]
POINT_MARKERS = ["o", "^", "s", "D", "P", "X", "v", "*"]
HOLLOW_AREA = 4.0  # a hollow marker is drawn at twice the diameter (four times the area)


def build_parser():
    parser = _base.make_parser(KIND, "Scatter of observations: paired rows (--x_from/--y_from) or exploded points.")
    add_common_args(
        parser,
        [
            "datafile", "configs", "names", "variables", "iterable", "reduce", "select", "save_values",
            "remove_value", "filename_select", "filename_suffix", "x", "y", "z", "labelx", "labelz",
            "rangex", "rangey", "logz", "title", "output", "subfolder", "note", "debug",
        ],
        overrides={"datafile": {"required": True}, "z": {"help": "Second column drawn against -x in a second panel"}},
    )
    add = parser.add_argument
    add("--labely", nargs="+", type=str, default=None, help="y-axis label (one for all panels or one per panel).")
    add("--iterable_mapping", "--hue_mapping", dest="iterable_mapping", type=str, default=None,
        help="Mapping renaming the hue values in the legend.")
    add("--iterable_color_mapping", "--hue_color_mapping", dest="iterable_color_mapping", type=str, default=None,
        help="Mapping giving the colour of each hue value.")

    group = parser.add_argument_group("paired rows")
    add = group.add_argument
    add("--x_from", type=str, default=None, metavar="COL=VALUE", help="Rows giving the x values.")
    add("--y_from", type=str, default=None, metavar="COL=VALUE", help="Rows giving the y values.")
    add("--error_column", type=str, default=None, help="Column with the errors of -y (default {y}Error).")
    add("--aggregate", choices=["weighted_mean", "mean", "none"], default="weighted_mean",
        help="Collapse each series to one point (inverse-variance weighted or plain mean) or keep every bin.")
    add("--connect", action="store_true", default=False, help="Join the points of a series (or the series points).")
    add("--annotate", action="store_true", default=False, help="Label each aggregated point with its series.")
    add("--annotate_bins", action="store_true", default=False, help="With --aggregate none, label points by -x.")
    add("--label_map", nargs="+", default=None, metavar="NAME=LABEL", help="Legend labels for --names values.")
    add("--label_regex", nargs=2, default=None, metavar=("PATTERN", "REPLACEMENT"),
        help="re.sub applied to --names values not in --label_map.")
    add("--label_regex_scale", type=float, default=None,
        help="Divide the first captured number of --label_regex by this factor.")

    group = parser.add_argument_group("points")
    add = group.add_argument
    add("--colorby", type=str, default=None, help="Column mapped to a continuous colour map (instead of --hue).")
    add("--marker_size", "--ms", type=float, default=120.0, help="Marker area (default 120).")
    add("--sizeby", type=str, default=None,
        help="Column scaling the marker area within [marker_size/scale, marker_size*scale].")
    add("--sizeby_scale", type=float, default=4.0, help="Spread of --sizeby (1 disables it).")
    add("--size_legend_loc", type=str, default="best", help="Location of the --sizeby legend.")
    add("--labelsize", type=str, default=None, help="Title of the --sizeby legend.")
    add("--markerby", type=str, default=None, help="Column mapped to marker shapes (two values: hollow/filled).")
    add_legend_args(parser)
    _base.add_output_args(parser)
    return parser


def main(argv=None):
    return _base.main(__import__(__name__, fromlist=["run"]), argv)


def _split_selector(text):
    column, _, value = str(text).partition("=")
    return column, value


def _config_rows(df, config, name):
    if config is not None:
        df = df[df["Config"] == config]
    if name is not None:
        df = df[df["Name"] == name]
    return df


# --- Paired rows ----------------------------------------------------------------------


def _number_text(value):
    return str(int(value)) if value == int(value) else str(value)


def _value_text(value):
    try:
        return _number_text(float(value))
    except (TypeError, ValueError):
        return str(value)


def _hue_label(value, column):
    mapped = map_iterable_label(value, column)
    return mapped if mapped != str(value) else _value_text(value)


def _label_resolver(args):
    exact = {}
    for pair in args.label_map or []:
        if "=" not in pair:
            rprint(f"[yellow]Warning:[/yellow] Ignoring malformed --label_map entry '{pair}' (expected raw=Label).")
            continue
        key, _, value = pair.partition("=")
        exact[key] = value
    pattern = re.compile(args.label_regex[0]) if args.label_regex else None

    def _expand(match):
        template = args.label_regex[1]
        if args.label_regex_scale and match.group(1) is not None:
            try:
                template = template.replace(r"\1", _number_text(float(match.group(1)) / args.label_regex_scale))
            except ValueError:
                pass
        return match.expand(template)

    def resolve(name):
        if name is None or name in exact:
            return exact.get(name, name)
        if pattern is not None:
            new, n = pattern.subn(_expand, name)
            if n:
                return new
        return name

    return resolve


def _triplet(rows, x, y, error):
    columns = [x, y] + ([error] if error in rows.columns else [])
    points = rows.explode(column=columns)
    if points.empty:
        return None
    try:
        bins = points[x].astype(float).to_numpy()
        values = points[y].astype(float).to_numpy()
        errors = points[error].astype(float).to_numpy() if error in rows.columns else np.full_like(values, np.nan)
    except (ValueError, TypeError):
        return None
    mask = ~np.isnan(bins) & ~np.isnan(values)
    return (bins[mask], values[mask], errors[mask]) if mask.any() else None


def _weighted_mean(values, errors):
    valid = np.isfinite(errors) & (errors > 0)
    if not valid.any():
        return float(np.mean(values)), np.nan
    weights = 1.0 / errors[valid] ** 2
    return float(np.sum(values[valid] * weights) / np.sum(weights)), float(1.0 / np.sqrt(np.sum(weights)))


def _plain_mean(values, errors):
    n = values.size
    return float(np.mean(values)), (float(np.std(values, ddof=1) / np.sqrt(n)) if n > 1 else np.nan)


def _fill_colors(explicit):
    """Fill None colours from the palette, never reusing an explicit one."""
    colors = ColorAllocator()
    colors.reserve(range(len(explicit)), lambda i: explicit[i][0])
    return [(colors.color_for(i), linestyle) for i, (_, linestyle) in enumerate(explicit)]


def _quadrants_by_density(ax, xs, ys):
    (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
    xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
    xs, ys = np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)
    counts = {
        "lower left": int(np.sum((xs <= xm) & (ys <= ym))),
        "lower right": int(np.sum((xs > xm) & (ys <= ym))),
        "upper left": int(np.sum((xs <= xm) & (ys > ym))),
        "upper right": int(np.sum((xs > xm) & (ys > ym))),
    }
    return sorted(counts, key=counts.get)


def run_paired(df, args):
    x_column, x_value = _split_selector(args.x_from)
    y_column, y_value = _split_selector(args.y_from)
    align = args.x or "Values"
    metric = args.y or "Counts"
    error_column = args.error_column or f"{metric}Error"
    for column, value in ((x_column, x_value), (y_column, y_value)):
        if value == "None" and column in df.columns:
            df[column] = df[column].fillna("None")

    configs, names = prepare_import(args)
    configs = configs if configs is not None else [None]
    names = names if names is not None else [None]
    resolve_name = _label_resolver(args)

    units = []
    for config, name in zip(configs, names):
        base = filter_dataframe(_config_rows(df, config, name), args)
        if base.empty:
            rprint(f"[yellow]Warning:[/yellow] No data for {config=}, {name=}. Skipping.")
            continue
        if args.iterable is not None:
            if args.iterable not in base.columns:
                rprint(f"[red]Error:[/red] Hue column '{args.iterable}' not found.")
                continue
            hues = sorted(base[base[args.iterable].notna()][args.iterable].unique().tolist())
        else:
            hues = [None]
        reduce_active = len(hues) > 8 and args.reduce
        for jdx, hue in enumerate(hues):
            if reduce_active and jdx % 2 == 1:
                continue
            subset = base[base[args.iterable] == hue] if hue is not None else base
            xs = _triplet(subset[subset[x_column].astype(str) == x_value], align, metric, error_column)
            ys = _triplet(subset[subset[y_column].astype(str) == y_value], align, metric, error_column)
            if xs is None or ys is None:
                rprint(f"[yellow]Warning:[/yellow] Missing '{x_value}' or '{y_value}' for {config=}, {name=}, hue={hue}. Skipping.")
                continue
            if xs[0].size != ys[0].size or not np.allclose(xs[0], ys[0], equal_nan=True):
                rprint(f"[yellow]Warning:[/yellow] '{x_value}' and '{y_value}' bins are not aligned for {config=}, {name=}. Skipping.")
                continue
            units.append({"config": config, "name": name, "hue": hue, "x": xs, "y": ys})

    if not units:
        rprint("[yellow]Warning:[/yellow] No valid points available to plot.")
        return None

    fig, axes, _, _ = create_panels(1)
    ax = axes[0]
    groups = list(dict.fromkeys((u["config"], u["name"]) for u in units))
    dual = args.iterable is not None and len(groups) > 1
    if dual:
        group_colors = dict(zip(groups, _fill_colors([make_config_color_and_style_from_args(args, config=c, name=n) for c, n in groups])))
        all_hues = sorted({u["hue"] for u in units if u["hue"] is not None})
        markers = {value: MARKERS[i % len(MARKERS)] for i, value in enumerate(all_hues)}
    else:
        explicit = []
        for u in units:
            if u["hue"] is not None:
                explicit.append((map_iterable_color(u["hue"], args.iterable_color_mapping, args.iterable), None))
            else:
                explicit.append(make_config_color_and_style_from_args(args, config=u["config"], name=u["name"]))
        unit_colors = _fill_colors(explicit)

    aggregated, drawn_x, drawn_y = [], [], []
    combine = _weighted_mean if args.aggregate == "weighted_mean" else _plain_mean
    for i, u in enumerate(units):
        (bins, xv, xe), (_, yv, ye) = u["x"], u["y"]
        hue_label = _hue_label(u["hue"], args.iterable) if u["hue"] is not None else None
        label = make_config_label_from_args(args, config=u["config"], name=resolve_name(u["name"]), iterable=hue_label)
        if dual:
            color, marker, point_label = group_colors[(u["config"], u["name"])][0], markers[u["hue"]], None
        else:
            color, marker, point_label = unit_colors[i][0], "o", label
        if args.aggregate == "none":
            ax.errorbar(xv, yv, xerr=xe if np.isfinite(xe).any() else None, yerr=ye if np.isfinite(ye).any() else None,
                        marker=marker, linestyle="-" if args.connect else "None", color=color, label=point_label, capsize=2)
            drawn_x += xv.tolist()
            drawn_y += yv.tolist()
            if args.annotate_bins:
                for b, px, py in zip(bins, xv, yv):
                    ax.annotate(f"{b:g}", (px, py), textcoords="offset points", xytext=(4, 4), fontsize=style.linelabelfontsize)
        else:
            px, pxe = combine(xv, xe)
            py, pye = combine(yv, ye)
            ax.errorbar([px], [py], xerr=[pxe] if np.isfinite(pxe) else None, yerr=[pye] if np.isfinite(pye) else None,
                        marker=marker, ms=8, linestyle="None", color=color, label=point_label, capsize=3)
            if args.annotate:
                ax.annotate(label, (px, py), textcoords="offset points", xytext=(6, 6), fontsize=style.linelabelfontsize)
            aggregated.append(((u["config"], u["name"]), color, px, py))
            drawn_x.append(px)
            drawn_y.append(py)

    if args.connect and args.aggregate != "none" and len(aggregated) > 1:
        if dual:
            by_group = {}
            for key, color, px, py in aggregated:
                by_group.setdefault(key, (color, []))[1].append((px, py))
            for color, points in by_group.values():
                if len(points) > 1:
                    ax.plot(*zip(*points), color=color, linestyle="--", linewidth=1, alpha=0.6, zorder=0)
        else:
            ax.plot([p[2] for p in aggregated], [p[3] for p in aggregated], color=style.role("muted"), linestyle="--", linewidth=1, zorder=0)

    ax.set_xlabel(resolve_axis_label(args.labelx, x_value, None))
    ax.set_ylabel(resolve_axis_label(args.labely[0] if args.labely else None, y_value, None))
    if args.annotate or args.annotate_bins:
        ax.margins(x=0.25, y=0.15)
    elif dual:
        ax.margins(x=0.15, y=0.1)
    if args.rangex is not None:
        ax.set_xlim(args.rangex)
    if args.rangey is not None:
        ax.set_ylim(args.rangey)

    if args.no_legend or args.draw_legend == "none":
        pass
    elif dual:
        color_ncol = 2 if len(groups) > 6 else 1
        shape_ncol = 2 if len(all_hues) > 6 else 1
        ranked = _quadrants_by_density(ax, drawn_x, drawn_y)
        taller_shape = -(-len(all_hues) // shape_ncol) > -(-len(groups) // color_ncol)
        shape_loc, color_loc = (ranked[0], ranked[1]) if taller_shape else (ranked[1], ranked[0])
        color_handles = [
            mlines.Line2D([], [], marker="o", linestyle="None", color=group_colors[g][0],
                          label=make_config_label_from_args(args, config=g[0], name=resolve_name(g[1])))
            for g in groups
        ]
        legend = apply_legend_style(ax, handles=color_handles, labels=[h.get_label() for h in color_handles],
                                    title=args.labelz, capitalize_labels=args.capitalize_legend, loc=color_loc, ncol=color_ncol)
        ax.add_artist(legend)
        shape_handles = [
            mlines.Line2D([], [], marker=markers[v], linestyle="None", color=style.role("ink"), label=_hue_label(v, args.iterable))
            for v in all_hues
        ]
        apply_legend_style(ax, handles=shape_handles, labels=[h.get_label() for h in shape_handles],
                           title=args.iterable, capitalize_labels=False, loc=shape_loc, ncol=shape_ncol)
    else:
        apply_legend_style(ax, title=args.labelz if args.labelz is not None else args.iterable,
                           capitalize_labels=args.capitalize_legend)

    add_title_and_note(fig, args)
    return save(fig, args, None, suffix=f"{x_value}_vs_{y_value}_scatter.png")


# --- Points ------------------------------------------------------------------------------


def explode_points(df, markerby=None, columns=None, hue=None):
    """One row per point of list-valued cells (only ``columns`` when given:
    the other list columns, e.g. histograms stored next to the samples, are
    dropped). Without --markerby only the first row per Config/Name and
    --hue value is kept, so distinct groups (e.g. truth and reco points) are
    not merged into one undistinguished scatter."""
    list_columns = [c for c in df.columns if df[c].apply(lambda v: isinstance(v, (list, tuple, np.ndarray))).any()]
    if columns is not None:
        df = df.drop(columns=[c for c in list_columns if c not in columns])
        list_columns = [c for c in list_columns if c in columns]
    if not list_columns:
        return df
    if not markerby:
        # A per-point (list) hue colours points within a row; only a per-row hue tells rows apart.
        keys = [c for c in ("Config", "Name", hue) if c and c in df.columns and c not in list_columns]
        grouped = df.groupby(keys if keys else (lambda _: 0), sort=False, dropna=False)
        kept = grouped.head(1)
        if len(kept) < len(df):
            others = [c for c in df.columns if c not in keys and c not in list_columns]
            differing = [c for c in others if (grouped[c].nunique(dropna=False) > 1).any()]
            hint = (f"they differ in {', '.join(differing)}; pass --hue or --markerby with one of these"
                    if differing else "pass --markerby <column>")
            rprint(f"[yellow]Warning:[/yellow] --markerby not set: keeping the first row{' per ' + '/'.join(keys) if keys else ''} "
                   f"({len(df) - len(kept)} of {len(df)} rows dropped; {hint} to draw and distinguish all of them).")
        df = kept
    try:
        return df.explode(column=list_columns).reset_index(drop=True)
    except ValueError:
        rprint(f"[yellow]Warning:[/yellow] Could not explode list columns {list_columns} (mismatched lengths).")
        return df


def _sizes(rows, column, base, vmin, vmax, scale):
    if column is None or column not in rows.columns:
        return base
    values = rows[column].astype(float).to_numpy()
    vmin = values.min() if vmin is None else vmin
    vmax = values.max() if vmax is None else vmax
    if vmax == vmin:
        return base
    sizes = base / scale + (values - vmin) / (vmax - vmin) * (base * scale - base / scale)
    return np.where(np.isnan(sizes), base, sizes)  # NaN sizes break matplotlib's extent computation


def _proxy(ax, **kwargs):
    """Legend-only scatter handle (drawn on ``ax`` for its styling, then removed)."""
    handle = ax.scatter([], [], **kwargs)
    handle.remove()
    return handle


def _size_levels(vmin, vmax, n_levels):
    """(values, labels) of the --sizeby legend: round values inside
    [vmin, vmax] (as axis ticks pick them), as plain numbers."""
    if pd.isna(vmin) or pd.isna(vmax) or vmax == vmin:
        return np.full(1, vmin), [f"{vmin:g}"]
    levels = MaxNLocator(n_levels - 1, steps=[1, 2, 5, 10]).tick_values(vmin, vmax)
    levels = levels[(levels >= vmin) & (levels <= vmax)]
    if levels.size < 2:
        levels = np.array([vmin, vmax])
    step = float(np.min(np.diff(levels)))
    digits = max(0, -int(np.floor(np.log10(step)))) if step > 0 else 0
    while digits < 6 and not np.allclose(np.round(levels, digits), levels):
        digits += 1
    return levels, [f"{v:.{digits}f}" for v in levels]


def _add_size_legend(ax, label, vmin, vmax, base, scale, loc, n_levels=4):
    existing = ax.get_legend()
    levels, texts = _size_levels(vmin, vmax, n_levels)
    valid = not (pd.isna(vmin) or pd.isna(vmax)) and vmax != vmin
    sizes = base / scale + (levels - vmin) / (vmax - vmin) * (base * scale - base / scale) if valid else np.full(levels.size, base)
    handles = [_proxy(ax, s=s, color=style.role("muted"), alpha=0.85, linewidths=0) for s in sizes]
    legend = apply_legend_style(ax, title=label, handles=handles, labels=texts,
                                capitalize_labels=False, scatterpoints=1, loc=loc)
    if existing is not None:
        ax.add_artist(existing)
    return legend


def _marker_map(df, column):
    """value -> (marker, hollow): two values share a circle (first hollow),
    more values cycle through marker shapes."""
    if column is None or column not in df.columns:
        return None
    values = sorted(df[column].dropna().unique().tolist(), key=str)
    if not values:
        return None
    if len(values) == 2:
        return {values[0]: ("o", True), values[1]: ("o", False)}
    return {v: (POINT_MARKERS[i % len(POINT_MARKERS)], False) for i, v in enumerate(values)}


def _marker_groups(df, column, markers):
    """(value, rows, marker, hollow), filled groups first so hollow markers stay on top."""
    if markers is None:
        return [(None, df, "o", False)]
    out = []
    for value, (marker, hollow) in sorted(markers.items(), key=lambda item: item[1][1]):
        rows = df[df[column] == value]
        if not rows.empty:
            out.append((value, rows, marker, hollow))
    return out


def _add_marker_legend(ax, title, markers):
    existing = ax.get_legend()
    values = [v for v, _ in sorted(markers.items(), key=lambda item: item[1][1])]
    handles = []
    for value in values:
        marker, hollow = markers[value]
        if hollow:
            handles.append(_proxy(ax, s=60 * HOLLOW_AREA, marker=marker, facecolors="none", edgecolors=style.role("muted"), linewidths=1.5, alpha=0.85))
        else:
            handles.append(_proxy(ax, s=60, marker=marker, color=style.role("muted"), alpha=0.85, linewidths=0))
    labels = [map_iterable_label(v, title, None, len(values)) for v in values]
    legend = apply_legend_style(ax, title=title, handles=handles, labels=labels, capitalize_labels=False,
                                scatterpoints=1, loc="lower left")
    if existing is not None:
        ax.add_artist(existing)
    return legend


def _scatter(ax, x, y, color, size, marker="o", hollow=False):
    if hollow:
        ax.scatter(x, y, s=np.asarray(size) * HOLLOW_AREA, marker=marker, alpha=0.85, zorder=3,
                   facecolors="none", edgecolors=color, linewidths=1.5)
    else:
        ax.scatter(x, y, c=color, s=size, marker=marker, alpha=0.85, zorder=3, linewidths=0)


def draw_points(rows, args, kdx):
    y_columns = [args.y] + ([args.z] if args.z else [])
    fig, axes, _, _ = create_panels(len(y_columns), grid=False)
    markers = _marker_map(rows, args.markerby)

    size_ranges = None
    size_range = (None, None)
    if args.sizeby and args.sizeby in rows.columns:
        if markers is not None:
            size_ranges = {}
            for value, group, _, _ in _marker_groups(rows, args.markerby, markers):
                values = group[args.sizeby].astype(float)
                size_ranges[value] = (values.min(), values.max())
        else:
            values = rows[args.sizeby].astype(float)
            size_range = (values.min(), values.max())

    def size_range_of(value):
        return size_ranges.get(value, (None, None)) if size_ranges is not None else size_range

    def draw_group(group, color, value, marker, hollow):
        vmin, vmax = size_range_of(value)
        sizes = _sizes(group, args.sizeby, args.marker_size, vmin, vmax, args.sizeby_scale)
        for ax, column in zip(axes, y_columns):
            _scatter(ax, group[args.x].to_numpy(), group[column].to_numpy(), color, sizes, marker, hollow)

    if args.colorby is not None and args.colorby in rows.columns:
        all_values = rows[args.colorby].astype(float).to_numpy()
        norm = LogNorm(vmin=all_values[all_values > 0].min(), vmax=all_values.max()) if args.logz else None
        last = None
        for value, group, marker, hollow in _marker_groups(rows, args.markerby, markers):
            colors = group[args.colorby].astype(float).to_numpy()
            vmin, vmax = size_range_of(value)
            sizes = _sizes(group, args.sizeby, args.marker_size, vmin, vmax, args.sizeby_scale)
            if hollow:
                sizes = np.asarray(sizes) * HOLLOW_AREA
            drawn = []
            for ax, column in zip(axes, y_columns):
                last = ax.scatter(group[args.x].to_numpy(), group[column].to_numpy(), c=colors, s=sizes, norm=norm,
                                  marker=marker, alpha=0.85, linewidths=1.5 if hollow else 0)
                drawn.append(last)
            if hollow:  # keep the colour-mapped edges, drop the fill
                for collection in drawn:
                    collection.set_edgecolor(collection.get_facecolors())
                    collection.set_facecolor("none")
        add_colorbar(fig, last, axes, args.labelz if args.labelz is not None else args.colorby)
    elif args.iterable is not None and args.iterable in rows.columns:
        rows = rows.dropna(subset=[args.iterable])
        # Sorted, so the same value set always gets the same colours.
        values = sorted(rows[args.iterable].unique().tolist(), key=str)
        colors = ColorAllocator()
        colors.reserve(values, lambda hue: map_iterable_color(hue, args.iterable_color_mapping, args.iterable))
        handles, labels = [], []
        for hue in values:
            group = rows[rows[args.iterable] == hue]
            color = colors.color_for(hue)
            handles.append(_proxy(axes[0], marker="o", color=color, s=60, alpha=0.85, linewidths=0))
            labels.append(map_iterable_label(hue, args.iterable, args.iterable_mapping, len(values)))
            for value, marker_group, marker, hollow in _marker_groups(group, args.markerby, markers):
                draw_group(marker_group, color, value, marker, hollow)
        if not args.no_legend:
            apply_legend_style(axes[0], title=args.labelz if args.labelz is not None else args.iterable,
                               handles=handles, labels=labels, capitalize_labels=args.capitalize_legend, loc="upper left")
    else:
        for value, group, marker, hollow in _marker_groups(rows, args.markerby, markers):
            draw_group(group, "C0", value, marker, hollow)

    if args.sizeby:
        label = args.labelsize or args.sizeby
        if size_ranges is not None:
            locations = ["upper right", "lower right"]
            for gdx, (vmin, vmax) in enumerate(size_ranges.values()):
                if pd.isna(vmin) or pd.isna(vmax) or vmin == vmax:
                    continue
                _add_size_legend(axes[-1], label, vmin, vmax, args.marker_size, args.sizeby_scale, locations[gdx % 2])
        elif size_range[0] is not None and not pd.isna(size_range[0]) and not pd.isna(size_range[1]) and size_range[0] != size_range[1]:
            _add_size_legend(axes[-1], label, *size_range, args.marker_size, args.sizeby_scale, args.size_legend_loc)
    if markers is not None:
        _add_marker_legend(axes[0], args.markerby, markers)

    xlabel = resolve_axis_label(args.labelx, args.x, rows)
    for i, (ax, column) in enumerate(zip(axes, y_columns)):
        if args.labely is None:
            ylabel = resolve_axis_label(None, column, rows)
        else:
            ylabel = args.labely[min(i, len(args.labely) - 1)]
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        if args.rangex is not None:
            ax.set_xlim(args.rangex)
    if args.rangey is not None:
        axes[0].set_ylim(args.rangey)

    if args.title is None and "Title" in rows.columns and not rows["Title"].isna().all():
        add_centered_suptitle(fig, str(rows["Title"].dropna().iloc[0]), fontsize=style.titlefontsize)
        apply_note_to_figure(fig, args.note)
    else:
        add_title_and_note(fig, args)
    return save(fig, args, kdx, suffix="scatter.png")


def run_points(df, args):
    if args.x is None or args.y is None:
        rprint("[red]Error:[/red] -x and -y are required without --x_from/--y_from.")
        return []
    # The selected rows first, then only the columns drawn become points.
    df = filter_dataframe(df, args)
    used = [c for c in (args.x, args.y, args.z, args.colorby, args.sizeby, args.iterable, args.markerby) if c]
    df = explode_points(df, markerby=args.markerby, columns=used, hue=args.iterable)
    for column in [args.x, args.y] + ([args.z] if args.z else []):
        if column not in df.columns:
            rprint(f"[red]Error:[/red] Column '{column}' not found. Available: {list(df.columns)}")
            return []
    df = filter_dataframe(df, args)
    if df.empty:
        rprint("[yellow]Warning:[/yellow] No data after filtering. Exiting.")
        return []
    configs, names = prepare_import(args)
    pairs = list(zip(configs, names)) if configs is not None else [(None, None)]
    outputs = []
    for kdx, (config, name) in enumerate(pairs):
        rows = _config_rows(df, config, name)
        if rows.empty:
            rprint(f"[yellow]Warning:[/yellow] No data for Config={config}, Name={name}. Skipping.")
            continue
        outputs.append(draw_points(rows, args, kdx))
    return outputs


def run(args):
    df = import_data(args)
    if df.empty:
        rprint("[yellow]Warning:[/yellow] No data loaded. Exiting.")
        return []
    if args.x_from or args.y_from:
        if not (args.x_from and args.y_from):
            rprint("[red]Error:[/red] --x_from and --y_from go together.")
            return []
        return [run_paired(df, args)]
    return run_points(df, args)


# --- Legacy command lines ----------------------------------------------------------------


def _legacy_pareto(tokens):
    from ..legacy import has, option_values

    variables = option_values(tokens, "--variables") or option_values(tokens, "-v") or []
    if len(variables) != 2:
        raise ValueError("script_compare_pareto needs exactly two --variables")
    if not has(tokens, "-x"):
        tokens += ["-x", "Values"]
    if not has(tokens, "-y"):
        tokens += ["-y", "Counts"]
    if not has(tokens, "--error_column"):
        tokens += ["--error_column", "CountsError"]
    return tokens + ["--x_from", f"Variable={variables[0]}", "--y_from", f"Variable={variables[1]}",
                     "--output_suffix", f"{variables[0]}_vs_{variables[1]}_pareto.png"]


def _legacy_event_display(tokens):
    from ..legacy import has

    for flag, default in (("-x", "X"), ("-y", "Y"), ("-z", "Z")):
        if not has(tokens, flag):
            tokens += [flag, default]
    return tokens + ["--output_suffix", "event_display.png"]


LEGACY = {"script_compare_pareto": _legacy_pareto, "script_event_display": _legacy_event_display}
