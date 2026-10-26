"""Titles, subtitles and number formatting (value ± error) for plots and tables."""

import re

import numpy as np
import pandas as pd

from . import registry, style
from .io import normalize_datafiles


def get_simple_title_from_script(args=None):
    """Default title: the --datafile name(s) in title case (underscores read
    as spaces), or the plot kind when there is no datafile."""
    if args is not None and getattr(args, "datafile", None):
        title_source = "_".join(normalize_datafiles(args.datafile))
    else:
        title_source = getattr(args, "kind", None) or "plot"

    title = " ".join(word.capitalize() for word in title_source.replace("_", " ").split())
    title = title.replace("Hist1d", "Histogram 1D").replace("Hist2d", "Histogram 2D")
    return title or "Plot"


def make_title_from_args(args):
    """--title when given (an empty string suppresses the title), else the
    default title from the datafile names (unless the style turns
    ``plot_settings.auto_title`` off)."""
    if getattr(args, "title", None) is not None:
        if args.title and not style.draw_titles and not getattr(args, "keep_title", False):
            from rich import print as rprint

            rprint(f"[dim]Note:[/dim] title '{args.title}' dropped in this medium (the caption is the title); "
                   "--keep_title keeps it.")
            return ""
        return args.title
    if not style.auto_title:
        return ""
    return get_simple_title_from_script(args)


def _title_case_words(text):
    """Capitalise the first letter of each plain word ("X only" -> "X Only");
    words starting with a symbol or math are left alone."""
    if not isinstance(text, str):
        return text
    return " ".join(w[:1].upper() + w[1:] if w[:1].isalpha() else w for w in text.split(" "))


def _panel_label(key, value):
    """Panel subtitle for one iterable value: booleans read as "{key}" /
    "Not {key}", numbers keep their key ("Energy: 10"), and named values
    stand alone ("Reference", not "Study: Reference")."""
    text = str(value).strip()
    if text.lower() in {"true", "false"}:
        return str(key) if text.lower() == "true" else f"Not {key}"
    try:
        float(text)
    except ValueError:
        return _title_case_words(text)
    return f"{key}: {text}"


def make_subtitle_from_args(args, iterables, plot_type="hist1d", idx=None):
    subtitle_parts = []

    if hasattr(args, "subtitle") and args.subtitle:
        subtitle_parts.append(args.subtitle)
    else:
        if plot_type == "hist2d":
            if hasattr(args, "iterable") and args.iterable:
                subtitle_parts.append(_panel_label(args.iterable, iterables[idx]))

        else:
            if hasattr(args, "variables") and args.variables:
                if idx is not None and 0 <= idx < len(args.variables):
                    subtitle_parts.append(_title_case_words(args.variables[idx]))
                else:
                    subtitle_parts.append("_".join(args.variables))

            if hasattr(args, "iterable") and args.iterable:
                if (hasattr(args, "select") and args.select is not None) and (
                    hasattr(args, "save_values") and args.save_values is not None
                ):
                    select_save_parts = []
                    for sel, val in zip(args.select, args.save_values):
                        if sel and val:  # Check if both sel and val have content
                            select_save_parts.append(f"{sel}: {val}")
                    if select_save_parts:  # Only add if select_save_parts is not empty
                        subtitle_parts.append(", ".join(select_save_parts))
                elif hasattr(args, "iterable") and args.iterable:
                    subtitle_parts.append(f"{args.iterable}")

    return " - ".join(subtitle_parts)


def _wants_scientific(value, args):
    """
    Decide whether `value` should be rendered in scientific notation:
    always when --scientific is set, or automatically when its magnitude
    falls outside the [--scientific_threshold_low, --scientific_threshold_high]
    window (either bound may be None/unset).
    """
    if args is None:
        return False

    if getattr(args, "scientific", False):
        return True

    abs_value = abs(value)

    low = getattr(args, "scientific_threshold_low", None)
    if low is not None and abs_value < low:
        return True

    high = getattr(args, "scientific_threshold_high", None)
    if high is not None and abs_value > high:
        return True

    return False


def _resolve_decimal_places(error):
    """Number of decimal places (plain notation) needed to show `error` to
    1 significant figure, or 2 if its leading digit is 1 (PDG rounding rule).
    Can be negative for errors coarser than the ones place (e.g. an error of
    ~20000 resolves to -3, i.e. round to the nearest thousand).
    Returns None if the error can't be used to resolve a precision.
    """
    if error is None or not np.isfinite(error) or error <= 0:
        return None

    exponent = int(np.floor(np.log10(abs(error))))
    leading_digit = int(abs(error) / 10**exponent + 1e-9)
    sig_figs = 2 if leading_digit == 1 else 1
    return sig_figs - 1 - exponent


