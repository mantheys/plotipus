"""Plot style settings shared by every plot kind.

The settings live as module attributes (``style.titlefontsize``,
``style.legend_style``, ...) that the drawing code reads at call time, so a
project can change them once with :func:`configure` before plotting.

A style file is JSON with the sections ``rcparams``, ``font_sizes``,
``plot_settings`` and ``mappings`` (label/colour dictionaries addressed by
name from ``--iterable_mapping`` and friends). Every section is optional and
merged over the defaults shipped in ``plotipus/data/style.json``.
"""

import copy
import json
from pathlib import Path

import matplotlib.pyplot as plt

_DEFAULTS_PATH = Path(__file__).with_name("data") / "style.json"
_MPLSTYLE_PATH = Path(__file__).with_name("data") / "plotipus.mplstyle"

_FALLBACK_LEGEND_STYLE = {"frameon": False, "loc": "best"}
_FALLBACK_NOTE_STYLE = {
    "fontsize": "large",
    "bbox": {
        "boxstyle": "round,pad=0.5",
        "facecolor": "white",
        "alpha": 0.8,
        "edgecolor": "gray",
        "linewidth": 0.5,
    },
}
_FALLBACK_MARGINS_INCHES = {
    "left": 0.96,
    "right": 0.40,
    "bottom": 0.72,
    "top": 0.60,
    "wspace": 0.25,
    "hspace": 0.15,
}

# Current configuration (merged defaults + user files).
_CONFIG = {}

# Label conventions a project can tune (empty by default):
#   capitalize_exceptions: word -> display form used by --capitalize_legend
#   redundant_legend_titles: legend titles that are dropped (lower case)
#   title_short_forms: (long, short) pairs swapped in when a title is too wide
capitalize_exceptions = {}
redundant_legend_titles = set()
title_short_forms = ()

mappings = {}


def _load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _deep_merge(base, update):
    merged = copy.deepcopy(base)
    for key, value in (update or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _publish():
    """Expose the merged configuration as module attributes."""
    global titlefontsize, subtitlefontsize, legendtitlefontsize, legendfontsize
    global xlabelfontsize, ylabelfontsize, xsublabelfontsize, ysublabelfontsize
    global linelabelfontsize, nbins, default_linewidth, figure_base_width
    global figure_panel_width, figure_height, figure_panel_font_scale
    global figure_margins_inches, figure_two_panel_hspace, legend_style
    global note_style, base_font_size, mappings, auto_title
    global capitalize_exceptions, redundant_legend_titles, title_short_forms

    rcparams = _CONFIG.get("rcparams", {})
    plt.rcParams.update(rcparams)
    base_font_size = float(plt.rcParams["font.size"])

    fonts = _CONFIG.get("font_sizes", {})
    titlefontsize = fonts.get("titlefontsize", "xx-large")
    subtitlefontsize = fonts.get("subtitlefontsize", "x-large")
    legendtitlefontsize = fonts.get("legendtitlefontsize", "xx-large")
    legendfontsize = fonts.get("legendfontsize", "x-large")
    xlabelfontsize = fonts.get("xlabelfontsize", "xx-large")
    ylabelfontsize = fonts.get("ylabelfontsize", "xx-large")
    xsublabelfontsize = fonts.get("xsublabelfontsize", "x-large")
    ysublabelfontsize = fonts.get("ysublabelfontsize", "x-large")
    linelabelfontsize = fonts.get("linelabelfontsize", "large")

    settings = _CONFIG.get("plot_settings", {})
    nbins = settings.get("nbins", 50)
    default_linewidth = settings.get("default_linewidth", 2)
    # Title from the datafile name when --title is not given.
    auto_title = bool(settings.get("auto_title", True))

    layout = settings.get("figure_layout", {})
    figure_base_width = layout.get("base_width", 8)
    figure_panel_width = layout.get("panel_width", 5)
    figure_height = layout.get("height", 6)
    # Font scale per number of panel columns: a figure with more columns is
    # shrunk more to fit the text width, so its text is enlarged to match.
    figure_panel_font_scale = {
        int(k): float(v) for k, v in layout.get("panel_font_scale", {}).items()
    }
    figure_margins_inches = layout.get("margins_inches", dict(_FALLBACK_MARGINS_INCHES))
    figure_two_panel_hspace = layout.get("two_panel_hspace", 0)

    legend_style = dict(
        settings.get(
            "legend_style",
            {**_FALLBACK_LEGEND_STYLE, "fontsize": legendfontsize, "title_fontsize": legendtitlefontsize},
        )
    )
    note_style = dict(settings.get("note_style", _FALLBACK_NOTE_STYLE))

    labels = _CONFIG.get("labels", {})
    capitalize_exceptions = dict(labels.get("capitalize_exceptions", {}))
    redundant_legend_titles = {str(t).lower() for t in labels.get("redundant_legend_titles", [])}
    title_short_forms = tuple(tuple(pair) for pair in labels.get("title_short_forms", []))

    mappings = _CONFIG.get("mappings", {})


def reset():
    """Restore the shipped defaults (matplotlib look and settings)."""
    global _CONFIG
    plt.style.use(str(_MPLSTYLE_PATH))
    _CONFIG = _load_json(_DEFAULTS_PATH)
    _CONFIG.setdefault("mappings", {})
    _publish()


def configure(config=None, **sections):
    """Merge a style file (path), a dict, and/or keyword sections over the
    current settings, e.g. ``configure("style.json")`` or
    ``configure(font_sizes={"titlefontsize": "large"})``."""
    global _CONFIG
    if config is not None:
        if not isinstance(config, dict):
            config = _load_json(Path(config).expanduser())
        _CONFIG = _deep_merge(_CONFIG, config)
    if sections:
        _CONFIG = _deep_merge(_CONFIG, sections)
    _publish()


def register_mappings(new_mappings):
    """Add (or replace) named label/colour mappings."""
    configure(mappings=dict(new_mappings))


def set_legend_option(key, value):
    """Override one legend option (e.g. ``loc`` or ``ncol``) for every legend
    drawn from now on."""
    legend_style[key] = value


def get_mapping_dict(mapping_name):
    if mapping_name is None:
        return None
    mapping = mappings.get(mapping_name)
    return mapping if isinstance(mapping, dict) else None


def resolve_mapped_color(color_value):
    """Accept matplotlib colours plus ``rgb(r,g,b)`` strings (0-1 or 0-255)."""
    if color_value is None or not isinstance(color_value, str):
        return color_value

    stripped = color_value.strip()
    if stripped.lower().startswith("rgb(") and stripped.endswith(")"):
        channels = stripped[4:-1].split(",")
        if len(channels) != 3:
            return stripped
        try:
            values = [float(channel.strip()) for channel in channels]
        except ValueError:
            return stripped
        if any(value > 1.0 for value in values):
            values = [value / 255.0 for value in values]
        return tuple(min(1.0, max(0.0, value)) for value in values)

    return stripped


reset()
