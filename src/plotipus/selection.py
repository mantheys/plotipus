import numpy as np
import pandas as pd

from itertools import product
from rich import print as rprint


def _normalize_selection_columns(select):
    if select is None:
        return []
    if isinstance(select, str):
        return [select]
    return list(select)


def prepare_selection(df, args):
    """
    Prepare the selection process for filtering the DataFrame based on unique values in specified columns.

    Parameters:
    df (pd.DataFrame): The DataFrame to filter.
    args (Namespace): An object containing 'iterable' and 'save_values' attributes for filtering.

    Returns:
    tuple: A tuple containing:
        - unique_combinations (list): A list of unique value combinations for the specified columns.
        - unique_values (dict): A dictionary mapping each column to its unique values.
    """
    # Initialize a dictionary to hold unique values for each specified column
    unique_values = {}

    # Iterate over the columns specified in 'iterable' to collect unique values
    for col in _normalize_selection_columns(args.select):
        if col not in df.columns:
            rprint(f"Column '{col}' not found in DataFrame columns. Skipping...")
            continue

        # Store unique values for the column
        unique_values[col] = df[col].unique()

        # Check if the column has multiple unique values and print a warning if so
        if len(unique_values[col]) > 1:
            print(
                f"Column '{col}' has multiple unique values: {unique_values[col]} of type {type(unique_values[col][0])}"
            )

    # If both 'select' and 'save_values' are provided, print the filtering information
    if args.select is not None and args.save_values is not None:
        print(
            f"Applying save_values filter: {args.save_values} for column: {args.select}"
        )

    # Generate all unique combinations of values from the specified columns
    unique_combinations = list(product(*unique_values.values()))

    return unique_combinations, unique_values


def _coerce_filter_value(series, raw_value, key, debug=False):
    """
    Coerce a CLI-provided filter value to match the dtype of a DataFrame column.

    Returns:
        tuple: (value, ok) where value is None to mean "match missing entries"
        and ok is False when the value could not be converted and the filter
        for this key should be skipped.
    """
    value = raw_value

    if isinstance(value, str) and value.lower() == "nan":
        value = None

    if isinstance(value, str) and value.lower() in ["true", "false"]:
        value = value.lower() == "true"

    if isinstance(series.iloc[0], np.bool_):
        value = np.bool_(value)

    if value is None or type(series.iloc[0]) == type(value):
        return value, True

    if debug:
        rprint(
            f"\t\tType mismatch for save_key {key}: dataframe has type {type(series.iloc[0])}, but value has type {type(value)}."
        )
        rprint(f"\t\tTrying to convert value to type {type(series.iloc[0])}.")

    try:
        if isinstance(series.iloc[0], (int, np.integer)):
            value = int(value)
        elif isinstance(series.iloc[0], (float, np.floating)):
            value = float(value)
        else:
            value = str(value)
    except ValueError:
        rprint(
            f"[red]Error:[/red] Could not convert value {raw_value} to type {type(series.iloc[0])}. Skipping."
        )
        return None, False

    if debug:
        rprint(f"\t\tConverted value to {type(value)} and selecting {key}={value}")

    return value, True


def filter_dataframe(df, args):
    """
    Keep the rows matching --variables (column ``Variable`` or
    --variable_name), the --select/--save_values pairs (values of one key are
    OR-ed, keys are AND-ed) and drop the --remove_value matches.
    """
    this_df = df.copy()
    variables = getattr(args, "variables", None)
    select = getattr(args, "select", None)
    save_values = getattr(args, "save_values", None)
    iterable = getattr(args, "iterable", None)
    debug = getattr(args, "debug", False)

    # Filter the DataFrame according to the input variables
    if variables is not None:
        variable_column = getattr(args, "variable_name", None) or "Variable"
        this_df = this_df[this_df[variable_column].isin(variables)]

    # Filter the DataFrame based on the unique value combinations for the selected columns
    if select is not None and save_values is not None:
        selection_values = {}
        for save_key, save_value in zip(
            _normalize_selection_columns(select), save_values
        ):
            selection_values.setdefault(save_key, []).append(save_value)

        for save_key, save_values in selection_values.items():
            # Check that the save_key exists in the dataframe and their entries match the type of save_value
            if save_key not in this_df.columns:
                rprint(
                    f"Save key {save_key} not found in dataframe columns. Skipping..."
                )
                continue

            if this_df.empty:
                continue

            if debug:
                rprint(
                    f"\tApplying select filtering on {save_key}={save_values} with values {this_df[save_key].unique().tolist()}"
                )

            matched_values = []
            for save_value in save_values:
                matched_value, ok = _coerce_filter_value(
                    this_df[save_key], save_value, save_key, debug
                )
                if ok:
                    matched_values.append(matched_value)

            if not matched_values:
                continue

            missing_requested = any(value is None for value in matched_values)
            non_missing_values = [
                value for value in matched_values if value is not None
            ]
            value_mask = this_df[save_key].isin(non_missing_values)
            if missing_requested:
                value_mask |= this_df[save_key].isna()

            if debug:
                rprint(f"\tSelecting {save_key} in {matched_values}")

            this_df = this_df[value_mask]

            if debug:
                rprint(f"\tSize after filtering: {len(this_df)}")

    elif save_values is not None:
        if debug:
            print(f"Applying save_values filtering on {iterable}")

        this_df = this_df[this_df[iterable].isin(save_values)]

    # Filter out the unique value combinations for the selected columns
    remove_value = getattr(args, "remove_value", None)
    if select is not None and remove_value is not None:
        _remove_keys = list(_normalize_selection_columns(select))
        if len(_remove_keys) < len(remove_value):
            _remove_keys += [_remove_keys[-1]] * (len(remove_value) - len(_remove_keys))
        for remove_key, value_to_remove in zip(_remove_keys, remove_value):
            if remove_key not in this_df.columns:
                rprint(
                    f"Remove key {remove_key} not found in dataframe columns. Skipping..."
                )
                continue

            if this_df.empty:
                continue

            if debug:
                rprint(
                    f"\tApplying remove_value filtering on {remove_key}={value_to_remove} with values {this_df[remove_key].unique().tolist()}"
                )

            matched_value, ok = _coerce_filter_value(
                this_df[remove_key], value_to_remove, remove_key, debug
            )
            if not ok:
                continue

            if matched_value is None:
                if debug:
                    rprint(f"\t\tRemoving missing values for {remove_key}")
                this_df = this_df[~this_df[remove_key].isna()]
            else:
                this_df = this_df[this_df[remove_key] != matched_value]

            if debug:
                rprint(f"\tSize after filtering: {len(this_df)}")

    elif remove_value is not None:
        if debug:
            print(f"Applying remove_value filtering on {iterable}")

        this_df = this_df[~this_df[iterable].isin(remove_value)]

    return this_df
