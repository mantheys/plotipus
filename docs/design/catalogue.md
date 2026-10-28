# Chart catalogue and support matrix

Phases 2 and 3 of the redesign: every chart a data scientist or physicist
routinely needs, mapped to the famous figures in [research.md](research.md)
(ids F01–F25) and to what plotipus can do today.

**How the status was decided.** A status is "supported" only when the command
was run and its PNG inspected. The probe ids (P01–P24, Q1–Q6) are the
commands in [repro/probe_scripts.txt](repro/probe_scripts.txt), run against
the toy data from [repro/make_data.py](repro/make_data.py)
(`cd docs/design/repro && python make_data.py && plotipus run probe`). Ids
starting with B refer to [bugs.md](bugs.md).

| Status | Meaning |
|---|---|
| ✅ | Works today with the command shown. |
| ◐ | Partly works; the missing options or bugs are listed. |
| ✗ | Not possible today; the smallest change that would cover it is sketched. |

**Design rule kept in every sketch.** Kinds follow the data relationship,
not the use case:
- `hist`: a 1D distribution of raw values.
- `map`: two continuous dimensions.
- `line`: y against an ordered x.
- `scatter`: individual observations.
- `cat`: values per category.
- `table`: aggregated numbers.

New charts become options of the kind whose relationship they show, so
there is no `roc` or `brazil` kind. Use-case presets live in example
command lists.

**Summary.**

| Group | ✅ | ◐ | ✗ |
|---|---|---|---|
| A Distributions | 12 | 0 | 0 |
| B Relationships | 9 | 0 | 0 |
| C Trends and fits | 10 | 0 | 0 |
| D Comparisons | 9 | 0 | 0 |
| E Ratios and significance | 8 | 0 | 0 |
| F ML diagnostics | 7 | 0 | 0 |
| G Uncertainty | 9 | 0 | 0 |
| H Small multiples and layout | 8 | 0 | 0 |
| I Annotations | 10 | 0 | 0 |
| J Tables | 7 | 0 | 0 |
| **Total (89)** | **89** | **0** | **0** |

Nearly half of the ◐ entries are partial only because of a bug in
[bugs.md](bugs.md), not because an option is missing. Fixing B01–B13 moves
about 12 of them to ✅.

---

## A. Distributions (one variable)

| id | chart | use | famous | status | command today / what is missing | smallest change |
|---|---|---|---|---|---|---|
| A1 | Histogram, step outline | compare shapes of a few samples | F03 | ✅ | `hist --datafile Ev -x Xv --hue Group --bins 40` (P12). Full-width edge bins, one range over all hues, entries outside reported and shown with `--flow hint\|show` (B09, fixed in T04). | — |
| A2 | Histogram of pre-binned counts | analysis outputs already binned | F03, F16 | ✅ | `line --datafile Spectra -x Energy -y Counts --hue Sample --plot_type step --logy` (example 1). | — |
| A3 | Filled / stacked histogram (stacked MC) | composition of a total | F03, F23 | ✅ | `line --datafile Spectrum -x Mass -y Counts --hue Sample --remove_value data --stacked [--plot_type step\|fill]` (B10a; fixed in T18). | — |
| A4 | Normalised / density histogram | shapes at different statistics | — | ✅ | `hist --datafile Ev -x Xv --hue Group --bins 40 --density --logy` (P13). | — |
| A5 | Weighted histogram | event weights | — | ✅ | `hist ... --weight Yv` (Q4). Errors not drawn: see G2. | — |
| A6 | Histogram with Poisson errors | counts with statistical uncertainty | F01, F03 | ✅ | `hist ... --errory_type poisson` (Garwood from the bin counts, √Σw² with `--weight`); `line ... --errory_type poisson` on pre-binned counts (T19). | — |
| A7 | KDE | smooth density of a sample | — | ✅ | `hist --datafile Scores -x Score --hue Class --hist_type kde` (T22.4, gallery A7): scipy `gaussian_kde`, Scott bandwidth or `--bw`, a band of the pointwise standard error; unit area, or counts per bin under `--data_hue` points. | — |
| A8 | ECDF / cumulative | quantiles, comparing tails | — | ✅ | `hist --hist_type ecdf` (T22.4, gallery A8): steps from 0 to 1 with a binomial band; `--cumulative [reverse]` accumulates a histogram with Garwood errors. | — |
| A9 | Box plot per category | distribution summaries side by side | — | ✅ | `line --binned --plot_type box --hue Sample` (P14): hues dodged per bin or per category of a non-numeric x, `--box_tick_labels ranges`, `--whis` (B16, fixed in T10). | — |
| A10 | Violin / strip / box per category | distributions per category | F25 | ✅ | Per category: `cat --datafile Showers -x Particle -y Response --kind violin` (or `box`, `strip`; T22.2, gallery A10b): the array cells of a category pooled as one distribution, hue values side by side, `--orient h`. Per bin of a numeric x: `line --binned --plot_type violin` (or `box`; example-feedback round 4). | — |
| A11 | Ridgeline (joy plot) | many distributions, ordered | — | ✅ | `hist --hue Model --hist_type kde --ridge [OVERLAP]` (T22.4, gallery A11): each hue on its own baseline, the first on top, named on the y axis. | — |
| A12 | Rug | raw positions under a hist or KDE | — | ✅ | `hist --hist_type kde --rug` (T22.4, gallery A12): a tick per value along the x axis, fainter the more there are. | — |

