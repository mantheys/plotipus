"""Project settings from ``plotipus.toml``.

The file is looked up from the working directory upwards; without one the
working directory is the project root and every setting has its default::

    [project]
    data_root = "input/data"        # root of relative --path values
    plots = "input/plots"           # command lists: <list>_scripts.txt
    tables = "input/tables"
    output = "output"               # default output/plots, output/tables
    style = ["paper", "config/style.json"]  # a named style (slides, slides-dark,
                                    # paper, paper-dark, open, open-dark,
                                    # classic) and/or style files (.json,
                                    # .mplstyle) merged over it
    plugins = ["my_project.plotipus_plugin"]
    python_path = ["src"]           # added to sys.path before plugins load
    medium = "slides"               # slides | paper | web (default: slides)
    media = ["slides", "paper"]     # what --medium all / plotipus run render
    theme = "light"                 # light | dark
    language = "plotipus"           # plotipus | open | classic
    save_style = false              # write <figure>.style.json next to each figure

    [header]                        # the experiment header and watermark
    experiment = "dune"             # a preset: atlas, cms, lhcb, alice, dune
    label = "plotipus"              # (or the preset's) bold label, top left
    label_status = "Preliminary"
    label_right = "13.6 TeV, 140 fb$^{-1}$"
    watermark = "wip"               # wip, preliminary, internal, simulation, draft, or text
    watermark_style = "corner"      # corner | diagonal

    [outputs.plots]                 # extra -o targets per command list
    solar = ["../THESIS/figures/solar"]

    [outputs.tables]
    thesis = ["../THESIS/tables"]

    [settings]
    default_operation = "mean"

The style of a figure is built in layers: the base settings, then the
named style's language, medium and dark theme from
``plotipus/data/styles/`` (default ``slides``: plotipus, slides, light;
``--style_preset``, ``--medium`` and ``--theme`` change it), then whatever
plugins changed, then the project's ``style`` files, which have the last
word, then ``[header]``, then ``--width``/``--aspect``. An experiment
preset (``--experiment``, ``[header] experiment`` or ``experiment-NAME`` in
the style list) is a layer between the medium and the dark theme. The
project's own medium and theme
write to ``output/plots``; any other pair writes to
``output/plots/<medium>[-dark]``.
"""

import importlib
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib

from . import registry, style

CONFIG_NAME = "plotipus.toml"
MEDIA = ("slides", "paper", "web")
THEMES = ("light", "dark")
DEFAULT_MEDIUM, DEFAULT_THEME, DEFAULT_LANGUAGE = "slides", "light", "plotipus"


@dataclass
class Project:
    root: Path
    data_root: Path
    plots_dir: Path
    tables_dir: Path
    output_dir: Path
    outputs: dict = field(default_factory=dict)
    settings: dict = field(default_factory=dict)
    config_file: Path = None
    medium: str = None
    media: list = None
    theme: str = None
    language: str = None
    preset: str = None
    experiment: str = None
    header: dict = field(default_factory=dict)
    save_style: bool = False
    styles: list = field(default_factory=list)
    rendering: "Rendering" = None
    _changes: tuple = None

    def output_paths(self, kind, list_name):
        """Extra output directories configured for a command list."""
        paths = self.outputs.get(kind, {}).get(list_name) or []
        if isinstance(paths, str):
            paths = [paths]
        return [str(self._resolve(p)) for p in paths]

    def _resolve(self, value):
        path = Path(value).expanduser()
        return path if path.is_absolute() else self.root / path

    def all_media(self):
        """The media of ``--medium all``: [project] media, else every medium."""
        return list(self.media or MEDIA)

    def own_style(self, preset=None):
        """(language, medium, theme) of the project, or of ``preset``: the
        named style, then the [project] language/medium/theme keys."""
        language, medium, theme = style.resolve_name(preset or self.preset or style.DEFAULT_NAME)
        if preset:
            return language, medium, theme
        return self.language or language, self.medium or medium, self.theme or theme

    def output_folder(self, medium, theme):
        """Sub-folder of a medium/theme pair below the plot outputs: none for
        the project's own pair, else ``<medium>`` (+ ``-dark``)."""
        _, own_medium, own_theme = self.own_style()
        own = (own_medium or DEFAULT_MEDIUM, own_theme or DEFAULT_THEME)
        pair = (medium or own[0], theme or own[1])
        if pair == own:
            return None
        return pair[0] + ("-dark" if pair[1] == "dark" else "")

    def layers(self, language, medium, theme, experiment=None):
        """Style layers [(name, path)]: the named layers of the combination
        (with the experiment preset), then the project style files."""
        experiment = self.experiment if experiment is None else experiment
        return (style.name_layers(language, medium, theme, experiment)
                + [(Path(s).name, self._resolve(s)) for s in self.styles])


@dataclass
class Rendering:
    """The style, medium, theme and figure size a command draws at."""
    medium: str
    theme: str
    width: float
    height: float
    layers: list
    folder: str
    language: str = None
    save_style: bool = False

    def describe(self):
        size = f"{self.width:g} x {self.height:g} in" if self.width else "classic size"
        layers = ", ".join(name for name, _ in self.layers) or "none"
        return (f"language={self.language} medium={self.medium or 'none'} theme={self.theme} width={size} "
                f"layers=[{layers}]" + (f" -> plots/{self.folder}" if self.folder else ""))

    def record(self):
        """The resolved style, for ``--save_style``."""
        return {"language": self.language, "medium": self.medium, "theme": self.theme,
                "size_inches": [self.width, self.height] if self.width else None,
                "layers": [[name, str(path)] for name, path in self.layers]}


