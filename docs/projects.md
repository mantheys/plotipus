# Projects

`plotipus.toml` (looked up from the working directory upwards):

```toml
[project]
data_root = "input/data"
plots = "input/plots"        # command lists <name>_scripts.txt
tables = "input/tables"
output = "output"
style = ["paper", "config/style.json"]  # a named style, then style files
plugins = ["my_project.plotipus_plugin"]
python_path = ["src"]
medium = "slides"            # slides | paper | web (default: the named style's)
media = ["slides", "paper"]  # rendered by --medium all and plotipus run
theme = "light"              # light | dark
language = "plotipus"        # plotipus | open | classic
save_style = false           # write <figure>.style.json next to each figure

[outputs.plots]              # extra output directories per command list
paper = ["../paper/figures"]

[settings]
default_operation = "mean"
```

## Styles, media and themes

A named style combines a language, a medium and a theme:

| name | language | medium | theme |
|---|---|---|---|
| `slides` (default) | plotipus | slides | light |
| `slides-dark` | plotipus | slides | dark |
| `paper`, `paper-dark` | plotipus | paper | light, dark |
| `open`, `open-dark` | open | web | light, dark |
| `classic` | the look before the redesign | — | — |

Name it in `style = [...]`, with `--style_preset NAME`, or by parts with
`[project] language/medium/theme` and `--medium`/`--theme`. Its layers come
from `src/plotipus/data/styles/` (`<language>.json`, `<medium>.json`,
`dark.json`, each naming its `.mplstyle`; `classic/` is complete on its
own). Then what plugins changed is applied again, then the project's style
files, which have the last word, then `--width` and `--aspect`. `plotipus run
<list> --dry_run` prints, for every command, the language, medium, theme,
size and layers it resolves to; `--save_style` writes them, with the
rcParams, to `<figure>.style.json`.

- **Medium**: `--medium` on any kind or on `plotipus run`, else `[project]
  medium`, else the named style's. `--medium all` (and `[project] media`
  with `plotipus run`) renders every listed medium.
- **Size**: each medium has a default `width` (slides: `slide`, 8 in at
  aspect 0.73; web: `slide` at 0.5625; paper: `single`, 3.4 in at 0.75).
  Presets live in the style's `widths`; a preset is inches (height =
  `aspect` × width) or `{"width": 6.8, "height": 3.0}`. Lower panels share
  the figure's height in slides (`"lower_panels": "share"`), so a plot with a
  ratio panel has the size of one without; elsewhere each adds 30% of the
  upper height (`"add"`). A row of panels shares the width and gets shorter
  (`"facet_rows": {"panel_aspect": 1.0, "min_height": 3.2}`): about square
  panels, at least 3.2 in, never taller than one plot. Text is never scaled for more
  panels (`panel_font_scale` only applies to `classic` and to style files
  that set `"width": null`, the size from `figure_layout`).
  `--single_panel_size` gives every figure the size of one panel.
- **Text drawn by plugins**: `style.text_scale` is the medium's scale for
  text a hook draws itself (1 in slides and web, 0.75 in paper), so labels
  sized for slides stay in proportion on a paper figure.
- **Output folders**: the project's own medium and theme write where they
  always did (`output/plots/`); any other pair writes to
  `output/plots/<medium>/` or `output/plots/<medium>-dark/`, and so do the
  `[outputs.plots]` and `-o` targets. File names are unchanged.
- **Titles**: no automatic title from the datafile name in any medium; an
  explicit `--title` is dropped in paper (with a note) unless `--keep_title`.

## Header and watermark

A project can carry an experiment header and a status watermark on every
figure:

```toml
[header]
experiment = "dune"            # atlas, cms, lhcb, alice, dune (or style = ["experiment-dune"])
label_status = "Preliminary"   # after the label ("DUNE", or label = "...")
label_right = "1.2 MW, 10 years"
watermark = "wip"              # wip, preliminary, internal, simulation, draft, or text
watermark_style = "corner"     # corner | diagonal
```

The same keys go in a style file's `"header"` section (`label`, `status`,
`right`, `position`, `watermark`, `watermark_style`, and the typography
`label_weight`, `label_style`, `status_weight`, `status_style`,
`label_size`, `status_size`, `right_size` as fractions of `font.size`), and
`--label`, `--label_status`, `--label_right`, `--label_position`,
`--watermark` (`none` drops the project's) and `--watermark_style` override
them per command. An experiment preset is a style layer between the medium
and the dark theme (`src/plotipus/data/styles/experiments/`; each file cites
its sources and lists what could not be verified under `_unverified`). The
header follows the medium's text size and the `ink` colour; the watermark
is `muted` under the header, or large and faint behind the data
(`diagonal`). The layout makes room for a header above the axes, and an
inside header gets headroom when data runs under it. A paper figure that
still has a watermark prints a reminder.

## Style files

Style files (JSON) are merged over the defaults
(`src/plotipus/data/style.json`): `palette` (a `--palette` name; an
`axes.prop_cycle` in `rcparams` is kept when `palette` is absent), `rcparams`, `font_sizes`, `plot_settings`
(figure layout, legend and note style, `band_alpha` for error bands, `stack_error` for the
hatched band of stacked simulation; `"auto_title": false` drops the
title taken from the datafile name; `"sci_in_label": false` keeps the
power-of-ten offset text at the axis end instead of in the label; `fit_color`
and `zero_line_color`, colours or roles; `diverging_cmap` for `--cmap diverging`; the sequential map is
`rcparams` `image.cmap`, `plotipus` by default, `plotipus_dark` in the dark theme), `labels` (capitalisation exceptions,
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
