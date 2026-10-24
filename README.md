# plotipus

Publication plots and tables from pickled pandas DataFrames, driven by plain
text command lists.

Analysis code writes its results as `.pkl` DataFrames (one row per series,
with whole arrays in the cells); plotipus turns them into figures and LaTeX
tables with one command each:

```bash
plotipus line --datafile Spectra -x Energy -y Counts --hue Sample --style Stage --logy
plotipus run paper          # every command in input/plots/paper_scripts.txt
```

## Install

```bash
# use the CLI
pipx install git+https://github.com/mantheys/plotipus.git

# development
git clone https://github.com/mantheys/plotipus.git && cd plotipus
python3 -m venv .venv && source .venv/bin/activate   # Debian/Ubuntu: apt install python3-venv
pip install -e ".[dev]"
```

Python ≥ 3.10; depends on numpy, pandas, matplotlib, scipy, rich and jinja2.

## Quick start

```bash
cd examples
python make_data.py          # toy pickles in input/data
plotipus run example         # figures in output/plots
plotipus run example --tables
```

To regenerate the examples from scratch after a change (`examples/Makefile`;
it uses `.venv/bin/python` when present):

```bash
make -C examples             # delete generated data and outputs, then rebuild all
make -C examples clean       # only delete them (input/data/*.pkl, output/)
make -C examples plots       # rebuild data and plots without deleting first
```

`plotipus init my_project` creates an empty project (`plotipus.toml`,
`input/{data,plots,tables}`, `output/`).

## Plot kinds

Kinds follow the data relationship (as in seaborn/plotly), not the use case.

