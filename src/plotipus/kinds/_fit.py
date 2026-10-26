"""Fit layer of the line kind (``--fit``).

Rows describe a fitted series: ``x``/``y`` arrays plus the model,
``FitFunction`` (a callable) or ``FitFunctionLabel`` (a name resolved by
:func:`plotipus.fits.get_function`), its ``Params``, ``ParamsError``,
``ParamsLabel`` and optionally ``ParamsUnit``, ``ParamsFormat``,
``FitFunctionFormula``, ``Chi2`` and ``FitComponents`` ({label: [model,
[parameter indices]]}, each drawn dashed). No fitting happens here: the stored
model is evaluated, drawn over the data with a parameter box, and each
``--lower`` entry adds a panel: ``residual`` (data - fit) / fit, or ``pull``
(data - fit) / error with the stored ``{y}Error``.
"""

import matplotlib.lines as mlines
import numpy as np
import pandas as pd
from rich import print as rprint

from .. import style
from ..args import resolve_axis_label
from ..fits import get_function
from ..format import _format_value_with_paren_error
from ..lower import MODEL_OPERATIONS, model_series, parse_lower
from ..palettes import current_colors
from ..panels import add_title_and_note, create_panels, save
from ..plot import (apply_legend_pair_clear_of_data, apply_legend_style, apply_legend_style_clear_of_data,
                    draw_horizontal_lines, draw_vertical_lines, format_ref_value, plot_data)
from ..selection import filter_dataframe
from ..transforms import edges_from_centers

# Labels of models stored by name only.
FUNCTION_BY_LABEL = {"Gaussian": "gaussian", "Double Gaussian": "double_gaussian"}


def add_fit_args(parser):
    group = parser.add_argument_group("fit (--fit)")
    add = group.add_argument
    add("--fit", action="store_true", default=False,
        help="Draw the stored fit of each row (FitFunction/FitFunctionLabel, Params) over the data, "
        "with its parameters; each --lower adds a panel: residual (data - fit)/fit or pull (data - fit)/error.")
    add("--chi2", action="store_true", default=False,
        help="Show chi2/ndof (stored Chi2 column, or Pearson chi2 for -y Counts).")
    add("--show_formula", action="store_true", default=False, help="Show FitFunctionFormula in the legend.")
    add("--line_labels", action="store_true", default=False,
        help="Label --vertical/--horizontal lines with their values when no label is given.")
    add("--fit_errors", action="store_true", default=True, help="Show parameter errors (default).")
    add("--no-fit_errors", dest="fit_errors", action="store_false", help="Hide parameter errors.")
    add("--fit_type_subtitle", action="store_true", default=True, help="Panel title '<model> Fit' (default).")
    add("--no-fit_type_subtitle", dest="fit_type_subtitle", action="store_false", help="No model subtitle.")
    add("--fit_color", type=str, default=None,
        help="Colour of the fit line (default: the style's ink role; 'red' restores the old look).")
    add("--fitindex", type=int, default=0, help="Index of the hue value whose fit is drawn.")
    add("--fit_rangex", nargs=2, type=float, default=None, help="x range of the drawn fit and residuals.")
    add("--max_fit_params", type=int, default=None, help="Show at most this many parameters.")
    add("--fitlegendposition", nargs=2, type=float, default=None,
        help="Axes position (x y) of the parameter box (default: a second legend placed clear of the data).")
    add("--errorx", action="store_true", default=False, help="Draw x error bars.")


def resolve_function(rows):
    """Model callable of the first row (FitFunction or FitFunctionLabel)."""
    if "FitFunction" in rows.columns:
        value = rows["FitFunction"].iloc[0]
        function = value if callable(value) else get_function(value)
        if function is not None:
            return function
    label = rows["FitFunctionLabel"].iloc[0] if "FitFunctionLabel" in rows.columns else None
    function = get_function(FUNCTION_BY_LABEL.get(label, label))
    if function is None:
        raise ValueError(f"No FitFunction column and no known function for FitFunctionLabel={label!r}.")
    return function


def _units(units, n):
    if units is None or (isinstance(units, float) and np.isnan(units)):
        units = [""] * n
    elif isinstance(units, str):
        units = [units] * n
    elif isinstance(units, (list, tuple, np.ndarray, pd.Series)):
        units = list(units)
    else:
        units = [str(units)] * n
    return (units + [""] * n)[:n]