## B. Relationships (two or more variables)

| id | chart | use | famous | status | command today / what is missing | smallest change |
|---|---|---|---|---|---|---|
| B1 | Scatter | raw relation | F08, F22, F25 | ✅ | `scatter --datafile Events -x TrueEnergy -y Hits --colorby RecoEnergy` (example); `scatter --datafile Ev -x Xv -y Yv --hue Group` draws every group (P16; B12, fixed in T05). | — |
| B2 | Scatter with error bars | measurements with uncertainties | F08, F09, F20 | ✅ | `line --plot_type errorbar --errory` (with `--errory_x`, or `--errorx_column LOW HIGH` for real bin edges, for x errors; P03, P04). Points are not joined unless `--connect` is given (B17, fixed in T07). | — |
| B3 | Scatter coloured / sized by a third variable | 3–4 variables at once | F22 | ✅ | `scatter ... --colorby RecoEnergy --sizeby Hits` (example). | — |
| B4 | 2D histogram | dense scatter | F22 | ✅ | `map --datafile Events -x TrueEnergy -y RecoEnergy --iterable Sample --logz` (example). One shared, labelled colorbar (B08, fixed in T09). Each panel keeps a single plot's size, wrapping past the medium's facet columns (L3). | — |
| B5 | Hexbin | dense scatter, smoother look | F22 | ✅ | `map --map_type hexbin --bins 40 --logz` (gallery B5; T22.9): `ax.hexbin` with the 2D histogram's colour scale, shared colorbar, `--norm global` and `--density`. | — |
| B6 | Gridded map (z on x×y) | functions, scans, images | F15 | ✅ | `map --datafile Contour -x XGrid -y YGrid -z ZGrid` (P17 for a 3×3 grid). | — |
| B7 | Contour lines / filled contours | levels of a 2D function | F10 | ✅ | `map ... -z ZGrid --contour --contour_sigmas 1 2 3 [--fill_contours]` (example). 2-dof Δχ² levels labelled by coverage, graded fills from the best fit outwards, solid/dashed/dotted outlines, `+` at the minimum (B03, fixed in T02). | Non-σ levels with inline `clabel`: I9. |
| B8 | Pair plot / corner plot | all pairs of N variables | — | ✅ | `map --corner TrueEnergy RecoEnergy Hits` (gallery B8; T22.9): N×N grid, 2D histograms (or `--map_type hexbin`) below the diagonal, step histograms with Garwood bands on it, axes shared per column and row, outer labels only, one colorbar. | One sample per figure (no overlaid hues). |
| B9 | Profile (mean y per x bin) | trend in a dense scatter | — | ✅ | `line --binned --estimator mean` (example 5): standard error of each bin's statistic, small bins dropped (B04, fixed in T03). | — |

