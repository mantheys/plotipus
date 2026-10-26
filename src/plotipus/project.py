"""Project settings from ``plotipus.toml``.

The file is looked up from the working directory upwards; without one the
working directory is the project root and every setting has its default::

    [project]
    data_root = "input/data"        # root of relative --path values
    plots = "input/plots"           # command lists: <list>_scripts.txt
    tables = "input/tables"
    output = "output"               # default output/plots, output/tables
    style = ["config/style.json"]   # style files merged over the defaults
                                    # (.json, or a matplotlib .mplstyle)
    plugins = ["my_project.plotipus_plugin"]
    python_path = ["src"]           # added to sys.path before plugins load
    medium = "slides"               # slides | paper | web (default: none, the old look)
    media = ["slides", "paper"]     # what --medium all / plotipus run render
    theme = "light"                 # light | dark
    language = "plotipus"           # the visual language (style layer, T16)

    [outputs.plots]                 # extra -o targets per command list
    solar = ["../THESIS/figures/solar"]

    [outputs.tables]
    thesis = ["../THESIS/tables"]

    [settings]
    default_operation = "mean"

A medium and theme select style layers by name: ``<language>``,
``<medium>`` and ``dark`` from ``plotipus/data/styles/`` (missing layers
are skipped), then the project's ``style`` files, which have the last
word, then ``--width``/``--aspect``. Without a medium anywhere no layer
applies (the look before media existed). The project's own medium and
theme write to ``output/plots``; any other pair writes to
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
    language: str = DEFAULT_LANGUAGE
    styles: list = field(default_factory=list)
    rendering: "Rendering" = None
    _base_style: tuple = None

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

    def output_folder(self, medium, theme):
        """Sub-folder of a medium/theme pair below the plot outputs: none for
        the project's own pair, else ``<medium>`` (+ ``-dark``)."""
        medium = medium or self.medium or DEFAULT_MEDIUM
        theme = theme or self.theme or DEFAULT_THEME
        if (medium, theme) == (self.medium or DEFAULT_MEDIUM, self.theme or DEFAULT_THEME):
            return None
        return medium + ("-dark" if theme == "dark" else "")

    def layers(self, medium, theme):
        """Style layers of a medium/theme pair: [(name, path)] of the named
        layers found in plotipus/data/styles, then the project style files."""
        names = []
        if medium is not None:
            names += [self.language, medium]
        if theme == "dark":
            names.append("dark")
        named = [(n, style.STYLES_DIR / f"{n}.json") for n in names if (style.STYLES_DIR / f"{n}.json").exists()]
        return named + [(Path(s).name, self._resolve(s)) for s in self.styles]


@dataclass
class Rendering:
    """The medium, theme and figure size a command draws at."""
    medium: str
    theme: str
    width: float
    height: float
    layers: list
    folder: str

    def describe(self):
        size = f"{self.width:g} x {self.height:g} in" if self.width else "classic size"
        layers = ", ".join(name for name, _ in self.layers) or "none"
        return (f"medium={self.medium or 'none'} theme={self.theme} width={size} layers=[{layers}]"
                + (f" -> plots/{self.folder}" if self.folder else ""))


def _check(value, allowed, option):
    if value is not None and value not in allowed:
        raise ValueError(f"{option} must be one of {', '.join(allowed)} (got '{value}').")
    return value


def apply_rendering(medium=None, theme=None, width=None, aspect=None, project=None):
    """Apply the style layers of a medium/theme pair (default: the
    project's) and the --width/--aspect overrides; returns the Rendering."""
    project = project or load_project()
    medium = _check(medium or project.medium, MEDIA, "--medium")
    theme = _check(theme or project.theme or DEFAULT_THEME, THEMES, "--theme")
    if project._base_style is None:  # a project set with set_project()
        project._base_style = style.snapshot()
    style.restore(project._base_style)
    layers = project.layers(medium, theme)
    for _, path in layers:
        style.configure(path)
    if width is not None or aspect is not None:
        style.set_geometry(width=width, aspect=aspect)
    project.rendering = Rendering(medium, theme, style.figure_width, style.figure_row_height, layers,
                                  project.output_folder(medium, theme))
    return project.rendering


def describe_rendering(medium=None, theme=None, width=None, aspect=None, project=None):
    """The Rendering a command would get, without changing the current style."""
    project = project or load_project()
    saved = style.snapshot()
    try:
        return apply_rendering(medium, theme, width, aspect, project)
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
        language=section.get("language", DEFAULT_LANGUAGE),
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

    styles = section.get("style", [])
    project.styles = [styles] if isinstance(styles, str) else list(styles)
    project._base_style = style.snapshot()
    apply_rendering(project=project)
    return project


def set_project(project):
    """Use ``project`` instead of the one found from the working directory."""
    global _PROJECT
    _PROJECT = project