def _too_many_digits(error_digits, max_digits=3):
    """True if the parenthetical error digits have grown past what 1-2
    significant figures should ever produce (allowing a little rounding
    slack, e.g. 9.6 -> "10"). A large digit count means the error's own
    magnitude is wildly different from the value's, usually an unconstrained
    or degenerate fit parameter, where the parenthetical notation breaks down.
    """
    return len(str(abs(error_digits))) > max_digits


def _format_value_with_paren_error(base_format, value, error):
    """Format `value +/- error` in compact parenthetical notation (e.g.
    "1.35(6)e-08" instead of "1.35e-08 +/- 6e-09"), the standard convention
    used in PDG/CODATA tables: the digits in parentheses are the error rounded
    to the value's last significant decimal place, in units of that place.
    Falls back to a plain formatted value if the error can't resolve a precision.
    """
    decimals = _resolve_decimal_places(error)
    if decimals is None:
        return format(value, base_format)
    if value != 0 and np.isfinite(value) and abs(error) < 1e-6 * abs(value):
        # An error far below the value's own precision (e.g. a parameter left
        # unconstrained by a degenerate fit, whose covariance collapses to ~0)
        # would print a dozen spurious decimals; show the plain value instead.
        return format(value, base_format)

    match = re.match(r"^\.?\d*([a-zA-Z%])$", base_format)
    type_char = match.group(1) if match else "f"
    if type_char in "gG":
        # The precision of "g" counts significant figures, not decimals:
        # resolve it to plain or scientific notation as format() would.
        exponent = int(np.floor(np.log10(abs(value)))) if value != 0 and np.isfinite(value) else 0
        type_char = "f" if -4 <= exponent < 6 else ("e" if type_char == "g" else "E")

    if type_char in "fF%":
        error_digits = int(round(abs(error) * 10**decimals))
        if decimals >= 0:
            value_str = format(value, f".{decimals}{type_char}")
        else:
            # format() can't take negative precision; pre-round to the
            # resolved place (e.g. nearest thousand) and show 0 decimals.
            # The last shown digit is then the ones place, so the error is
            # written in ones too (45 +/- 23 -> "50(20)", not "50(2)").
            value_str = format(round(value, decimals), f".0{type_char}")
            error_digits = int(round(abs(error), decimals))
        if _too_many_digits(error_digits):
            # Error dwarfs the value (e.g. an unconstrained/degenerate fit
            # parameter) -- parenthetical notation isn't meaningful, fall back
            # to showing value and error independently.
            return f"{value_str} $\\pm$ {format(error, base_format)}"
        return f"{value_str}({error_digits})"

    if type_char in "eEgG":
        value_exponent = (
            int(np.floor(np.log10(abs(value)))) if value != 0 and np.isfinite(value) else 0
        )
        mantissa_decimals = max(decimals + value_exponent, 0)
        mantissa_part, _, exponent_part = format(
            value, f".{mantissa_decimals}{type_char}"
        ).partition("e")
        error_digits = int(round(abs(error) / 10 ** (value_exponent - mantissa_decimals)))
        if _too_many_digits(error_digits):
            return f"{format(value, base_format)} $\\pm$ {format(error, base_format)}"
        exponent_suffix = f"e{exponent_part}" if exponent_part else ""
        return f"{mantissa_part}({error_digits}){exponent_suffix}"

    return format(value, base_format)


def _siunitx(text, args):
    """Wrap a formatted number in siunitx's \\num{} when --siunitx is set, so
    that e.g. '2.38e+03' prints as 2.38 x 10^3 and '1.35(6)e-08' keeps its
    parenthetical uncertainty. Placeholders ('---') are left as they are."""
    if args is None or not getattr(args, "siunitx", False) or text == "---":
        return text
    return "\\num{" + text.replace("$\\pm$", "\\pm").replace("±", "\\pm") + "}"


def _significant(value, digits):
    """`value` rounded to `digits` significant figures in plain positional
    notation, trailing zeros trimmed (2384 -> '2380', 0.016834 -> '0.0168')."""
    return np.format_float_positional(float(f"{value:.{digits}g}"), trim="-")


def format_with_error(
    row, args=None, threshold=1e-3, significant_figures=1, error_format="±"
):
    return _siunitx(
        _format_with_error(row, args, threshold, significant_figures, error_format), args
    )