## C. Trends, fits and time series

| id | chart | use | famous | status | command today / what is missing | smallest change |
|---|---|---|---|---|---|---|
| C1 | Lines, colour by hue, style by a second variable | several series vs x | F11, F13 | ✅ | `line ... --hue Sample --style Stage` (example 1). Past the palette, colours repeat with a warning (B02, fixed in T01); `--palette` picks the palette. | — |
| C2 | Line with uncertainty band | curve ± σ | F14, F15 | ✅ | `line --errory --plot_type line` (bands are the default for lines and steps), or `--errory_type bands` with any plot type (P09; B11, fixed in T07). | — |
| C3 | Stored fit over data with parameter box | publish a fit result | F06, F08, F19 | ✅ | `line --datafile Fit -x X -y Counts --fit --plot_type errorbar --errory` (P04). Fit line in the style's `ink` role (`--fit_color`, T11). | — |
| C4 | Fit with residual panel | fit quality | F01, F06, F07, F09 | ✅ | `... --fit --lower residual` (P04): (data−fit)/fit, masked where the fit is below 1e-3 of its peak (B13, fixed in T06). | — |
| C5 | Fit with pull panel | fit quality in σ | F01, F17 | ✅ | `... --fit --lower pull` (P05): (data−fit)/σ with ±1σ/±2σ bands; `--lower residual --lower pull` stacks both (B13, fixed in T06). | — |
| C6 | Several model curves over data | model comparison | F09, F12, F17 | ✅ | `line --hue Model --plot_type line --series_type data=errorbar` (F09, F12, F17): points with error bars for data, on top, lines for the models; `--series_type_mapping` sets the types in a style file (T21). | — |
| C7 | Stacked area | composition over x | F23 | ✅ | `--stacked --plot_type line` (`fill_between` from the running total; B10 fixed in T18). | — |
| C8 | Time series with dates | monitoring, Keeling curve | F13 | ✅ | `line -x Day` with a datetime column (T22.10): date numbers on a `ConciseDateFormatter` axis; decimal years still work as numbers. | — |
| C9 | Smoothed / rolling line | trend under noise | F13, F14 | ✅ | `line --smooth 15 [--smooth_kind savgol] [--smooth_only]` (T22.10): the smoothed line over the faint raw series. | — |
| C10 | Many series with a sequential colour | ordered hue (runs, energies) | F11 | ✅ | `line --hue Run --hue_cmap viridis` (also `hist`; T22.5): numeric hues by value, others in draw order, a colorbar instead of the colour legend. | — |

## D. Comparisons across categories

