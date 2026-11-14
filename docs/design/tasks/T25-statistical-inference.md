# T25 Statistical inference backlog

**Wave 8 · depends on: nothing open (T02, T19, T20 and T22.9 are merged)**

What likelihood and Bayesian analyses draw today, checked against what
plotipus can do. The list comes from the figures that the field's tools
produce by default (corner and GetDist for posteriors, ArviZ for MCMC
diagnostics, pyhf/cabinetry and CMS Combine for binned likelihood fits,
RooUnfold-style unfolding reports), and from the figures of the papers that
use them. Each item is small enough for one session. Start a session with:

> Read `docs/design/tasks/00-README.md` and item T25.N in
> `docs/design/tasks/T25-statistical-inference.md`, then implement it on
> branch `task/T25-N-<name>`.

Every item follows the common rules and definition of done in
[00-README.md](00-README.md): tests, an example in
`examples/gallery`, a row in [../catalogue.md](../catalogue.md) and a
paragraph in `docs/options.md`. Kinds still follow the data relationship:
there is no `impact` or `trace` kind, only options of `line`, `hist`, `map`,
`cat` and `table`. Struck through: done.

**Already covered** (no item needed): 1D likelihood scans with Δχ² and CL
lines (catalogue G7), 2D Δχ² confidence regions of several datasets with
their combination (G8), nested ±1σ/±2σ bands and Brazil plots (G5), local
p₀ with σ lines (E7), pulls of a stored fit and pull distributions (C5, E8),
Garwood and Clopper–Pearson intervals (G2, G3), correlation tables as
annotated heatmaps (D8), ECDFs (A8).

## Data conventions to settle first

Posterior samples follow the existing rule, one row per series with arrays
in the cells: **one row per chain or per experiment, one array column per
parameter**, plus optional `Weight` (nested sampling, importance weights)
and `LogLike` columns of the same length. T25.1 uses it. Two things are
still open and belong in the style guide's section F once an item needs
them:

- chains of one run as separate rows (a `Chain` column) so that diagnostics
  can compare them, joined on demand (the corner plot joins the rows of one
  `--contour_hue` value already);
- draws of a *curve* (posterior predictive, toys of a spectrum): a 2D array
  cell, draws × bins, next to the 1D `Bin` array.

## Bayesian analyses

| item | need | today | smallest change | effort |
|---|---|---|---|---|
| ~~T25.1~~ | ~~Posterior corner plot: credible regions of every parameter pair, marginals with median and 68.3% interval, several chains or experiments overlaid, injected values~~ | ~~`map --corner` drew raw 2D histograms of one sample~~ | ~~`map --corner ... --contour [--contour_hue COL] [--weight COL] [--corner_truth V ...]`~~ | ~~M~~ |
| T25.2 | Corner refinements: highest-density intervals instead of equal-tailed ones for skewed marginals; the prior over each marginal; KDE-smoothed marginals; a second set of samples in the upper triangle; the points outside the outermost region; per-parameter ranges | Equal-tailed 68.3% interval, step marginals, one triangle, `--percentile` for every variable | `--corner_interval quantile\|hdi`, `--corner_prior COLUMN-SUFFIX` (a density per parameter), `--hist_type kde` on the diagonal, `--corner_upper VALUE` (a `--contour_hue` value), `--corner_points`, `--corner_range LOW HIGH ...` | M |
| T25.3 | MCMC diagnostics: trace of each parameter per chain with its marginal at the side; rank plots (Vehtari et al. 2021); autocorrelation against lag; running mean | Not possible: `line` has no implicit x and no side panel | `line -y PARAM --index` (x is the draw number), `--side hist` (marginal sharing y), `hist --hist_type rank --hue Chain`, `line --transform autocorr`; a gallery group "Sampling diagnostics" | M |
| T25.4 | Convergence and summary numbers: mean, sd, 68.3/95.4% intervals, R-hat, bulk and tail effective sample size per parameter | `table --stats mean var corr`; no quantiles of array cells, no R-hat or ESS | `table --stats median hdi rhat ess` over a `Chain` column, with `--siunitx`; warn when R-hat > 1.01 (no silent guesses) | S |
| T25.5 | Forest plot: one row per parameter (or per measurement) with nested 68.3/95.4% intervals, several models side by side, the value printed at the right, a band for the average | `cat --kind point --orient h` with one error bar; no nested intervals, no value column | `cat --errory_column Low68 High68 Low95 High95` (thick inside thin), `--value_text`, `--horizontal_band` for the average; intervals computed from array cells with `--interval 68.3 95.4`. Serves measurement compilations (PDG-style summary plots, signal strength per channel) too | M |
| T25.6 | Posterior predictive checks: the data over the 68.3/95.4% band of predicted spectra, or over a sample of predicted curves | Bands only from stored `{y}Error` columns | `line --draws_column Y2D`: median and nested quantile bands from a draws × bins cell (`--band_levels 68.3 95.4`), or `--spaghetti N` thin translucent curves | M |
| T25.7 | Coverage and calibration of an inference (simulation-based inference, amortised posteriors): expected against empirical coverage (P–P) with its binomial band, simulation-based calibration rank histograms with the uniform band, Q–Q plots | ECDF with a binomial band (A8); calibration curve (F4) | `hist --hist_type ecdf --reference uniform\|normal --difference` (ECDF minus the reference, with the simultaneous band), `hist --hist_type rank --expected_band`, `scatter --qq` | S |
| T25.8 | Model comparison: log-evidence or information-criterion differences with their errors against a reference model, Jeffreys-scale guide lines | `cat --kind point --orient h` draws it; nothing computes the differences | An example and `cat --relative_to VALUE` (differences to one category, errors in quadrature); `--horizontal` for the scale | S |

