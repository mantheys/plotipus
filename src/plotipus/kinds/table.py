"""table: aggregate --y per row group and column into a LaTeX (and HTML) table.

Rows are the loaded configurations (``Config``, optionally preceded by a
``--row_group`` column and followed by ``--row_name``); columns are the
values of ``--variable_name`` (default ``Variable``) listed in
``--variables``, optionally grouped by ``--column_group``. Each cell is the
``--agg`` (mean/sum) of --y over its rows, formatted with its propagated
error (``{y}Error``), a percentile band (``--error_band``) or alone.
"""

import html
import os
from pathlib import Path

import numpy as np
import pandas as pd
from rich import print as rprint

from .. import registry, style
from ..args import add_common_args
from ..format import format_value, format_with_band, format_with_error
from ..io import import_data, make_name_from_args, save_table_to_paths
from ..project import load_project
from ..selection import filter_dataframe
from . import _base

KIND = "table"
X_THRESHOLD_COLUMN = "XThreshold"


def build_parser():
    parser = _base.make_parser(KIND, "Aggregate --y into a LaTeX/HTML table (rows: configs, columns: --variables).")
    add_common_args(
        parser,
        ["datafile", "configs", "names", "variables", "iterable", "select", "save_values", "remove_value",
         "filename_select", "x", "rangex", "y", "output", "debug"],
        overrides={
            "names": {"flags": ["--names"]},
            "variables": {"flags": ["--variables", "-v"], "help": "Values of --variable_name shown as columns"},
            "debug": {"flags": ["--debug"]},
        },
    )
    add = parser.add_argument

    group = parser.add_argument_group("layout")
    add = group.add_argument
    add("--variable_title", "-t", "--labely", type=str, default=None,
        help="Display name of --y used as the column group header")
    add("--variable_name", "-n", type=str, default=None,
        help="Column pivoted into the table columns (default 'Variable', or 'Particle' with --name_columns)")
    add("--row_group", type=str, default=None,
        help="Column shown in front of Config in the row labels (e.g. one built with --derive_column)")
    add("--derive_column", nargs="+", default=None, metavar="NAME=prefix:SOURCE[:upper]",
        help="Add column NAME (when missing) from the text of SOURCE before the first '_'; ':upper' upper-cases NAME")
    add("--add_column", nargs="+", default=None, metavar="HOOK[=COLUMN]",
        help="Add a column with a plugin builder (registry.table_columns)")
    add("--rename_names", nargs="+", default=None,
        help="OLD=NEW pairs renaming samples (Name column and --names) so they are tabulated as one")
    add("--name_columns", action="store_true", help="Rows = configs, columns = names (sample prefix)")
    add("--row_name", "-r", type=str, default=None, help="Extra row-index column (e.g. Stage)")
    add("--row_name_mapping", type=str, default=None, help="Mapping renaming/ordering the --row_name values")
    add("--drop_config", action="store_true", help="Rows keyed only by --row_name")
    add("--x_thresholds", nargs="+", type=float, default=None,
        help="One row per threshold, keeping x >= each value (upper edge from --rangex)")
    add("--x_threshold_mode", choices=["lower", "exact"], default="lower",
        help="'lower': x >= threshold; 'exact': x == threshold")
    add("--x_threshold_label", type=str, default="{:g}", help="Format of the threshold row labels")
    add("--x_threshold_title", type=str, default="Threshold", help="Header of the threshold column")
    add("--column_group", type=str, default=None, help="Second column key: one group of columns per value")
    add("--column_group_order", nargs="+", type=str, default=None, help="--column_group values kept, in order")
    add("--column_group_titles", nargs="+", type=str, default=None, help="Titles of the --column_group_order values")
    add("--column_group_drop", nargs="+", type=str, default=None, metavar="GROUP=VARIABLE",
        help="Columns left out of one group only")
    add("--row_order", nargs="+", type=str, default=None, help="Order of the --row_name values inside each block")
    add("--block_rows", action="store_true", help="Blocked booktabs layout, config label on the first row of each block")
    add("--variable_titles", nargs="+", type=str, default=None, help="Titles of the --variables columns (with --column_group)")
    add("--row_titles", nargs="+", type=str, default=None, help="Titles of the --row_order values")
    add("--variable_units", nargs="+", type=str, default=None, help="Unit appended to each --variables column title")
    add("--variable_mapping", type=str, default=None, help="Mapping renaming/ordering the column titles")
    add("--label_mapping", type=str, default=None, help="Mapping applied to the row labels of the first column")
    add("--row_name_title", type=str, default=None, help="Header of the --row_name column with --block_rows")
    add("--first_header", type=str, default=None, help="Header of the first (row label) column")
    add("--emph", type=int, default=None, help="Index of the column wrapped in \\emph")
    add("--it", type=int, default=None, help="Index of the column wrapped in \\textit")

    group = parser.add_argument_group("values")
    add = group.add_argument
    add("--agg", choices=["mean", "sum"], default="mean", help="Aggregation of --y within each cell")
    add("--error_mode", choices=["quadrature", "linear", "std", "sem", "max"], default="quadrature",
        help="How per-row errors combine: quadrature (independent), linear (correlated), max, or std/sem "
        "of the raw --y values")
    add("--error_column", type=str, default=None, help="Column holding the --y error when not '{y}Error'")
    add("--no_error", action="store_true", help="Show values without errors")
    add("--error_band", nargs=2, default=None, metavar=("LOW", "HIGH"),
        help="Columns of a band shown as 'value (LOW--HIGH)'")
    add("--error_band_variables", nargs="+", default=None, metavar="VARIABLE", help="Variables shown with the band")
    add("--band_fallback", default=None, metavar="COLUMN", help="Column shown when the band collapses")
    add("--band_fallback_unit", default=None, help="siunitx unit of --band_fallback")
    add("--band_fallback_mark", default=None, help="Math-mode mark after --band_fallback entries")
    add("--count_column", type=str, default=None, help="Column summed per cell and shown in parentheses")
    add("--derived_variable", nargs="+", default=None, metavar="NEW=SOURCE/DIVISOR",
        help="Column NEW = column SOURCE / DIVISOR")
    add("--melt", nargs="+", default=None, metavar="COLUMN",
        help="Wide input: these scalar columns become rows (name in --variable_name, value in --y)")
    add("--multiply", type=float, default=None, help="Scale --y (and errors) by this factor")
    add("--multiply_variable", nargs="+", default=None, metavar="VARIABLE=FACTOR", help="Scale one variable")
    add("--multiply_row", nargs="+", type=float, default=None, help="Per-config scale factors (matching --configs)")
    add("--missing", type=str, default=None, help="Text of empty cells (default NaN)")
    add("--decimals", type=int, default=None, help="Decimals of values without error (default 2)")
    add("--sig_figs", type=int, default=None, help="Significant figures of values without error")
    add("--threshold", type=float, default=1e-3, help="Values below this magnitude print as '---'")
    add("--zero_error_plain", action="store_true", help="Values with zero error print bare")
    add("--scientific", action="store_true", help="Always use scientific notation")
    add("--scientific_threshold_low", type=float, default=None)
    add("--scientific_threshold_high", type=float, default=None)
    add("--compact_error", action="store_true", help="value(error) notation for plain values")
    add("--compact_scientific", action="store_true", help="value(error) notation for scientific values")
    add("--siunitx", action="store_true", help="Wrap values in \\num{}")

    group = parser.add_argument_group("output")
    add = group.add_argument
    add("--title", type=str, default=None, help="Title row (and caption when --caption is not given)")
    add("--caption", type=str, default=None, help="LaTeX caption (wraps the tabular in --table_env)")
    add("--caption_file", type=str, default=None,
        help="Caption read from a file (path, or name in the project's captions_dir setting)")
    add("--header_title", type=str, default=None, help="Title row above \\toprule")
    add("--label", type=str, default=None, help="\\label after the caption")
    add("--table_env", type=str, default="table*", help="Float environment; 'none' writes only the tabular")
    add("--bare", action="store_true", help="Shorthand for --table_env none")
    add("--no_table", action="store_true", help="Drop the \\begin/\\end{table} lines")
    add("--no_tabular", action="store_true", help="Also drop the \\begin/\\end{tabular} lines")
    add("--output_name", type=str, default=None, help="Fixed output file name")
    add("--html", action="store_true", help="Also write an HTML table")
    return parser