| id | chart | use | famous | status | command today / what is missing | smallest change |
|---|---|---|---|---|---|---|
| D1 | Bar chart (integrated arrays) | totals per category | — | ✅ | `cat --datafile Distributions -x Distribution --hue Sample -y Counts --select Distribution -s Resonance --kind bar` (example `yields`): patch handles, legend clear of the bars, labels rotated only when they overlap (B07, fixed in T08). | — |
| D2 | Bar chart of scalar cells | one metric per category | — | ✅ | `cat --datafile Importance -x Feature -y Importance --hue Model --kind bar` (P10): a scalar cell is one value already (B07, fixed in T08). | — |
| D3 | Grouped bars | category × group | — | ✅ | `cat --kind bar --hue ...` dodges hues (example `yields`; B07 fixed in T08). | — |
| D4 | Stacked bars per category | composition per category | F23 | ✅ | `cat --datafile Yields -x Stage -y Counts --hue Particle --kind bar --stacked --errory` (gallery D4): one stack per category, the legend from the top, a hatched band of the total's error; `--data_hue` points on top. | — |
| D5 | Horizontal bars (sorted) | long labels, rankings | — | ✅ | `cat --datafile Importance -x Feature -y Importance --hue Model --kind bar --orient h --sort desc --errory` (T22.1, gallery D5): categories down the y axis, the first on top, sorted by their total. | — |
| D6 | Dot plot / Cleveland dot | many categories, precise values | — | ✅ | `cat --kind point --orient h --sort desc --errory` (T22.1, gallery D6): marker-only legend handles, series side by side within each category. | — |
| D7 | Lollipop | rankings with less ink | — | ✅ | `cat --kind lollipop --orient h --sort desc --errory` (T22.1, gallery D7): a thin stem from zero and the value as a marker, its error bar capped. | — |
| D8 | Heatmap of a category × category table | correlation / yields | F25 | ✅ | `map -x A -y B -z Value --annotate .2f --matrix` (T22.3): string x/y become one tick per name, cell values written dark on light and light on dark. | — |
| D9 | Before/after (slope) chart | paired change | — | ✅ | `cat --datafile Spectra -x Stage -y Counts --integrate_over Energy --hue Sample --kind line` (legends avoid the data, B06 fixed in T15). | — |

## E. Ratios, differences and significance

| id | chart | use | famous | status | command today / what is missing | smallest change |
|---|---|---|---|---|---|---|
| E1 | Ratio panel to a reference series | shape agreement | F03 | ✅ | `line ... --lower ratio --reference_value signal` (example 2; P02). No legend when the ratios keep the upper colours, else one "X / reference" entry each (B06, fixed in T15). | — |
| E2 | Data / (sum of MC) ratio | data–simulation agreement | F03 | ✅ | `--lower ratio --reference_sum bkg_a bkg_b signal --reference_sum_label MC` (Q2). | — |
| E3 | Data points over stacked MC with ratio panel | the HEP control plot | F03 | ✅ | `line --datafile Spectrum -x Mass -y Counts --hue Sample --stacked --plot_type fill --overlay data --stack_total_error --lower ratio` (fixed in T18). Errors are the stored ones until T19 adds Poisson intervals. | — |
| E4 | Several lower panels | ratio and difference together | F01 | ✅ | `--lower ratio --lower relative_difference` (Q6). | — |
| E5 | S/√B or significance panel | optimisation | — | ✅ | `--lower group --reference_group signal --other_group ... --group_significance` (example 3). The panel's legend repeats the formula as raw text. | — |
| E6 | Residual relative to a named model component | bump over background | F01, F09 | ✅ | `line --fit --lower residual:Background` (T22.14): data minus a `FitComponents` entry, with the rest of the fit (the signal) over it; `--lower subtract --reference_value bkg` for stored curves. | — |
| E7 | Local p0 scan with σ reference lines | discovery significance | F04 | ✅ | `line --logy --hue Kind --sigma_lines 1 2 3 4 5` (T20): dashed lines at the one-sided p-values of nσ, labelled "1σ" ... at the right edge (`--sigma_line_color`); the expected-curve band works (B11, fixed in T07). | — |
| E8 | Pull distribution | fit validation | — | ✅ | `hist --datafile Pulls -x Pull --overlay_gaussian` (T22.13): the unit normal scaled to the entries (pulls computed upstream). | — |

## F. Machine-learning diagnostics

All curves are precomputed by the analysis (plotipus does not fit or score).

