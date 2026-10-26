"""Loading pickled DataFrames and saving figures/tables.

Input files are pickles of a DataFrame (or of anything ``pd.DataFrame`` can
build: a dict of DataFrames, a dict of scalars, a list of records). A
``--datafile`` entry is looked up as ``{config}_{name}_{entry}.pkl`` (or with
just one of the two prefixes) under the project's data root, or under
``--path`` (relative to the data root, or absolute). Plugins can add lookup
locations (``registry.resolvers``) and decorate loaded frames
(``registry.post_load_hooks``).
"""

import os
import pickle
from collections import Counter
from itertools import product
from pathlib import Path
from typing import Optional

import pandas as pd
from rich import print as rprint

from . import registry
from .project import current_rendering, load_project
from .selection import selection_pairs


# --- Loading -------------------------------------------------------------------


def _dataframe_from_pickle_payload(data):
    if isinstance(data, dict):
        if data and all(isinstance(value, pd.DataFrame) for value in data.values()):
            return pd.concat(data, names=["Source"]).reset_index(level=0)

        if data and all(not isinstance(value, (list, tuple, dict, pd.Series, pd.Index)) for value in data.values()):
            return pd.DataFrame([data])

    return pd.DataFrame(data)


def normalize_datafiles(datafile):
    if datafile is None:
        return []
    if isinstance(datafile, (list, tuple)):
        return list(datafile)
    return [datafile]


def resolve_input_data_dir(path_override=None):
    """``(directory, is_default)`` for a ``--path`` value: the project data
    root for None/'default', the value itself when absolute, else the value
    inside the data root."""
    default_input_dir = load_project().data_root

    if path_override is None:
        return default_input_dir, True

    raw_path = str(path_override).strip()
    if not raw_path or raw_path.lower() == "default":
        return default_input_dir, True

    resolved = Path(raw_path).expanduser()
    if resolved.is_absolute():
        return resolved, False

    return default_input_dir / resolved, False


def pair_paths_with_datafiles(path, datafiles):
    paths = normalize_datafiles(path)
    n = len(datafiles)
    if not paths:
        return [None] * n
    if len(paths) == 1:
        return paths * n
    if len(paths) == n:
        return paths

    rprint(
        f"[red]Error:[/red] --path was given {len(paths)} value(s) but --datafile "
        f"has {n} entr{'y' if n == 1 else 'ies'}. Provide a single --path value "
        "(applied to every file) or exactly one value per --datafile entry."
    )
    return None


def datafile_candidates(input_dir, prefix, entry, is_default=True):
    """Ordered candidate paths for ``{prefix}{entry}.pkl`` under ``input_dir``:
    plugin resolver candidates first, then the plain file."""
    input_dir = Path(input_dir)
    candidates = []

    def add(path):
        path = Path(path)
        if path not in candidates:
            candidates.append(path)

    for resolver in registry.resolvers:
        for path in resolver(entry, input_dir, prefix, is_default) or []:
            add(path)
    add(input_dir / f"{prefix}{entry}.pkl")
    return candidates


def bare_datafile_candidates(datafile, input_dir, is_default=True):
    """Candidates for a ``--datafile`` entry without config/name prefix: the
    entry as a path, then the lookups under ``input_dir``."""
    candidate = Path(datafile).expanduser()
    candidates = [candidate]
    if candidate.suffix == ".pkl":
        entry = candidate.stem
        candidates.append(Path(input_dir) / candidate.name)
    else:
        entry = candidate.name
    for path in datafile_candidates(input_dir, "", entry, is_default):
        if path not in candidates:
            candidates.append(path)
    return candidates


class _Unpickler(pickle.Unpickler):
    """Unpickler resolving functions stored by name (e.g. fit models pickled
    from a script's ``__main__``) through :func:`plotipus.fits.get_function`
    when their original module cannot provide them."""

    def find_class(self, module, name):
        try:
            return super().find_class(module, name)
        except (AttributeError, ImportError):
            from .fits import get_function

            function = get_function(name)
            if function is None:
                raise
            return function