def lower_model_series(spec, series, args, label):
    """Residual/pull series of the drawn series against their stored model."""
    from .line import _lower_series

    out = []
    for i, s in enumerate(series):
        if s.rows is None or s.categorical or "Params" not in s.rows.columns:
            continue
        try:
            function = resolve_function(s.rows)
        except ValueError as error:
            rprint(f"[yellow]Warning:[/yellow] {error}")
            continue
        model = function(np.asarray(s.x, dtype=float), *s.rows["Params"].iloc[0])
        error = s.error if s.error is not None and np.ndim(s.error) == 1 else None
        values = model_series(s.y, model, error, spec.name)
        out.append(_lower_series(s.x, values, None, s.color, s.linestyle, label if not out else None, s.linewidth))
    return out


def _data_style(args):
    plot_type = args.plot_type if args.plot_type is not None else ("errorbar" if args.errory else "plot")
    if plot_type == "step":
        return "plot", {"drawstyle": "steps-mid"}
    if plot_type == "plot":
        return "plot", {"marker": "o", "linestyle": "None"}
    return plot_type, {}


def _parameter_lines(args, rows, params, chi2, n_points):
    """Text lines of the parameter box: (text, italic) pairs."""
    labels = rows["ParamsLabel"].iloc[0]
    errors = rows["ParamsError"].iloc[0]
    formats = rows["ParamsFormat"].iloc[0] if "ParamsFormat" in rows.columns else [".4g"] * len(params)
    units = _units(rows["ParamsUnit"].iloc[0] if "ParamsUnit" in rows.columns else None, len(params))
    shown = len(params) if args.max_fit_params is None else min(args.max_fit_params, len(params))
    lines = []
    for row, (label, fmt, value, error, unit) in enumerate(zip(labels, formats, params, errors, units)):
        if row >= shown:
            break
        unit = str(unit).strip()
        if unit in {"%", "\\%"}:
            value, error = value * 100, error * 100
        suffix = f" {unit}" if unit else ""
        if args.fit_errors:
            lines.append((f"{label} = {_format_value_with_paren_error(fmt, value, error)}{suffix}", False))
        else:
            lines.append((r"{0} = {1:{2}}{3}".format(label, value, fmt, suffix), False))
    if shown < len(params):
        lines.append((f"+ {len(params) - shown} more", True))

    if args.chi2 and chi2 is None:
        rprint("[yellow]Warning:[/yellow] Skipping chi2/ndof: the Pearson chi2 assumes raw counts; "
               f"use -y Counts or store a Chi2 column (y is '{args.y}').")
    elif args.chi2:
        ndof = max(n_points - len(params), 0)
        reduced = chi2 / ndof if ndof > 0 else float("nan")
        lines.append((r"$\chi^2$/ndof = {0:0.2f}".format(reduced), False))
    return lines


def _parameter_box(ax, args, lines):
    """The parameters as a text box at --fitlegendposition (axes coordinates)."""
    x0, y0 = args.fitlegendposition
    font = {"size": style.legendfontsize}
    ax.text(x0, y0, "Fit Parameters:", fontdict={**font, "weight": "bold"}, transform=ax.transAxes)
    for row, (text, italic) in enumerate(lines):
        ax.text(x0, y0 - 0.08 - 0.06 * row, text, fontdict={**font, "style": "italic"} if italic else font,
                transform=ax.transAxes)


def _parameter_legend_kwargs(lines):
    """Legend arguments showing the parameter lines without handles."""
    handles = [mlines.Line2D([], [], linestyle="none") for _ in lines]
    return dict(handles=handles, labels=[text for text, _ in lines], title="Fit parameters", handlelength=0,
                handletextpad=0)