| id | chart | use | famous | status | command today / what is missing | smallest change |
|---|---|---|---|---|---|---|
| F1 | ROC curve | classifier comparison | — | ✅ | `line --datafile ROC -x FPR -y TPR --hue Model --plot_type line --line 0 0 1 1` (P08). Log axes: P22 (HEP "background rejection" style via `--logy`). | — |
| F2 | Precision–recall | imbalanced classes | — | ✅ | Same as F1 with `-x Recall -y Precision`. | — |
| F3 | Learning curve with band | over/under-fitting | — | ✅ | `line --datafile Learning -x TrainSize -y Score --hue Split --errory --errory_type bands --plot_type line --logx` (P09). | — |
| F4 | Calibration (reliability) curve + counts | probability calibration | — | ✅ | `line -x Predicted -y Observed --line 0 0 1 1 --lower column:Count --lower_plot_type bar` (T22.12): numeric bars take 80% of the x spacing. | — |
| F5 | Confusion matrix | per-class errors | — | ✅ | `map -x Predicted -y True -z Count --norm horizontal --annotate .0% --matrix` (T22.3). | — |
| F6 | Feature importance | model explanation | — | ✅ | `cat --datafile Importance -x Feature -y Importance --hue Model --kind bar --orient h --sort desc --errory` (T22.1, gallery F6): scalar cells (B07, fixed in T08) as sorted horizontal bars with their spread. | — |
| F7 | Score distributions per class | separation | — | ✅ | `hist -x Score --hue Class --density --logy` (as P13). | — |

## G. Uncertainty

| id | chart | use | famous | status | command today / what is missing | smallest change |
|---|---|---|---|---|---|---|
| G1 | Symmetric / asymmetric error bars | measurements | F07, F09 | ✅ | `--errory` with `{y}Error`, or `{y}Error+`/`{y}Error-` columns. | — |
| G2 | Computed Poisson (Garwood) intervals | low counts | F03, F16 | ✅ | `--errory_type poisson` in `line` and `hist` (Garwood, `intervals.garwood`); the default for `--overlay` data without an error column whose y are counts (T19). | — |
| G3 | Efficiency intervals in plots | bounded efficiencies | — | ✅ | `line --errory_type clopper_pearson --count_column N [--efficiency_scale 100]`: bars or bands inside [0, 1] (T19, shared with `table --clopper_pearson`). | — |
| G4 | Single band around a curve | systematic band | F14 | ✅ | `line --errory --errory_type bands` (B11, fixed in T07); series colour at `plot_settings.band_alpha` (default 0.2). | — |
| G5 | Nested ±1σ/±2σ bands (Brazil plot) | expected limits | F02, F04, F05 | ✅ | `line --plot_type line --errory --errory_column LimitErr1 LimitErr2 --band_colors brazil` (T20): one opaque band per column (or `C+`/`C-` pair), innermost on top, `graded` by default, legend "Expected ±1σ", "±2σ" (`--band_labels`). | — |
| G6 | Hatched systematic band on a stack total | MC uncertainty | F03 | ✅ | `--stack_total_error` (stacked errors in quadrature) or `--stack_total_error_column COL` (precomputed, e.g. with systematics); hatch from `plot_settings.stack_error` (T18). | — |
| G7 | 1D likelihood scan with Δχ² = 1, 4 lines | parameter intervals | — | ✅ | `line --datafile Scan -x Mu -y DeltaNLL --plot_type line --delta_chi2_lines 1 4` (or `--cl_lines 68.27 95.45 --cl_dof 1`; T20). `--horizontal_label`s now sit at the right edge, just above their lines (P07; `--horizontal_label_pos left\|auto`). | — |
| G8 | 2D Δχ² confidence contours, several datasets | joint constraints | F10 | ✅ | `map --contour` with configs, or `--contour_hue COLUMN` for datasets in one file (gallery G8): one hue per dataset, levels by line style, one legend entry per dataset and per level (B03, fixed in T02); `--combine_op squared_sum` adds the joint region. | — |
| G9 | Error-bar magnification with note | tiny errors | F06, F17 | ✅ | `line ... --errory --error_scale 400` (F06, F17): the drawn errors only, "(errors ×400)" in the legend label (T21). | — |

## H. Small multiples and layout

