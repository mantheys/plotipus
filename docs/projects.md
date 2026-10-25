# Projects

`plotipus.toml` (looked up from the working directory upwards):

```toml
[project]
data_root = "input/data"
plots = "input/plots"        # command lists <name>_scripts.txt
tables = "input/tables"
output = "output"
style = ["config/style.json"]
plugins = ["my_project.plotipus_plugin"]
python_path = ["src"]

[outputs.plots]              # extra output directories per command list
paper = ["../paper/figures"]

[settings]
default_operation = "mean"
```

## Style files

Style files (JSON) are merged over the defaults
(`src/plotipus/data/style.json`): `palette` (a `--palette` name; an
`axes.prop_cycle` in `rcparams` is kept when `palette` is absent), `rcparams`, `font_sizes`, `plot_settings`
(figure layout, legend and note style, `band_alpha` for error bands, `stack_error` for the
hatched band of stacked simulation; `"auto_title": false` drops the
title taken from the datafile name), `labels` (capitalisation exceptions,
legend titles to drop, title short forms) and `mappings` (named
label/colour dictionaries used by the `*_mapping` options).

* `mplstyle`: a matplotlib style, or a list of them, applied with
  `plt.style.use` before the file's `rcparams`. An entry is a `.mplstyle`
  path (relative to the style file) or a style name (`"dark_background"`).
  Files are merged in order, so a later file's `mplstyle` overrides an
  earlier file's `rcparams`. A `.mplstyle` file can also be listed directly
  in `style = [...]` of `plotipus.toml`.
* `roles`: the colours plotipus draws with besides the data colours:
  `ink` (text, data points, fit, reference lines and line-style legend
  handles), `muted` (guides: y = 1, the 100% efficiency line, Δχ² lines,
  mean bands, zero lines), `faint` (pull bands, grids), `paper` (background,
  outlines on images) and `accent` (highlights). Missing roles follow the
  rcParams: `ink` is `text.color`, `paper` is `axes.facecolor`, `muted` and
  `faint` are 50% and 10% of ink mixed into paper, so a dark `mplstyle` gives
  light guides without further settings. Any colour in `mappings`,
  `legend_style` or `note_style` may name a role: `"role:muted"`.

```json
{"mplstyle": "dark_background", "roles": {"accent": "#ff7f0e"},
 "mappings": {"config_color": {"total": "role:ink"}}}
```

## Plugins

Plugins adapt plotipus to a project without changing it. A plugin module
defines `setup(registry)` and can register:

* `registry.add_resolver(f)`: extra lookup locations for data files;
* `registry.add_post_load(f)` / `add_post_concat(f)`: decorate or check loaded frames;
* `registry.add_label_hook(column, f)` / `add_color_hook(column, f)`: labels and colours of a column's values;
* `registry.config_label = f`: legend labels of config/name series;
* `registry.table_columns[name] = f`: derived table columns;
* `registry.add_argument(*flags, **kwargs)`: extra options for every kind
  (read back from `args` by a hook);
* `registry.add_figure_hook(f)`: `f(fig, args)` runs on every figure just
  before it is saved (experiment labels, watermarks, logos);
* `plotipus.fits.register_module(m)`: fit models referenced by stored fits;
* a matplotlib style (import it in `setup`).

## Command lists

One command per line; blank lines and lines starting with `#` or `%` are
skipped. A line is `<kind> [options]` or a project script (`scripts/x.py ...`,
run with the current Python). `plotipus run LIST` accepts `--jobs N`,
`--match TEXT`, `--dry_run` (print the commands) and `--check` (only parse
them).

Command lines written for the original plotting scripts of the
LOWE_RECONSTRUCTION_PUBLICATION repository (`scripts/script_*.py ...`) are
translated automatically (`plotipus translate <line>` shows the result) and
keep their output file names.