def main(argv=None):
    return _base.main(__import__(__name__, fromlist=["run"]), argv)


# --- Helpers -------------------------------------------------------------------------


def _mapping(name):
    return style.get_mapping_dict(name) or {} if name else {}


def resolve_caption_file(value):
    """Caption text from a path, or from ``<captions_dir>/<name>.txt``."""
    candidates = [value] if value.endswith(".txt") else [value, f"{value}.txt"]
    for candidate in candidates:
        if os.path.exists(candidate):
            return Path(candidate).read_text().strip()
    project = load_project()
    captions = project._resolve(project.settings.get("captions_dir", "input/captions"))
    for candidate in candidates:
        path = captions / os.path.basename(candidate)
        if path.exists():
            return path.read_text().strip()
    print(f"Caption file not found: {value}")
    return None


def trim_environment_lines(text, no_table, no_tabular):
    """Drop the \\begin/\\end{table} (and with ``no_tabular`` {tabular}) lines."""
    kept = []
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if no_table and stripped.startswith(("\\begin{table", "\\end{table")):
            continue
        if no_tabular and stripped.startswith(("\\begin{tabular", "\\end{tabular")):
            continue
        kept.append(line)
    return "".join(kept)


def derive_columns(df, specs):
    """``NAME=prefix:SOURCE[:upper]``: NAME from the text of SOURCE before '_'."""
    for spec in specs or []:
        name, _, rule = spec.partition("=")
        parts = rule.split(":")
        if parts[0] != "prefix" or len(parts) < 2:
            raise ValueError(f"Invalid --derive_column '{spec}' (expected NAME=prefix:SOURCE[:upper])")
        if name not in df.columns:
            df[name] = df[parts[1]].str.split("_").str[0]
        if "upper" in parts[2:]:
            df[name] = df[name].str.upper()
    return df


