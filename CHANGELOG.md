# Changelog

## Unreleased

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
  sides, no grid, frameless legends, Petroff-10 colours) on an 8 × 4.5 in
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