def read_pickle_frame(path):
    """Load one pickle as a DataFrame (all-NaN columns dropped)."""
    with Path(path).open("rb") as handle:
        data = _Unpickler(handle).load()
    frame = _dataframe_from_pickle_payload(data)
    return frame.dropna(axis=1, how="all")


def _load_datafile(datafile, datafile_entry, input_dir):
    loaded_df = read_pickle_frame(datafile)
    if loaded_df.empty:
        return loaded_df

    loaded_df["_Datafile"] = datafile_entry
    loaded_df["_Source"] = str(datafile)
    for hook in registry.post_load_hooks:
        loaded_df = hook(loaded_df, Path(datafile), Path(input_dir))
    return loaded_df


def prepare_import(args):
    """Pair --configs with --names: equal lengths pair one-to-one, a single
    value pairs with every value of the other list, and either may be None to
    load the files of the other alone. Returns (configs, names) or (None, None)."""
    configs = getattr(args, "configs", None)
    names = getattr(args, "names", None)
    if configs is None and names is None:
        return None, None

    if configs is None:
        return [None] * len(names), names
    if names is None:
        return configs, [None] * len(configs)
    if len(configs) == len(names):
        return configs, names
    if len(configs) == 1:
        return configs * len(names), names
    if len(names) == 1:
        return configs, names * len(configs)

    rprint("[red]Error:[/red] When providing multiple configurations and names, they must either be of the same length, or one of them must be of length 1.")
    return None, None


def import_data(args):
    """Load and concatenate every file selected by --datafile/--path/
    --configs/--names. Rows carry ``_Datafile``, ``_Source`` and, for
    config/name loads, ``_Occurrence`` (the requested slot)."""
    df = pd.DataFrame()

    datafile_entries = normalize_datafiles(getattr(args, "datafile", None))
    path_entries = pair_paths_with_datafiles(getattr(args, "path", None), datafile_entries)
    if path_entries is None:
        return df

    arg_configs = getattr(args, "configs", None)
    arg_names = getattr(args, "names", None)
    if getattr(args, "name_columns", False) and arg_configs is not None and arg_names is not None:
        # Cross-product loading: every (config, name) pair gets its own file lookup
        # instead of the strict 1-to-1/1-to-N pairing used by prepare_import.
        pairs = list(product(arg_configs, arg_names))
        configs = [config for config, _ in pairs]
        names = [name for _, name in pairs]
    else:
        configs, names = prepare_import(args)

    loaded_chunks = []
    if arg_configs is None and arg_names is None:
        for datafile_entry, path_entry in zip(datafile_entries, path_entries):
            input_dir, is_default = resolve_input_data_dir(path_entry)
            candidate_paths = bare_datafile_candidates(datafile_entry, input_dir, is_default)
            datafile = next((path for path in candidate_paths if path.exists()), None)
            if datafile is None:
                print(f"Data file not found: {candidate_paths[0]}")
                continue

            loaded_df = _load_datafile(datafile, datafile_entry, input_dir)
            if not loaded_df.empty:
                loaded_chunks.append(loaded_df)
    elif configs is not None:
        pair_counts = Counter(zip(configs, names))
        duplicates = [pair for pair, count in pair_counts.items() if count > 1]
        if duplicates:
            dup_desc = "; ".join(
                f"Config={c}, Name={n}" if n is not None else f"Config={c}"
                for c, n in duplicates
            )
            rprint(
                f"[yellow]Warning:[/yellow] Duplicate config/name pair(s) requested: "
                f"{dup_desc}. Each occurrence will be loaded and plotted as an "
                "independent line."
            )

        # `occurrence` tags which requested slot a row came from, so duplicate
        # (config, name) pairs stay distinguishable further down the pipeline.
        for occurrence, (config, name) in enumerate(zip(configs, names)):
            for datafile_entry, path_entry in zip(datafile_entries, path_entries):
                # --path may carry {config}/{name} placeholders for nested layouts.
                if isinstance(path_entry, str) and ("{config}" in path_entry or "{name}" in path_entry):
                    path_entry = path_entry.format(config=config, name=name)
                input_dir, is_default = resolve_input_data_dir(path_entry)
                if arg_configs is None:
                    prefixes = [f"{name}_"]
                elif arg_names is None:
                    prefixes = [f"{config}_", ""]
                else:
                    prefixes = [f"{config}_{name}_"]

                candidate_paths = []
                for prefix in prefixes:
                    for path in datafile_candidates(input_dir, prefix, datafile_entry, is_default):
                        if path not in candidate_paths:
                            candidate_paths.append(path)

                datafile = next((path for path in candidate_paths if path.exists()), None)
                if datafile is None:
                    print(f"Data file not found: {candidate_paths[0]}")
                    continue

                loaded_df = _load_datafile(datafile, datafile_entry, input_dir)
                if loaded_df.empty:
                    continue
                loaded_df["_Occurrence"] = occurrence
                loaded_chunks.append(loaded_df)

    if loaded_chunks:
        df = pd.concat(loaded_chunks, ignore_index=True)

    if not df.empty:
        for hook in registry.post_concat_hooks:
            result = hook(df)
            if result is not None:
                df = result

    # --variable_column: the panels (--variables) come from another column.
    variable_column = getattr(args, "variable_column", None)
    if variable_column is not None and not df.empty:
        if variable_column not in df.columns:
            raise SystemExit(f"--variable_column {variable_column!r} is not a column of the data.")
        df["Variable"] = df[variable_column].astype(str)

    if getattr(args, "debug", False):
        rprint("DataFrame columns and types:")
        rprint({col: df[col].dtype for col in df.columns})
        rprint("\nDataFrame preview:")
        rprint(df)

    return df


