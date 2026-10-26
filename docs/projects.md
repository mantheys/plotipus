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
medium = "slides"            # slides | paper | web (unset: the classic look)
media = ["slides", "paper"]  # rendered by --medium all and plotipus run
theme = "light"              # light | dark

[outputs.plots]              # extra output directories per command list
paper = ["../paper/figures"]

[settings]
default_operation = "mean"
```

## Media and themes

A medium (`slides`, `paper`, `web`) and a theme (`light`, `dark`) select
style layers by name: `plotipus`, then the medium, then `dark`, from
`src/plotipus/data/styles/` (missing layers are skipped). The project's
`style` files come after them and have the last word, then `--width` and
`--aspect`. `plotipus run <list> --dry_run` prints, for every command, the
medium, theme, size and layers it resolves to.

- **Medium**: `--medium` on any kind or on `plotipus run`, else `[project]
  medium`. `--medium all` (and `[project] media` with `plotipus run`)
  renders every listed medium. Without a medium anywhere no layer applies:
  the classic geometry and titles.
- **Size**: each medium has a default `width` (slides and web: `slide`,
  8 in at aspect 0.5625; paper: `single`, 3.4 in at 0.75). Presets live in
  the style's `widths`; a preset is inches (height = `aspect` × width) or
  `{"width": 6.8, "height": 3.0}`. A row of panels shares the width; each
  lower panel adds 30% of the upper height. Text is never scaled for more
  panels (`panel_font_scale` only applies to the classic geometry).
- **Output folders**: the project's own medium and theme write where they
  always did (`output/plots/`); any other pair writes to
  `output/plots/<medium>/` or `output/plots/<medium>-dark/`, and so do the
  `[outputs.plots]` and `-o` targets. File names are unchanged.
- **Titles**: no automatic title from the datafile name in any medium; an
  explicit `--title` is dropped in paper (with a note) unless `--keep_title`.

## Style files

Style files (JSON) are merged over the defaults
(`src/plotipus/data/style.json`): `palette` (a `--palette` name; an
`axes.prop_cycle` in `rcparams` is kept when `palette` is absent), `rcparams`, `font_sizes`, `plot_settings`
(figure layout, legend and note style, `band_alpha` for error bands, `stack_error` for the
hatched band of stacked simulation; `"auto_title": false` drops the
title taken from the datafile name; `"sci_in_label": false` keeps the
power-of-ten offset text at the axis end instead of in the label), `labels` (capitalisation exceptions,
legend titles to drop, title short forms) and `mappings` (named
label/colour dictionaries used by the `*_mapping` options).

* `plot_settings.figure_layout`: the figure size (`base_width`,
  `panel_width` per extra panel, `height`) is the printed size and never
  changes. Before saving, the margins and the space between panels are
  measured from what was drawn (tick and axis labels, titles, legends,
  colorbars) plus `pad_inches` (default 0.04), so nothing is clipped at any
  size. `margins_inches` is the smallest margin allowed; `"fixed_margins":
  true` uses it exactly instead (the layout before T13). Upper and lower
  panels keep `two_panel_hspace` between them.
* `font_sizes`: `xlabelfontsize`/`ylabelfontsize` set rcParams
  `axes.labelsize`, which every kind uses for its axis labels; lower panels
  use `ysublabelfontsize`.

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