| id | chart | use | famous | status | command today / what is missing | smallest change |
|---|---|---|---|---|---|---|
| H1 | Facets by a column (wrapped grid) | same plot per group | F25, F11 | ✅ | `line ... --variables panel0 panel1 panel2 panel3` (P18; any column via `--variable_column`). | — |
| H2 | Shared axes and colour scales across facets | honest comparison | F25 | ✅ | `line --sharex col\|all --sharey row\|all` (T22.6; compact grids share x by column and y by row, outer tick labels only); `map` panels share one colour scale and colorbar (T09) and y with `--compact`. | `hist`/`scatter` keep one row. |
| H3 | Facet grid (rows × columns by two columns) | two-factor comparison | F15 | ✅ | `line --facet_row COL --facet_col COL` (or one of them with `--variables`; T22.6), each cell with its own `--lower` panels and per-row `--panel_labely`/`--panel_rangey`. | — |
| H4 | Upper + lower panels | ratios, residuals | F01, F07 | ✅ | `--lower` (repeatable). | — |
| H5 | Inset axes | zoom, second view | F02, F13, F18 | ✅ | `line --inset X0 X1 [Y0 Y1]` (a zoom with connectors) or `--inset_args 'OPTIONS'` (another selection or x/y, `--binned` too), placed by `--inset_pos x y w h` (T22.7). | — |
| H6 | Secondary axis (unit conversion) | GHz vs cm⁻¹, energy vs wavelength | F06 | ✅ | `--secondary_x cm-1->GHz` (built-in, style `mappings.conversions`, plugin, or inline `'FORWARD;INVERSE'`; gallery H6). | — |
| H7 | Broken or hybrid log/linear axis | wide dynamic range | F05, F07 | ✅ | `--xscale 'log<30<linear'` (log below 30, linear above, `--scale_split`; gallery H7) or `--xscale symlog[:LINTHRESH]`. | — |
| H8 | Figure sized for a journal column | publication | all | ✅ | `--medium paper --width single\|onehalf\|double\|nature\|INCHES`, `--aspect H/W` (T14). | — |

## I. Annotations

| id | chart | use | famous | status | command today / what is missing | smallest change |
|---|---|---|---|---|---|---|
| I1 | Reference lines (h/v/diagonal) with labels | thresholds, expectations | F04, F05, F08 | ✅ | `--horizontal`, `--vertical`, `--line x0 y0 x1 y1`, `--diagonal` (map). | — |
| I2 | Highlighted points and regions | best fit, signal window | F08, F10 | ✅ | `--point`, `--square`. | — |
| I3 | Free text box | selection, dataset | — | ✅ | `--note`. | — |
| I4 | Experiment / status label ("plotipus Preliminary", lumi, √s) | publication | F01–F05 | ✅ | Built in (T17): `--label 'TEXT' --label_status Preliminary --label_right 'TEXT'`, `--experiment atlas|cms|lhcb|alice|dune`, `--watermark wip`; logos through a figure hook. | — |
| I5 | Text at data coordinates, arrows | region labels | F10, F18 | ✅ | `--text X Y 'TEXT' --text_coords data --arrow X2 Y2` (repeatable, every kind; T22.8). | — |
| I6 | Direct labels at line ends (no legend) | few series | F17 | ✅ | `line --direct_labels` (T22.8): each line series named at its last point in view, in its colour, moved apart. | — |
| I7 | Inverted axis | magnitudes | F21, F22 | ✅ | Reversed range: `--rangey 1 0` (Q1). | — |
| I8 | Shaded excluded region (polygon) | "No Big Bang" region | F10 | ✅ | `--region 'x1,y1 x2,y2 …' [--region_hatch // --region_label TEXT]` (every kind; T22.8): under the data, never widening the axes. | — |
| I9 | Inline contour labels | iso-lines | F10 | ✅ | `map --contour --contour_labels` (T22.8): each level's label on its line; the legend keeps one entry per map. | — |
| I10 | Legend outside / above the axes | crowded plots | — | ✅ | `--legend_loc outside`, and automatically past 6 entries or when no position inside is free; the layout reserves the room (B06, fixed in T15). | — |