# --- Output names ------------------------------------------------------------------

# Attributes holding the operation of a run (one per kind); the first one set
# is written into the output name.
_OPERATION_ATTRIBUTES = ("operation", "combine_op", "estimator", "hist_combine", "agg")

# Options that only appear in the output name when listed in --filename_select:
# (attribute, include its value, default value that is never written).
FILENAME_OPTION_SPECS = [
    ("combined_contours_only", False, None),
    ("fill_contours", False, None),
    ("contour_smoothing_sigma", True, 0),
    ("background_smoothing_sigma", True, 0),
    ("contour_sigmas", True, None),
]


def make_name_from_args(
    args,
    idx: Optional[int] = None,
    prefix: Optional[str] = None,
    suffix: Optional[str] = None,
):
    """Output file name built from the run's arguments.

    Parts are joined with ``_``: datafile, configs, names (the parts that
    identify a run and are kept when the name is too long), then x/y/z,
    variables, iterable, select pairs, operation and a few flags. Names
    longer than 150 characters lose their largest expendable parts first;
    keys listed in --filename_select are never dropped. ``idx`` picks one
    config/name when a run writes one figure per pair.
    """
    name_parts = []
    protected_parts = set()
    filename_select_values = {
        str(value).strip().casefold()
        for value in (getattr(args, "filename_select", None) or [])
        if str(value).strip()
    }

    def filename_selected(*aliases):
        return any(str(alias).casefold() in filename_select_values for alias in aliases)

    def add(text, essential=False, protected=False):
        if text:
            name_parts.append((text, essential))
            if protected:
                protected_parts.add(len(name_parts) - 1)

    if prefix is not None:
        add(prefix, essential=True, protected=filename_selected("prefix"))

    if hasattr(args, "datafile"):
        add(
            "_".join(normalize_datafiles(args.datafile)),
            essential=True,
            protected=filename_selected("datafile"),
        )

    show_configs = getattr(args, "show_configs", None)
    configs = getattr(args, "configs", None)
    if configs:
        if idx is not None and 0 <= idx < len(configs):
            text = configs[idx]
        elif show_configs:
            # Only the configs actually drawn identify the plot; configs loaded
            # solely to be combined need not be spelled out.
            shown = [c for c in configs if c in show_configs]
            text = "_".join(shown) if shown else "_".join(configs)
        else:
            text = "_".join(configs)
        add(text, essential=True, protected=filename_selected("config", "configs"))

    for proj in getattr(args, "project", None) or []:
        if proj and isinstance(proj, str):
            add(proj, protected=filename_selected("project", "projects"))

    if getattr(args, "project_offset", None) not in (None, 0):
        add(f"project_offset_{args.project_offset:g}", protected=filename_selected("project_offset"))

    if getattr(args, "project_scale", None) not in (None, 1):
        add(f"project_scale_{args.project_scale:g}", protected=filename_selected("project_scale"))

    if getattr(args, "project_reference", None):
        add(f"project_reference_{args.project_reference}", protected=filename_selected("project_reference"))

    names = getattr(args, "names", None)
    if names:
        text = names[idx] if idx is not None and 0 <= idx < len(names) else "_".join(names)
        add(text, essential=True, protected=filename_selected("name", "names"))

    for axis in ("x", "y", "z"):
        value = getattr(args, axis, None)
        if value and isinstance(value, str):
            add(value, protected=filename_selected(axis))

    if getattr(args, "errory", False):
        add("error")

    if getattr(args, "variables", None):
        add("_".join(args.variables), protected=filename_selected("variable", "variables"))

    select = getattr(args, "select", None)
    save_values = getattr(args, "save_values", None)
    if getattr(args, "iterable", None):
        if select is None and save_values is not None:
            iterable_parts = [f"{val}" for val in save_values if val]
            if iterable_parts:
                add("_".join(iterable_parts), protected=filename_selected("iterable"))
        else:
            add(f"{args.iterable}", protected=filename_selected("iterable"))

    if select:
        # --filename_select names --select keys that must survive the
        # length-based trimming below (so runs that only differ in one
        # select/save_values pair do not overwrite each other).
        if save_values:
            # One part per key: --select Sample -s A B gives "sample_a_b".
            grouped = {}
            for sel, val in selection_pairs(select, save_values):
                if sel and val:
                    grouped.setdefault(sel, []).append(str(val))
            if filename_select_values:
                for sel, vals in grouped.items():
                    selected = str(sel).casefold() in filename_select_values
                    add(f"{sel}_{'_'.join(vals)}", essential=selected, protected=selected)
            else:
                select_parts = [f"{sel}_{'_'.join(vals)}" for sel, vals in grouped.items()]
                if select_parts:
                    add("_".join(select_parts))
        else:
            if filename_select_values:
                for sel in select:
                    if sel:
                        selected = str(sel).casefold() in filename_select_values
                        add(sel, essential=selected, protected=selected)
            else:
                add("_".join(select))

    for attribute in _OPERATION_ATTRIBUTES:
        value = getattr(args, attribute, None)
        if value:
            add(str(value))
            break

    if getattr(args, "lower_series_data", None):
        add(str(args.lower_series_data))
    if getattr(args, "group_significance", False):
        add("significance")
    if getattr(args, "lower_series", None):
        add(str(args.lower_series))
    if getattr(args, "lower_plot_style", None):
        add(str(args.lower_plot_style))
    if getattr(args, "lower_series_density", False):
        add("density")

    for flag, text in (
        ("logx", "logx"),
        ("logy", "logy"),
        ("logz", "logz"),
        ("no_lower_plot", "no_lower"),
        ("invert_style", "invert_style"),
    ):
        if getattr(args, flag, False):
            add(text)

    for option_name, include_value, default in FILENAME_OPTION_SPECS:
        if not filename_selected(option_name) or not hasattr(args, option_name):
            continue
        option_value = getattr(args, option_name)
        if include_value:
            if option_value is None or option_value == default:
                continue
            if isinstance(option_value, (list, tuple)):
                value_text = "-".join(str(value) for value in option_value)
            else:
                value_text = f"{option_value:g}" if isinstance(option_value, float) else str(option_value)
            add(f"{option_name}_{value_text}", protected=True)
        elif option_value:
            add(option_name, protected=True)

    # --filename_suffix tags runs that differ only in a non-filename option.
    filename_suffix = getattr(args, "filename_suffix", None)
    if filename_suffix:
        add(str(filename_suffix), essential=True, protected=True)

    max_len = 150
    suffix_part = ("_" + suffix) if suffix is not None else ""

    def joined(drop):
        return "_".join(text for i, (text, _) in enumerate(name_parts) if i not in drop)

    dropped = set()
    if len(joined(dropped)) + len(suffix_part) > max_len:
        # Drop the biggest non-essential parts first until the name fits.
        droppable_by_size = sorted(
            (i for i, (_, essential) in enumerate(name_parts) if not essential and i not in protected_parts),
            key=lambda i: -len(name_parts[i][0]),
        )
        for i in droppable_by_size:
            if len(joined(dropped)) + len(suffix_part) <= max_len:
                break
            dropped.add(i)

    if protected_parts and len(joined(dropped)) + len(suffix_part) > max_len:
        # --filename_select fields outrank ordinary essential fields.
        droppable_essential = sorted(
            (
                i
                for i, (_, essential) in enumerate(name_parts)
                if essential and i not in protected_parts and i not in dropped
            ),
            key=lambda i: -len(name_parts[i][0]),
        )
        for i in droppable_essential:
            if len(joined(dropped)) + len(suffix_part) <= max_len:
                break
            dropped.add(i)

    export_name = joined(dropped)
    if len(export_name) + len(suffix_part) > max_len:
        if protected_parts:
            # Keep every explicitly selected field, even beyond max_len.
            export_name = "_".join(
                text for i, (text, _) in enumerate(name_parts) if i in protected_parts and i not in dropped
            )
        else:
            budget = max(max_len - len(suffix_part), 0)
            export_name = export_name[:budget].rstrip("_")

    if suffix is not None:
        export_name = export_name + "_" + suffix

    export_name = export_name.replace(" ", "_").replace("-", "_").replace("#", "n")
    return export_name.lower()


