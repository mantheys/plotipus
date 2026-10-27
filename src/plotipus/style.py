"""Plot style settings shared by every plot kind.

The settings live as module attributes (``style.titlefontsize``,
``style.legend_style``, ...) that the drawing code reads at call time, so a
project can change them once with :func:`configure` before plotting.

A style file is JSON with the sections ``rcparams``, ``font_sizes``,
``plot_settings``, ``roles`` and ``mappings`` (label/colour dictionaries addressed by
name from ``--iterable_mapping`` and friends), and the keys ``palette`` (a
name from :mod:`plotipus.palettes`, default ``petroff10``), ``mplstyle``
(matplotlib style files, relative to the style file, or style names; applied
before the file's ``rcparams``) and ``contours`` (confidence contours of
``map --contour``: ``dof``, ``fill_mix``, ``linestyles``, ``label``,
``background``). Every section is optional and merged over the defaults shipped
in ``plotipus/data/style.json``.

Named styles (T16) combine a language (``plotipus``, ``open``), a medium
(``slides``, ``paper``, ``web``) and a theme (``light``, ``dark``): ``slides``
(the default), ``slides-dark``, ``paper``, ``paper-dark``, ``open``,
``open-dark``, and ``classic``, the look before the redesign. Their layers
live in ``plotipus/data/styles``; see :func:`name_layers`.

Figure size: ``widths`` (named presets: inches, or ``{"width", "height"}``),
``aspect`` (height/width) and ``width`` (the preset or inches to draw at).
Without ``width`` the old geometry (``figure_layout`` base/panel widths)
is used.

Colours that are not data colours come from the ``roles`` (see :func:`role`):
``ink`` (text, data points, fit and reference lines), ``muted`` (guides),
``faint`` (pull bands, grids), ``paper`` (background, outlines on images) and
``accent`` (highlights). Mapping colours may name one as ``"role:ink"``.
"""

import copy
import json
from pathlib import Path

import matplotlib
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt

from . import colormaps  # noqa: F401  (registers the plotipus colour maps)
from . import palettes

_DEFAULTS_PATH = Path(__file__).with_name("data") / "style.json"
# Named style layers: languages, media, themes and classic/.
STYLES_DIR = Path(__file__).with_name("data") / "styles"

LANGUAGES = ("plotipus", "open", "classic")
# name -> (language, medium, theme)
NAMES = {
    "slides": ("plotipus", "slides", "light"),
    "slides-dark": ("plotipus", "slides", "dark"),
    "paper": ("plotipus", "paper", "light"),
    "paper-dark": ("plotipus", "paper", "dark"),
    "open": ("open", "web", "light"),
    "open-dark": ("open", "web", "dark"),
    "classic": ("classic", None, "light"),
}
DEFAULT_NAME = "slides"
EXPERIMENTS_DIR = STYLES_DIR / "experiments"


def experiments():
    """Names of the experiment presets (``--experiment``)."""
    return sorted(path.stem for path in EXPERIMENTS_DIR.glob("*.json"))
_MPLSTYLE_PATH = Path(__file__).with_name("data") / "plotipus.mplstyle"

