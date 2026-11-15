# Changelog

## Unreleased

New options; every existing command renders as before, except the colorbar
of `map --corner`, which is now as tall as the grid and as wide as the bar of
a single plot (it was a hairline beside the lower rows).

- `map --corner X1 X2 ... --contour`: a posterior corner plot. Below the
  diagonal, the credible regions of each pair (`--contour_sigmas`; the
  smallest regions holding 68.3, 95.4, ... % of the points), filled from the
  sample's colour towards the paper; on the diagonal, the marginal density
  of each variable, for a single sample with its median and central 68.3%
  interval shaded and written above the panel (`--no_corner_titles`).
  `--contour_hue COLUMN` overlays one sample per value (chains, experiments,
  a combination) in its own colour, `--weight COLUMN` takes weighted samples,
  and `--corner_truth V1 V2 ...` (`--corner_truth_label`) marks reference
  values. The legend takes the empty upper triangle.
- Posterior corner plots say how to read them (T25.21–T25.25, T25.27 and the
  band of T25.28; design in `docs/design/corner-plots.md`). The legend names
  what the regions hold ("68.3% (2D region)"), the interval of the marginals
  and the number of draws, with the effective sample size when it is smaller;
  plotipus warns when a region rests on too few draws. New options:
  `--corner_levels 68 90` (content instead of σ), `--corner_interval
  quantile|hdi|limit`, `--corner_cyclic VAR [LOW HIGH]` (regions and intervals
  across the end of a periodic axis), `--corner_bound VAR LOW HIGH` (no
  smoothing across a bound; a one-sided limit where the marginal is highest at
  it), `--corner_split VAR VALUE | COLUMN` with `--corner_split_marginals` and
  `--prior_odds` (posterior probabilities of discrete hypotheses, odds and
  Bayes factors), `--corner_upper profile --loglike COLUMN` (the profile
  likelihood of the same draws above the diagonal), `--corner_upper corr`
  (correlation coefficients with their Monte Carlo error), `--corner_mc_error
  [N]` (the outer region's outline under resampling) and `--corner_band VAR
  LOW HIGH [LABEL]`.
- Posterior corner plots, continued (T25.26): `--corner_prior VALUE` (the
  `--contour_hue` value holding prior draws: dashed marginals and outer region
  in the neutral colour), `--corner_shrinkage` (σ/σ₀ and Δ/σ₀ under each
  title, with a warning above 0.9) and `--corner_block COLUMN ...`
  (`--corner_block_labels`; derived parameters as marginals in the top-right
  block of the upper triangle, from four variables). On paper a posterior
  corner plot is now drawn at the `double` width, with a note (`--width
  single` keeps the column); this changes the size of the existing paper
  examples `posterior` and `posteriors`.
- The web medium (`open`, `open-dark`) states its sizing like slides and
  paper: `lower_panels: share` (as before, by default) and `facet_columns: 2`,
  so a row of three or more facets wraps into rows of two instead of growing
  to three plots' width. The style renders of `docs/design/styles` are redrawn
  at the sizes the styles have had since 0.1.0 (a lower panel no longer makes
  them taller).
- `scatter`: the marker size follows the number of points (the markers cover
  about 30% of the axes, between the style's data marker and 45% of its
  diameter) instead of a fixed area of 120 points², which hid the colours on
  paper and in dense plots; a notice points to `map --map_type hexbin` when
  even the smallest marker overlaps. `--marker_size` still sets the area, and
  `--colorby` points are drawn in a fixed random order. Scatter figures
  without `--marker_size` change; the examples and the gallery no longer pass
  it.
- `--transparent` (every kind): saves the figure without its background. The
  mascot of the README is drawn with it; `examples/mascot/dark` and
  `mascot-dark.png` are gone.

- `line --binned --compact`: `--panel_equal_width` (every panel as wide as the
  widest, each on its own x scale, with minor ticks per panel) and
  `--facet_row COL` (one stacked compact axis per value of COL, titled by
  `--variable_label_map`; `--panel_rangex` takes one set of ranges for all
  rows or one per row; `--panel_vertical_file` is read again per row).
- `line`, `cat`: `--multiply_where COLUMN=VALUE FACTOR` (repeatable) rescales
  the matching rows, on top of `--multiply`.
- `cat`: `--variable_panels` draws one panel per `--variables` value, with
  `--panel_grid`, `--sharey`, `--panel_title`, `--variable_mapping`,
  `--variable_label_map`, `--center_last_row` and `--legend_panel`;
  `--error_style band` (with `--kind line`) draws the errors as a band.
- `--legend_loc 'top center'`: one legend above the panels, centred on all of
  them, its entries in evenly filled columns.

## 0.1.0 (2026-11-07)

First tagged release, archived on Zenodo.

### `--remove_value COLUMN=VALUE` and unmatched removals (T22.20)

- `--remove_value COLUMN=VALUE` removes the rows whose COLUMN is VALUE,
  whatever the order of the `--select` keys. A plain value still pairs with
  the `--select` keys by position (or the `--hue` column without
  `--select`); a value with `=` whose left part is not a column stays a
  plain value.
- A `--remove_value` that removes no row in any filtering step of a command
  is reported once, naming the column it was paired with. Before, a value
  paired with the wrong key (e.g. the first `--select` key) did nothing,
  silently.

### `cat --kind point` markers (T22.19)

- Without error bars, `cat --kind point` drew every hue value as a circle
  while the legend showed each value's own marker (square, triangle, ...).
  The points now use the legend's marker.

### Upper-panel tick labels with tiny values (T22.18)

- Where an upper panel meets a lower one, plotipus hides the upper panel's
  lowest y label if it collides with the lower panel's top label. The match
  used an absolute tolerance of 1e-12, so with tick values below that (e.g.
  cross sections around 1e-45 cm^2) every label was hidden. The match is
  now relative; a tick at zero uses the axis range.

### Lower panels compare series with gaps (T22.17)

- Operations between series in a lower panel (`ratio`, `subtract`,
  `group`, ...) compare them on the x values they all share. A series with
  NaN points (dropped on extraction) or a different x range used to be
  skipped with "x values are not aligned"; it is now compared where it has
  values, and a warning says how many points were left out. Only a series
  sharing no x value with the first is still skipped.

### Parquet input (T22.16)

- `--datafile NAME` also finds `NAME.parquet` (and the `{config}_{name}_`
  forms) when no `NAME.pkl` exists; a full path to a `.parquet` file works
  too. List cells are read back as numpy arrays and lists of lists as 2D
  arrays, so every kind draws from Parquet exactly as from a pickle.
- `plotipus.save_frame(frame, path)` writes a frame in the plotipus
  convention (2D array cells included); `plotipus.load_frame` reads both
  formats.
- Needs pyarrow: `pip install 'plotipus[parquet]'`. Pickle-only projects
  are unaffected; a pickle wins over a Parquet file of the same name.

## The redesign (T01–T19)

This is the breaking release: plotipus now draws in the `slides` style by
default, at the size a figure is shown at, and many old defaults that were
bugs are gone.

**To keep the old look, pin `classic`:** `style = ["classic"]` in
`plotipus.toml`, or `--style_preset classic` on one command. It restores the
old size (8 × 6 in), fonts, tab10 colours, red fit and zero lines, 1-dof
contours, fixed margins, 100 dpi PNGs, automatic titles and offset text.
The bug fixes below stay fixed under `classic`.

### Experiment presets and watermarks (T17)

- A header label above the axes: `--label`, `--label_status`,
  `--label_right` (or `[header]` in `plotipus.toml`, or a style's
  `"header"`), and experiment presets `--experiment atlas|cms|lhcb|alice|dune`
  with each experiment's label typography (and its fonts and palette where
  its guidelines or mplhep set them). Text only; logos stay with figure hooks.
- A status watermark: `--watermark wip|preliminary|internal|simulation|draft|TEXT`,
  in the corner or `--watermark_style diagonal` behind the data;
  `--watermark none` drops a project's watermark for one command.
- Nothing changes for figures without these options.

### Styles (T16)

- The default style is `slides`: the plotipus language (ticks in on four
  sides, no grid, frameless legends, Petroff-10 colours) on an 8 × 5.84 in
  slide at 14 pt sans. The other names are `slides-dark`, `paper` (a 3.4 in
  journal column at 8 pt Computer Modern, no titles), `paper-dark`, `open`
  (L-shaped frame, ticks out, a faint y grid; 8 in at 96 dpi), `open-dark`
  and `classic`. Choose one with `style = ["paper"]`, `--style_preset NAME`,
  or by parts with `--medium` and `--theme`. Restore: `classic`.
- `--save_style` (or `[project] save_style = true`) writes
  `<figure>.style.json`, the resolved style layers and rcParams, next to
  each figure.
- `map --cmap diverging` uses the style's map for signed values (`RdBu_r`,
  `berlin` on dark backgrounds).
- Dark themes use Petroff-10 in the same order with lightened twins of its
  three darkest colours (contrast ≥ 3.5:1 on the background).
- Plugin settings keep their say over the named style; the project's style
  files have the last word.

### Behaviour changes by task, and how to restore each

| task | change | restore |
|---|---|---|
| T01 | Every series of a figure gets its own colour (mappings first, then the next free palette colour); the palette is Petroff-10; past its end colours repeat with a warning. `--combined_color`, `--sum_color`, `--reference_sum_color` default to the next free colour. | `--palette tab10` (or `classic`); reused colours were a bug |
| T02 | Δχ² contours for 2 dof (2.30, 6.18, 11.83), labelled "68.3% CL"; graded fills, solid/dashed/dotted outlines, a `+` at the minimum, no background by default. | `--contour_dof 1 --contour_label sigma --background all` (or `classic`) |
| T03 | Binned estimators draw their uncertainty (s.e.m. and friends), named in the y label. | `--no_error_label` for the label |
| T04 | `hist` bins every hue on the same edges over the range of all hues; `--flow` marks entries outside the range. | none (bugs) |
| T05 | `scatter --hue` keeps every group. | none (bug) |
| T06 | `--fit --lower pull` is (data − fit)/σ with ±1σ/±2σ bands; one panel per `--lower`. | `--lower_labely` for the old label |
| T07 | Bands for lines and steps, bars for points; error-bar points are not joined. | `--errory_type bars`, `--connect` |
| T09 | One shared, labelled colorbar per row of `map` panels; empty bins are blank. | `--colorbar each` |
| T10 | Box plots dodge the hues, label the bins and list each group once. | none (bugs) |
| T11 | Colours that are not data colours come from style roles (ink, muted, faint, paper); zero lines are muted and dashed, fit lines ink. | `--lower_zero_color red`, `--fit_color red` (or `classic`) |
| T12 | Tick labels are plain numbers; a common power of ten goes into the axis label ("Density (×10⁻²)"); PNGs at 300 dpi. | `--no-sci_in_label`; `"rcparams": {"savefig.dpi": 100}` (or `classic`) |
| T13 | Margins and panel spacing are measured, so nothing is clipped; colorbars no longer narrow their panels; axis labels share one size. | `"figure_layout": {"fixed_margins": true}` (or `classic`) |
| T14 | Media (`slides`, `paper`, `web`) and themes; `--width`, `--aspect`; other media write to `output/plots/<medium>[-dark]/`; no automatic titles in a medium; paper drops `--title`. | `--keep_title`; `classic` keeps the old size and titles |
| T15 | Legends never cover data (corners, free spots, headroom, then above the axes); entries follow the data; lower panels in the upper colours draw no legend. | `--legend_loc <corner>`, `--legend_order data` |
| T18 | `--stacked` stacks in data space for every binned plot type; `--overlay` keeps data out of the stack. | none (bug) |
| T19 | `--errory_type poisson` (exact Garwood intervals; the default for `--overlay data` without an error column) and `--errory_type clopper_pearson --count_column N`; in slides and web the y label names the interval. | `--errory_type bars` with an error column; `"plot_settings": {"error_label": false}` |