| Kind | Draws | Typical options |
|---|---|---|
| `line` | y against an ordered x, one series per `--hue` value, line style per `--style` value | `--plot_type step\|stepmid\|line\|errorbar\|plot\|bar\|barh\|box`, `--lower`, `--stacked`, `--sum_iterables`, `--merge_iterables`, `--rebin`, `--by_config`, `--fit`, `--binned --estimator mean\|median\|std\|rms\|sum\|max\|min` (see [Binned estimators](#binned-estimators)) |
| `scatter` | observations: exploded points with colour/size/marker encodings, or pairs of metrics (`--x_from Variable=Purity --y_from Variable=Completeness`) | `--colorby`, `--sizeby`, `--markerby`, `--aggregate` |
| `hist` | 1D histograms of per-event arrays | `--bins`, `--weight`, `--density`, `--hist_combine`, `--flow none\|hint\|show` |
| `map` | 2D: histogram of point arrays, image of a grid (`-z`), contour layer (`--contour`) | `--norm`, `--diagonal`, `--logz`, `--colorbar`, `--contour_sigmas`, `--contour_dof`, `--contour_label`, `--fill_contours`, `--background`, `--no_best_fit` |
| `cat` | one value per category (integrated arrays) | `--integrate_over`, `--kind point\|line\|bar` |
| `table` | aggregated values as LaTeX (and HTML) tables | `--variables`, `--agg`, `--error_band`, `--clopper_pearson`, `--siunitx`, `--caption_file` |

`plotipus <kind> --help` lists every option.

### Shared options

* **Data**: `--datafile` (files `{config}_{name}_{datafile}.pkl` when
  `--configs`/`--names` are given, else `{datafile}.pkl`), `--path` (relative
  to the data root), `--select COL -s VALUE` / `--remove_value`,
  `--variables` (values of the `Variable` column, one panel each).
* **Encodings**: `--hue` (alias `--iterable`), `--style` (alias
  `--comparable`), `--iterable_mapping`/`--iterable_color_mapping` and
  `--comparable_mapping` (named mappings from the style file),
  `--invert_style`, `--comparable_fill_strength`. `--hue X --style X` draws
  one legend whose entries carry both the colour and the line style.
* **Colours**: `--palette NAME` picks the categorical palette (default
  `petroff10`; also `petroff6`, `petroff8`, `okabe-ito`, `tol-bright`,
  `tol-muted`, `tab10` (matplotlib's default, the colours before this
  change), `seaborn-colorblind`, `tableau-colorblind10`, `root`). A value
  keeps its colour in every panel and lower panel, a mapped colour is never
  given to another value, and the combined/sum series (`--combined_color`,
  `--sum_color`, `--reference_sum_color`, default: a free colour) never
  share one. With more values than colours, colours repeat and a warning
  is printed.
* **Axes and overlays**: `--labelx/--labely/--labelz`, `--rangex/--rangey`,
  `--logx/--logy`, `--horizontal`, `--vertical`, `--point`, `--square`,
  `--line`, `--xtick`, `--note`, `--title`.
* **Output**: `-o DIR [DIR ...]`, `--subfolder`, `--output_suffix`,
  `--filename_select` (keys that must stay in the generated file name).

### Lower panels

A lower panel is the same kind of panel as the upper one; it plots a column
derived from (or stored in) the same DataFrame. Each `--lower` adds one:

```bash
--lower ratio                 # every series / the reference series (--reference, --reference_value)
--lower relative_difference   # also subtract, asymmetry, excess, excess_probability, sum, mean, rms
--lower group --reference_group S --other_group B1 B2 --group_significance   # S/sqrt(B)
--lower residual              # data against the stored fit (with --fit); also pull
--lower column:Significance   # a series stored in the pickle (with SignificanceError)
--lower events:OpHit          # event markers read from OpHit* columns
```

The lower panel is styled with the upper-panel options prefixed by `lower_`:
`--lower_plot_type errorbar`, `--lower_labely`, `--lower_rangey`,
`--lower_logy`, `--lower_horizontal`, ...

### Colorbars

`map` panels showing the same quantity share one colour scale and one
colorbar right of the row (`--colorbar shared`, the default unless `--norm`
normalises each panel); `--colorbar each` draws one per panel. Every bar is
labelled: `--labelz`, else the `--norm` label, else "Counts"/"Density", else
the `-z` column. Empty bins are blank, and with `--logz` the scale starts at
the smallest non-empty bin.

### Contours

`map --contour -z DCHI2` draws confidence regions of Δχ² maps (or
significance maps with `--contour_level_mode z_values`):

* `--contour_dof 2` (default) puts the 1/2/3σ levels at Δχ² = 2.30, 6.18,
  11.83, the joint region of two parameters; `--contour_dof 1` gives
  Δχ² = 1, 4, 9.
* `--contour_label cl` (default) labels levels "68.3% CL", "95.4% CL",
  "99.7% CL"; `sigma` labels them "1σ" (or "1σ (2 dof)").
* `--fill_contours` fills one hue per map, darkest at the best fit and lighter
  outwards (`--fill_alpha`, `--fill_outer_alpha`). Outlines are solid, dashed
  and dotted (`--contour_linestyles`), and a `+` marks the minimum
  (`--no_best_fit` hides it).
* `--background none` (default); with `all`/`combined`/`first`, a Δχ²
  background is blank beyond the outermost level and its colorbar reads Δχ².
* `--horizontal`, `--vertical`, `--line`, `--square` and `--point` are drawn
  above the contours, in the text colour (white on a background image that
  fills the panel); the grid or `--rangex`/`--rangey` keeps the frame.

The style file's `contours` section sets the defaults:
`{"dof": 2, "fill_mix": [1.0, 0.55, 0.25], "linestyles": ["-", "--", ":"], "label": "cl", "background": "none"}`.
`--contour_dof 1 --contour_label sigma --background all` restores the
levels, labels and background used before.

### Binned estimators

`line --binned` bins raw per-event x/y arrays and draws `--estimator` of y
per x bin, as error bars on markers (not joined) unless `--plot_type` says
otherwise:

* **Errors** (`--estimator_error`): `sem` (default) is the standard error
  of the statistic: mean σ/√n, median 1.2533·σ/√n, std σ/√(2(n−1)), rms by
  the delta method, sum √Σy² (√n for counts, √Σw² for weights), none for
  max/min (σ is the bin's sample standard deviation). With `--errory`, the
  stored per-event errors are propagated instead (mean √Σe²/n, sum √Σe²,
  median 1.2533·√Σe²/n, std/rms to first order, max/min the selected
  event's error). `std` draws the bin's spread σ; `none` the bare values.
* **Small bins**: bins with fewer than `--min_count` entries (default 5)
  are dropped, with a note; `--min_count 1` keeps every non-empty bin.
* **Label**: the y label gets the error's name, e.g. "(mean ± s.e.m.)",
  unless `--note` is given or `--no_error_label` is passed.

## Python

```python
import plotipus

plotipus.plot("line", "--datafile", "Spectra", "-x", "Energy", "-y", "Counts", "--hue", "Sample")

from plotipus import load_frame, plot_data, create_common_subplots, format_with_error, style
style.configure("my_style.json")
fig, ax = create_common_subplots()
```

## Projects

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

**Style files** (JSON) are merged over the defaults
(`src/plotipus/data/style.json`): `palette` (a `--palette` name; an
`axes.prop_cycle` in `rcparams` is kept when `palette` is absent), `rcparams`, `font_sizes`, `plot_settings`
(figure layout, legend and note style; `"auto_title": false` drops the
title taken from the datafile name), `labels` (capitalisation exceptions,
legend titles to drop, title short forms) and `mappings` (named
label/colour dictionaries used by the `*_mapping` options).

**Plugins** adapt plotipus to a project without changing it. A plugin module
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

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