def _format_with_error(
    row, args=None, threshold=1e-3, significant_figures=1, error_format="±"
):
    mean = row[(args.y, getattr(args, "operation", "mean"))]
    error = row[(f"{args.y}Error", "<lambda>")]

    threshold = getattr(args, "threshold", threshold) if args is not None else threshold

    if abs(mean) < threshold:  # Check if mean is smaller than threshold
        return "---"  # Return '---' if mean is below threshold

    scientific = _wants_scientific(mean, args)
    decimals = significant_figures if significant_figures is not None else 1

    if error == 0 and args is not None and getattr(args, "zero_error_plain", False):
        return _significant(mean, 3)

    if pd.isna(error) or np.isinf(error) or error == 0 or error > 100 * abs(mean):
        if scientific:
            return f"{mean:.{decimals}e} ± {np.nan}"
        return f"{mean:.2f} ± {np.nan}"  # Return mean ± error with 2 decimal places

    if scientific:
        if args is not None and getattr(args, "compact_scientific", False):
            return _format_value_with_paren_error("e", mean, error)
        if error_format == "±":
            format_string = f"{{:.{decimals}e}} ± {{:.{decimals}e}}"
        elif error_format == "()":
            format_string = f"{{:.{decimals}e}}({{:.{decimals}e}})"
        else:
            print(f"Unknown format: {error_format}. Defaulting to '±'")
            format_string = f"{{:.{decimals}e}} ± {{:.{decimals}e}}"
        return format_string.format(mean, error)

    if args is not None and getattr(args, "compact_error", False):
        return _format_value_with_paren_error("f", mean, error)

    # Determine significant figures based on error if not provided
    error_magnitude = -int(np.floor(np.log10(abs(error)))) + 1
    if significant_figures is None:
        significance = max(
            2, error_magnitude
        )  # Use error to decide significant figures

    else:
        significance = error_magnitude - 2 + significant_figures
        if significance < 0:
            significance = 0

    if error_format == "±":
        format_string = f"{{:.{significance}f}} ± {{:.{significance}f}}"

    elif error_format == "()":
        format_string = f"{{:.{significance}f}}({{:.{significance}f}})"  # Ensure at least specified significant figures

    else:
        print(f"Unknown format: {error_format}. Defaulting to '±'")
        format_string = f"{{:.{significance}f}} ± {{:.{significance}f}}"

    return format_string.format(mean, error)


def _band_number(value, decimals):
    """A percentile bound: integers (e.g. counts) as integers, otherwise at the
    value's precision."""
    if float(value).is_integer():
        return f"{value:.0f}"
    return f"{value:.{decimals}f}"


def format_with_band(row, args=None, threshold=1e-3):
    """
    Format an aggregated value followed by the band given by --error_band,
    e.g. '0.5 (0--1)' for a mean with the 16th/84th percentiles of its
    distribution. Unlike a symmetric std, the band never leaves the physical
    range of the quantity (a count distribution piled up at 0 would otherwise
    print as 0.2(30), i.e. a band reaching -2.8). The bounds are printed as
    given, so for strongly skewed distributions the mean may lie outside them.
    """
    operation = getattr(args, "operation", "mean")
    low_col, high_col = args.error_band
    mean = row[(args.y, operation)]
    low = row[(low_col, operation)]
    high = row[(high_col, operation)]

    threshold = getattr(args, "threshold", threshold) if args is not None else threshold
    if abs(mean) < threshold and abs(high) < threshold:
        return "---"

    # Precision from the band half-width (PDG rule), never coarser than units;
    # a zero-width band falls back to two significant figures of the value.
    decimals = _resolve_decimal_places((high - low) / 2)
    if decimals is None:
        decimals = 1 - int(np.floor(np.log10(abs(mean)))) if mean != 0 else 0
    decimals = max(decimals, 0)

    value = f"{mean:.{decimals}f}"
    siunitx = args is not None and getattr(args, "siunitx", False)

    # A collapsed band (e.g. 0--0 when most events are 0) says nothing about
    # the tail that drives the mean; show the --band_fallback column instead,
    # marked so the caption can explain it.
    fallback = getattr(args, "band_fallback", None) if args is not None else None
    if fallback is not None and low == high:
        other = row[(fallback, operation)]
        other_text = _significant(other, 2)
        unit = getattr(args, "band_fallback_unit", None)
        if siunitx:
            other_text = (
                f"\\qty{{{other_text}}}{{{unit}}}" if unit else f"\\num{{{other_text}}}"
            )
            value = f"\\num{{{value}}}"
        elif unit:
            other_text = f"{other_text} {unit}"
        mark = getattr(args, "band_fallback_mark", None)
        return f"{value} ({other_text})" + (f"${mark}$" if mark else "")

    lo, hi = _band_number(low, decimals), _band_number(high, decimals)
    if siunitx:
        return f"\\num{{{value}}} (\\numrange{{{lo}}}{{{hi}}})"
    return f"{value} ({lo}--{hi})"