# --- Saving ------------------------------------------------------------------------


def default_output_dir(kind="plots"):
    """``<project output>/plots`` or ``<project output>/tables``."""
    return str(load_project().output_dir / kind)


def _output_dirs(output_arg, default_dir, subfolder):
    output_paths = [] if output_arg is None else (output_arg if isinstance(output_arg, list) else [output_arg])
    dirs = []
    for output_path in output_paths or [None]:
        if output_path is None:
            output_dir = default_dir
        else:
            output_dir = os.path.dirname(output_path) if os.path.splitext(output_path)[1] else output_path
        if subfolder:
            output_dir = os.path.join(output_dir, subfolder)
        dirs.append(output_dir)
    return dirs


def save_table_to_paths(write_func, output_arg, output_file, default_output_dir=None, rprint_func=None, subfolder=None):
    """Call ``write_func(full_path)`` for every --output directory (or the
    default table directory when none is given)."""
    rprint_func = rprint_func or rprint
    default_dir = default_output_dir or globals()["default_output_dir"]("tables")
    for output_dir in _output_dirs(output_arg, default_dir, subfolder):
        os.makedirs(output_dir, exist_ok=True)
        full_path = os.path.join(output_dir, output_file)
        write_func(full_path)
        rprint_func(f"[green]Success:[/green] Table saved to:\n{full_path}")


