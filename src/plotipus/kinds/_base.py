"""Pieces every plot kind uses: parser, setup and per-figure grouping.

A kind module defines ``build_parser()`` and ``run(args)``; :func:`main`
parses ``argv``, loads the project (style, plugins) and calls ``run``.
"""

import argparse

import matplotlib

from .. import registry
from ..args import add_common_args
from ..encodings import setup_legend_frame
from ..io import prepare_import
from ..project import load_project


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
    add("--sci_in_label", action="store_true", default=None,
        help="Put a common power of ten in the axis label, e.g. 'Density (x10^-2)' (default: the style's "
        "plot_settings.sci_in_label, true).")
    add("--no-sci_in_label", dest="sci_in_label", action="store_false",
        help="Keep matplotlib's offset text at the end of the axis.")


def main(module, argv=None):
    # The project (style) loads first: options such as --legend_loc adjust
    # the loaded style while the arguments are parsed.
    load_project()
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