def _check(value, allowed, option):
    if value is not None and value not in allowed:
        raise ValueError(f"{option} must be one of {', '.join(allowed)} (got '{value}').")
    return value


# [header] keys of plotipus.toml -> keys of the style's "header" section.
_HEADER_KEYS = {"label": "label", "label_status": "status", "label_right": "right",
                "watermark": "watermark", "watermark_style": "watermark_style"}


def apply_rendering(medium=None, theme=None, width=None, aspect=None, project=None, preset=None,
                    save_style=None, experiment=None, single_panel=None):
    """Apply the style of a named preset and/or medium/theme (default: the
    project's) and the --width/--aspect overrides; returns the Rendering."""
    project = project or load_project()
    if project._changes is None:  # a project set with set_project()
        project._changes = style.difference(style.default_state(), style.snapshot())
    language, own_medium, own_theme = project.own_style(preset)
    medium = _check(medium or own_medium, MEDIA, "--medium")
    theme = _check(theme or own_theme or DEFAULT_THEME, THEMES, "--theme")
    layers = project.layers(language, medium, theme, experiment)
    style.restore(style.base_state())
    style.apply_layers(layers[:len(layers) - len(project.styles)])
    # Plugins (and settings changed before the project loaded) keep their
    # say over the named style; the project's style files have the last word.
    style.replay(project._changes)
    style.apply_layers(layers[len(layers) - len(project.styles):])
    if project.header:
        style.configure(header=project.header)
    if width is not None or aspect is not None or single_panel:
        style.set_geometry(width=width, aspect=aspect, single_panel=single_panel)
    project.rendering = Rendering(medium, theme, style.figure_width, style.figure_row_height, layers,
                                  project.output_folder(medium, theme), language,
                                  project.save_style if save_style is None else save_style)
    return project.rendering


def describe_rendering(medium=None, theme=None, width=None, aspect=None, project=None, preset=None,
                       experiment=None):
    """The Rendering a command would get, without changing the current style."""
    project = project or load_project()
    saved = style.snapshot()
    try:
        return apply_rendering(medium, theme, width, aspect, project, preset, experiment=experiment)
    finally:
        style.restore(saved)


def current_rendering():
    project = _PROJECT
    return project.rendering if project is not None else None


_PROJECT = None


def find_config(start=None):
    current = Path(start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        candidate = directory / CONFIG_NAME
        if candidate.is_file():
            return candidate
    return None


def load_project(start=None, reload=False):
    """Load (once) the project around ``start`` and apply its style/plugins."""
    global _PROJECT
    if _PROJECT is not None and not reload:
        return _PROJECT

    config_file = find_config(start)
    config = {}
    root = Path(start or Path.cwd()).resolve()
    if config_file is not None:
        with open(config_file, "rb") as handle:
            config = tomllib.load(handle)
        root = config_file.parent

    section = config.get("project", {})

    def resolve(value, default):
        path = Path(section.get(value, default)).expanduser()
        return path if path.is_absolute() else root / path

    project = Project(
        root=root,
        data_root=resolve("data_root", "input/data"),
        plots_dir=resolve("plots", "input/plots"),
        tables_dir=resolve("tables", "input/tables"),
        output_dir=resolve("output", "output"),
        outputs=config.get("outputs", {}),
        settings=config.get("settings", {}),
        config_file=config_file,
        medium=section.get("medium"),
        media=section.get("media"),
        theme=section.get("theme"),
        language=_check(section.get("language"), style.LANGUAGES, "[project] language"),
        save_style=bool(section.get("save_style", False)),
    )
    _PROJECT = project

    for entry in section.get("python_path", []):
        path = str(project._resolve(entry))
        if path not in sys.path:
            sys.path.insert(0, path)

    # Plugins first (they may install a matplotlib style), then the style
    # files, which have the final say.
    for plugin in section.get("plugins", []):
        module = importlib.import_module(plugin)
        setup = getattr(module, "setup", None)
        if callable(setup):
            setup(registry)

    # A named style in the style list picks the project's style; the other
    # entries are style files.
    styles = section.get("style", [])
    for entry in [styles] if isinstance(styles, str) else styles:
        name = str(entry).strip().lower()
        if project._resolve(entry).exists():
            project.styles.append(entry)
        elif name in style.NAMES:
            project.preset = name
        elif name.startswith("experiment-"):
            project.experiment = name[len("experiment-"):]
        else:
            project.styles.append(entry)
    header = dict(config.get("header", {}))
    project.experiment = header.pop("experiment", project.experiment)
    unknown = set(header) - set(_HEADER_KEYS)
    if unknown:
        raise ValueError(f"Unknown [header] key(s) in {config_file}: {', '.join(sorted(unknown))}.")
    project.header = {_HEADER_KEYS[key]: value for key, value in header.items()}
    project._changes = style.difference(style.default_state(), style.snapshot())
    apply_rendering(project=project)
    return project


def set_project(project):
    """Use ``project`` instead of the one found from the working directory."""
    global _PROJECT
    _PROJECT = project