def _draw_fit_rows(ax_top, lowers, rows, args, kind):
    """Data, fit curve, lower panels ((spec, axes) pairs) and parameters of one hue value; returns
    (lower-panel limits, function label, formula, parameter lines)."""
    label_value = rows[args.iterable].iloc[0] if args.iterable is not None else "Data"
    function_label = rows["FitFunctionLabel"].iloc[0] if "FitFunctionLabel" in rows.columns else None
    formula = rows["FitFunctionFormula"].iloc[0] if "FitFunctionFormula" in rows.columns else None
    x = rows[args.x].values[0].astype(float)
    y = rows[args.y].values[0].astype(float)
    params = rows["Params"].iloc[0]
    function = resolve_function(rows)
    fit = function(x, *params)

    plot_type, style_kwargs = _data_style(args)
    error = rows[f"{args.y}Error"].values[0] if args.errory else None
    is_data = bool(args.data_hue) and str(label_value) in {str(v) for v in args.data_hue}
    if is_data:
        # As with --data_hue in plain line plots: ink points with their error bars, above the fit.
        stored = rows[f"{args.y}Error"].values[0] if f"{args.y}Error" in rows.columns else None
        xerr = None
        if args.errory_x and len(x) > 1:
            xerr = np.diff(edges_from_centers(x)) / 2
        plot_data(args, ax_top, x, y=y, plot_type="errorbar", yerr=stored, xerr=xerr, fmt="o", zorder=3,
                  label=label_value, color=style.role("ink"))
    else:
        plot_data(args, ax_top, x, y=y, errory=error, label=label_value, plot_type=plot_type, **style_kwargs)
    if not kind["draw_fit"]:
        return None, function_label, formula, None

    lo, hi = args.fit_rangex if args.fit_rangex is not None else (np.min(x), np.max(x))
    fit_x = np.linspace(lo, hi, 1000)
    palette = current_colors()
    fit_color = args.fit_color or (palette[0] if is_data else style.role("ink"))
    plot_data(args, ax_top, fit_x, y=function(fit_x, *params), label="Fit", color=fit_color, plot_type="plot", linestyle="-")
    components = rows["FitComponents"].iloc[0] if "FitComponents" in rows.columns else None
    if not isinstance(components, dict):
        components = {}  # NaN in rows without components
    for cdx, (name, (model, indices)) in enumerate(components.items()):
        component = get_function(model)
        if component is None:
            rprint(f"[yellow]Warning:[/yellow] Unknown model {model!r} of fit component {name!r}; skipping it.")
            continue
        color = palette[(cdx + 1) % len(palette)] if is_data else palette[cdx % len(palette)]
        plot_data(args, ax_top, fit_x, y=component(fit_x, *[params[i] for i in indices]), label=name,
                  color=color, plot_type="plot", linestyle="--")

    diff = y - fit
    mask = np.isfinite(fit) & (fit != 0) & np.isfinite(diff)
    if args.fit_rangex is not None:
        mask &= (x >= lo) & (x <= hi)
    limits = []
    for spec, ax_bottom in lowers:
        values, errors = _lower_values(spec, x, y, fit, error, rows, args, mask)
        limit = _lower_limit(spec, values, len(params))
        limits.append(limit)
        if values is None:
            continue
        plot_data(args, ax_bottom, x, y=values, errory=errors if args.errory else None,
                  color=style.role("ink"), plot_type=plot_type, **style_kwargs)
        ax_bottom.set_ylim(-limit, limit)

    if "Chi2" in rows.columns and pd.notna(rows["Chi2"].iloc[0]):
        chi2 = float(rows["Chi2"].iloc[0])
    elif args.y == "Counts":
        chi2 = (diff[mask] ** 2 / fit[mask]).sum() if fit[mask].size > 0 else 0
    else:
        chi2 = None
    lines = _parameter_lines(args, rows, params, chi2, int(mask.sum()))
    if args.fitlegendposition is not None:
        _parameter_box(ax_top, args, lines)
    return limits, function_label, formula, lines


def _lower_specs(args):
    """One lower panel per --lower entry: residual or pull (anything else, as
    before, is drawn as a residual)."""
    specs = []
    for text in args.lower or []:
        spec = parse_lower(text)
        if spec.name not in MODEL_OPERATIONS:
            rprint(f"[yellow]Warning:[/yellow] --lower {text} is not available with --fit; drawing the residual.")
            spec = parse_lower("residual")
        specs.append(spec)
    return specs


def _lower_values(spec, x, y, fit, error, rows, args, mask):
    """(values, errors) of one lower panel, NaN outside *mask*; values None
    when a pull has no errors to divide by."""
    if spec.name == "pull":
        error_column = f"{args.y}Error"
        if error_column not in rows.columns:
            rprint(f"[yellow]Warning:[/yellow] --lower pull needs the {error_column} column; the pull panel is empty.")
            return None, None
        sigma = np.asarray(rows[error_column].values[0], dtype=float)
        values = model_series(y, fit, sigma, "pull")
        values[~(mask & (sigma > 0))] = np.nan
        return values, np.where(np.isfinite(values), 1.0, np.nan)
    # Where the fit is ~0 (the tails of a peak) the relative residual diverges.
    small = np.abs(fit) < 1e-3 * np.nanmax(np.abs(fit[mask])) if mask.any() else np.zeros_like(mask)
    values = model_series(y, fit, None, "residual")
    values[~mask | small] = np.nan
    errors = None
    if error is not None:
        with np.errstate(divide="ignore", invalid="ignore"):
            errors = np.where(np.isfinite(values), np.asarray(error, dtype=float) / fit, np.nan)
    return values, errors


