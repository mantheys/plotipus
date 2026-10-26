"""Pieces every plot kind uses: parser, setup and per-figure grouping.

A kind module defines ``build_parser()`` and ``run(args)``; :func:`main`
parses ``argv``, loads the project (style, plugins) and calls ``run``.
"""

import argparse
import sys

import matplotlib

from .. import registry
from .. import style
from ..args import add_common_args, add_media_args, parse_media_args, with_medium
from ..encodings import setup_legend_frame
from ..io import prepare_import
from ..project import apply_rendering, load_project


def make_parser(kind, description):
    parser = argparse.ArgumentParser(prog=f"plotipus {kind}", description=description)
    parser.set_defaults(kind=kind)
    for flags, kwargs in registry.arguments:
        parser.add_argument(*flags, **kwargs)
    return parser


def add_output_args(parser):
    add = parser.add_argument
    add("--output_suffix", type=str, default=None,
        help="Last part of the output file name (default: the kind, e.g. 'line.png').")
    add("--filename_prefix", type=str, default=None, help="First part of the output file name.")
    add("--format", type=str, default=None, help="File format when --output_suffix has no extension (default png).")
    add("--show", action="store_true", default=False, help="Keep figures open (interactive use).")
    add_media_args(parser)
    add("--sci_in_label", action="store_true", default=None,
        help="Put a common power of ten in the axis label, e.g. 'Density (x10^-2)' (default: the style's "
        "plot_settings.sci_in_label, true).")
    add("--no-sci_in_label", dest="sci_in_label", action="store_false",
        help="Keep matplotlib's offset text at the end of the axis.")


def main(module, argv=None):
    # The project (style) loads first: options such as --legend_loc adjust
    # the loaded style while the arguments are parsed. --medium/--theme/
    # --width/--aspect pick the style, so they are read before that.
    argv = list(sys.argv[1:] if argv is None else argv)
    media = parse_media_args(argv)
    project = load_project()
    if media.medium == "all":
        outputs = []
        for medium in project.all_media():
            outputs += main(module, with_medium(argv, medium)) or []
        return outputs
    if all(getattr(media, k) is None for k in ("medium", "theme", "width", "aspect")):
        return _run(module, argv)
    saved, rendering = style.snapshot(), project.rendering
    try:
        try:
            apply_rendering(media.medium, media.theme, media.width, media.aspect)
        except ValueError as error:
            module.build_parser().error(str(error))
        return _run(module, argv)
    finally:
        style.restore(saved)
        project.rendering = rendering


def _run(module, argv):
    parser = module.build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "show", False):
        matplotlib.use("Agg")
    setup_legend_frame(args)
    return module.run(args)


def figure_groups(df, args, overlay=False):
    """``[(index, config, name, rows)]``: one entry per --configs/--names pair
    (rows of that pair), or a single entry with every row when ``overlay``
    (or when neither option is given)."""
    configs, names = prepare_import(args)
    if overlay or configs is None:
        # The output name of an overlaid figure carries the first config/name
        # unless --overlay_name_all asks for all of them.
        index = None if getattr(args, "overlay_name_all", False) or configs is None else 0
        return [(index, None, None, df)]
    groups = []
    for kdx, (config, name) in enumerate(zip(configs, names)):
        mask = None
        if config is not None and "Config" in df.columns:
            mask = df["Config"] == config
        if name is not None and "Name" in df.columns:
            name_mask = df["Name"] == name
            mask = name_mask if mask is None else mask & name_mask
        groups.append((kdx, config, name, df if mask is None else df[mask]))
    return groups


__all__ = ["add_common_args", "add_output_args", "figure_groups", "main", "make_parser"]