## J. Tables

| id | table | use | status | command today / what is missing |
|---|---|---|---|---|
| J1 | Values ± errors per config and variable | results summary | ✅ | `table --datafile Summary -y Value --variables Efficiency Purity Rate` (example). |
| J2 | Efficiency table with Clopper–Pearson intervals | bounded efficiencies | ✅ | `table ... --clopper_pearson COLUMN`. |
| J3 | siunitx / booktabs output with caption and label | paper-ready | ✅ | `--siunitx --caption ... --label ...`. |
| J4 | HTML twin of a table | reports | ✅ | `--html`. |
| J5 | Cut flow (yields by selection stage, several samples) | event selection | ✅ | `table --datafile Yields -y Counts --hue Particle --variable_name Stage --cutflow` (T22.11, gallery J5): events with their error, efficiencies relative to the previous and the first stage as Clopper–Pearson intervals. |
| J6 | Summary statistics table (mean, std, correlation) | "same stats" (F25) | ✅ | `table -x X -y Y --row_name Dataset --stats mean var corr line` (T22.11); `--agg std\|median` for cells. |
| J7 | Fit-parameter table from stored fits | publication | ✅ | `table --fit_params --row_name Dataset` (T22.11): one column per `ParamsLabel`, value ± error in `ParamsFormat`. |

---

## Mapping of the famous figures

How close plotipus gets to each Phase 1 figure today, and the catalogue rows
that close the gap.

| Figure | Closest today | Blocking rows |
|---|---|---|
| F01 ATLAS H→γγ | errorbar data + stored S+B fit + residual | C5, E6, G2 |
| F02 CMS H→γγ weighted | data + fit | G5, H5 |
| F03 H→ZZ*→4ℓ | stacked bars, data stacked too | E3, G2, G6 |
| F04 local p0 | log-y lines | E7, G5 |
| F05 Brazil plot | expected ± one band | G5, E7 |
| F06 COBE FIRAS | data + stored model + residual | G9, H6 |
| F07 Planck TT | asymmetric errors + model + residual | H7 (optional) |
| F08 Hubble 1929 | errorbar points + stored linear fits | — (✅ with two fits stored per hue) |
| F09 SN Hubble diagram | errorbar + model curves + subtract panel, `--logx` | C6 |
| F10 Ω_M–Ω_Λ | contours (B03) | B7, I5, I8 |
| F11 rotation curves | many lines | C10 |
| F12 NGC 3198 | errorbar + component curves | C6 |
| F13 Keeling curve | lines on decimal year | C8, H5 |
| F14 hockey stick | line + band | C9, G4 |
| F15 GW150914 | lines + bands, facets | H3, G5 |
| F16 KamLAND L/E | errorbar + step model | G2 (variable-width bins already draw as x errors) |
| F17 LEP Z lineshape | errorbar + 3 curves | G9, I6 |
| F18 R ratio | log-log errorbar, many hues | C10, H5, I5 |
| F19 Geiger–Marsden | log-y errorbar + stored model | — (✅ with a registered model) |
| F20 Moseley | errorbar + stored linear fits | — (✅) |
| F21 Leavitt | scatter + fits, inverted y (`--rangey`) | — (✅) |
| F22 HR diagram | 2D hist with log z, inverted y | B08 |
| F23 Nightingale rose | stacked bars as a fallback | D4 (polar out of scope) |
| F24 Minard | out of scope (variable-width flow lines) | — |
| F25 Anscombe / Datasaurus | facets of scatters | B1 fix, H2, J6 |

Out of scope, by design: geographic maps (Snow, Minard's route), polar-area
charts (Nightingale), 3D surfaces, interactive output.
