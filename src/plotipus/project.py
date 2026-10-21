"""Project settings from ``plotipus.toml``.

The file is looked up from the working directory upwards; without one the
working directory is the project root and every setting has its default::

    [project]
    data_root = "input/data"        # root of relative --path values
    plots = "input/plots"           # command lists: <list>_scripts.txt
    tables = "input/tables"
    output = "output"               # default output/plots, output/tables
    style = ["config/style.json"]   # style files merged over the defaults
    plugins = ["my_project.plotipus_plugin"]
    python_path = ["src"]           # added to sys.path before plugins load

    [outputs.plots]                 # extra -o targets per command list
    solar = ["../THESIS/figures/solar"]

    [outputs.tables]
    thesis = ["../THESIS/tables"]

    [settings]
    default_operation = "mean"
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

    def output_paths(self, kind, list_name):
        """Extra output directories configured for a command list."""
        paths = self.outputs.get(kind, {}).get(list_name) or []
        if isinstance(paths, str):
            paths = [paths]
        return [str(self._resolve(p)) for p in paths]

    def _resolve(self, value):
        path = Path(value).expanduser()
        return path if path.is_absolute() else self.root / path


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
    for style_file in [styles] if isinstance(styles, str) else styles:
        style.configure(project._resolve(style_file))

    return project


def set_project(project):
    """Use ``project`` instead of the one found from the working directory."""
    global _PROJECT
    _PROJECT = project