def _lower_limit(spec, values, n_params):
    """Symmetric y range of one lower panel."""
    finite = values[np.isfinite(values)] if values is not None else np.array([])
    if spec.name == "pull":
        return max(3.0, 1.2 * float(np.max(np.abs(finite)))) if finite.size else 3.0
    if not finite.size:
        return 1
    low, high = np.percentile(finite, [5, 95])
    limit = max(abs(low), abs(high)) * 2
    if limit == 0 or not np.isfinite(limit):
        limit = 1e-3
    if limit > 1e3:
        limit = n_params
    return limit


def _lower_label(spec):
    """(y label, formula subtitle) of a lower panel. The formula goes inside
    the panel: as the y label it is taller than a lower panel."""
    if spec.name == "pull":
        return "Pull", "(Data − Fit) / σ"
    return "Residual", "(Data − Fit) / Fit"


def _lower_subtitle(ax, text):
    ax.text(0.01, 0.97, text, transform=ax.transAxes, ha="left", va="top", fontsize="medium",
            color=style.role("muted"))


def _pull_bands(ax):
    """Light bands at +-1 and +-2 sigma; where they overlap (within 1 sigma) they read darker."""
    for width in (2, 1):
        ax.axhspan(-width, width, color=style.role("faint"), alpha=0.7, linewidth=0, zorder=-2)


def _residual_reference(ax, args):
    color = getattr(args, "lower_zero_color", None) or style.role("muted")
    if args.fit_rangex is None:
        ax.axhline(y=0, color=color, linestyle="--", zorder=-1)
        return
    lo, hi = args.fit_rangex
    xmin, xmax = ax.get_xlim()
    if xmin < lo:
        ax.plot([xmin, lo], [0, 0], color=color, linestyle="--", zorder=-1)
    ax.plot([max(xmin, lo), min(xmax, hi)], [0, 0], color=color, linestyle="-", zorder=-1)
    if xmax > hi:
        ax.plot([hi, xmax], [0, 0], color=color, linestyle="--", zorder=-1)
    ax.set_xlim(xmin, xmax)


def _show_formula(fig, ax, legend, formula):
    if not formula:
        rprint("[yellow]Warning:[/yellow] --show_formula was set but no FitFunctionFormula column was found.")
        return
    text = str(formula)
    fit_text = next((t for t in legend.get_texts() if t.get_text().strip() == "Fit"), None)
    if fit_text is not None and len(text) <= 20:
        fit_text.set_text(f"Fit: {text}")
        return
    fig.canvas.draw()
    box = legend.get_window_extent(renderer=fig.canvas.get_renderer())
    x1, y0 = ax.transAxes.inverted().transform((box.x1, box.y0))
    ax.text(x1, y0 - 0.015, text, fontdict={"size": style.legendfontsize}, transform=ax.transAxes,
            ha="right", va="top", wrap=True)


