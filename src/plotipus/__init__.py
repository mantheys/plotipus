"""plotipus: publication plots and tables from pickled pandas DataFrames.

Command line: ``plotipus <kind> [options]`` draws one figure (kinds: line,
scatter, hist, map, cat, table) and ``plotipus run <list>`` runs a list of
such commands. From Python, the same building blocks are importable::

    from plotipus import style, load_frame, plot_data, create_common_subplots
"""

__version__ = "0.1.0"

from . import registry, style
from .format import format_value, format_with_band, format_with_error
from .io import import_data, read_frame as load_frame, save_figure_to_paths, write_parquet_frame as save_frame
from .plot import (
    add_centered_suptitle,
    apply_legend_style,
    apply_legend_style_clear_of_data,
    apply_note_to_figure,
    create_common_subplots,
    create_common_two_panel_figure,
    draw_horizontal_lines,
    draw_vertical_lines,
    plot_data,
)
from .project import load_project


def plot(kind, *argv):
    """Run a plot kind from Python with command-line arguments, e.g.
    ``plotipus.plot("line", "--datafile", "Example", "-x", "E", "-y", "N")``."""
    from .legacy import kind_module

    argv = list(argv[0]) if len(argv) == 1 and isinstance(argv[0], (list, tuple)) else list(argv)
    return kind_module(kind).main(argv)


__all__ = [
    "add_centered_suptitle",
    "apply_legend_style",
    "apply_legend_style_clear_of_data",
    "apply_note_to_figure",
    "create_common_subplots",
    "create_common_two_panel_figure",
    "draw_horizontal_lines",
    "draw_vertical_lines",
    "format_value",
    "format_with_band",
    "format_with_error",
    "import_data",
    "load_frame",
    "load_project",
    "plot",
    "plot_data",
    "registry",
    "save_figure_to_paths",
    "save_frame",
    "style",
]