def _scale(values, factors):
    return [np.asarray(v) * f if v is not None else v for v, f in zip(values, factors)]


def _melt(df, args):
    """Scalar columns of --melt become rows (array cells of --x and the band carried along)."""
    is_array = {c: df[c].map(lambda v: isinstance(v, (list, tuple, np.ndarray))).any() for c in df.columns}
    carried = [c for c in [args.x, *(args.error_band or [])] if c in df.columns and c not in args.melt]
    scalar_cols = [c for c in df.columns if c not in args.melt and not is_array[c]]
    df = df.melt(id_vars=scalar_cols + carried, value_vars=args.melt, var_name=args.variable_name, value_name=args.y)
    hashable = [c for c in df.columns if c != "Signal" and c != args.y and not is_array.get(c, False)]
    if any(is_array.values()):
        return df.drop_duplicates(subset=hashable + [args.variable_name])
    return df.drop_duplicates(subset=[c for c in df.columns if c != "Signal"] if "Signal" in df.columns else None)


def _error_aggregator(args):
    if args.error_mode == "std":
        return lambda x: np.std(x, ddof=1) if len(x) > 1 else 0.0
    if args.error_mode == "sem":
        return lambda x: np.std(x, ddof=1) / np.sqrt(len(x)) if len(x) > 1 else 0.0
    if args.error_mode == "linear":
        return (lambda x: np.sum(x)) if args.operation == "sum" else (lambda x: np.sum(x) / len(x))
    if args.error_mode == "max":
        return lambda x: np.max(x)
    if args.operation == "sum":
        return lambda x: np.sqrt(np.sum(x**2))
    return lambda x: np.sqrt(np.sum(x**2)) / len(x)