def run_fit(df, args):
    """One figure per --configs/--names pair: data of each hue value, the
    fit of the --fitindex-th one, its parameters and residuals."""
    from ..io import prepare_import

    if args.variables is not None and args.iterable is not None:
        rprint("Both variables and iterable arguments provided. Please provide only one of them.")
        return []
    configs, names = prepare_import(args)
    configs = configs if configs is not None else [None]
    names = names if names is not None else [None]
    specs = _lower_specs(args) if not args.no_lower_plot else []
    outputs = []
    for kdx, (config, name) in enumerate(zip(configs, names)):
        fig, upper, lowers, _ = create_panels(1, n_lower=len(specs))
        ax_top, ax_bottoms = upper[0], lowers[0]
        if ax_bottoms:
            ax_top.xaxis.get_offset_text().set_visible(False)
        mask = pd.Series(True, index=df.index)
        if "Config" in df.columns:
            mask &= df["Config"] == config
        if "Name" in df.columns:
            mask &= df["Name"] == name
        group = df[mask]
        hues = group[args.iterable].unique() if args.iterable is not None else [None]
        limits, function_label, formula, subset, parameter_lines = None, None, None, group, None
        for jdx, hue in enumerate(hues):
            if args.reduce and args.iterable is not None and len(hues) > 8 and jdx % 2 == 1:
                continue
            rows = group if hue is None else group[group[args.iterable] == hue]
            rows = filter_dataframe(rows, args)
            if rows.empty:
                continue
            subset = rows
            result = _draw_fit_rows(ax_top, list(zip(specs, ax_bottoms)), rows, args, {"draw_fit": jdx == args.fitindex})
            function_label, formula = result[1], result[2]
            if result[3] is not None:
                parameter_lines = result[3]
            if result[0] is not None:
                limits = result[0]

        if function_label is None:
            rprint("[yellow]Warning:[/yellow] No valid fit entries available to plot.")
            import matplotlib.pyplot as plt

            plt.close(fig)
            continue

        ax_top.set_ylabel(resolve_axis_label(args.labely, args.y, subset), fontsize=style.ysublabelfontsize)
        if args.rangex is not None:
            ax_top.set_xlim(args.rangex)
        if args.rangey is not None:
            ax_top.set_ylim(args.rangey)
        if args.logy:
            ax_top.set_yscale("log")
        if args.logx:
            ax_top.set_xscale("log")
        if args.fit_type_subtitle:
            ax_top.set_title(f"{function_label} Fit", fontsize=style.subtitlefontsize)

        handles, labels = ax_top.get_legend_handles_labels()
        fits = [i for i, label in enumerate(labels) if str(label).strip() == "Fit"]
        if args.data_hue:
            # Data, the fit, then its components.
            data = {str(v) for v in args.data_hue}
            order = sorted(range(len(labels)), key=lambda i: (str(labels[i]) not in data, i not in fits))
            handles, labels = [handles[i] for i in order], [labels[i] for i in order]
        elif fits:
            handles.append(handles.pop(fits[0]))
            labels.append(labels.pop(fits[0]))
        legend = None
        parameters = parameter_lines if args.fitlegendposition is None else None
        if not args.no_legend and parameters:
            # The parameters as a second legend, both placed clear of the data and of each other.
            legend, _ = apply_legend_pair_clear_of_data(
                ax_top, dict(title=args.labelz, handles=handles, labels=labels, capitalize_labels=args.capitalize_legend),
                _parameter_legend_kwargs(parameters))
        elif not args.no_legend:
            legend = apply_legend_style(ax_top, title=args.labelz, handles=handles, labels=labels,
                                        capitalize_labels=args.capitalize_legend)
        elif parameters:
            apply_legend_style_clear_of_data(ax_top, **_parameter_legend_kwargs(parameters))
        if args.show_formula and legend is not None:
            _show_formula(fig, ax_top, legend, formula)

        xlabel = resolve_axis_label(_first(args.labelx), args.x, subset)
        for spec, ax_bottom, limit in zip(specs, ax_bottoms, limits or [None] * len(specs)):
            if args.rangex is not None:
                ax_bottom.set_xlim(args.rangex)
            _residual_reference(ax_bottom, args)
            if args.logx:
                ax_bottom.set_xscale("log")
            if spec.name == "pull":
                _pull_bands(ax_bottom)
            if limit is not None:
                ax_bottom.set_ylim(-limit, limit)
            label, subtitle = _lower_label(spec)
            if args.lower_labely is not None:
                label = args.lower_labely
            else:
                _lower_subtitle(ax_bottom, subtitle)
            ax_bottom.set_ylabel(label, fontsize=style.ysublabelfontsize)
        (ax_bottoms[-1] if ax_bottoms else ax_top).set_xlabel(xlabel)

        vertical, horizontal = args.vertical, args.horizontal
        vertical_labels = args.vertical_label
        if vertical_labels is None:
            vertical_labels = [format_ref_value(v) for v in vertical] if args.line_labels and vertical else []
        horizontal_labels = args.horizontal_label
        if horizontal_labels is None:
            horizontal_labels = [format_ref_value(v) for v in horizontal] if args.line_labels and horizontal else []
        draw_vertical_lines(ax_top, vertical, labels=vertical_labels, styles=args.vertical_style,
                            colors=args.vertical_color, fontsize=style.linelabelfontsize)
        for ax_bottom in ax_bottoms:
            draw_vertical_lines(ax_bottom, vertical, labels=[], fontsize=style.linelabelfontsize)
        draw_horizontal_lines(ax_top, horizontal, labels=horizontal_labels, styles=args.horizontal_style,
                              colors=args.horizontal_color, fontsize=style.linelabelfontsize)
        from ..panels import draw_overlays

        args_points = _PointsOnly(args)
        draw_overlays(ax_top, args_points)
        add_title_and_note(fig, args)
        outputs.append(save(fig, args, kdx, suffix="fit.png"))
    return outputs


def _first(value):
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


class _PointsOnly:
    """View of the arguments exposing only the --point overlay."""

    def __init__(self, args):
        self.point = getattr(args, "point", None)
        self.point_label = getattr(args, "point_label", None)

    def __getattr__(self, name):
        return None