def clopper_pearson(passed, total, confidence=0.6827):
    """Central Clopper-Pearson interval (low, high) of the fraction
    passed/total at the given confidence level. Exact for binomial counts and
    always inside [0, 1]: at 0 or 100% efficiency the interval is one-sided
    instead of a symmetric error crossing the bound (100.0 ± 0.9)."""
    from scipy.stats import beta

    alpha = 1 - confidence
    low = beta.ppf(alpha / 2, passed, total - passed + 1) if passed > 0 else 0.0
    high = beta.ppf(1 - alpha / 2, passed + 1, total - passed) if passed < total else 1.0
    return float(low), float(high)


def format_with_interval(value, low, high, args=None, threshold=1e-3):
    """
    Format a value with an asymmetric interval as ``$value^{+up}_{-down}$``,
    e.g. a Clopper-Pearson efficiency. Precision follows format_with_error
    (one significant figure) of the smaller non-zero side, so both sides stay
    visible (a 100% efficiency prints as 100.00^{+0.00}_{-0.01}).
    """
    threshold = getattr(args, "threshold", threshold) if args is not None else threshold
    if not np.isfinite(value) or abs(value) < threshold:
        return "---"
    up, down = max(high - value, 0.0), max(value - low, 0.0)
    sides = [e for e in (up, down) if e > 0 and np.isfinite(e)]
    if not sides:
        return f"{value:.2f}"
    decimals = max(-int(np.floor(np.log10(min(sides)))), 0)
    return f"${value:.{decimals}f}^{{+{up:.{decimals}f}}}_{{-{down:.{decimals}f}}}$"


def format_value(row, args=None, threshold=1e-3):
    """
    Format an aggregated value with no uncertainty, for use when the source
    data has no *Error column to propagate (see format_with_error for the
    version that includes a propagated error).
    """
    mean = row[(args.y, getattr(args, "operation", "mean"))]

    threshold = getattr(args, "threshold", threshold) if args is not None else threshold

    if abs(mean) < threshold:  # Check if mean is smaller than threshold
        return "---"

    if _wants_scientific(mean, args):
        return _siunitx(f"{mean:.2e}", args)

    sig_figs = getattr(args, "sig_figs", None) if args is not None else None
    if sig_figs is not None:
        return _siunitx(_significant(mean, sig_figs), args)

    decimals = getattr(args, "decimals", None)
    return _siunitx(f"{mean:.{decimals if decimals is not None else 2}f}", args)


def make_config_label_from_args(args, config=None, name=None, iterable=None):
    """Legend label of one config/name line.

    Labels come from the ``config_dict`` and ``name_dict`` mappings (raw
    values otherwise). With one config the name tells lines apart and vice
    versa; with several of each both are shown. An --iterable value is
    appended when given. A plugin can replace this with
    ``registry.config_label``.
    """
    if registry.config_label is not None:
        return registry.config_label(args, config, name, iterable)
    config_dict = style.get_mapping_dict("config_dict") or {}
    name_dict = style.get_mapping_dict("name_dict") or {}
    config_label = config_dict.get(config, str(config)) if config is not None else None
    name_label = name_dict.get(name, str(name)) if name is not None else None

    num_configs = len(args.configs) if getattr(args, "configs", None) else 0
    num_names = len(args.names) if getattr(args, "names", None) else 0

    if num_names <= 1 or name_label is None:
        parts = [config_label]
    elif num_configs <= 1 or config_label is None:
        parts = [name_label]
    else:
        parts = [config_label, name_label]
    label = ", ".join(str(p) for p in parts if p is not None)

    if iterable is not None and getattr(args, "iterable", None) is not None:
        label += f", {iterable}"
    return label


def make_config_color_and_style_from_args(args, config=None, name=None):
    """(colour, linestyle) of one config/name line from the ``config_color``,
    ``config_line`` and (one config, several names) ``name_color`` mappings."""
    if config is None:
        return None, None

    num_configs = len(args.configs) if getattr(args, "configs", None) else 0
    num_names = len(args.names) if getattr(args, "names", None) else 0
    if num_configs == 1 and num_names > 1:
        name_color = style.get_mapping_dict("name_color") or {}
        return style.resolve_mapped_color(name_color.get(name)) if name else None, None

    config_color = style.get_mapping_dict("config_color") or {}
    config_line = style.get_mapping_dict("config_line") or {}
    return style.resolve_mapped_color(config_color.get(config)), config_line.get(config)