def _row_label(x, group, show_group, show_config):
    """Row label of a (group, Config) index entry: group, config or both."""
    if not group:
        return f"{x}"
    if show_group and show_config:
        return f"{x[0]} {x[1]}"
    return f"{x[0]}" if show_group else f"{x[1]}"


# --- Table ---------------------------------------------------------------------------


def build_table(df, args):
    """The formatted table as a DataFrame (header levels as columns)."""
    config_dict = _mapping("config_dict")
    group = args.row_group
    n_configs, n_names = len(args.configs or []), len(args.names or [])

    if args.name_columns:
        # Config stays the configuration; Particle is the sample prefix of Name.
        df["Config"] = df["Config"].map(lambda x: config_dict.get(x, x))
        df["Particle"] = df["Name"].str.split("_").str[0]
    elif n_names <= 1:
        df["Config"] = df["Config"].map(lambda x: config_dict.get(x, x))
    else:
        particle_dict = _mapping("particle_dict")
        df["Config"] = df["Name"].str.split("_").str[0].map(lambda x: particle_dict.get(x, x))

    if args.variables is None:
        if args.name_columns:
            args.variables = sorted(df[args.variable_name].unique().tolist())
        else:
            args.variables = [""]
            df[args.variable_name] = ""
    # NaN pivot values are dropped unless --variables asks for "None".
    if "None" in args.variables:
        df[args.variable_name] = df[args.variable_name].fillna("None")

    subset = filter_dataframe(df, args)
    group_values = []
    if args.column_group:
        group_values = args.column_group_order or sorted(subset[args.column_group].dropna().unique())
        subset = subset[subset[args.column_group].isin(group_values)]

    y, y_error = args.y, f"{args.y}Error"
    cols = [args.x, y] if args.x is not None else [y]
    if y_error in subset.columns:
        cols.append(y_error)
    if f"{args.x}Error" in subset.columns:
        cols.append(f"{args.x}Error")
    band_columns = [*(args.error_band or []), *([args.band_fallback] if args.band_fallback else [])]
    cols.extend(band_columns)
    if args.count_column:
        cols.append(args.count_column)

    lead = [group] if group else []
    row_index = ([args.row_name] if args.row_name else []) if args.drop_config else lead + ["Config"] + ([args.row_name] if args.row_name else [])
    if args.x_thresholds is not None:
        row_index = row_index + [X_THRESHOLD_COLUMN]
    custom_rows = bool(args.row_name) or args.drop_config or args.x_thresholds is not None

    points = subset.explode(column=cols).dropna(subset=cols + [args.variable_name])

    if args.x_thresholds is not None and args.x is not None:
        points[args.x] = points[args.x].astype(float)
        upper = args.rangex[1] if args.rangex is not None else np.inf
        print(f"Applying x-axis thresholds {args.x_thresholds} (upper edge {upper})")
        parts = []
        for threshold in args.x_thresholds:
            if args.x_threshold_mode == "exact":
                keep = np.isclose(points[args.x], threshold)
            else:
                keep = (points[args.x] >= threshold) & (points[args.x] <= upper)
            part = points[keep].copy()
            part[X_THRESHOLD_COLUMN] = threshold
            parts.append(part)
        points = pd.concat(parts, ignore_index=True)
    elif args.rangex is not None and args.x is not None:
        points[args.x] = points[args.x].astype(float)
        print(f"Applying x-axis range filter: {args.rangex[0]} to {args.rangex[1]}")
        points = points[(points[args.x] >= args.rangex[0]) & (points[args.x] <= args.rangex[1])]

    variable_column = args.variable_name if args.variable_name in points.columns else "Variable"
    for item in args.multiply_variable or []:
        variable, factor = item.rsplit("=", 1)
        mask = points[variable_column].astype(str) == variable
        for column in [y, *([y_error] if y_error in points.columns else []), *(args.error_band or [])]:
            points.loc[mask, column] = points.loc[mask, column] * float(factor)

    if args.derived_variable:
        extra = []
        for item in args.derived_variable:
            new_name, ratio = item.split("=", 1)
            source, divisor = ratio.rsplit("/", 1)
            part = points[points[variable_column].astype(str) == source].copy()
            part[variable_column] = new_name
            part[y] = part[y] / float(divisor)
            if y_error in part.columns:
                part[y_error] = part[y_error] / float(divisor)
            extra.append(part)
        points = pd.concat([points, *extra], ignore_index=True)

    if args.multiply is not None:
        points[y] = points[y] * args.multiply
        for band_column in args.error_band or []:
            points[band_column] = points[band_column] * args.multiply
        if y_error in points.columns:
            points[y_error] = points[y_error] * args.multiply

    keys = row_index + ([args.column_group] if group_values else []) + [args.variable_name]
    from_spread = args.error_mode in ("std", "sem")
    has_error = (y_error in points.columns or from_spread) and not args.no_error
    op = args.operation
    if args.error_band and not args.no_error:
        table = points.groupby(keys).agg({column: [op] for column in [y, *band_columns]})
        band_variables = args.error_band_variables
        table[y] = table.apply(
            lambda row: format_with_band(row, args=args)
            if band_variables is None or row.name[-1] in band_variables
            else format_value(row, args=args),
            axis=1,
        )
        table = table.drop(columns=[(column, op) for column in band_columns])
    elif has_error:
        if from_spread:
            # The error comes from the spread of --y itself.
            points[y_error] = points[y]
        table = points.groupby(keys).agg({y: [op], y_error: _error_aggregator(args)})
        table[y] = table.apply(lambda row: format_with_error(row, args=args), axis=1)
        table = table.drop(columns=[(y_error, "<lambda>")])
    else:
        table = points.groupby(keys).agg({y: [op]})
        table[y] = table.apply(lambda row: format_value(row, args=args), axis=1)
    table.columns = table.columns.droplevel(1)

    if args.count_column:
        counts = points.groupby(keys)[args.count_column].sum().reindex(table.index).fillna(0).astype(int)
        number = (lambda n: f"\\num{{{n}}}") if args.siunitx else str
        table[y] = [f"{value} ({number(n)})" if n > 0 else "--" for value, n in zip(table[y], counts)]

    if group_values:
        table = table.reset_index()
        group_key = [args.column_group, args.variable_name]
    else:
        group_key = args.variable_name
    value_name = args.variable_title if args.variable_title is not None else y
    table = table.rename(columns={y: value_name}).pivot_table(
        index=row_index, columns=group_key, values=[value_name], aggfunc="first"
    )

    # Row labels from the (group, Config) index, unless the layout is custom.
    if not custom_rows:
        if args.name_columns:
            show = (False, True) if n_configs <= 2 else (True, True)
        elif n_names <= 1:
            show = (True, False) if n_configs <= 2 else (True, True)
        elif n_configs == 1:
            show = (False, True)
        else:
            show = (True, True)
        table.index = table.index.map(lambda x: _row_label(x, group, *show))
        table.index.name = "Particle" if n_names > 1 and not args.name_columns else "Configuration"

    if args.x_thresholds is not None:
        label = args.x_threshold_label.format
        if isinstance(table.index, pd.MultiIndex):
            level = table.index.names.index(X_THRESHOLD_COLUMN)
            table.index = table.index.set_levels([label(v) for v in table.index.levels[level]], level=level)
        else:
            table.index = table.index.map(label)
        table.index.names = [args.x_threshold_title if n == X_THRESHOLD_COLUMN else n for n in table.index.names]

    if args.row_name and args.row_name_mapping:
        # Rename the --row_name values and order them like the mapping keys.
        row_mapping = _mapping(args.row_name_mapping)
        is_multi = isinstance(table.index, pd.MultiIndex)
        present = list(dict.fromkeys(table.index.get_level_values(args.row_name) if is_multi else table.index))
        ordered = [v for v in row_mapping if v in present] + [v for v in present if v not in row_mapping]
        if is_multi:
            table = table.reindex(ordered, level=args.row_name).rename(index=row_mapping, level=args.row_name)
        else:
            table = table.reindex(ordered).rename(index=row_mapping)

    if group_values:
        wanted = pd.MultiIndex.from_tuples(
            [(table.columns.get_level_values(0)[0], g, v) for g in group_values for v in args.variables]
        )
        table = table.reindex(columns=wanted)
    else:
        table = table.reindex(columns=args.variables, level=1)

    variable_mapping = _mapping(args.variable_mapping) if not group_values else {}
    if variable_mapping:
        present = list(dict.fromkeys(table.columns.get_level_values(1)))
        ordered = [v for v in variable_mapping if v in present] + [v for v in present if v not in variable_mapping]
        table = table.reindex(columns=ordered, level=1)

    if not custom_rows:
        if n_configs == 1 and n_names > 1 and not args.name_columns:
            table = table.reindex(style.mappings.get("particle_order", []), level="Particle")
        if (n_configs > 2 and n_names == 1) or (args.name_columns and n_configs > 2):
            table = table.reindex(style.mappings.get("config_order", []), level="Configuration")

    # Column titles: --variable_mapping, then component names (--name_columns), then units.
    units = dict(zip(args.variables, args.variable_units)) if args.variable_units is not None else {}
    if (variable_mapping or args.name_columns or units) and not group_values:
        component = _mapping("component")

        def _display(raw):
            if raw in variable_mapping:
                label = variable_mapping[raw]
            elif args.name_columns and isinstance(raw, str):
                label = component.get(raw, raw.capitalize())
            else:
                label = raw
            unit = units.get(raw)
            return f"{label} ({unit})" if unit else label

        table.columns = pd.MultiIndex.from_tuples([(c[0], _display(c[1])) for c in table.columns])

    table = table.dropna(how="all")
    if args.missing is not None:
        table = table.fillna(args.missing)

    if args.block_rows and (args.row_name or args.x_thresholds is not None):
        # Blocks follow --configs, rows inside a block follow --row_order.
        config_rank = {config_dict.get(c, c): i for i, c in enumerate(args.configs or [])}
        row_rank = {v: i for i, v in enumerate(args.row_order or [])}
        order = [
            (config_rank.get(idx[-2], len(config_rank)), row_rank.get(idx[-1], len(row_rank)), idx[-1] if args.row_name else i)
            for i, idx in enumerate(table.index)
        ]
        table = table.iloc[sorted(range(len(order)), key=order.__getitem__)]
    elif args.melt:
        # Melted tables: rows follow --configs (labels may start with the group).
        names = [str(config_dict.get(c, c)) for c in args.configs or []]

        def _rank(idx):
            label = str(idx[-1] if isinstance(idx, tuple) else idx)
            return next((i for i, n in enumerate(names) if label == n or label.endswith(" " + n)), len(names))

        order = [_rank(idx) for idx in table.index]
        table = table.iloc[sorted(range(len(order)), key=order.__getitem__)]

    table = table.reset_index()

    if group_values:
        if args.column_group_drop:
            drop = {tuple(item.split("=", 1)) for item in args.column_group_drop}
            table = table[[c for c in table.columns if (c[1], c[2]) not in drop]]
        titles = dict(zip(group_values, args.column_group_titles or group_values))
        variable_titles = dict(zip(args.variables, args.variable_titles or args.variables))
        table.columns = pd.MultiIndex.from_tuples(
            [(titles.get(c[1], c[1]), variable_titles.get(c[2], c[2])) if c[1] != "" else (c[0], "") for c in table.columns]
        )

    if args.row_titles and args.row_order and args.row_name:
        row_titles = dict(zip(args.row_order, args.row_titles))
        for col in table.columns:
            if col[0] == args.row_name:
                table[col] = table[col].map(lambda v: row_titles.get(v, v))
    return table