def save_figure_to_paths(fig, output_arg, output_file, default_output_dir=None, rprint_func=None, subfolder=None,
                         sci_in_label=None):
    """Save ``fig`` into every --output directory (or the default plot
    directory when none is given); ``sci_in_label`` as in
    :func:`plotipus.plot.finish_tick_labels`."""
    from .plot import _shorten_title_to_fit, apply_measured_layout, finish_tick_labels

    finish_tick_labels(fig, sci_in_label)
    apply_measured_layout(fig)

    # Layout may have narrowed the title since it was set; re-check it fits.
    _shorten_title_to_fit(fig, getattr(fig, "_suptitle", None))

    rprint_func = rprint_func or rprint
    default_dir = default_output_dir or globals()["default_output_dir"]("plots")
    # Another medium/theme than the project's goes to <output>/<medium>[-dark].
    rendering = current_rendering()
    if rendering is not None and rendering.folder:
        subfolder = os.path.join(rendering.folder, subfolder) if subfolder else rendering.folder
    for output_dir in _output_dirs(output_arg, default_dir, subfolder):
        os.makedirs(output_dir, exist_ok=True)
        full_path = os.path.join(output_dir, output_file)
        fig.savefig(full_path)
        rprint_func(f"[green]Success:[/green] Plot saved to:\n{full_path}")
