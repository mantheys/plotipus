# Reproduced bugs, root causes and proposed fixes

Every bug below was reproduced on `main` (88c031c, matplotlib 3.11.2, pandas
3.1.0) and traced to the code; none is inferred from symptoms alone. To
reproduce them:

```bash
cd docs/design/repro
python make_data.py          # toy pickles (the examples' data plus a few probes)
plotipus run repro           # one PNG per bug in output/plots, named *_B<nn>.png
```

The commands are in [repro/repro_scripts.txt](repro/repro_scripts.txt).
Line numbers refer to `src/plotipus/` at 88c031c.

Severity: **S1** wrong or misleading content, **S2** unreadable or broken
output, **S3** cosmetic or inconsistent.

| id | sev | summary | where |
|---|---|---|---|
| [B01](#b01-repeated-colour-in---by_config-the-maintainers-report) | S1 | `--by_config` reuses a colour for the combined series and ignores `config_color` | line.py:170, 1234–1247 |
| [B02](#b02-colour-cycle-wraps-silently-past-10-series) | S1 | Colours wrap silently after 10 hues; `--hue X --style X` gives two legends | encodings.py:152; cat.py:120; map.py:639–649; line.py:701, 813 |
| [B03](#b03-contour-plots-are-hard-to-read-the-maintainers-report) | S1 | Contour levels use 1-dof Δχ² for 2D maps; filled bands alternate opacity; one colour for every level | map.py:320–336, 487–541, 676–691 |
| [B04](#b04-binned-estimators-carry-no-uncertainty) | S1 | `--binned --estimator` draws no error bars; stored errors are averaged | _estimator.py:105–123; transforms.py:335–360 |
| [B05](#b05-tick-labels-like-4e-2) | S3 | Tick labels such as `4e-2`, `-1.5e-2` | plot.py:141–167 |
| [B06](#b06-legends-cover-data) | S2 | Legends cover data (stacked, cat, filled areas); ratio panel labels only one of its series | line.py:874, 976–979; plot.py:303–410; cat.py:187 |
| [B07](#b07-cat-legend-handles-layout-and-scalar-crash) | S2 | `cat`: line handles for bars, fixed rotation and margin, crash on scalar cells | cat.py:79–87, 119–122, 164, 179, 190 |
| [B08](#b08-2d-histogram-colorbars) | S2 | Only the last colorbar is labelled; panels have independent colour scales | map.py:238–263 |
| [B09](#b09-hist-edge-bins-range-and-label) | S1 | `hist`: half-width edge bins, range from the first hue only, legend "None" | hist.py:105–112, 147–153 |
| [B10](#b10---stacked-only-works-for-bars-and-stacks-everything) | S1 | `--stacked` is silently ignored for step plots and stacks the data with the simulation | line.py:468, 617–666 |
| [B11](#b11---errory_type-bands-ignored-unless---plot_type-line) | S2 | `--errory_type bands` is ignored unless `--plot_type line` | plot.py:702–731; line.py:477–481 |
| [B12](#b12-scatter---hue-drops-all-but-the-first-group) | S1 | `scatter --hue` on array cells draws only the first group | scatter.py:367–380 |
| [B13](#b13---fit---lower-pull-draws-the-relative-residual) | S1 | `--fit --lower pull` draws `(data−fit)/fit` and labels it so | _fit.py:148–195, 318 |
| [B14](#b14-hard-coded-colours-ignore-the-style) | S3 | Hard-coded black/red/grey/white break dark and custom styles | 20+ call sites |
| [B15](#b15-layout-in-fixed-inches-clips-labels) | S2 | Fixed-inch margins clip long tick or axis labels; label sizes differ between kinds | plot.py:43–80; kinds/* |
| [B16](#b16-box-plots) | S2 | `--plot_type box`: garbled tick labels, overlapping hue groups, repeated legend entries | plot.py:855–857 |
| [B17](#b17-points-joined-by-lines-and-low-resolution-output) | S3 | Error-bar data joined by lines; PNGs saved at 100 dpi | line kind `--plot_style`; style.json |

---

## B01 Repeated colour in `--by_config` (the maintainer's report)

**Reproduce:** `B01` (the examples' efficiency plot). "Small Detector" and
"Average" are both C0 blue; the `config_color` mapping (small → C3,
large → C4) in `examples/style.json` is ignored.

**Root cause.** `prepare_import` pairs the two `--configs` with the single
`--names` value, giving two configs and two names (io.py:172–175). In
`run_by_config`, `two_lines = len(configs) == 2 and len(names) == 2` is
therefore true, and that branch assigns `f"C{ldx}"` without consulting the
mappings (line.py:1234–1235):

```python
if two_lines:
    color, linestyle = f"C{ldx}", "-"          # mapping ignored
elif single:
    color, linestyle = f"C{(kdx + offset) % 10}", "-"
else:
    color, base_linestyle = make_config_color_and_style_from_args(...)
```

The combined series is then drawn with `args.combined_color`, whose default
is the literal `"C0"` (line.py:170), the colour already taken by the first
config. The `offset = 1` reserved for `--combine_op` (line.py:1163) only
applies to the `single` and mapped branches. A second, latent collision:
`kdx` advances per `--hue` value but `ldx` restarts for each one, so with
`--hue` and two configs every hue value gets C0/C1.

**Fix.** Allocate colours through one function for all three branches:
mapping first, then the next unused palette index (a per-figure
`ColorAllocator` that remembers which colours are taken). Change the
`--combined_color` default to `None`, meaning "next free colour", or
black/ink for a total. Remove the `two_lines` special case.

**Fixed in T01.** `palettes.ColorAllocator` gives every series of a figure
its colour (mapping first, then the next free palette slot); the
`two_lines` branch is gone and `--combined_color`/`--sum_color`/
`--reference_sum_color` default to the next free colour. Restore option:
none (the reuse was a bug); `--palette tab10` restores the old colours.

## B02 Colour cycle wraps silently past 10 series

**Reproduce:** `B02a` (12 runs: run10/run11 repeat run00/run01) and `B02b`.

**Root cause.**
- Every kind builds `"C{n}"` strings: `resolve_cycle_color` (encodings.py:152–154), `cat.py:120` (`C{idx % 10}`), `hist.py:108–110`, `map.py:639–649`, `line.py:701` and `line.py:813`.
- matplotlib resolves `CN` modulo the length of `axes.prop_cycle`, so index 10 is C0 again. The explicit `% 10` in several places also hard-codes the cycle length, so a longer cycle in a style would be truncated.
- When hue values outnumber the colours, nothing switches to a second channel and nothing warns.
- With `--hue X --style X`, `_finish_upper` draws a colour legend and a separate line-style legend for the same values (B02b) instead of one legend whose entries carry both.

**Fix.**
- Read the cycle length from `plt.rcParams["axes.prop_cycle"]` and drop every `% 10`.
- When there are more values than colours, assign (colour, line style) pairs: colour cycles fastest, and the style changes on each wrap. Print a warning suggesting `--colorby` (a sequential colormap) for ordered values such as run numbers.
- Merge the two legends when `--hue == --style`.

**Fixed in T01.** No `C{n}` strings or `% 10` remain at these sites; the
cycle length comes from the active palette (`--palette`, style key
`palette`, default `petroff10`). Past its end colours repeat with one
warning per figure; line styles stay reserved for `--style` and mapped
configs (maintainer's decision: no automatic colour × line-style product).
`--hue X --style X` draws one legend whose entries carry both encodings.

## B03 Contour plots are hard to read (the maintainer's report)

**Reproduce:** `B03` (examples' contour plot).

There are four separate root causes.

1. **Wrong levels for a 2D confidence region.** `contour_levels` uses `s**2` in `sigma_probability` mode (map.py:487–489), so the levels are Δχ² = 1, 4, 9. Those are the 1-parameter (1 dof) thresholds. For a joint region in two parameters (the usual "1σ/2σ/3σ contour" of a 2D scan), the 68.27/95.45/99.73% levels are Δχ² = 2.30, 6.18, 11.83. The contour labelled "1σ" therefore encloses only 39.3% probability. `sigma_labels` writes "1σ" with no indication of the convention (map.py:492–498). Some communities do draw 1-dof contours in 2D, so this must be an explicit option, not a silent default.

2. **Filled bands alternate in opacity.** `draw_filled` builds `levels=[-inf, 1, 4, 9, inf]` and treats the first band (below the lowest level) as the "outer" one with `alpha_max` (map.py:520–534). For a Δχ² map, the band below the lowest level is the innermost region, around the best fit. The resulting alphas are: inside 1σ 0.95, 1σ–2σ 0.475, 2σ–3σ 0.95, outside 0. Opacity therefore does not increase with confidence: the 1–2σ ring looks like a hole between two solid shapes, which is exactly what the example shows.

3. **One colour for everything.** `band_hues(color, n)` returns `[color] * n` when `color` is not a palette (map.py:320–325). Every band, every outline and every legend handle is C0, so the legend shows three identical swatches, `1σ 2σ 3σ`.

4. **The background competes with the contours.** The raw Δχ² image is drawn with viridis up to its maximum (88). The colorbar is labelled with the column name `ZGrid`, there is no best-fit marker, and the blue fills sit on a blue-purple background.

**Fix.**
- Add `--contour_dof {1,2}` (default 2) and label levels by coverage ("68.3% CL") or as "1σ (2 dof)".
- In filled mode, order bands from the best fit outwards: the innermost region darkest, each outer ring lighter, outside unfilled. Use one hue per dataset in graded lightness (e.g. 100/60/30% mix with the paper colour).
- Use solid, dashed and dotted outlines for 1σ, 2σ and 3σ, so the levels survive greyscale and CVD.
- Mark the minimum with a `+`.
- Turn the background off by default for Δχ² maps (`--background none`). When it is requested, clip it at the outermost level and label the colorbar `Δχ²`.

**Fixed in T02.** `--contour_dof {1,2}` (default 2: Δχ² = 2.30, 6.18,
11.83) and `--contour_label {cl,sigma}` (default `cl`: "68.3% CL"); filled
bands are graded from the best fit outwards (one hue mixed with the paper
colour, style `contours.fill_mix`), outside unfilled; outlines solid, dashed
and dotted, and legend handles carry each level's line style and fill; a `+`
marks the minimum (`--no_best_fit`); `--background` defaults to `none`, and
a requested Δχ² background is blank beyond the outermost level with a `Δχ²`
colorbar. Defaults come from the style's `contours` section. Restore option:
`--contour_dof 1 --contour_label sigma --background all` (the old fills were
the bug); legacy translations append `--contour_dof 1`.

## B04 Binned estimators carry no uncertainty

**Reproduce:** `B04` (examples' "Mean Resolution" plot) has `--plot_type
errorbar`, but no error bars appear, and the bin means of ~270 events each
are joined by lines.

**Root cause.** `_reduce_cell` computes `bin_reduce(x, y, edges, estimator)`
and nothing else (_estimator.py:120–123). The estimator table
(transforms.py:335–344) has no notion of the uncertainty of a statistic.
Errors exist only when the user also passes an error column with
`--errory`, and that column is then reduced with the *same* estimator
(_estimator.py:122). The bin's mean error is reported as the uncertainty of
the bin mean, overstating it by √n.

**Fix.** Make each estimator return `(value, error)`:
- mean: σ/√n.
- median: 1.2533·σ/√n, or a bootstrap with a fixed seed.
- std: σ/√(2(n−1)).
- rms: the delta method.
- sum: √Σw² for weights, √n for counts.

Propagate stored per-event errors as √Σe²/n for the mean. Add
`--estimator_error {sem,std,none}` and say which one is used in the legend
or `--note`. Drop bins with fewer than `--min_count` (default 5) entries
instead of drawing a meaningless value (std = 0 for one event).

**Fixed in T03.** Each estimator returns `(value, error)`
(`transforms.estimate`/`bin_estimate`); stored errors are propagated;
`--estimator_error`, `--min_count` and the y-label suffix
(`--no_error_label`) are in. Joined points under an explicit `--plot_type
errorbar` are B17 (T07).

## B05 Tick labels like `4e-2`

**Reproduce:** the examples' `hist` (`4e-2`, `3.5e-2`, …) and `B04`
(`-1.5e-2`).

**Root cause.** `_make_threshold_formatter` turns every |value| < 0.1 into a
plain `"{mantissa}e{exp}"` string (plot.py:141–157). It is installed as the
major formatter of both axes by `hist.py:175`, `line.py:1283`,
`_estimator.py:210, 328` and `map.py:287, 816`, which overrides the style's
`axes.formatter.use_mathtext` and offset settings.

**Fix.**
- Remove the custom formatter and use `ScalarFormatter(useMathText=True)` with `axes.formatter.limits` from the style.
- Better, move the power of ten into the axis label ("Density [10⁻²]") following the complaint consensus (research Part 2 §4).
- Keep `LogFormatterSciNotation` on log axes.

## B06 Legends cover data

**Reproduce:** `B06a` (stacked bars) and the examples' cat plot; `B06b`
(ratio panel).

**Root cause.**
- For `--stacked`, `_finish_upper` hard-codes `loc="upper left",
  bbox_to_anchor=(0, 1)` (line.py:976–979). That is where the tallest bars
  are on falling spectra.
- `cat` hard-codes `"lower left"` (cat.py:187), which is inside the bars.
- The automatic placement `apply_legend_style_clear_of_data` scores
  candidate boxes by sampled points on drawn paths (plot.py:303–410).
  Filled patches (bars, `fill_between` bands, filled contours) contribute
  only their outline vertices, so a box inside a bar or a band looks empty.
- The legends are frameless (`frameon: false`), so overlap is not even
  softened.
- In the lower panel, `_lower_series(..., label if first else None)`
  (line.py:874) labels only the first series. A ratio panel with two
  coloured series shows one legend entry, "Ratio".

**Fix.**
- Make filled areas occupied when scoring (rasterise the axes to an occupancy mask, or sample patch interiors).
- Remove the hard-coded locations.
- When no corner is free, reserve headroom: extend the y range by the legend height, or place the legend above the axes (matplotlib's `loc="outside upper center"`).
- In ratio panels, either label each series "X / reference" or put no legend at all and let the y label say "Ratio to Signal" (the colours already match the upper panel).

## B07 cat: legend handles, layout and scalar crash

**Reproduce:** `B07a` (examples' cat plot) and `B07b` (traceback).

**Root cause.**
- Hue handles are always `Line2D(..., linestyle="-", marker=marker)`
  (cat.py:119–122), even for `--kind bar`. The legend therefore shows
  line+marker icons next to bars.
- Tick labels are always rotated 20° (cat.py:164), even for two short
  categories.
- `fig.subplots_adjust(bottom=0.22)` (cat.py:190) adds a large empty band
  under the axes.
- A y grid is switched on here only (cat.py:179). No other kind does this.
- `integrate_row` calls `len(y)` on the cell (cat.py:79–87), so a
  DataFrame with one scalar per row (feature importances, a metric per
  model) crashes with `TypeError: len() of unsized object`. One value per
  category is the kind's stated purpose.

**Fix.**
- Use `Patch` handles for bars.
- Rotate tick labels only when they overlap, which the layout can measure.
- Let the margin come from the layout engine (B15).
- Treat scalar cells as already integrated.
- Move the grid decision into the style.

## B08 2D histogram colorbars

**Reproduce:** `B08` (examples' `map --iterable Sample --logz`).

**Root cause.**
- The colorbar label is set after the panel loop on the last `cbar` only
  (map.py:260–263), so every panel but the last has an unlabelled colorbar.
- Each panel gets its own `fig.colorbar` (map.py:238, 253) with its own
  colour limits, so equal colours mean different counts in different panels.
- Under-range bins (1 count, log scale) take the darkest colour, the same as
  the most significant structure in viridis.

**Fix.**
- Use one shared norm and one colorbar for the row (`fig.colorbar(mappable, ax=axes)`) when panels share a quantity, or label every bar.
- Set `vmin` at the lowest non-empty bin and leave empty bins blank.

**Fixed in T09.** Panels of one `map` figure share a norm (`vmin`/`vmax`
over all of them) and one colorbar right of the row (`--colorbar shared`,
default unless `--norm`); `--colorbar each` restores per-panel bars, now
each labelled. Empty bins are masked on linear and log scales, and a log
scale starts at the smallest non-empty bin. Bars are as tall as the axes,
4% of their width with 2% padding (scatter `--colorby` too).

## B09 hist: edge bins, range and label

**Reproduce:** `B09a` (flat distribution: the first and last bins are drawn
half as wide; legend "None") and `B09b` (group C cut at x ≈ 3.8).

**Root cause.**
- `hist` passes bin centres to `plot_data(..., plot_type="plot",
  drawstyle="steps-mid")` (hist.py:152–153). `steps-mid` puts the steps
  halfway between centres, so the outermost half-bins are lost.
- The histogram range is computed once per panel, from the first hue value
  (`if idx not in ranges: ranges[idx] = _histogram_range(x, ...)`,
  hist.py:147–149). Every other hue is silently clipped to it.
- Without `--hue`, `_series_style` labels the series `f"{value}"`, which is
  `"None"` (hist.py:111).

**Fix.**
- Draw with `ax.stairs(counts, edges)`.
- Compute the range over all hues in the panel, plus under- and overflow markers (mplhep's `flow="hint"`).
- Use no legend for a single unnamed series.

**Fixed in T04.** `hist` draws with `ax.stairs(counts, edges)`; the range is
computed once per panel over all drawn hues (`--panel_rangex`, `--rangex`,
`--percentile` keep their precedence) and every hue gets the same edges. New
`--flow {none,hint,show}` (default `none`) marks or adds the entries outside
the range, whose number is printed in every mode. A single series without
`--hue` gets no legend and no "None" label. Restore option: none (all three
were bugs).

## B10 `--stacked` only works for bars and stacks everything

**Reproduce:** `B10a` (`--stacked --plot_type step` draws overlapping,
unstacked steps) and `B10b` (`--stacked` puts the data on top of the
simulation).

**Root cause.**
- `draw_series` stacks only when `plot_type in (None, "bar")`
  (line.py:468). Every other plot type falls through to the unstacked
  drawing with no warning.
- The stack loop (line.py:617–666) adds every hue value to
  `stack_bottoms`, so there is no way to stack the simulation and overlay
  the data. The canonical data/MC comparison (research F03) cannot be
  drawn.

**Fix.**
- Implement stacking in data space: cumulative sums drawn as `stairs` with `baseline` = the previous cumulative sum, or `fill_between`. This works for step, filled step and bars.
- Add `--overlay VALUE [...]` (hue values drawn on top, unstacked, as points with Poisson errors) and `--stack_total_error` (hatched band on the stack total).

## B11 `--errory_type bands` ignored unless `--plot_type line`

**Reproduce:** `B11` draws error bars although bands were requested.

**Root cause.** `--errory_type` is only read inside the `plot_type ==
"line"` branch of `plot_data` (plot.py:702–731). Without `--plot_type`,
`draw_series` goes to the error-bar path (line.py:477–481).

**Fix.** Read `--errory_type` before dispatching on plot type: bands for
`line`/`step`/default, bars only for points.

**Fixed in T07.** `plot_data` resolves `--errory_type` before the plot
type: bands (stepwise across the bins for steps) for `line`/`step` and
`--errory_type bands`, bars for points by default. Restore option:
`--errory_type bars`.

## B12 scatter `--hue` drops all but the first group

**Reproduce:** `B12`. Three groups are requested, and only group A is drawn;
the legend shows one entry.

**Root cause.** `explode_points` keeps only the first row per Config/Name
when `--markerby` is not set (scatter.py:367–380). The intent is not to
merge unrelated rows, but it ignores `--hue`. The warning says to pass
`--markerby`, which is not what the user asked for.

**Fix.** Include the `--hue` column, and any `--style` column, in the
grouping keys before dropping rows.

## B13 `--fit --lower pull` draws the relative residual

**Reproduce:** `B13`. The lower panel is labelled `(Data - Fit)/Fit`,
although `pull` was requested.

**Root cause.**
- With `--fit`, the line kind goes through `_fit.py`. `_draw_fit_rows`
  always computes `diff / fit` (_fit.py:170–179), whatever the value of
  `--lower`. The y label is hard-coded (_fit.py:318).
- The generic `lower_model_series`, which does implement pull
  (lower.py:279–289), is not called on this path.
- The relative residual also diverges where the fit goes to zero (the tails
  of a Gaussian). That is why the lower panel shows ±1 error bars filling
  the range.
- The fit line is hard-coded red and the residual markers black.

**Fix.**
- Route the fit's lower panel through `lower_model_series`.
- Default to `pull` for count data.
- Use the data colour (or ink) for the fit and residuals.

## B14 Hard-coded colours ignore the style

**Reproduce:** render any `--style` plot with the slides/dark overlay
([styles/slides/png/01_spectra_hue_style.png](styles/slides/png/01_spectra_hue_style.png)):
the line-style legend handles are black on a dark background.

**Root cause.** These literals bypass the style:
- `color="black"` in encodings.py:242, 273, 281; cat.py:159; scatter.py:351; _fit.py:194; _estimator.py:286; plot.py:1324.
- Red zero lines in line.py:889 and _fit.py:209–217.
- Grey in line.py:961, 987–991, 1278; panels.py:131; scatter.py:321, 412, 454.
- White/black in map.py:256, 822, and the combined contour default `"black"` (map.py:125).

**Fix.** Introduce style roles in style.json: `ink` (text and reference
lines), `muted` (guides and bands), `paper` (background), `accent`
(highlight). Use them everywhere. ggplot2 4.0 does the same with
`ink`/`paper`/`accent` (research Part 1 §2.4).

## B15 Layout in fixed inches clips labels

**Reproduce:** in the current style, "Mean Resolution" in `B04` touches the
left edge. In the column-width candidate styles it is clipped:
[styles/compare/05_binned_mean.png](styles/compare/05_binned_mean.png).

**Root cause.**
- `apply_common_figure_margins` converts fixed inch margins from
  style.json to figure fractions (plot.py:43–80). Nothing measures the
  actual tick-label or axis-label extents, except `grow_for_tick_labels`,
  which handles rotated categorical labels only.
- Kinds also disagree on label sizes: some call
  `set_xlabel(..., fontsize=style.xlabelfontsize)` (xx-large), others rely
  on rcParams `axes.labelsize` (x-large). In the examples, scatter's "Hits"
  is larger than hist's "Reco Energy".

**Fix.**
- Measure, then set margins: after drawing, compute each axis's tight bbox and grow the margins to fit, keeping the axes size fixed.
- Alternatively, use matplotlib's constrained layout with fixed figure width.
- Set all label sizes in one place (rcParams), and remove the per-call `fontsize=`.

## B16 Box plots

**Reproduce:** `B16`.
- The x tick labels are the bin positions printed with many decimals, and
  they overlap.
- The three hue groups are drawn at identical positions, on top of one
  another.
- The legend repeats "Median Yv" once per group, with the same orange.

**Fix.** Dodge hue groups within each bin, format tick labels with the
axis formatter (or as bin ranges), and use one legend entry per group,
coloured by group.

## B17 Points joined by lines, and low-resolution output

- **Points joined by lines.** With `--plot_type errorbar`, the line kind
  applies its `--plot_style` default, which joins the points (B04).
  _fit.py:105 already works around this ("Points only (the line kind's
  --plot_style default would join them)"). Measured points with error bars
  should not be joined unless `--connect` is given.

  **Fixed in T07** (this point; output resolution is T12). Error bars on
  points use `linestyle="none"`; `--connect` restores the joined look, and
  the `_fit.py` workaround is gone.
- **Low resolution.** `savefig.dpi` is unset, so PNGs are written at the
  100 dpi figure DPI: 800×600 px for an 8×6 in figure. Use vector output
  (PDF) for papers and `savefig.dpi: 300` for PNG.

## Non-bugs worth noting

- **`--reference` takes an index.** `--reference data` fails argument
  parsing; the hue value goes in `--reference_value`. Accepting either
  would remove a common stumble.
- **Step outlines drop to the axis at the outer edges on log axes.** This
  is the conventional HEP histogram look, and `--step_open` already
  exists.