def blocked_tabular(table, args, label_mapping, n_group):
    """Booktabs tabular with one block of rows per configuration; the first
    ``n_group`` columns form the block label (shown on its first row)."""
    cols = list(table.columns)
    n_lead = sum(1 for c in cols if c[1] == "")
    value_cols = cols[n_lead:]
    groups = []
    for c in value_cols:
        if groups and groups[-1][0] == c[0]:
            groups[-1][1] += 1
        else:
            groups.append([c[0], 1])
    lines = [f"\\begin{{tabular}}{{ll{'c' * len(value_cols)}}}", "\\toprule"]
    # No group row when every value column sits under one empty title.
    if not (len(groups) == 1 and not str(groups[0][0]).strip()):
        lines.append(" & " + "".join(f" & \\multicolumn{{{n}}}{{c}}{{{t}}}" for t, n in groups) + " \\\\")
    lines.append(" & ".join(["Configuration", str(args.row_name_title or args.row_name)] + [c[1] for c in value_cols]) + " \\\\")
    lines.append("\\midrule")
    previous = None
    for _, row in table.iterrows():
        block = tuple(row.iloc[:n_group])
        first = " ".join(str(v) for v in block)
        first = label_mapping.get(first, first)
        if block == previous:
            first = ""
        elif previous is not None:
            lines.append("\\addlinespace")
        previous = block
        name = str(row.iloc[n_group])
        cells = [first, label_mapping.get(name, name)] + [str(v) for v in row.iloc[n_lead:]]
        lines.append(" & ".join(cells) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    return "\n".join(lines) + "\n"


HTML_TEMPLATE = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {
                    font-family: Arial, sans-serif;
                    margin: 20px;
                }
                table {
                    border-collapse: collapse;
                    margin-top: 20px;
                }
                th, td {
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: center;
                }
                th {
                    background-color: #4CAF50;
                    color: white;
                }
                tr:nth-child(even) {
                    background-color: #f2f2f2;
                }
                tr:hover {
                    background-color: #ddd;
                }
                td:first-child, th:first-child {
                    text-align: left;
                }
            </style>
        </head>
        <body>
            <h1>TITLE</h1>
        TABLE
        </body>
        </html>
        """


def run(args):
    if args.bare:
        args.table_env = "none"
    # The formatters read the aggregation as ``operation``.
    args.operation = args.agg
    if args.variable_name is None:
        args.variable_name = "Particle" if args.name_columns else "Variable"

    df = import_data(args)
    if args.error_column and args.error_column in df.columns:
        df[f"{args.y}Error"] = df[args.error_column]
    if args.rename_names:
        rename = dict(pair.split("=", 1) for pair in args.rename_names)
        if "Name" in df.columns:
            df["Name"] = df["Name"].replace(rename)
        if args.names:
            args.names = list(dict.fromkeys(rename.get(n, n) for n in args.names))
    if df.empty:
        print("No data to plot. Exiting.")
        return None

    for spec in args.add_column or []:
        hook, _, column = spec.partition("=")
        if hook not in registry.table_columns:
            raise KeyError(f"No table column builder '{hook}' (available: {', '.join(registry.table_columns)})")
        df = registry.table_columns[hook](df, args, column or hook)
    if args.melt:
        df = _melt(df, args)
    if args.multiply_row is not None:
        # Per-config factors, keyed by the raw --configs values.
        factors = df["Config"].map(dict(zip(args.configs, args.multiply_row))).fillna(1.0)
        for column in [args.y, f"{args.y}Error", *(args.error_band or [])]:
            if column in df.columns:
                df[column] = _scale(df[column], factors)
    df = derive_columns(df, args.derive_column)

    table = build_table(df, args)
    print(table.to_string(index=False))

    label_mapping = _mapping(args.label_mapping)
    if label_mapping:
        table.iloc[:, 0] = table.iloc[:, 0].map(lambda v: label_mapping.get(v, v))
    if args.first_header is not None:
        first = table.columns[0]
        new_first = (args.first_header,) + tuple("" for _ in first[1:]) if isinstance(first, tuple) else args.first_header
        table.columns = [new_first] + list(table.columns[1:])
        if isinstance(first, tuple):
            table.columns = pd.MultiIndex.from_tuples(table.columns)
    if args.it is not None and 0 <= args.it < table.shape[1]:
        table.iloc[:, args.it] = "\\textit{" + table.iloc[:, args.it] + "}"
    if args.emph is not None and 0 <= args.emph < table.shape[1]:
        table.iloc[:, args.emph] = "\\emph{" + table.iloc[:, args.emph] + "}"

    filename = args.output_name or make_name_from_args(args, prefix=None, suffix="table.tex")
    if args.table_env == "none":
        filename = filename.replace(".tex", "_tabular.tex")
    elif args.no_tabular:
        filename = filename.replace(".tex", "_no_tabular.tex")
    elif args.no_table:
        filename = filename.replace(".tex", "_no_table.tex")

    caption = args.caption
    if caption is None and args.caption_file is not None:
        caption = resolve_caption_file(args.caption_file)
    if caption is None:
        caption = args.title

    def write_latex(path):
        if args.block_rows:
            n_group = (1 if args.row_group else 0) + (0 if args.drop_config else 1)
            tabular = blocked_tabular(table, args, label_mapping, n_group)
        else:
            tabular = table.to_latex(index=False, column_format="l" + "c" * (table.shape[1] - 1),
                                     multicolumn_format="c", bold_rows=False, escape=False)
        width = table.shape[1]
        if args.header_title:
            tabular = tabular.replace("\\toprule\n", f"\\multicolumn{{{width}}}{{c}}{{{args.header_title}}} \\\\\n\\toprule\n", 1)
        if args.title:
            title_row = f"\\multicolumn{{{width}}}{{c}}{{{args.title}}} \\\\\n\\midrule\n"
            tabular = tabular.replace("\\toprule\n", "\\toprule\n" + title_row, 1)
        if caption is not None and args.table_env != "none":
            label = f"\\label{{{args.label}}}\n" if args.label else ""
            tabular = (f"\\begin{{{args.table_env}}}[t]\n{tabular}\\caption{{{caption}}}\n{label}"
                       f"\\end{{{args.table_env}}}\n")
        if args.no_table or args.no_tabular:
            tabular = trim_environment_lines(tabular, no_table=True, no_tabular=args.no_tabular)
        with open(path, "w") as handle:
            handle.write(tabular)

    save_table_to_paths(write_latex, args.output, filename)

    if args.html:
        content = (HTML_TEMPLATE.replace("TITLE", html.escape(args.title or "Table"), 1)
                   .replace("TABLE", table.to_html(index=False, border=0), 1))

        def write_html(path):
            with open(path, "w") as handle:
                handle.write(content)

        save_table_to_paths(write_html, args.output, make_name_from_args(args, prefix=None, suffix="table.html"))
    return filename


# --- Legacy command lines ------------------------------------------------------------


def _legacy_aggregate_table(tokens):
    from ..legacy import option_values, rename

    score = option_values(tokens, "--adjcl_selection_score")
    tokens = rename(tokens, {"--operation": "--agg", "--adjcl_selection_score": None, "--note": None})
    # The old script always built an upper-cased Geometry (config prefix) row level.
    tokens += ["--derive_column", "Geometry=prefix:Config:upper", "--row_group", "Geometry"]
    if score:
        tokens += ["--add_column", f"adjcl_selection_score={score[0]}"]
    return tokens


LEGACY = {"script_aggregate_table": _legacy_aggregate_table}