## Likelihood fits and frequentist results

| item | need | today | smallest change | effort |
|---|---|---|---|---|
| T25.9 | Nuisance-parameter pulls and impacts (the ATLAS/CMS ranking plot): (θ̂ − θ₀)/Δθ with its post-fit constraint per parameter, the ±1σ pre- and post-fit impacts on the parameter of interest as bars on a second axis, sorted by impact, the first N shown | Pulls or impacts alone with `cat --orient h --sort`; no second value axis on a `cat` | `cat --orient h --twin_column ImpactUp ImpactDown --twin_label 'Δμ'` (bars on a top axis centred on 0, behind the points), `--top N`, the ±1 band of the pull axis from `--horizontal_band` | M |
| T25.10 | Profile-likelihood scans read for the reader: the interval where −2Δln L crosses 1 and 4, drop lines to the axis, the result written as μ = x⁺ᵃ₋ᵦ; total against statistical-only curves; a warning for a second minimum inside the interval | Curves and the Δχ² lines (G7); crossings are read by eye | `line --scan_interval 1 [4]`: interpolated crossings, drop lines, the result in the legend (per hue); disjoint intervals reported, never merged | S |
| T25.11 | Correlation and covariance matrices of fit parameters: diverging map centred on 0, values written in the cells, one triangle only, parameters grouped (signal, background, detector), large matrices thinned to the entries above a threshold | `map -z --matrix --annotate --cmap diverging` (D8) | `map --triangle lower\|upper`, `--group_lines` from a group column, `--threshold 0.2` (drops rows and columns without a larger entry), `--rangez -1 1` by default for a column named like a correlation | S |
| T25.12 | Pre-fit and post-fit distributions of a multi-region fit: the regions side by side on one axis with separators and names, data over the stack, the post-fit uncertainty band, the pre-fit total as a dashed line, one ratio panel | One region per panel (`--variables`, `--compact`); `--stack_total_error` (G6) | Check `line --binned --compact --panel_equal_width` against a three-region fit and add what is missing: `--series_type Prefit=line`, region names above the panels, one shared ratio panel | M |
| T25.13 | Stat ⊕ syst error bars on points: inner bar (statistical) with caps, outer bar (total) without; the same in tables as `x ± stat ± syst` | One error per point; nested *bands* for lines (G5) | `--errory_column YStat YTotal` on points: caps at the first, full length to the last; `table --error_columns` for the split value | S |
| T25.14 | Limits that are not bands: upper limits as downward arrows on points; 2D exclusion curves with ticks or hatching on the excluded side; observed against expected ±1σ exclusion lines | `--region` polygons with hatching (I8); contours without an "excluded side" | `--limit_column IsLimit` (arrow from the value, no lower bar), `map --contour --excluded_side inside\|outside` (hatched fringe along the line) | M |
| T25.15 | Test-statistic distributions from toys: the histogram of q under each hypothesis, the observed value as an arrow, the tail shaded with its p-value, the asymptotic χ² curve over it | `hist` with `--vertical` and `--overlay_gaussian` (E8) | `hist --overlay_pdf chi2:DOF\|halfchi2:DOF\|normal:MU:SIGMA` (generalises `--overlay_gaussian`), `--observed VALUE` (arrow, shaded tail, p-value with its binomial error in the legend) | S |
| T25.16 | Goodness of fit beyond χ²/ndof: the p-value next to it, a saturated-model or toy-based GOF, residuals in σ with the ±1/±2 bands (done), a runs or autocorrelation hint for correlated residuals | `--fit --chi2`, `--lower pull` (C5) | `--chi2 pvalue` in the fit legend; warn when ndof ≤ 0 or bins have fewer than 5 expected entries | S |
| T25.17 | Unfolding reports: response matrix normalised per truth bin (done: `--norm`), purity, stability and efficiency per bin, the unfolded spectrum against generators with stat and total bars (T25.13), the bin-to-bin correlation matrix (T25.11) | The pieces exist except T25.11 and T25.13 | A gallery group "Unfolding" on a toy response; `table --stats` for purity and stability | S |
| T25.18 | Uncertainty budgets: the relative uncertainty per source against x, the sources summed in quadrature into the total, and the same as a table sorted by size | `line --hue Source` draws the curves; nothing checks or draws the quadrature sum | `line --quadrature_total` (the total as an ink line, with a warning if a stored `Total` row disagrees), `table --breakdown` | S |
| T25.19 | Sensitivity studies: median significance or Δχ² against exposure or a true parameter value with the band from the other parameters, coverage fractions (the fraction of δ_CP values above 3σ), discovery reach curves, Asimov against toys | Lines with bands from stored columns (C2, G5); `--sigma_lines` | An example group "Sensitivity" (neutrino oscillation toy); `line --yscale sqrt` for √Δχ² axes; nothing else expected, to be confirmed by drawing them | S |

## Inputs

| item | need | today | smallest change | effort |
|---|---|---|---|---|
| T25.20 | Read what the samplers and fitters write, without a hand-written converter per analysis: ArviZ `InferenceData` (NetCDF), emcee/zeus HDF5 backends, GetDist chain files, nested-sampling outputs with weights, pyhf/cabinetry fit results, `RooFitResult`, HEPData YAML | Pickle or Parquet in the plotipus convention only | `plotipus convert SOURCE NAME`: writes `input/data/NAME.parquet` in the convention above (one row per chain, a `Weight` column where the source has one); readers as optional extras, never a dependency of the plotting | M |

## Order

T25.2 and T25.4–T25.6 build on the sample conventions of T25.1. T25.13 comes
before T25.5 and T25.17, which use its nested bars. T25.9 is the only item
that needs a new axis (the twin value axis of `cat`), so it should not
overlap with other `cat` work. T25.20 is independent.