_FALLBACK_LEGEND_STYLE = {"frameon": False, "loc": "best"}
_FALLBACK_NOTE_STYLE = {
    "fontsize": "large",
    "bbox": {
        "boxstyle": "round,pad=0.5",
        "facecolor": "role:paper",
        "alpha": 0.8,
        "edgecolor": "role:muted",
        "linewidth": 0.5,
    },
}
# Contour defaults; "dof" is left out so that a style setting it can be told apart.
_FALLBACK_CONTOURS = {
    "fill_mix": [1.0, 0.55, 0.25],
    "linestyles": ["-", "--", ":"],
    "label": "cl",
    "background": "none",
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

ROLES = ("ink", "muted", "faint", "paper", "accent")
# Share of ink mixed into paper for the derived roles.
_ROLE_INK_SHARE = {"muted": 0.5, "faint": 0.1}
_DEFAULT_ACCENT = "#bd1f01"  # the red of petroff10

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


def _mplstyle_rcparams(entries, base_dir):
    """rcParams set by ``plt.style.use(entries)`` over the current ones.

    ``entries`` is a path, a style name, or a list of them; a path is
    relative to ``base_dir`` (the style file's folder)."""
    if isinstance(entries, (str, Path)):
        entries = [entries]
    resolved = []
    for entry in entries:
        candidate = Path(base_dir, Path(entry).expanduser())
        resolved.append(str(candidate) if candidate.is_file() else entry)
    before = dict(plt.rcParams)
    with matplotlib.rc_context():
        plt.style.use(resolved)
        after = dict(plt.rcParams)
    return {key: value for key, value in after.items() if before.get(key) != value}


def _expand_mplstyle(config, base_dir):
    """``config`` with its ``mplstyle`` key folded into ``rcparams`` (under the
    file's own rcparams, so they win), so that later files override it."""
    entries = config.get("mplstyle")
    if not entries:
        return config
    config = dict(config)
    config.pop("mplstyle")
    config["rcparams"] = {**_mplstyle_rcparams(entries, base_dir), **config.get("rcparams", {})}
    return config


def _as_color(value):
    """A style colour: matplotlib colours, ``rgb(...)``, hex without ``#``."""
    value = resolve_mapped_color(value)
    if isinstance(value, str) and not mcolors.is_color_like(value) and mcolors.is_color_like("#" + value):
        return "#" + value
    return value


def _mix(color, other, share):
    """``share`` of ``color`` mixed into ``other``, as a hex string."""
    a, b = mcolors.to_rgb(color), mcolors.to_rgb(other)
    return mcolors.to_hex([share * x + (1 - share) * y for x, y in zip(a, b)])


def role(name):
    """The colour of role ``name`` (one of :data:`ROLES`).

    From the style's ``roles`` section; otherwise derived from the current
    rcParams: ``ink`` is ``text.color``, ``paper`` is ``axes.facecolor``,
    ``muted`` and ``faint`` are mixes of the two."""
    if name not in ROLES:
        raise ValueError(f"Unknown colour role '{name}' (expected one of {', '.join(ROLES)}).")
    configured = (_CONFIG.get("roles") or {}).get(name)
    if configured is not None:
        return _as_color(configured)
    if name == "ink":
        return plt.rcParams["text.color"]
    if name == "paper":
        paper = plt.rcParams["axes.facecolor"]
        return plt.rcParams["figure.facecolor"] if mcolors.to_rgba(paper)[3] == 0 else paper
    if name == "accent":
        return _DEFAULT_ACCENT
    return _mix(role("ink"), role("paper"), _ROLE_INK_SHARE[name])


def role_colors(value):
    """``value`` with every ``"role:NAME"`` string (also inside dicts and
    lists, e.g. a legend or note style) replaced by the role's colour."""
    if isinstance(value, dict):
        return {key: role_colors(item) for key, item in value.items()}
    if isinstance(value, list):
        return [role_colors(item) for item in value]
    if isinstance(value, str) and value.strip().startswith("role:"):
        return role(value.strip()[len("role:"):].strip())
    return value


def _publish():
    """Expose the merged configuration as module attributes."""
    global titlefontsize, subtitlefontsize, legendtitlefontsize, legendfontsize
    global xlabelfontsize, ylabelfontsize, xsublabelfontsize, ysublabelfontsize
    global linelabelfontsize, nbins, default_linewidth, band_alpha, figure_base_width
    global figure_panel_width, figure_height, figure_panel_font_scale
    global figure_margins_inches, figure_two_panel_hspace, legend_style, figure_pad_inches, figure_fixed_margins
    global note_style, base_font_size, mappings, auto_title, contours, stack_error, sci_in_label, error_label
    global capitalize_exceptions, redundant_legend_titles, title_short_forms
    global widths, figure_aspect, figure_width, figure_row_height, draw_titles
    global fit_color, zero_line_color, diverging_cmap, diverging_marker_cmap, header, figure_single_panel, text_scale
    global figure_lower_panels, figure_facet_width, figure_layout_mode

    rcparams = _CONFIG.get("rcparams", {})
    plt.rcParams.update(rcparams)
    # The colour cycle: the "palette" key, else an explicit axes.prop_cycle, else the default palette.
    palette = _CONFIG.get("palette")
    if palette is not None or "axes.prop_cycle" not in rcparams:
        palettes.apply(palette or palettes.DEFAULT)
    else:
        palettes.active = None
    base_font_size = float(plt.rcParams["font.size"])

    fonts = _CONFIG.get("font_sizes", {})
    # Axis labels take rcParams axes.labelsize in every kind; a style's
    # x/ylabelfontsize writes into it.
    if "ylabelfontsize" in fonts or "xlabelfontsize" in fonts:
        plt.rcParams["axes.labelsize"] = fonts.get("ylabelfontsize", fonts.get("xlabelfontsize"))
    titlefontsize = fonts.get("titlefontsize", "xx-large")
    subtitlefontsize = fonts.get("subtitlefontsize", "x-large")
    legendtitlefontsize = fonts.get("legendtitlefontsize", "xx-large")
    legendfontsize = fonts.get("legendfontsize", "x-large")
    xlabelfontsize = fonts.get("xlabelfontsize", plt.rcParams["axes.labelsize"])
    ylabelfontsize = fonts.get("ylabelfontsize", plt.rcParams["axes.labelsize"])
    xsublabelfontsize = fonts.get("xsublabelfontsize", "x-large")
    ysublabelfontsize = fonts.get("ysublabelfontsize", "x-large")
    linelabelfontsize = fonts.get("linelabelfontsize", "large")

    settings = _CONFIG.get("plot_settings", {})
    nbins = settings.get("nbins", 50)
    default_linewidth = settings.get("default_linewidth", 2)
    # Opacity of --errory_type bands (series colour, no edge).
    band_alpha = float(settings.get("band_alpha", 0.2))
    # Band of the stacked simulation's total error (--data_hue --stacked --errory).
    error_label = bool(settings.get("error_label", False))
    stack_error = {"label": "Sim. unc.", "hatch": "////", "color": "role:muted", **settings.get("stack_error", {})}
    # Title from the datafile name when --title is not given.
    auto_title = bool(settings.get("auto_title", True))
    # A common power of ten in the axis label instead of offset text.
    sci_in_label = bool(settings.get("sci_in_label", True))
    # An explicit --title is drawn (false in paper: the caption is the title).
    draw_titles = bool(settings.get("titles", True))
    # Fit lines (default: ink, or the palette's first colour over data), the
    # y = 0 line of lower panels, and --cmap diverging. Colours may be roles.
    fit_color = settings.get("fit_color")
    zero_line_color = settings.get("zero_line_color", "role:muted")
    diverging_cmap = settings.get("diverging_cmap", "RdBu_r")
    # Signed colours of markers (scatter --colorby): the centre must stand out
    # from the background, so it is the opposite of the filled cells' map
    # (dark at 0 on light paper, light at 0 on a dark theme).
    diverging_marker_cmap = settings.get("diverging_marker_cmap", diverging_cmap)
    # Scale for the free texts of plugins and figure hooks (relative font
    # sizes already follow the medium's font.size; dense media shrink them).
    text_scale = float(settings.get("text_scale", 1.0))
    # The experiment header and watermark (see plotipus.header).
    header = dict(_CONFIG.get("header", {}))

    widths = {name: value for name, value in _CONFIG.get("widths", {}).items()}
    figure_aspect = float(_CONFIG.get("aspect", 0.75))
    geometry = _CONFIG.get("cli_geometry", {})
    figure_single_panel = bool(geometry.get("single_panel", False))
    figure_width, figure_row_height = resolve_width(
        geometry.get("width", _CONFIG.get("width")), widths, figure_aspect, geometry.get("aspect"))
    # Lower panels "add" height to the upper panel's, or "share" the figure's.
    figure_lower_panels = str(_CONFIG.get("lower_panels", "add"))
    # Facets side by side: each adds facet_width (a share of one plot's
    # width) to the figure; --layout panels keeps one plot's size instead.
    figure_facet_width = float(_CONFIG.get("facet_width", 0.6))
    figure_layout_mode = str(_CONFIG.get("layout", "facets"))

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
    # Measured layout: margins are the drawn extents plus this padding
    # (margins_inches is then a minimum); fixed_margins keeps margins_inches exactly.
    figure_pad_inches = float(layout.get("pad_inches", 0.04))
    figure_fixed_margins = bool(layout.get("fixed_margins", False))

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
    contours = {**_FALLBACK_CONTOURS, **_CONFIG.get("contours", {})}


def resolve_width(spec, presets, aspect, forced_aspect=None):
    """(width, row height) in inches of a ``--width`` value: a preset name or
    inches; (None, None) without one. A preset may fix its own height
    (``{"width": 6.8, "height": 3.0}``) unless ``forced_aspect`` is given."""
    if spec is None:
        return None, None
    entry = presets.get(str(spec).strip().lower(), spec)
    try:
        if isinstance(entry, dict):
            width = float(entry["width"])
            height = entry.get("height") if forced_aspect is None else None
        else:
            width, height = float(entry), None
    except (TypeError, ValueError, KeyError):
        raise ValueError(f"Unknown width '{spec}': use inches or one of {', '.join(presets)}.") from None
    ratio = float(forced_aspect) if forced_aspect is not None else aspect
    return width, float(height) if height is not None else ratio * width


def set_geometry(width=None, aspect=None, single_panel=None):
    """Draw at ``width`` (preset or inches) and/or ``aspect`` (height/width),
    overriding the style (the --width and --aspect options); with
    ``single_panel``, a figure of several panels keeps the size of one
    (--single_panel_size)."""
    geometry = {k: v for k, v in (("width", width), ("aspect", aspect), ("single_panel", single_panel))
                if v is not None}
    _CONFIG["cli_geometry"] = geometry
    _publish()


def snapshot():
    """The current settings and rcParams, for :func:`restore`."""
    return copy.deepcopy(_CONFIG), dict(plt.rcParams)


def restore(saved):
    """Return to a :func:`snapshot` (e.g. before rendering another medium)."""
    global _CONFIG
    config, rc = saved
    dict.update(plt.rcParams, rc)
    _CONFIG = copy.deepcopy(config)
    _publish()


def layer_path(name):
    """The style file of layer ``name`` (``<name>.json`` or ``<name>/style.json``
    in plotipus/data/styles), or None."""
    for candidate in (STYLES_DIR / f"{name}.json", STYLES_DIR / name / "style.json"):
        if candidate.is_file():
            return candidate
    return None


def name_layers(language, medium=None, theme="light", experiment=None):
    """[(layer, path)] of a language/medium/theme combination, in the order
    they apply: the language, the medium, the experiment preset and the dark
    theme (whose readable colours win over an experiment's palette).
    ``classic`` is complete on its own (no medium or theme layer)."""
    names = [language] if language == "classic" else [n for n in (language, medium) if n]
    found = [(n, layer_path(n)) for n in names]
    if experiment and experiment != "none":
        path = EXPERIMENTS_DIR / f"{experiment}.json"
        if not path.is_file():
            raise ValueError(f"Unknown experiment '{experiment}': use one of {', '.join(experiments())}.")
        found.append((f"experiment-{experiment}", path))
    if language != "classic" and theme == "dark":
        found.append(("dark", layer_path("dark")))
    missing = [n for n, path in found if path is None]
    if missing:
        raise ValueError(f"Unknown style layer(s): {', '.join(missing)}.")
    return found


def resolve_name(name):
    """(language, medium, theme) of a named style."""
    key = str(name).strip().lower()
    if key not in NAMES:
        raise ValueError(f"Unknown style '{name}': use one of {', '.join(NAMES)}.")
    return NAMES[key]


def _dict_difference(before, after):
    """The keys of ``after`` that differ from ``before`` (recursively)."""
    out = {}
    for key, value in after.items():
        old = before.get(key, object())
        if isinstance(value, dict) and isinstance(old, dict):
            sub = _dict_difference(old, value)
            if sub:
                out[key] = sub
        elif value != old:
            out[key] = copy.deepcopy(value)
    return out


def difference(before, after):
    """What changed between two :func:`snapshot` states, for :func:`replay`."""
    return _dict_difference(before[0], after[0]), _dict_difference(before[1], after[1])


def replay(changes):
    """Apply a :func:`difference` (e.g. what plugins changed) again."""
    config, rc = changes
    if rc:
        # rcParams set directly (plugin rcParams, plt.style.use) are recorded
        # like a style file's, so the layers published after them keep them; a
        # colour cycle set this way replaces the palette of earlier layers.
        recorded = {key: repr(value) if key == "axes.prop_cycle" else value for key, value in rc.items()
                    if key != "axes.prop_cycle" or "palette" not in config}
        config = _deep_merge(config, {"rcparams": recorded})
    if config:
        configure(config)
    dict.update(plt.rcParams, rc)


def base_state():
    """The settings before any named style (the classic files, at matplotlib
    defaults), as a :func:`snapshot`."""
    return copy.deepcopy(_BASE)


def default_state():
    """The settings of the default style (``slides``), as a :func:`snapshot`."""
    return copy.deepcopy(_DEFAULT)


def apply_layers(layers):
    """Merge style layers [(name, path)] in order."""
    for _, path in layers:
        configure(path)


def reset():
    """Restore the shipped defaults: the default named style (``slides``)
    over the base settings."""
    global _CONFIG, _BASE, _DEFAULT
    plt.style.use(["default", str(_MPLSTYLE_PATH)])
    _CONFIG = _load_json(_DEFAULTS_PATH)
    _CONFIG.setdefault("mappings", {})
    _publish()
    _BASE = snapshot()
    apply_layers(name_layers(*NAMES[DEFAULT_NAME]))
    _DEFAULT = snapshot()


def _merge(config, base_dir):
    """Merge one style file's settings over the current ones. An explicit
    colour cycle (rcparams, or a mplstyle setting one) replaces the palette
    of an earlier layer unless the file names a palette too."""
    global _CONFIG
    config = _expand_mplstyle(config, base_dir)
    fonts = config.get("font_sizes", {})
    if ("xlabelfontsize" in fonts) != ("ylabelfontsize" in fonts):
        # One rcParam sizes both axis labels: a file setting one sets both.
        size = fonts.get("ylabelfontsize", fonts.get("xlabelfontsize"))
        config = {**config, "font_sizes": {**fonts, "xlabelfontsize": size, "ylabelfontsize": size}}
    _CONFIG = _deep_merge(_CONFIG, config)
    if "axes.prop_cycle" in config.get("rcparams", {}) and "palette" not in config:
        _CONFIG["palette"] = None


def configure(config=None, **sections):
    """Merge a style file (path), a dict, and/or keyword sections over the
    current settings, e.g. ``configure("style.json")`` or
    ``configure(font_sizes={"titlefontsize": "large"})``. A ``.mplstyle``
    path is applied as ``{"mplstyle": path}``; relative ``mplstyle`` paths
    resolve against the style file's folder (the working directory for a
    dict)."""
    global _CONFIG
    if config is not None:
        base_dir = Path.cwd()
        if not isinstance(config, dict):
            path = Path(config).expanduser()
            # A bare .mplstyle file is a style file with only that key.
            config = {"mplstyle": str(path)} if path.suffix == ".mplstyle" else _load_json(path)
            base_dir = path.parent
        _merge(config, base_dir)
    if sections:
        _merge(sections, Path.cwd())
    _publish()


def register_mappings(new_mappings):
    """Add (or replace) named label/colour mappings."""
    configure(mappings=dict(new_mappings))


def set_layout(mode=None):
    """The --layout of this run: 'facets' or 'panels' (None: the style's)."""
    global figure_layout_mode
    figure_layout_mode = str(mode or _CONFIG.get("layout", "facets"))


def compact_gap():
    """gridspec wspace between compact panels: touching for --layout panels
    (one plot split in parts), a narrow gap between facets."""
    return 0.0 if figure_layout_mode == "panels" else 0.08


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
    """Accept matplotlib colours plus ``rgb(r,g,b)`` strings (0-1 or 0-255)
    and roles (``role:ink``)."""
    if color_value is None or not isinstance(color_value, str):
        return color_value

    stripped = color_value.strip()
    if stripped.startswith("role:"):
        return role(stripped[len("role:"):].strip())
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
