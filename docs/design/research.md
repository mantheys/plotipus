# plotipus design research

Phase 1 of the plotipus examples/style redesign (2026-10-24). Three research
strands, each with its own sources:

1. [Default styles and galleries of other engines](#part-1-default-styles-of-plotting-engines)
2. [Common complaints about plotting defaults and APIs](#part-2-common-complaints)
3. [Famous plots from the history of science](#part-3-famous-plots-as-reproduction-targets)

Every factual claim carries a link. Claims that could not be checked against
a source are marked **(unverified)** where they appear and are collected at
the end of each part. Stack Overflow vote/view counts were read from the
Stack Exchange API on 2026-10-24; Reddit could not be searched (HTTP 403), so
no Reddit claims are made.

## Synthesis: what the research says plotipus should do

These are the conclusions that drive [style_spec.md](style_spec.md),
[catalogue.md](catalogue.md) and [roadmap.md](roadmap.md).

| Finding | Evidence | Consequence for plotipus |
|---|---|---|
| Figure size and font size are the two biggest pain points in matplotlib by a wide margin. | Figure size is the #1 matplotlib question of all time (3267 votes / 6.4M views); 4 font-size questions are in the top 20 (Part 2 §1–2). | Design every figure at its printed size (column width, pt fonts). The current 8×6 in canvas with `xx-large` labels is shrunk ~2.3× when placed in a 3.4 in column. |
| Physics styles and data-science styles form two families. | ROOT, mplhep, SciencePlots: ticks in, mirrored, minor ticks, no grid, frameless legend. matplotlib/seaborn/ggplot2/Makie: ticks out, grid, often despined (Part 1 §3). | Offer both as named styles; pick one as default (the three candidates in `styles/` span this). |
| The CVD-safe cycles that are now standard are Petroff and Okabe–Ito/Wong. | matplotlib 3.10 `petroff10`, ROOT 6.34 `kP6/8/10`, mplhep CMS (Petroff-6) and ATLAS (Okabe–Ito); none of the out-of-the-box matplotlib/plotly/Vega/ggplot2/bokeh cycles is CVD-designed (Part 1 §2.10, §3). | Ship Petroff-10 as the default cycle; never wrap silently past its end. |
| Colours wrapping after 10 and "same category, different colour" are recurring complaints. | plotly forum and matplotlib discourse threads; SO "get cycle state"/"reset cycle"/"hue order" questions (Part 2 §6). | Colour belongs to the category, not draw order; past the palette, add a second channel (line style/marker) and warn. |
| Legends covering data and legends outside the axes are top-3 questions. | "Legend outside the plot": 1732 / 2.2M (Part 2 §3). | Legends are placed in measured empty space or outside with reserved room, and never over filled areas. |
| Colorbars: one shared bar, matching height, label with units. | Six colorbar questions above 100 votes (Part 2 §5). | Shared norm and one colorbar for panels that share a scale; always labelled. |
| Uncertainty defaults differ between engines and are never labelled. | seaborn bootstrap 95% CI band, Vega-Lite SE, mplhep Garwood Poisson, ROOT `E` options (Part 1 §3); Wilke ch. 16 (Part 2 §10). | Pick one interval per data kind (Poisson/Garwood for counts, Clopper–Pearson for efficiencies, SEM for binned means) and say which in the legend. |
| Math text no longer matches LaTeX papers since matplotlib 2.0. | `mathtext.fontset` changed from `cm` to `dejavusans` (Part 2 §2). | The paper style sets text and math in the same family without needing a TeX install. |
| The famous figures need a short list of features again and again. | Inset axes, nested ±1σ/±2σ bands, panel grids, labelled reference lines, error-bar scaling, inverted/broken axes, Poisson intervals, user fit functions (Part 3, cross-cutting gaps). | These become the "missing" rows of the catalogue and the roadmap order. |


---

# Part 1: default styles of plotting engines


Researched 2026-10-24. Every claim has a source link. Anything marked **(unverified)** is from memory and was not confirmed against a source. Hex codes are quoted from source files unless noted.

### 1. Summary comparison

| Engine / style | Font (size) | Colour cycle (n) | CVD-safe cycle? | Seq. / div. cmap | Grid / spines | Ticks | Legend | Default size | Uncertainty default |
|---|---|---|---|---|---|---|---|---|---|
| matplotlib default (>=2.0) | DejaVu Sans, 10 pt; mathtext `dejavusans`; no usetex | tab10 (10) | No (red/green pair) | viridis / none set | no grid, 4 spines | out, no minor | `best`, frame, alpha 0.8, rounded | 6.4x4.8 in @100 dpi | `errorbar` capsize 0; no band primitive beyond `fill_between` |
| mpl `classic` | 12 pt, mathtext `cm` | `bgrcmyk` (7) | No | jet | none | in | upper right, square | 8x6 in @80 dpi | capsize 3 |
| mpl `petroff10` / 6 / 8 | (inherits) | Petroff (10/6/8) | **Yes, by design** | (inherits) | (inherits) | (inherits) | (inherits) | (inherits) | (inherits) |
| seaborn `set_theme()` | Arial→DejaVu Sans, 12 pt (notebook) | `deep` (10) | No; `colorblind` variant exists | (mpl's) | darkgrid `#EAEAF2`, white grid | out | (mpl's) | (mpl's) | **mean ± bootstrap 95 % CI, 1000 resamples, as a band** |
| plotly `plotly` | "Open Sans", 12 px | Plotly (10) | No | Plasma / none set | `#E5ECF6` plot bg, white grid | outside | outside right (x=1.02) | 700x450 px | per-point `error_y`; bands are manual `fill` traces |
| ggplot2 `theme_grey` | 11 pt base, device default family | hue, `l=65, c=100` | No | `#132B43`→`#56B1F7` gradient; viridis for ordered factors | grey panel, white grid | out | right | device size; ggsave 300 dpi | `geom_smooth` 95 % CI ribbon, alpha 0.4 |
| Vega-Lite / Altair | sans-serif, labels 10, titles 11 bold | tableau10 (10) | No | blues (ramp), yellowgreenblue (heatmap) / blueorange | grid on for continuous axes, `#ddd` | 5 px | right | 200x200 px view | errorband/errorbar extent `stderr` |
| Observable Plot | system-ui, 10 px | observable10 (10) | partly (unverified) | turbo / RdBu | off (unverified) | out | (none by default, unverified) | width 640, height from scales | no error mark (unverified) |
| bokeh | 13 px legend | category20-style per-renderer pick (no cycler) | No | n/a | grid on (unverified), outline `#e5e5e5` | out (unverified) | top_right, alpha 0.95 | 600x600 px | `Whisker` (TeeHead 10), `Band` fill `#fff9ba` alpha 0.4 |
| ROOT (`Modern`, 6.x) | font 42 (Helvetica), sizes 0.035 NDC | no cycle; indices; `PLC/PMC` from palette; kP6/8/10 sets since 6.34 | Petroff sets yes | kBird | no grid, frame box | in? (unverified) | border 1, white | canvas 700x500 px | auto error bars `E` when errors exist; `E1`..`E6` variants |
| mplhep CMS | TeX Gyre Heros 26 pt | Petroff 6 | **Yes** | (mpl's) | none | in, mirrored, minor | frameless | 10x10 in | `histplot` Poisson (Garwood) interval |
| mplhep ATLAS | TeX Gyre Heros 14 pt | Okabe-Ito-like 7 (ATLAS2) | Yes | (mpl's) | none | in, mirrored, minor | frameless | 8x6 in | same |
| SciencePlots `science` | serif + LaTeX | 7-colour custom | partly | (mpl's) | none | in, mirrored, minor | frameless | 3.5x2.625 in | (mpl's) |
| ultraplot / proplot | TeX Gyre Heros 9 pt | `colorblind` | Yes | Fire / BuRd | grid on, alpha 0.1 | out, minor on | square, alpha 0.8 | refwidth 2.5 in per panel; savefig 1000 dpi | `shadestd`/`barstd`-style keywords (unverified) |
| Makie | TeX Gyre Heros Makie, 14 | Wong (7) | **Yes** | viridis | grid on (alpha 0.12), 4 spines | out (align 0), no minor | frame black | 600x450 units | `errorbars` whiskerwidth 0; `band` |

### 2. Per-engine notes

#### 2.1 matplotlib (default rcParams, >= 2.0)
Source: the bundled `matplotlibrc` https://raw.githubusercontent.com/matplotlib/matplotlib/main/lib/matplotlib/mpl-data/matplotlibrc
- **Typography.** `font.family: sans-serif`, first sans font DejaVu Sans, `font.size: 10`. `axes.titlesize: large`, `axes.labelsize: medium`, `legend.fontsize: medium`. Math: `mathtext.fontset: dejavusans`, `text.usetex: False`, so math uses the built-in mathtext parser by default.
- **Colour cycle.** `cycler(color='tab10')`: `#1f77b4 #ff7f0e #2ca02c #d62728 #9467bd #8c564b #e377c2 #7f7f7f #bcbd22 #17becf` (hex converted from the floats quoted at https://matplotlib.org/stable/users/explain/colors/colors.html). It is not CVD-safe: C2 green and C3 red are adjacent **(unverified as a formal claim; it is the usual criticism)**.
- **Colormap.** `image.cmap: viridis`. The colormap guide recommends `BrBG`/`RdBu` for diverging data and notes that `coolwarm` spans a narrow L* range (https://matplotlib.org/stable/users/explain/colors/colormaps.html). Version 3.10 added the dark-centred diverging maps `berlin`, `managua` and `vanimo` from Crameri's Scientific Colour Maps 8.0.1 (https://matplotlib.org/3.10.1/users/prev_whats_new/whats_new_3.10.0.html).
- **Grid and spines.** `axes.grid: False`. All four spines are on. `axes.linewidth: 0.8`.
- **Ticks.** `xtick.direction: out`, `xtick.minor.visible: False`, major/minor tick lengths 3.5/2.
- **Legend.** `loc: best`, `frameon: True`, `framealpha: 0.8`, `fancybox: True` (rounded corners).
- **Figure.** 6.4x4.8 in, `figure.dpi: 100`, `savefig.dpi: figure`. `lines.linewidth: 1.5`.
- **Uncertainty.** `errorbar.capsize: 0`, so error bars have no caps by default. There is no band primitive with error semantics: users call `fill_between` themselves.

**Bundled style sheets.** The full list is at https://matplotlib.org/stable/gallery/style_sheets/style_sheets_reference.html: default, classic, Solarize_Light2, bmh, dark_background, fast, fivethirtyeight, ggplot, grayscale, petroff10, petroff6, petroff8, the seaborn-v0_8 family (base, bright, colorblind, dark, dark-palette, darkgrid, deep, muted, notebook, paper, pastel, poster, talk, ticks, white, whitegrid) and tableau-colorblind10.
- **classic** reproduces the pre-2.0 look: 12 pt; figure 8x6 in at 80 dpi; savefig 100 dpi; cycle `bgrcmyk`; cmap `jet`; ticks `in`; linewidth 1.0; legend `upper right`, not fancy, `numpoints: 2`; mathtext `cm`; `errorbar.capsize: 3`; `axes.autolimit_mode: round_numbers`; `axes.xmargin: 0` (https://raw.githubusercontent.com/matplotlib/matplotlib/main/lib/matplotlib/mpl-data/stylelib/classic.mplstyle).
- **ggplot**: grey panel `E5E5E5` with white solid grid drawn below the data, outward dark-grey ticks, a 7-colour cycle that starts with red, and patch colour `#348ABD` (https://raw.githubusercontent.com/matplotlib/matplotlib/main/lib/matplotlib/mpl-data/stylelib/ggplot.mplstyle).
- **bmh**: `eeeeee` axes background, dashed grid `b2b2b2` at 0.5 pt, ticks `in`, mathtext `cm`, linewidth 2. Cycle: `348ABD A60628 7A68A6 467821 D55E00 CC79A7 56B4E9 009E73 F0E442 0072B2`; the last six are Okabe-Ito colours (https://raw.githubusercontent.com/matplotlib/matplotlib/main/lib/matplotlib/mpl-data/stylelib/bmh.mplstyle).
- **fivethirtyeight**: `f0f0f0` figure and axes, 14 pt, linewidth 4, tick length 0, grid `cbcbcb`. Cycle: `008fd5 fc4f30 e5ae38 6d904f 8b8b8b 810f7c` (https://raw.githubusercontent.com/matplotlib/matplotlib/main/lib/matplotlib/mpl-data/stylelib/fivethirtyeight.mplstyle).
- **tableau-colorblind10**: `006BA4 FF800E ABABAB 595959 5F9ED1 C85200 898989 A2C8EC FFBC79 CFCFCF` (https://raw.githubusercontent.com/matplotlib/matplotlib/main/lib/matplotlib/mpl-data/stylelib/tableau-colorblind10.mplstyle).
- **petroff10** was added in 3.10. It "aims to be both generally pleasing aesthetically and colorblind accessible such that it could serve as a default" (https://matplotlib.org/3.10.1/users/prev_whats_new/whats_new_3.10.0.html). Colours: `3f90da ffa90e bd1f01 94a4a2 832db6 a96b59 e76300 b9ac70 717581 92dadd` (https://raw.githubusercontent.com/matplotlib/matplotlib/main/lib/matplotlib/mpl-data/stylelib/petroff10.mplstyle).
- **petroff6** is `5790fc f89c20 e42536 964a8b 9c9ca1 7a21dd` and **petroff8** is `1845fb ff5e02 c91f16 c849a9 adad7d 86c8dd 578dff 656364` (https://raw.githubusercontent.com/matplotlib/matplotlib/main/lib/matplotlib/mpl-data/stylelib/petroff6.mplstyle, …/petroff8.mplstyle). They appear in the 3.11 gallery as the "petroffN styles" (https://matplotlib.org/3.11.0/gallery/style_sheets/petroff10.html). That they were added exactly in 3.11.0 is **(unverified)**.

#### 2.2 seaborn
- **Themes.** The five themes are darkgrid, whitegrid, dark, white and ticks; darkgrid is the default. The contexts are paper, notebook, talk and poster; notebook is the default. `despine()` removes the top and right spines and supports `offset` and `trim` (https://seaborn.pydata.org/tutorial/aesthetics.html). `set_theme()` defaults to `context='notebook', style='darkgrid', palette='deep', font='sans-serif', font_scale=1` (https://seaborn.pydata.org/generated/seaborn.set_theme.html).
- **rcmod values** (https://raw.githubusercontent.com/mwaskom/seaborn/master/seaborn/rcmod.py):
  - Base context: font, label and title sizes 12; tick labels and legend 11; axes linewidth 1.25; lines 1.5; major ticks 6 long, minor 4.
  - Context scale factors: paper 0.8, notebook 1, talk 1.5, poster 2.
  - darkgrid: axes face `#EAEAF2` with a white grid. whitegrid: white face with a grid at 0.8 grey. ticks: no grid, ticks on the bottom and left.
  - Ticks point `out` in every theme. Sans-serif fallback list: Arial, DejaVu Sans, Liberation Sans, Bitstream Vera Sans.
- **Palettes** (https://raw.githubusercontent.com/mwaskom/seaborn/master/seaborn/palettes.py). `deep` is `#4C72B0 #DD8452 #55A868 #C44E52 #8172B3 #937860 #DA8BC3 #8C8C8C #CCB974 #64B5CD`, a muted reordering of tab10. `colorblind` is `#0173B2 #DE8F05 #029E73 #D55E00 #CC78BC #CA9161 #FBAFE4 #949494 #ECE133 #56B4E9`.
- **Uncertainty.** This is the most opinionated default of any engine. `lineplot(estimator='mean', errorbar=('ci', 95), n_boot=1000, seed=None, err_style='band')` (https://seaborn.pydata.org/generated/seaborn.lineplot.html). Repeated observations therefore collapse to mean ± a bootstrapped 95 % CI drawn as a translucent band, and the band is not reproducible unless a seed is given. The error-bar tutorial treats the choices `sd`/`se`/`pi`/`ci` as the "spread vs. uncertainty" axis; `errorbar="se"` draws ±1 SE (https://seaborn.pydata.org/tutorial/error_bars.html).
- **seaborn.objects.** The interface is a declarative `Plot` built from `Mark` (Dot, Line, Bar, Area, Range, …), `Stat` (Agg, Est, Hist, PolyFit) and `Move` (Dodge, Jitter, Stack). Error bars come from `Range` combined with `Est(errorbar=...)`, and themes are set with `Plot.theme({...rc})` (https://seaborn.pydata.org/tutorial/objects_interface.html). The default theme "uses the same parameters as seaborn.set_theme() with no additional arguments" and can be changed globally through `Plot.config.theme` (https://seaborn.pydata.org/generated/seaborn.objects.Plot.theme.html). The Band mark's default alpha is **(unverified)**.

#### 2.3 plotly
- **Templates.** The built-ins are ggplot2, seaborn, simple_white, plotly, plotly_white, plotly_dark, presentation, xgridoff, ygridoff, gridon and none; the default is `plotly`. It has a `#E5ECF6` plot background, white paper, white gridlines and font colour `#2a3f5f` (https://plotly.com/python/templates/). `plotly_white` swaps in a white plot area with light grey gridlines **(unverified detail)**.
- **Typography.** `layout.font` is `"Open Sans", verdana, arial, sans-serif` at 12, colour `#444`. Default size 700x450 px. The vertical legend sits outside to the right (x=1.02, y=1, xanchor left). The legend appears automatically only when 2 or more traces are shown (https://plotly.com/python/reference/layout/). Math is rendered with MathJax in the browser **(unverified for static export)**.
- **Colours.** The Plotly sequence is `#636EFA #EF553B #00CC96 #AB63FA #FFA15A #19D3F3 #FF6692 #B6E880 #FF97FF #FECB52` (https://plotly.com/python/discrete-color/); it is not CVD-designed. The default continuous scale is Plasma (https://plotly.com/python/colorscales/).
- **Uncertainty.** `error_x`/`error_y` take column names, with `error_y_minus` for asymmetric errors (https://plotly.com/python/error-bars/). Continuous bands are built by hand with `fill='toself'` or `fill='tonexty'` and an rgba fill such as `rgba(0,100,80,0.2)` (https://plotly.com/python/continuous-error-bars/).

#### 2.4 ggplot2
- **Themes.** `theme_grey` is the default: "grey background and white gridlines". `theme_bw` is the "classic dark-on-light" theme; `theme_minimal` has "no background annotations"; `theme_classic` has axis lines and no gridlines. `base_size = 11` and `base_family = ""` (https://ggplot2.tidyverse.org/reference/ggtheme.html).
- **theme_grey internals in 4.0** (https://raw.githubusercontent.com/tidyverse/ggplot2/main/R/theme-defaults.R):
  - Line and rect sizes are `base_size/22`. `ink="black"`, `paper="white"`, `accent="#3366FF"`.
  - Panel fill is `col_mix(ink, paper, 0.92)`, which is about grey92. Gridlines use the paper colour; minor gridlines are half width.
  - Axis text is 0.8× in a ~30 % grey. The legend sits on the right.
  - Default point size 1.5 with shape 19.
- **ggplot2 4.0 changes.** It added `ink`/`paper`/`accent` roles that propagate into layer defaults, `element_geom()`/`from_theme()`, and palettes stored in the theme (`palette.colour.discrete` etc.) (https://www.tidyverse.org/blog/2025/09/ggplot2-4-0-0/). Example: `theme(palette.colour.discrete = "Okabe-Ito")` (https://ggplot2.tidyverse.org/reference/scale_colour_discrete.html).
- **Colours.** The discrete default is `scale_colour_discrete`. Its hue palette uses `h = c(0,360)+15, c = 100, l = 65` (https://ggplot2.tidyverse.org/reference/scale_hue.html). Equal-luminance hues are not CVD-safe and do not survive greyscale.
  - Continuous default: `scale_colour_gradient(low="#132B43", high="#56B1F7")`. `gradient2` uses mid "white" (https://ggplot2.tidyverse.org/reference/scale_gradient.html). Binned scales use the continuous palette (https://ggplot2.tidyverse.org/reference/scale_colour_continuous.html).
  - Viridis is the default only for **ordered factors** ("viridis is the default colour/fill scale for ordered factors", option "D") (https://ggplot2.tidyverse.org/reference/scale_viridis.html). It is not the default for continuous scales.
- **Size and output.** `ggsave` uses the current device size, `dpi = 300` (https://ggplot2.tidyverse.org/reference/ggsave.html).
- **Uncertainty.** `geom_smooth` has `se = TRUE`, `level = 0.95` and ribbon alpha 0.4 (https://ggplot2.tidyverse.org/reference/geom_smooth.html). A bare `geom_ribbon` has `alpha = NA` (opaque) with its fill taken from the theme (https://ggplot2.tidyverse.org/reference/geom_ribbon.html). Note that the smoothing ribbon is translucent while a user ribbon is opaque.

#### 2.5 Vega-Lite / Altair
Altair compiles to Vega-Lite, so the Vega and Vega-Lite defaults apply.
- **Defaults from Vega's `config.js`** (https://raw.githubusercontent.com/vega/vega/main/packages/vega-parser/src/config.js):
  - Guide labels are sans-serif 10; guide titles are sans-serif 11 bold.
  - Ticks are 5 px. Grid `#ddd`, axis domain `#888`. The legend is oriented right.
  - Default mark colour `#4c78a8` (tableau10 blue). Default point size 30 with stroke width 2.
  - Ranges: category = tableau10, ordinal = blues, heatmap = yellowgreenblue, ramp = blues, diverging = blueorange.
- **Gridlines** default on for continuous, non-binned scales (https://vega.github.io/vega-lite/docs/axis.html). The scale docs confirm the nominal → tableau10, ordinal → blues and rect heatmap → yellowgreenblue defaults (https://vega.github.io/vega-lite/docs/scale.html).
- **Size.** A continuous view is 200x200 px by default. Discrete axes use a step of 20 px per category (https://vega.github.io/vega-lite/docs/size.html).
- **Uncertainty.** `errorband` (and `errorbar`) aggregate the raw data with a default extent of `"stderr"`. Band colour defaults to `#4682b4` (https://vega.github.io/vega-lite/docs/errorband.html). Tableau10 is not CVD-optimised **(unverified as a formal claim)**.

#### 2.6 Observable Plot
- **Size.** Default width 640; height comes from the scales (for example 396) (https://raw.githubusercontent.com/observablehq/plot/main/docs/features/plots.md).
- **Styling.** The SVG gets `font-family: system-ui, sans-serif`, `font-size: 10` and `fill: currentColor`, with `--plot-background: white`. It inherits the page's text colour, which gives free dark-mode support (https://raw.githubusercontent.com/observablehq/plot/main/src/plot.js).
- **Colour schemes.** Categorical defaults to **observable10**: `#4269d0 #efb118 #ff725c #6cc5b0 #3ca951 #ff8ab7 #a463f2 #97bbf5 #9c6b4e #9498a0` (https://raw.githubusercontent.com/d3/d3-scale-chromatic/main/src/categorical/observable10.js). The sequential default is **turbo**, "chosen primarily to ensure high-contrast visibility". The diverging default is RdBu (https://raw.githubusercontent.com/observablehq/plot/main/docs/features/scales.md).
- **Grid and uncertainty.** The grid is opt-in (`grid: true` in the examples, same source as above). There is no dedicated error-bar mark; users compose `ruleX`/`ruleY` and `areaY` **(unverified)**.

#### 2.7 bokeh
- **Plot.** 600x600 px, toolbar on the right, `min_border` 5, outline `#e5e5e5`, white background, canvas backend (https://raw.githubusercontent.com/bokeh/bokeh/branch-3.9/src/bokeh/models/plots.py).
- **Colours.** There is no property cycler. `get_default_color` returns the entry of an 18-colour category20-ordered list (`#1f77b4`, `#ff7f0e`, `#ffbb78`, …) at index = number of existing glyph renderers. The list mixes tab20 dark and light shades, so consecutive glyphs can get a colour and its pale twin (https://raw.githubusercontent.com/bokeh/bokeh/branch-3.9/src/bokeh/plotting/_renderer.py). Palettes include Category10/20, Bokeh and `Colorblind` 3–8 (https://docs.bokeh.org/en/latest/docs/reference/palettes.html).
- **Legend.** `top_right`, vertical, border `#e5e5e5`, background alpha 0.95, labels 13 px, click_policy none (https://raw.githubusercontent.com/bokeh/bokeh/branch-3.9/src/bokeh/models/annotations/legends.py).
- **Uncertainty.** `Whisker` draws `TeeHead(size=10)` caps. `Band` fills `#fff9ba` at alpha 0.4 with a `#cccccc` line (https://raw.githubusercontent.com/bokeh/bokeh/branch-3.9/src/bokeh/models/annotations/geometry.py).
- **Themes.** caliber, carbon, dark_minimal, light_minimal, night_sky and contrast (https://docs.bokeh.org/en/latest/docs/reference/themes.html).

#### 2.8 ROOT
- **Styles.** The predefined styles are Plain, Bold, Video, Pub, Classic, Default (= Classic), Modern and ATLAS (https://hep.lancs.ac.uk/~ajf/root/TStyle_8cxx_source.html, 6.30 mirror). The TStyle docs say "`Modern`: Used when ROOT starts" (https://root.cern/doc/master/classTStyle.html).
- **Modern** (same 6.30 source):
  - No frame border; white canvas, pad and stat box.
  - Font 42 for titles, labels, stat and legend. Font 42 is Helvetica **(font-to-face mapping unverified)**.
  - Axis label and title sizes 0.035 (fraction of pad), plot title 0.05.
  - `OptStat(1111)` turns the stat box on by default. Histogram line colour `kBlue+2`. Function line width 2, colour 2 (red).
  - Legend border 1, white fill.
- **Base defaults.** `TStyle::Reset` sets canvas 700x500, `fErrorX = 0.5` (horizontal error bars span half the bin width) and `fEndErrorSize = 2`. The ATLAS style sets `EndErrorSize(0)` and mirrored ticks (`PadTickX`).
- **Palette.** `SetPalette(Int_t ncolors = kBird, …)` makes **kBird** the default (https://root.cern/doc/master/TStyle_8h_source.html). kBird arrived with the 6.04 "many new beautiful palettes (kBird!)" (https://root.s3-website.cern.ch/releases/release-60400). The TColor docs classify the 63 predefined palettes as CVD-friendly or not. The 50-index basic colour table is grouped: 0–9 grey, 10–19 brown, 20–29 blue, 30–39 red, 40–49 basic (https://root.cern/doc/master/classTColor.html). kRed is 632, kBlue 600, kGreen 416 and so on (same source). Indices 2/3/4 are red/green/blue **(unverified on that page)**.
- **Line colours.** There is no line colour cycle. Users set colours explicitly or use the `PLC`/`PMC` draw options, which pick line or marker colours from the current palette according to how many such objects are already in the pad (https://root.cern/doc/master/classTHistPainter.html).
- **Petroff sets.** Since **6.34**, ROOT ships Petroff's 6/8/10 sets as named colours `kP6Blue`, `kP6Yellow`, `kP6Red`, `kP6Grape`, `kP6Gray`, `kP6Violet`, …, `kP10Blue+0..9` (https://root.cern.ch/blog/new-color-schemes/, https://root.cern.ch/doc/v634/accessiblecolorschemes_8C_source.html).
- **Uncertainty.** A histogram with errors is drawn with error bars by default (`HIST` suppresses them). The options are:
  - `E`: bars only.
  - `E0`: also marks empty bins.
  - `E1`: end caps.
  - `E2`: rectangles.
  - `E3`: filled band.
  - `E4`: smoothed band.
  - `E5`/`E6`: `E3`/`E4` ignoring empty bins.
  - `X0`: removes the x error.
  
  Source: https://root.cern/doc/master/classTHistPainter.html. The default tick direction is inward with length 0.03 **(unverified)**.

#### 2.9 mplhep (scikit-hep)
Use with `hep.style.use("CMS")` and the other experiment styles.
- **CMS** (https://raw.githubusercontent.com/scikit-hep/mplhep/master/src/mplhep/styles/cms.py):
  - Font: `font.sans-serif = ["TeX Gyre Heros", "Helvetica", "Arial"]` at **26 pt**. Mathtext is `custom` with TeX Gyre Heros rm/it/bf and `mathtext.default: regular`, so math matches the text face.
  - Figure **10x10 in**. Cycle = **Petroff 6** (`#5790fc #f89c20 #e42536 #964a8b #9c9ca1 #7a21dd`).
  - Ticks `in` with minor ticks visible and mirrored to the top and right; major/minor lengths 12/6. Legend frameless.
- **ATLAS** (= ATLAS2) (https://raw.githubusercontent.com/scikit-hep/mplhep/master/src/mplhep/styles/atlas.py):
  - TeX Gyre Heros/Helvetica/Nimbus Sans at 14 pt, figure 8x6 in, `mathtext.default: it`, labels x-large, linewidth 2.
  - Ticks in, minor ticks on, mirrored. Legend frameless.
  - Cycle (7): `#d55e00 #56b4e9 #e69f00 #f0e442 #009e73 #cc79a7 #0072b2` (Okabe-Ito ordering). `ATLAS1`/`ATLASAlt` use Petroff 10.
- **LHCb2** (current `LHCb`):
  - Serif TeX Gyre Termes (a Times clone) at 14 pt, figure 12x9 in.
  - Ticks in, mirrored, minor ticks on, major/minor 14/7. Axes width 2, lines 3.3, errorbar capsize 2.5. Legend frameless.
  - Source: https://raw.githubusercontent.com/scikit-hep/mplhep/master/src/mplhep/styles/lhcb.py
- **ALICE** (https://raw.githubusercontent.com/scikit-hep/mplhep/master/src/mplhep/styles/alice.py):
  - TeX Gyre Heros with `stixsans` math, figure 12x9 in.
  - Large sizes: labels 32, ticks 25, legend 28.
  - Ticks in. Legend frameless. No prop_cycle of its own.
- **histplot** (https://raw.githubusercontent.com/scikit-hep/mplhep/master/src/mplhep/plot.py):
  - `histtype="step"` by default; also 'fill', 'errorbar', 'bar', 'barstep' and 'band'. `flow="hint"` draws markers for under/overflow. `binwnorm` normalises by bin width.
  - `yerr=True` means sqrt(N), or a Poisson interval when w2 is given. For unweighted (integer) data the error method is `"poisson"` and computes a **Garwood interval** when scipy is available, otherwise sqrt(w2). Weighted data uses sqrt(sumw2) (https://raw.githubusercontent.com/scikit-hep/mplhep/master/src/mplhep/_utils.py).
- **Experiment label** (https://raw.githubusercontent.com/scikit-hep/mplhep/master/src/mplhep/label.py):
  - `exp_label(exp="CMS", data=False, lumi=138, year=2018)` places a bold experiment name above the axes on the left (loc 0) and prepends "Simulation" unless `data=True`.
  - The right-hand side reads `138 $\mathrm{fb^{-1}}$, 2018 (13 TeV)`; `com` defaults to 13 TeV and takes a format string.
- **CMS colour guideline.** CMS recommends Petroff's 6/8/10 sequences, with the 6-colour set as default and 8/10 for more categories. The CMS guideline page (https://cms-analysis.docs.cern.ch/guidelines/plotting/colors/) is behind CERN SSO, so the exact wording is **(unverified)**. mplhep's CMS style uses Petroff-6, which is consistent with this.

#### 2.10 Petroff palettes (arXiv:2107.02270)
- **Method.** Survey-trained aesthetic model plus hard constraints:
  - Minimum perceptual distance, including under simulated CVD.
  - Minimum lightness difference, so the colours survive greyscale.
  - Maximum lightness, for contrast against white.
  - A saliency term, so colours are nameable.
  
  The output is 6-, 8- and 10-colour sequences proposed "as reasonable defaults" (https://arxiv.org/abs/2107.02270).
- **Ordering.** Each published sequence is the highest-scoring ordering from the cycle model, so it should be used as published (https://github.com/mpetroff/accessible-color-cycles).
- **Adoption.** matplotlib (3.10 petroff10; petroff6/8 in the 3.11 docs), ROOT 6.34 (kP6/kP8/kP10), mplhep CMS (Petroff-6) and mplhep ATLAS1 (Petroff-10). Sources are cited above.

#### 2.11 SciencePlots
Since 2.0 it requires `import scienceplots`. Styles combine, e.g. `['science','ieee']`. The `science` style uses LaTeX by default (`no-latex` exists) (https://raw.githubusercontent.com/garrettj403/SciencePlots/master/README.md).
- **science** (https://raw.githubusercontent.com/garrettj403/SciencePlots/master/src/scienceplots/styles/science.mplstyle):
  - Figure **3.5x2.625 in**. Cycle `0C5DA5 00B945 FF9500 FF2C00 845B97 474747 9e9e9e`.
  - Ticks in, mirrored, minor ticks on, major/minor 3/1.5 at width 0.5. Axes 0.5, lines 1.0.
  - Legend frameless. `savefig.bbox: tight` with `pad_inches 0.05`.
  - Serif fonts, `text.usetex: True` with amsmath/amssymb.
- **ieee**: 3.3x2.5 in, **600 dpi**, 8 pt Times-like serif. The cycle pairs black/red/blue/green with solid/dashed/dotted/dash-dot line styles so it survives B/W printing (https://raw.githubusercontent.com/garrettj403/SciencePlots/master/src/scienceplots/styles/journals/ieee.mplstyle).
- **nature**: 3.3x2.5 in, **7 pt** sans (DejaVu Sans/Arial/Helvetica), DejaVu Sans math, sfmath preamble, lines 1.0, markers 3 (https://raw.githubusercontent.com/garrettj403/SciencePlots/master/src/scienceplots/styles/journals/nature.mplstyle).
- **Colour styles.** bright, high-vis and Paul Tol's `discrete-rainbow-N`, among others (README above).

#### 2.12 proplot / ultraplot
ultraplot is the maintained fork of proplot. Defaults from https://raw.githubusercontent.com/Ultraplot/ultraplot/main/ultraplot/internals/rcsetup.py and https://ultraplot.readthedocs.io/en/latest/configuration.html:
- **Typography.** TeX Gyre Heros at **9 pt**. `formatter.zerotrim` removes trailing zeros on tick labels.
- **Colours.** Cycle `colorblind`; qualitative `colorblind10`. Sequential cmap **Fire**, diverging **BuRd**, cyclic twilight. `negcolor/poscolor` blue7/red7 for signed bars.
- **Grid and ticks.** Grid on at alpha 0.1. Ticks out with minor ticks on.
- **Legend.** Square (`fancybox False`), framealpha 0.8, black edge.
- **Figure.** **`subplots.refwidth = 2.5 in`**: the figure size is derived from a reference panel width, with tight layout and automatic axis sharing. `figure.figsize` is 4x4. `figure.dpi` 100 but **`savefig.dpi` 1000** ("academic journal recommendation").
- **Uncertainty.** Proplot-style `shadestd`/`barstd`/`fadestd`/`boxstd` keywords on 1D plot commands **(unverified; the docs page fetched did not cover them)**.

#### 2.13 Makie (Julia)
- **Theme** (https://raw.githubusercontent.com/MakieOrg/Makie.jl/master/Makie/src/theming.jl):
  - Font `TeX Gyre Heros Makie`, fontsize 14. Scene size 600x450 ("4/3 aspect ratio"). Colormap viridis.
  - Linewidth 1.5, markersize 9, linecap butt. CairoMakie export uses `px_per_unit 2`, `pt_per_unit 0.75`.
  - Palette = **Wong**: `#0072B2 #E69F00 #009E73 #CC79A7 #56B4E9 #D55E00 #F0E442`, from Wong, "Points of view: Color blindness", *Nature Methods* 8 (2011) **(citation from memory; unverified)**.
- **Axis** (https://docs.makie.org/stable/reference/blocks/axis): grid visible at `RGBAf(0,0,0,0.12)`, all spines on, `xtickalign 0` (outward), no minor ticks, bold title. The docs list the inherit fallback for label and tick sizes as 16, while the theme sets fontsize 14, so the effective size is **(unverified)**.
- **Legend.** Frame visible, black frame (https://docs.makie.org/stable/reference/blocks/legend).
- **Uncertainty.** `errorbars` defaults to `whiskerwidth 0` (no caps) and inherits line colour and width (https://docs.makie.org/stable/reference/plots/errorbars).
- **Themes.** theme_ggplot2, theme_minimal, theme_black, theme_light, theme_dark and theme_latexfonts (https://docs.makie.org/stable/explanations/theming/predefined_themes).

### 3. Cross-cutting observations
- **Two families of tick style.** Data-science engines (matplotlib, seaborn, ggplot2, plotly, Makie, ultraplot) use outward ticks, often with no minor ticks, and frequently a grid. Physics and journal styles (ROOT ATLAS, mplhep, SciencePlots, mpl `classic`, `bmh`) use inward, mirrored ticks with minor ticks on, no grid and a frameless legend. Every physics-oriented style surveyed converges on the second.
- **CVD-designed colour cycles.** Only Petroff (matplotlib petroffN, ROOT kP*, mplhep CMS/ATLAS1), Wong/Okabe-Ito (Makie, mplhep ATLAS2, bmh tail), seaborn `colorblind`, tableau-colorblind10 and ultraplot `colorblind` are designed for CVD. The out-of-the-box defaults of matplotlib, plotly, Vega, ggplot2 and bokeh are not.
- **Default uncertainty presentations differ widely:**
  - seaborn: bootstrap 95 % CI band.
  - Vega-Lite: standard error.
  - ggplot2 `geom_smooth`: 95 % CI ribbon at alpha 0.4.
  - mplhep: Garwood Poisson interval on counts.
  - ROOT: sqrt(sumw2) bars spanning half the bin width.
  - matplotlib, Makie: capless bars.
  
  None of them annotates which interval is shown.
- **Sizing philosophy.** Engines size either the canvas in pixels (plotly 700x450, bokeh 600x600, Vega 200x200 per view, Observable width 640) or the figure in inches (matplotlib 6.4x4.8, mplhep 8–12 in). Journal styles instead fix the physical column width (SciencePlots 3.3–3.5 in) or a reference panel width (ultraplot 2.5 in). Only the journal-width approach lets font point sizes mean what they say in print.

### 4. Lessons for plotipus
1. **Default to a Petroff cycle.** Use petroff10, or petroff6 when there are 6 or fewer series, in published order. It is now endorsed by matplotlib, ROOT and CMS, it was designed for CVD and greyscale, and it ships in mpl ≥ 3.10, so plotipus needs no hard-coded hex values. Keep Wong/Okabe-Ito as a named alternative.
2. **Offer a "physics" preset and a "data-science" preset as the two families.** The physics preset has inward mirrored ticks with minor ticks on, no grid, a frameless legend and `best` placement. The data-science preset has outward ticks, a light grid (ultraplot's alpha 0.1 is a good subtle value) and despined top/right axes.
3. **Size by physical width and target, not by pixels.** Provide `--width single|double|<in>` presets (3.3–3.5 in single column, ~7 in double, as in SciencePlots/journals) and derive height from an aspect ratio, in the spirit of ultraplot's `refwidth`. Scale fonts like seaborn contexts (paper 0.8 / talk 1.5 / poster 2) instead of fixing absolute sizes. This avoids mplhep's 26 pt-on-10 in approach, which only works when the figure is shrunk.
4. **Make math match text without requiring LaTeX.** Use mplhep's `mathtext.fontset: custom` with the same face as the text (TeX Gyre Heros) or `stixsans`, with `usetex` as an opt-in. SciencePlots' LaTeX-by-default is a common install failure (its README says "SciencePlots requires Latex").
5. **Be explicit about the uncertainty model and print it.** Choose one default per data kind and state it in a caption/footer or `--verbose` output:
   - Counts: Garwood Poisson interval, as in mplhep. This matches the new `--clopper_pearson` philosophy for efficiencies: intervals never go past physical bounds.
   - Weighted counts: sqrt(sumw2).
   - Aggregated repeated measurements: mean ± SE, with an opt-in CI. If bootstrap is used, always seed it; seaborn's `seed=None` default makes figures non-reproducible.
6. **Borrow mplhep's experiment and lumi label as a generic "header" feature.** It puts a bold left label plus a status word on the left and `L (√s)` or other metadata on the right, above the axes. This works well for any lab or collaboration branding.
7. **Use bands for continuous x and bars for discrete or binned x.** Give bands translucency around 0.3–0.4: ggplot2 `geom_smooth` and bokeh `Band` both use 0.4. Draw the central line in the same hue. For histograms, offer ROOT-like options: step plus error bars with an x-extent (ROOT `fErrorX=0.5`), a hatched or filled `E2`-style uncertainty box for systematics, and an `E3`-style band.
8. **Defaults that cost nothing:**
   - Viridis for sequential data, with ultraplot/proplot-style automatic switching to a diverging map (RdBu/BuRd) when data straddle zero.
   - Never jet or turbo for physical quantities. Turbo is Observable's default, which shows the "visibility over perceptual ordering" trade-off.
   - mpl 3.10's berlin/managua/vanimo for dark-background diverging plots.
9. **Save defaults.** Use vector output when possible and otherwise ≥300 dpi (ggplot2's ggsave default is 300, SciencePlots ieee uses 600 dpi). Use a tight bbox with a small pad (SciencePlots: 0.05 in). Respect `currentColor`/transparent backgrounds for dark-mode slides, as Observable Plot does.
10. **Keep "classic" reproducibility in mind.** Store the full resolved rcParams (style + overrides) next to each output. Matplotlib's own 2.0 transition and the many `seaborn-v0_8-*` renames show that defaults change, and pinned styles keep old figures reproducible.

---

# Part 2: common complaints


*Research notes for the plotipus design doc. Compiled 2026-10-24.*

**Method.** Frequency estimates come mainly from Stack Overflow (SO) score and view counts. I pulled them live from the Stack Exchange API on 2026-10-24, using the all-time top-voted `[matplotlib]` questions and title searches per theme. The API endpoint was `api.stackexchange.com/2.3/questions?tagged=matplotlib&sort=votes`. Every SO figure below is "score / views" from that snapshot. I added GitHub issues (found through the GitHub search API), Hacker News threads (found through the HN Algolia API), and the literature the brief listed. Reddit's search API returned HTTP 403, and web search returned no Reddit threads, so **this note cites no Reddit claims**. Anything I could not confirm against a source is marked *(unverified)*.

Two biases in this method:
- SO counts measure *how often people get stuck*, not *how much the result hurts the reader*.
- Expert critiques (Tufte, Wilke, Crameri, Petroff) measure the opposite: harm to the reader.

The ranking weighs both. A theme with low SO traffic but strong expert consensus, such as colour-vision deficiency (CVD), is ranked by its impact on readers, and the table says so.

---

### Ranked summary

| Rank | Theme | Rough frequency (SO evidence) | Reader impact | Fix consensus, in one line |
|---|---|---|---|---|
| 1 | **Multi-panel layout & figure sizing** (spacing, cut-off labels, shared axes, ratio panels) | Very high. The #1 SO matplotlib question of all time is figure size (3267 / 6.4M). Subplot figure size: 690 / 1.9M. Subplot spacing: 603 / 1.0M. Cut-off labels: 501 / 583k | High | Size figures in physical units for the target column. Use a constraint-based layout engine. Share axes and suppress inner tick labels. |
| 2 | **Fonts & typography** (sizes, LaTeX mismatch) | Very high. Font-size questions: 938 / 2.3M, 933 / 2.6M, 530 / 1.3M, 538 / 1.1M | High in print | One base size in pt, tied to the document. Match the paper's font family. Avoid scaling figures in LaTeX. |
| 3 | **Legends** (placement, overlap, multiple axes) | Very high. "Legend outside the plot" is #3 overall (1732 / 2.2M), plus 527 / 1.6M, 496 / 537k, 352 / 423k, 304 / 270k | Medium-high | Place the legend outside or in empty space, reserving room in the layout. Order entries to match the data. Label directly when possible. |
| 4 | **Tick & axis formatting, log axes** | High. Tick frequency: 794 / 1.9M. Log axes: 615 / 1.6M. Rotated labels: 661 / 1.4M. Scientific notation: 161 / 250k | Medium | Use decade labels on log axes, minor ticks without labels, no surprising offset text, and readable (non-overlapping) category labels. |
| 5 | **2D maps & colorbars** (size, shared bar, range, norm, levels) | High. 371 / 440k, 301 / 372k, 223 / 831k, 157 / 278k, 113 / 180k | High: wrong norm or map misleads | The colorbar matches the axes height. One shared bar for panels that share a scale. Explicit vmin/vmax. Log or diverging norms with a meaningful centre. |
| 6 | **Colour: cycles & too many series** | Medium-high. "Different coloured lines": 237 / 477k. Per-series scatter colour: 239 / 1.0M. Get default cycle: 190 / 208k. Colours repeat after 10 (plotly forum and matplotlib discourse threads) | High | Cap categorical colours at roughly 8. Beyond that, use redundant coding or direct labels. Never silently wrap the cycle. |
| 7 | **Colour: rainbow/jet & perceptual maps** | Low on SO today, because viridis fixed the default. Very high in the literature (Borland & Taylor 2007; Crameri et al. 2020) | Very high | Use perceptually uniform sequential maps, and diverging maps only for data with a meaningful midpoint. |
| 8 | **Clutter / chartjunk** (frames, grids, stats boxes, spines) | Medium. Remove frame: 281 / 541k. Remove top/right spines: 247 / 253k. Grid behind data: 214 / 232k. ROOT stats-box threads | Medium | Maximise data-ink "within reason". Use light, sparse grids and no decorative boxes. |
| 9 | **Accessibility / CVD** | Low on SO (top question has 7 votes / 12k views) but one of matplotlib's longest-running open issues (#9460, 46 comments). CMS ran a collaboration-wide palette vote | Very high: about 8% of males | Use CVD-safe default sequences (Okabe–Ito, Petroff), redundant coding, and grayscale-safe maps. |
| 10 | **Error bars / uncertainty** | Low-medium. Caps missing: 32 / 50k. Errorbar connects points: 32 / 55k. linestyle in rcParams: 34 / 116k | High in science | State what the bar means (SD, SE, CI). Use asymmetric intervals correctly. Bands for curves. Caps are a matter of taste. |
| 11 | **API ergonomics** (pyplot vs OO, leaky wrappers, global state) | Medium-high. cla/clf/close: 772 / 1.2M. "Why `fig, ax = plt.subplots()`": 486 / 608k. Seaborn figure size: 528 / 1.4M. HN threads | Indirect | Use one explicit object model and composable styles, and keep every setting reachable without dropping down a layer. |

---

### 1. Multi-panel layout and figure sizing

**Frequency.** This is the largest cluster by far. "How do I change the size of figures drawn with Matplotlib?" is the most-voted matplotlib question of all time (3267 / 6.4M) [SO 332289](https://stackoverflow.com/questions/332289/how-do-i-change-the-size-of-figures-drawn-with-matplotlib). Its subplot variant has 690 / 1.9M [SO 14770735](https://stackoverflow.com/questions/14770735/how-do-i-change-the-figure-size-with-subplots), and the seaborn variant has 528 / 1.4M [SO 31594549](https://stackoverflow.com/questions/31594549/how-to-change-the-figure-size-of-a-seaborn-axes-or-figure-level-plot). About 20 of the top 100 matplotlib questions are layout or sizing questions.

**Examples**
- *Overlapping or cut-off labels.* "Improve subplot size/spacing with many subplots" has 603 / 1.0M [SO 6541123](https://stackoverflow.com/questions/6541123/improve-subplot-size-spacing-with-many-subplots). "How to adjust padding with cutoff or overlapping labels" has 501 / 583k [SO 6774086](https://stackoverflow.com/questions/6774086/how-to-adjust-padding-with-cutoff-or-overlapping-labels). "tight_layout() doesn't take into account figure suptitle" has 320 / 227k [SO 8248467](https://stackoverflow.com/questions/8248467/tight-layout-doesnt-take-into-account-figure-suptitle). The same suptitle problem appears as GitHub issues [#829](https://github.com/matplotlib/matplotlib/issues/829) and [#5355](https://github.com/matplotlib/matplotlib/issues/5355).
- *Shared axes.* "Common xlabel/ylabel for subplots" appears twice: 302 / 1.0M [SO 6963035](https://stackoverflow.com/questions/6963035/how-to-set-common-axes-labels-for-subplots) and 279 / 439k [SO 16150819](https://stackoverflow.com/questions/16150819/common-xlabel-ylabel-for-matplotlib-subplots). "sharex but don't show x tick labels for both" has 114 / 108k [SO 4209467](https://stackoverflow.com/questions/4209467/sharex-axis-but-dont-show-x-axis-tick-labels-for-both-just-one). "Shared axes and no space between subplots" has 13 / 19k [SO 22607444](https://stackoverflow.com/questions/22607444/pyplot-shared-axes-and-no-space-between-subplots). Shared log axes also print stray minor tick labels on every panel [mpl #8903](https://github.com/matplotlib/matplotlib/issues/8903).
- *Ratio panels (HEP).* Plain matplotlib has no first-class ratio panel. The SO question on overlaying histograms with a ratio plot is small (4 / 6.7k) [SO 34857963](https://stackoverflow.com/questions/34857963/using-matplotlib-how-could-one-compare-histograms-by-overlaying-them-and-by-sho). Its low count suggests HEP users rely on ROOT's `TRatioPlot` or on mplhep. Those tools have their own friction: `TRatioPlot` axis titles run off the canvas when enlarged, and the fix is to set sizes on three separate reference axes [ROOT forum](https://root-forum.cern.ch/t/axes-labels-in-tratioplot-are-partially-out-of-the-canvas-if-their-size-is-too-large/52663). The ROOT tutorial hard-codes pixel fonts (font 43) to keep both pads consistent [ratioplot.C](https://root.cern/doc/master/ratioplot_8C_source.html). mplhep added ratio, pull and efficiency comparison panels for this reason [mplhep docs](https://mplhep.readthedocs.io/en/latest/index.html).
- *Plotly.* "Remove space between subplots in Plotly" has 53 / 59k [SO 31526045](https://stackoverflow.com/questions/31526045/remove-space-between-subplots-in-plotly). "Subplots with plotly express" has 45 / 82k [SO 56727843](https://stackoverflow.com/questions/56727843/how-can-i-create-subplots-with-plotly-express).

**Fix consensus**
- Use a layout engine that accounts for every decoration: titles, suptitles, colorbars and outside legends. Matplotlib's `constrained` layout does this, and `tight_layout` is the older, partial solution [constrained layout guide](https://matplotlib.org/3.7.4/_downloads/959d7ad21c495080950ee84dc5d9f025/constrainedlayout_guide.py).
- Size the figure in the units of the target document and never rescale it in LaTeX, so fonts stay at body size [Timo Denk](https://blog.timodenk.com/exporting-matplotlib-plots-to-latex/). Tools such as [latexplotlib](https://pypi.org/project/latexplotlib/0.6.1/) and [matplotlib-latex-bridge](https://matplotlib-latex-bridge.readthedocs.io/en/latest/matplotlib_latex_bridge.html) exist only to do this.
- In small multiples, use identical axis ranges and order panels meaningfully. Wilke: "I generally recommend against using different axis scalings in separate panels" [Wilke ch. 21](https://clauswilke.com/dataviz/multi-panel-figures.html). Rougier et al.'s Rule 3 is "Adapt the Figure to the Support Medium" [Ten Simple Rules](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1003833).

### 2. Fonts and typography

**Frequency.** Four separate font-size questions sit in matplotlib's top 20, with about 7.3M views combined:
- 938 / 2.3M [SO 3899980](https://stackoverflow.com/questions/3899980/how-to-change-the-font-size-on-a-matplotlib-plot)
- 933 / 2.6M [SO 12444716](https://stackoverflow.com/questions/12444716/how-do-i-set-the-figure-title-and-axes-labels-font-size)
- 530 / 1.3M for tick labels [SO 6390393](https://stackoverflow.com/questions/6390393/how-to-change-tick-label-font-size)
- 538 / 1.1M for legends [SO 7125009](https://stackoverflow.com/questions/7125009/how-to-change-legend-fontsize-with-matplotlib-pyplot)

Seaborn adds 75 / 232k [SO 36220829](https://stackoverflow.com/questions/36220829/fine-control-over-the-font-size-in-seaborn-plots).

**Examples**
- *LaTeX mismatch.* "Matplotlib, consistent font using LaTeX" has 83 / 120k [SO 11367736](https://stackoverflow.com/questions/11367736/matplotlib-consistent-font-using-latex). "Not using latex font while text.usetex==True" has 57 / 60k [SO 17958485](https://stackoverflow.com/questions/17958485/matplotlib-not-using-latex-font-while-text-usetex-true). "latex could not be found" has 55 / 191k [SO 58121461](https://stackoverflow.com/questions/58121461/runtimeerror-failed-to-process-string-with-tex-because-latex-could-not-be-found), which shows that `usetex` adds a fragile system dependency.
- *Default mathtext changed.* Matplotlib 2.0 moved mathtext from Computer Modern to DejaVu Sans, so `$...$` labels no longer look like the paper unless `mathtext.fontset='cm'` is set [mpl 2.0 style changes](https://matplotlib.org/3.4.1/users/dflt_style_changes.html).
- *Sizes relative to the figure.* The 2.0 defaults shrank the figure to 6.4×4.8 in and reduced font sizes "to maintain their size relative to the overall size of the figure" [mpl 2.0 style changes](https://matplotlib.org/3.4.1/users/dflt_style_changes.html). A figure placed in a 3.4-inch column is therefore shrunk about 2×, and text ends up near 5 pt. This is the root cause of the "fonts too small in paper" complaint *(the inference is mine; the numbers come from the cited defaults)*.
- *The offset/exponent label is a separate text object with its own size*: 32 / 25k [SO 34227595](https://stackoverflow.com/questions/34227595/how-to-change-font-size-of-the-scientific-notation-offset).

**Fix consensus.** Set one base font size in points that matches the document, with relative sizes for the other text elements. Match the document's font family, either through mathtext `cm`/STIX or through the PGF backend, which typesets the text with LaTeX itself [TU Berlin course](https://platform.commit.tu-berlin.de/en/book/sci-python/chapter/ch18/section/s01). Style packages like SciencePlots exist because "changing the styles of matplotlib figures can be time-consuming" [TDS/SciencePlots](https://towardsdatascience.com/creating-scientific-plots-the-easy-way-with-scienceplots-and-matplotlib-d86a62e2ab46).

### 3. Legends

**Frequency.** "How to put the legend outside the plot" is the #3 matplotlib question of all time (1732 / 2.2M) [SO 4700614](https://stackoverflow.com/questions/4700614/how-to-put-the-legend-outside-the-plot). Its follow-up, "Moving legend outside the axis makes it cut off by the figure box", has 304 / 270k [SO 10101700](https://stackoverflow.com/questions/10101700/moving-matplotlib-legend-outside-of-the-axis-makes-it-cutoff-by-the-figure-box).

**Examples**
- *Multiple axes and subplots.* "Secondary axis with twinx(): how to add to legend" has 496 / 537k [SO 5484922](https://stackoverflow.com/questions/5484922/secondary-axis-with-twinx-how-to-add-to-legend). "Single legend for many subplots" has 352 / 423k [SO 9834452](https://stackoverflow.com/questions/9834452/how-do-i-make-a-single-legend-for-many-subplots).
- *Seaborn.* "Move seaborn plot legend" has 103 / 224k [SO 27019079](https://stackoverflow.com/questions/27019079/move-seaborn-plot-legend-to-a-different-position). Editing legend titles for figure-level functions has 121 / 376k [SO 45201514](https://stackoverflow.com/questions/45201514/how-to-edit-a-seaborn-legend-title-and-labels-for-figure-level-functions). The GitHub issues "Not clear how to reposition seaborn.histplot legend" [#2280](https://github.com/mwaskom/seaborn/issues/2280) and "Plot legend needs more customizability" [#2994](https://github.com/mwaskom/seaborn/issues/2994) are among the seaborn issues with the most reactions.
- *Plotly.* A horizontal legend overlaps the plot [plotly.py #3367](https://github.com/plotly/plotly.py/issues/3367). Duplicate legend entries across subplots: 23 / 27k [SO 26939121](https://stackoverflow.com/questions/26939121/how-to-avoid-duplicate-legend-labels-in-plotly-or-pass-custom-legend-labels).
- *Matplotlib's own history.* `legend.loc='best'` became the default in 2.0 to "minimize overlap with data" [2.0 changes](https://matplotlib.org/3.4.1/users/dflt_style_changes.html). Automatic outside placement was requested in 2014 [#3745](https://github.com/matplotlib/matplotlib/issues/3745) and eventually arrived as `loc="outside right upper"` under constrained layout [figlegend demo 3.7](https://matplotlib.org/3.7.1/gallery/text_labels_and_annotations/figlegend_demo.html), after long PRs [#13072](https://github.com/matplotlib/matplotlib/pull/13072) and [#19743](https://github.com/matplotlib/matplotlib/pull/19743). Users still report constrained layout collapsing outside legends [discourse](https://discourse.matplotlib.org/t/constrained-layout-collapses-legend-outside-of-plot/22498).

**Fix consensus**
- The legend must never cover data. Either reserve layout space for an outside legend or find genuinely empty space. `'best'` only checks overlap with data at the time it is drawn.
- Order legend entries to match the visual order of the data: "If there is a clear visual ordering in your data, make sure to match it in the legend" [Wilke ch. 20](https://clauswilke.com/dataviz/redundant-coding.html).
- Prefer direct labels: "Whenever possible, design your figures so they don't need a legend" [Wilke ch. 20](https://clauswilke.com/dataviz/redundant-coding.html).

### 4. Tick formatting and log axes

**Frequency.** High.
- "Changing the tick frequency" has 794 / 1.9M [SO 12608788](https://stackoverflow.com/questions/12608788/changing-the-tick-frequency-on-the-x-or-y-axis).
- "Plot logarithmic axes" has 615 / 1.6M [SO 773814](https://stackoverflow.com/questions/773814/plot-logarithmic-axes).
- "Rotate axis tick labels" has 661 / 1.4M [SO 10998621](https://stackoverflow.com/questions/10998621/rotate-axis-tick-labels).
- Overlapping x tick labels has 73 / 213k [SO 26700598](https://stackoverflow.com/questions/26700598/matplotlib-showing-x-tick-labels-overlapping).

**Examples**
- *Scientific notation and offset surprises.* "Prevent scientific notation" has 161 / 250k [SO 28371674](https://stackoverflow.com/questions/28371674/prevent-scientific-notation). "Format axis offset-values" has 100 / 116k [SO 3677368](https://stackoverflow.com/questions/3677368/format-axis-offset-values-to-whole-numbers-or-specific-number). "Absolute values rather than offset values" has 32 / 27k [SO 9303728](https://stackoverflow.com/questions/9303728/yaxis-range-display-using-absolute-values-rather-than-offset-values). Matplotlib switches to an offset once it saves 4 or more digits (`axes.formatter.offset_threshold=4`) [2.0 changes](https://matplotlib.org/3.4.1/users/dflt_style_changes.html).
- *Log ticks.* "Log scale tick label number formatting" has 81 / 144k [SO 21920233](https://stackoverflow.com/questions/21920233/matplotlib-log-scale-tick-label-number-formatting). "Remove scientific notation on log-log plot" has 33 / 43k [SO 49750107](https://stackoverflow.com/questions/49750107/how-to-remove-scientific-notation-on-a-matplotlib-log-log-plot). "Disable minor ticks of log plot" has 35 / 49k [SO 10781077](https://stackoverflow.com/questions/10781077/how-to-disable-the-minor-ticks-of-log-plot-in-matplotlib). "Grid lines at all ticks on log-log" has 47 / 100k [SO 3590905](https://stackoverflow.com/questions/3590905/how-do-i-show-logarithmically-spaced-grid-lines-at-all-ticks-on-a-log-log-plot-u). Setting log major ticks leaves "interfering minor tick labels" [mpl #8386](https://github.com/matplotlib/matplotlib/issues/8386).
- *Histograms on log scale.* 58 / 169k [SO 47850202](https://stackoverflow.com/questions/47850202/plotting-a-histogram-on-a-log-scale-with-matplotlib). Logarithmic bins: 107 / 127k [SO 6855710](https://stackoverflow.com/questions/6855710/how-to-have-logarithmic-bins-in-a-python-histogram).
- *Log in 3D is weak*, raised in the HN thread on "Effectively Using Matplotlib" [HN 14668706](https://news.ycombinator.com/item?id=14668706).

**Fix consensus.** Label log axes at decades as 10^n, with unlabelled minor ticks at 2–9 and an option to label them when the range covers fewer than two decades. Do not use an offset or multiplier unless the user asks for one. When a multiplier is used, put it in the axis label ("Events / 10³"), not in a floating corner. Rotate or thin category labels automatically. Log bins should go with log axes.

### 5. 2D maps and colorbars

**Frequency.** High: six colorbar questions each above 100 votes.
- One colorbar for all subplots: 371 / 440k [SO 13784201](https://stackoverflow.com/questions/13784201/how-to-have-one-colorbar-for-all-subplots)
- Colorbar size to match the graph: 301 / 372k [SO 18195758](https://stackoverflow.com/questions/18195758/set-matplotlib-colorbar-size-to-match-graph)
- Set colorbar range: 223 / 831k [SO 3373256](https://stackoverflow.com/questions/3373256/set-colorbar-range)
- Discrete colorbar: 157 / 278k [SO 14777066](https://stackoverflow.com/questions/14777066/matplotlib-discrete-colorbar)
- Midpoint of a colormap: 133 / 117k [SO 7404116](https://stackoverflow.com/questions/7404116/defining-the-midpoint-of-a-colormap-in-matplotlib)
- Log colorbar for scatter: 113 / 180k [SO 17201172](https://stackoverflow.com/questions/17201172/a-logarithmic-colorbar-in-matplotlib-scatter-plot)

**Examples**
- *Sizing.* The usual workarounds are `make_axes_locatable(...).append_axes("right", size="5%", pad=0.05)` [axes_grid1 docs](https://members.cbio.mines-paristech.fr/~nvaroquaux/tmp/matplotlib/mpl_toolkits/axes_grid1/overview.html) and the "magic numbers" `fraction=0.046, pad=0.04` *(SO answer seen only through a mirror, [tencent](https://cloud.tencent.com/developer/ask/71233); unverified on SO itself)*. Users report that colorbars "take space from axes" [discourse](https://discourse.matplotlib.org/t/how-to-prevent-colorbar-from-taking-space-from-axes/18998), and that adding colorbar axes breaks `tight_layout` [mpl #21749](https://github.com/matplotlib/matplotlib/issues/21749).
- *Norms.* Log-normalised imshow with the colorbar in raw units: 55 / 121k [SO 2546475](https://stackoverflow.com/questions/2546475/how-can-i-draw-a-log-normalized-imshow-plot-with-a-colorbar-representing-raw-the). Scientific notation on colorbars: 43 / 68k [SO 25983218](https://stackoverflow.com/questions/25983218/scientific-notation-colorbar). Colorbar title offset: 39 / 61k [SO 17475619](https://stackoverflow.com/questions/17475619/how-do-i-adjust-offset-colorbar-title-in-matplotlib).
- *Plotly* has the same need: "Logarithmic color scale in plotly" has 14 / 15k [SO 50392372](https://stackoverflow.com/questions/50392372/logarithmic-color-scale-in-plotly).
- *Seaborn.* Users ask for a colorbar instead of a legend for a numeric hue [seaborn #2172](https://github.com/mwaskom/seaborn/issues/2172).

**Fix consensus**
- The colorbar should be exactly the height of its axes and always carry a label with units.
- Panels that share a scale get one shared colorbar.
- vmin/vmax should be explicit or shared.
- Use a log norm for data spanning several decades, and a diverging map with a centred norm only when the data has a meaningful midpoint.
- Wilke treats sequential and diverging scales as separate tools [Wilke ch. 4](https://clauswilke.com/dataviz/color-basics.html).

### 6. Colour cycles and too many series

**Frequency.** Medium-high.
- "How to get different colored lines for different plots": 237 / 477k [SO 4805048](https://stackoverflow.com/questions/4805048/how-to-get-different-colored-lines-for-different-plots-in-a-single-figure)
- "Different color for each series in scatter": 239 / 1.0M [SO 12236566](https://stackoverflow.com/questions/12236566/setting-different-color-for-each-series-in-scatter-plot)
- "Get default line color cycle": 190 / 208k [SO 42086276](https://stackoverflow.com/questions/42086276/get-default-line-color-cycle)
- "Reset color cycle": 90 / 66k [SO 24193174](https://stackoverflow.com/questions/24193174/reset-color-cycle-in-matplotlib)
- "Set default color cycle for all subplots": 80 / 79k [SO 9397944](https://stackoverflow.com/questions/9397944/how-to-set-the-default-color-cycle-for-all-subplots-with-matplotlib)

**Examples**
- *Wrap-around after 10.* Plotly users complain about "line or marker color repetition if more than 10 traces" [plotly forum](https://community.plotly.com/t/line-or-marker-color-repetition-if-more-than-10-traces/78719). A matplotlib user with about 30 curves asks how to vary the line style as well [discourse](https://discourse.matplotlib.org/t/labeling-distinguishing-lots-of-curves-on-a-single-plot/14179). The common answer is to sample a colormap, often `jet`, for the cycle (30 / 77k) [SO 30079590](https://stackoverflow.com/questions/30079590/use-matplotlib-color-map-for-color-cycle). That answer brings back problem 7.
- *Same colour meaning different things.* The cycle is per-axes, so the same category gets different colours in different panels or files unless users manage the cycle state. That is why "get cycle state" (106 / 74k) [SO 13831549](https://stackoverflow.com/questions/13831549/get-matplotlib-color-cycle-state) and "reset color cycle" are popular. Seaborn users ask how to pin hue order and colours: "set hue order" has 30 / 64k [SO 65147132](https://stackoverflow.com/questions/65147132/how-to-set-the-hue-order-in-seaborn-plots), and "colour by hue name" has 61 / 123k [SO 46173419](https://stackoverflow.com/questions/46173419/change-bar-color-according-to-hue-name).
- *History.* Matplotlib 2.0 replaced `bgrcmyk` with Tableau's category10 [2.0 changes](https://matplotlib.org/3.4.1/users/dflt_style_changes.html).

**Fix consensus**
- Qualitative scales "work best when there are three to five different categories", and past 8–10 categories, matching colours to a legend becomes impractical [Wilke ch. 19](https://clauswilke.com/dataviz/color-pitfalls.html).
- Above that, group the categories, facet them, or label directly.
- Use redundant coding with marker or line style [Wilke ch. 20](https://clauswilke.com/dataviz/redundant-coding.html).
- Assign colours to *categories*, not to draw order, so a category keeps its colour across panels and files.

### 7. Rainbow / jet colormaps

**Frequency.** SO traffic is now low ("lighter jet" has 3 / 26k [SO 58288579](https://stackoverflow.com/questions/58288579/how-to-get-a-lighter-jet-colormap-in-matplotlib)) because matplotlib 2.0 replaced the default. The literature is extensive. A 2023 IEEE CG&A viewpoint notes that avoiding rainbow maps "has become dogma in the visualization community" [UNH summary of Ware, Stone & Szafir](https://ccom.unh.edu/publications/rainbow-colormaps-are-not-all-bad).

**Examples**
- Borland & Taylor, "Rainbow color map (still) considered harmful", IEEE CG&A 27(2), 2007 [Utah library page](https://www.sci.utah.edu/~kpotter/Library/Papers/borland:2007:RCCH/index.html). ParaView's developers responded that ParaView, MATLAB and others all defaulted to rainbow [ParaView wiki](https://www.paraview.org/ParaView/index.php/Default_Color_Map). MATLAB later replaced jet with parula [Jacobson blog](https://www.cs.toronto.edu/~jacobson/weblog/4082.html).
- Van der Walt & Smith's SciPy 2015 talk "A Better Default Colormap for Matplotlib" argued that jet has a non-monotonic lightness gradient, that small data changes produce large perceptual changes, and that it is not robust for colour-blind viewers. Viridis ("option D") was designed to be perceptually uniform in colour and in grayscale [bids.github.io/colormap](https://bids.github.io/colormap/); [rud.is summary](https://rud.is/b/2015/07/20/using-the-new-viridis-colormap-in-r-thanks-to-simon-garnier); [matplotlib RFC](https://discourse.matplotlib.org/t/rfc-candidates-for-a-new-default-colormap/19309). The matplotlib docs still call restoring jet "strongly discouraged" [2.0 changes](https://matplotlib.org/3.4.1/users/dflt_style_changes.html). *(The talk video is commonly linked as youtube.com/watch?v=xAoljeRJ3lU; unverified.)*
- Crameri, Shephard & Heron, "The misuse of colour in science communication", Nat. Commun. 11, 5444 (2020). They name rainbow-like and red–green maps as the main offenders and call on publishers to act [PMC7595127](https://pmc.ncbi.nlm.nih.gov/articles/PMC7595127).
- Wilke: "The rainbow color scale is not an appropriate scale to visualize continuous data values"; it is "highly non-monotonic" [Wilke ch. 19](https://clauswilke.com/dataviz/color-pitfalls.html). Rougier et al.'s Rule 6 advises avoiding jet and rainbow defaults [Ten Simple Rules](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1003833).

**Fix consensus.** Use a perceptually uniform sequential map (viridis family, cividis, or Crameri's scientific maps) by default. Use a diverging map only around a meaningful centre. Keep rainbow maps for cyclic or categorical-like special cases, if at all.

### 8. Clutter and chartjunk

**Frequency.** Medium.
- Remove frame: 281 / 541k [SO 14908576](https://stackoverflow.com/questions/14908576/how-to-remove-frame-from-a-figure)
- Remove top and right axis: 247 / 253k [SO 925024](https://stackoverflow.com/questions/925024/how-can-i-remove-the-top-and-right-axis)
- Grid behind data: 214 / 232k [SO 1726391](https://stackoverflow.com/questions/1726391/matplotlib-draw-grid-lines-behind-other-graph-elements)
- Remove white padding: 360 / 367k [SO 11837979](https://stackoverflow.com/questions/11837979/removing-white-space-around-a-saved-image)
- Seaborn plus a secondary y axis gives double grids: 54 / 123k [SO 26868304](https://stackoverflow.com/questions/26868304/how-to-get-rid-of-grid-lines-when-plotting-with-seaborn-pandas-with-secondary)

**Examples**
- *Tufte.* He coined "chartjunk" and the data-ink ratio in *The Visual Display of Quantitative Information* (1983) [Wikipedia: Chartjunk](https://en.wikipedia.org/wiki/Chartjunk). Rougier et al.'s Rule 8 is "Avoid 'Chartjunk'" [Ten Simple Rules](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1003833).
- *Wilke's moderation.* "Maximize the data–ink ratio, within reason." He argues that removing every grid line leaves data "floating", and that grid lines are most useful perpendicular to the key variable [Wilke ch. 23](https://clauswilke.com/dataviz/balance-data-context.html).
- *ROOT.* The statistics box is drawn by default, and the gray default canvas has been a complaint since at least 2001 [BNL list](https://www.sdcc.bnl.gov/brahms/private/list_hyper/brahms-l/0393.html). Users struggle to remove a "sticky" stats box, because `gStyle->SetOptStat(0)` does not affect histograms that already have a `TPaveStats` [roottalk 2003](https://root.cern.ch/root/roottalk/roottalk03/2998.html); [ROOT forum](https://root-forum.cern.ch/t/impossible-to-remove-stat-box-of-a-histogram-in-the-gui/44800). ROOT now ships a "Modern" style used at startup [TStyle source](https://root.cern.ch/doc/v636/TStyle_8cxx_source.html). *(I did not confirm which version made "Modern" the default; unverified.)*
- *Matplotlib defaults.* Data sitting on the spine and becoming "nearly invisible", compared with R's 4% padding [discourse "Better defaults"](https://discourse.matplotlib.org/t/better-defaults-all-around/18961). Matplotlib 2.0 then added 5% data margins and outward ticks to avoid "a porcupine appearance" [2.0 changes](https://matplotlib.org/3.4.1/users/dflt_style_changes.html). HEP styles (ATLAS/CMS) instead use inward ticks on all four sides *(per mplhep styles; unverified detail)*.

**Fix consensus**
- No stats boxes, titles inside the plot, or legend frames by default.
- Grids light or off.
- Pick one consistent spine convention per style.
- Keep the margins that stop data from touching the frame.
- Context, such as experiment labels and luminosity, should be compact text rather than boxes.

### 9. Accessibility (CVD, grayscale)

**Frequency.** This is the clearest mismatch between how often users ask and how much it matters. The top SO question has 7 / 12k [SO 69897460](https://stackoverflow.com/questions/69897460/how-to-make-matplotlib-markers-colorblind-friendly-in-a-simple-way). Meanwhile "Color blind-friendly default color cycle" [mpl #9460](https://github.com/matplotlib/matplotlib/issues/9460) has been open since 2017 with 46 comments and the most reactions of any color-cycle issue. Maintainers there said "Visual changes are only done in major releases". About 8% of males and 0.5% of females have CVD [Wilke ch. 19](https://clauswilke.com/dataviz/color-pitfalls.html).

**Examples**
- *Petroff 2021.* "Accessible Color Sequences for Data Visualization" (arXiv:2107.02270) combines CVD-aware distance constraints with an aesthetics model trained on survey data, and produces 6-, 8- and 10-colour cycles [arXiv](https://arxiv.org/abs/2107.02270v3). These shipped as `petroff10` in matplotlib 3.10 [mpl 3.10 gallery](https://matplotlib.org/3.10.0/gallery/style_sheets/petroff10.html), with petroff6/8 by 3.11 [mpl 3.11 gallery](https://matplotlib.org/3.11.0/gallery/style_sheets/petroff10.html), and in ROOT [accessiblecolorschemes.C](https://root.cern.ch/doc/v638/accessiblecolorschemes_8C.html).
- *CMS.* The CMS Diversity and Inclusion Office ran a call for palettes (15 1D combinations and 5 2D maps), held a collaboration-wide vote, and built the winners into official tools [CMS](https://cms.cern/node/2203). *(Commonly reported that the winners are Petroff's sequences; unverified.)*
- *Crameri et al. 2020* single out red–green maps as inaccessible [PMC7595127](https://pmc.ncbi.nlm.nih.gov/articles/PMC7595127).
- *HEP "Brazil plot".* The ±1σ/±2σ expected-limit bands are conventionally green and yellow [DESY stats lecture](https://indico.desy.de/event/13610/contributions/13666/attachments/9230/10838/Lecture_on_Statistics_partI.pdf). Green and yellow are close in lightness and can be hard to tell apart for deuteranopes *(the CVD critique is a plausible inference; I did not find a published critique — unverified)*. The convention is entrenched, so a tool should offer it but let users choose a lightness-ordered alternative.

**Fix consensus**
- Default to a CVD-tested categorical sequence (Okabe–Ito or Petroff).
- Use redundant coding with markers, line styles or hatches. Wilke warns that dashed lines add noise [Wilke ch. 20](https://clauswilke.com/dataviz/redundant-coding.html).
- Use sequential maps that are monotonic in lightness, so they survive grayscale printing.
- Test with a CVD simulator [Wilke ch. 19](https://clauswilke.com/dataviz/color-pitfalls.html).

### 10. Error bars and uncertainty

**Frequency.** Low-medium on SO, but a matter of correctness in science.
- "Errorbar caps missing": 32 / 50k [SO 18434492](https://stackoverflow.com/questions/18434492/matplotlib-errorbar-caps-missing)
- "errorbar keeps connecting my points with lines": 32 / 56k [SO 40020274](https://stackoverflow.com/questions/40020274/pyplot-errorbar-keeps-connecting-my-points-with-lines)
- "errorbar with linestyle=None in rcParams": 34 / 116k [SO 18498742](https://stackoverflow.com/questions/18498742/how-do-you-make-an-errorbar-plot-in-matplotlib-using-linestyle-none-in-rcparams)
- Asymmetric error bars for one point: 11 / 20k [SO 31812469](https://stackoverflow.com/questions/31812469/plotting-asymmetric-error-bars-for-a-single-point-using-errorbar)
- Seaborn caps: 21 / 58k [SO 35915431](https://stackoverflow.com/questions/35915431/top-and-bottom-line-on-errorbar-with-python-and-seaborn)

**Examples**
- Matplotlib 2.0 turned caps off by default (`errorbar.capsize=0`) and gave no stated rationale [2.0 changes](https://matplotlib.org/3.4.1/users/dflt_style_changes.html). This produced the "caps missing" questions.
- Several issues come from rcParams leaking into error bars: `lines.markeredgecolor` recoloured caps [mpl #29780](https://github.com/matplotlib/matplotlib/issues/29780), multicolour error bars could not have caps [mpl #14480](https://github.com/matplotlib/matplotlib/issues/14480), and users asked for separate errorbar rc defaults [mpl #8071](https://github.com/matplotlib/matplotlib/issues/8071). A legend/zorder interaction is reported in [SO 16770049](https://stackoverflow.com/questions/16770049/strange-matplotlib-zorder-behavior-with-legend-and-errorbar).
- Wilke's guidance [Wilke ch. 16](https://clauswilke.com/dataviz/visualizing-uncertainty.html):
  - Always state whether a bar is SD, SE or CI, and at what level.
  - Consider graded error bars and confidence bands.
  - Caps are "largely a matter of personal taste" and add noise in dense plots.
  - Overlapping bars do not show non-significance.

**Fix consensus.** The figure (legend or caption) should say what the uncertainty is. Use asymmetric intervals natively. Bands are better than bar forests for curves. Error bars should not inherit line or marker styling meant for data lines. For counts and efficiencies, use intervals that respect the physical bounds; plotipus's Clopper–Pearson table option already does this.

### 11. API ergonomics

**Frequency.** Medium-high.
- "When to use cla(), clf() or close()": 772 / 1.2M [SO 8213522](https://stackoverflow.com/questions/8213522/when-to-use-cla-clf-or-close-for-clearing-a-plot)
- "What does the argument mean in fig.add_subplot(111)": 605 / 562k [SO 3584805](https://stackoverflow.com/questions/3584805/what-does-the-argument-mean-in-fig-add-subplot111)
- "Why do many examples use `fig, ax = plt.subplots()`": 486 / 608k [SO 34162443](https://stackoverflow.com/questions/34162443/why-do-many-examples-use-fig-ax-plt-subplots)
- "Save plot to image file instead of displaying it": 1808 / 3.3M, the #2 question overall [SO 9622163](https://stackoverflow.com/questions/9622163/save-plot-to-image-file-instead-of-displaying-it)
- "Savefig outputs blank image": 364 / 435k [SO 9012487](https://stackoverflow.com/questions/9012487/savefig-outputs-blank-image)

**Examples**
- *Two interfaces.* Pyplot's implicit "current axes" is convenient but makes targeting specific plots harder [TU Berlin](https://commit-web.commit.tu-berlin.de/en/book/sci-python/chapter/ch15/section/s01). On HN, one commenter calls matplotlib "an example of unnecessarily complex and confusing 'organic' API" [HN 14668706](https://news.ycombinator.com/item?id=14668706), and a blog commenter counts "at least three completely different ways" to create figures [Daily Dose of DS](https://blog.dailydoseofds.com/p/the-most-underrated-and-underutilized/comments).
- *Leaky wrappers.* Pandas and seaborn hand back matplotlib axes: "You have to break through the abstraction pretty much immediately" [HN 14668706](https://news.ycombinator.com/item?id=14668706). Seaborn's axes-level vs figure-level split creates its own question set, such as the figure size question at 528 / 1.4M above and per-facet axis labels [SO 39352563](https://stackoverflow.com/questions/39352563/how-to-add-x-axis-labels-to-every-plot-in-a-seaborn-figure-level-plot).
- *Global rcParams.* "Setting axes.linewidth without changing the rcParams global dict" has 51 / 117k [SO 2553521](https://stackoverflow.com/questions/2553521/setting-axes-linewidth-without-changing-the-rcparams-global-dict). "Local rcParams for one figure" has 13 / 6.9k [SO 22792779](https://stackoverflow.com/questions/22792779/how-to-set-local-rcparams-or-rcparams-for-one-figure-in-matplotlib).
- *Prebinned data.* HEP users have histograms that are already binned, which `plt.hist` handles poorly. mplhep's `histplot` and matplotlib's `stairs` (3.4) were added for this [scientific-python blog](https://blog.scientific-python.org/introducing-mplhep/). Step-function questions are common: 46 / 101k [SO 8921296](https://stackoverflow.com/questions/8921296/how-do-i-plot-a-step-function), and "step plot where=post" has 32 / 28k [SO 35067304](https://stackoverflow.com/questions/35067304/pandas-dataframe-step-plot-where-post).
- *Other comparisons.* On HN, ggplot2's grammar is praised for consistency, while one commenter calls it "wildly unpythonic" [HN 14668706](https://news.ycombinator.com/item?id=14668706). Rougier's open book has a full part on "Matplotlib's defaults and styling system" and on figure design [rougier/scientific-visualization-book](https://github.com/rougier/scientific-visualization-book), discussed on HN [29229103](https://news.ycombinator.com/item?id=29229103) and [41572437](https://news.ycombinator.com/item?id=41572437).

**Fix consensus**
- One explicit object model.
- Declarative styles that scope per figure rather than globally.
- Wrappers that expose every visual setting so users never have to drop down a layer.
- Headless and file-first by default for batch use.
- Rougier et al.'s Rule 5 sums it up: "Do Not Trust the Defaults… They are good enough for any plot but they are best for none" [Ten Simple Rules](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1003833).

---

### Design principles these complaints imply

1. **Physical size first.** Every figure is defined by its target width (column, page or slide) in inches or cm, plus a base font size in points. Never scale after rendering. This addresses the #1 and #2 themes at once.
2. **The layout engine owns all decorations.** Constrained-style layout always accounts for titles, outside legends, colorbars, ratio panels and experiment labels. Users should never need `subplots_adjust` or `bbox_inches` tricks.
3. **Legends never cover data.** Place them in measured empty space, or outside with reserved room. Order entries to match the data. Offer direct labels as an option.
4. **Colour is bound to categories, not draw order.** The same category keeps the same colour across panels, files and runs. Exceeding the palette is an error or warning, never a silent wrap, and redundant coding (markers or line styles) is the fallback.
5. **Accessible by default.** The categorical default is a CVD-tested sequence (Petroff or Okabe–Ito). Sequential maps are perceptually uniform and grayscale-safe. Jet and rainbow are opt-in with a warning. Conventional HEP palettes such as Brazil bands are available but not the default.
6. **Norms are first-class.** 2D maps get explicit linear, log or centred-diverging norms, shared vmin/vmax across panels, colorbars matching the axes height, and a mandatory colorbar label with units.
7. **Ticks that read like a paper.** Decade labels on log axes, unlabelled minor ticks, no floating offset or multiplier text (move it into the axis label), and automatic thinning or rotation of crowded labels.
8. **Uncertainty is explicit and correct.** Support asymmetric and bounded intervals natively. Record what the uncertainty means (SD, SE, CI or Clopper–Pearson). Error bars do not inherit data-line styling. Prefer bands for curves.
9. **Low ink, but not floating.** No stats boxes, frames or chartjunk by default. Light or optional grids. Keep data margins so points never sit on the spine. Context such as experiment labels is compact text.
10. **Multi-panel means consistent.** Shared axes hide inner tick labels. Ratio and pull panels are built in, sharing x, with no gap and aligned labels. Small multiples share scales unless the user explicitly overrides it.
11. **Typography matches the document.** One switch selects the paper's font family (CM or STIX via mathtext, or PGF), without requiring a system LaTeX install for the common case.
12. **Declarative, scoped, overridable.** Styles are named and composable, and apply per figure rather than through global rcParams. Every visual setting is reachable from the CLI or config, so users never have to drop into matplotlib to finish a plot.

---

# Part 3: famous plots as reproduction targets

Each figure has an id (F01–F25) that [catalogue.md](catalogue.md) refers to. The **NEW** markers below were written from the README; the verified support status of each feature is in the catalogue's support matrix.


Research date: 2026-10-24. Every bibliographic fact and figure description below was checked against the source linked in its section: the paper PDF (read via arXiv/alphaXiv), the publisher record, or the data-provider page. Anything I could not confirm is marked **(unverified)**. Figure numbers appear only where I read them in the paper itself.

How to read the "plotipus requirement" lines: they use plotipus vocabulary (`line`, `scatter`, `hist`, `map`, `cat`, `table`, `--lower ratio|residual|pull|column:...`, `--fit`, `--contour`, `--logx/--logy`, `--stacked`, `--horizontal`). **NEW** marks a capability plotipus probably lacks today, judging from the README option table.

### Summary table

| id | figure | year | plot type | data | verified? |
|---|---|---|---|---|---|
| F01 | ATLAS H→γγ m_γγ spectrum (4 panels) | 2012 | points+errors, S+B fit, bkg curve, residual lower panels, weighted variant | synthetic (HEPData unverified) | yes (paper Fig. 4) |
| F02 | CMS H→γγ S/(S+B)-weighted m_γγ with 1σ/2σ bkg bands + inset | 2012 | points+errors, fit curves, ±1σ/±2σ band, inset | synthetic | yes (paper Fig. 3) |
| F03 | H→ZZ*→4ℓ m_4ℓ (ATLAS & CMS) | 2012 | stacked bkg hist + data points + signal on top | public (CMS Open Data rec. 5500/5501) + synthetic | yes |
| F04 | Local p0 vs m_H with σ lines | 2012 | log-y lines, obs solid / exp dashed, ±1σ band, horizontal σ lines | synthetic (asymptotic formula) | yes (ATLAS Fig. 9, CMS Fig. 14) |
| F05 | "Brazil band" CLs / μ limit | 2012 | log-y obs line, exp dashed, green/yellow ±1σ/±2σ bands | synthetic | yes (ATLAS Fig. 7a, CMS Fig. 13) |
| F06 | COBE FIRAS CMB blackbody | 1990–96 | points with (magnified) errors on Planck curve + residual panel | public (NASA LAMBDA) | mostly; "±400σ" error-bar convention unverified for original |
| F07 | Planck 2018 TT power spectrum | 2018 | points+asym errors, theory curve, residual panel, hybrid log/linear x | public (Planck Legacy Archive) | yes (Planck 2018 VI Fig. 1); file columns unverified |
| F08 | Hubble velocity–distance diagram | 1929 | scatter + two fitted lines (individual/grouped) + cross | public (Table 1 in paper, transcribed below) | yes |
| F09 | SN Ia Hubble diagram + Δ(m−M) panel | 1998 | points+errors, 3 cosmology curves, residual lower panel, log-x | public (Union2.1) | yes (Riess Fig. 4) |
| F10 | Ω_M–Ω_Λ confidence contours | 1998/99 | filled 68/95/99.7% contours + reference lines + region labels | synthetic chi² grid from Union2.1 | yes (Riess Fig. 6; Perlmutter Fig. 7) |
| F11 | Rubin, Ford & Thonnard flat rotation curves | 1980 | multi-series line/points v(R) | synthetic (or digitise) | citation yes; figure layout unverified |
| F12 | NGC 3198 disk + halo decomposition | 1985 | data points + component curves (disk, gas, halo, total) | synthetic | citation via secondary sources |
| F13 | Keeling curve (Mauna Loa CO2) | 1958– | time-series line, monthly + deseasonalised | public (NOAA GML CSV) | yes (columns read) |
| F14 | "Hockey stick" (MBH99) | 1999 | line + uncertainty band + instrumental overlay + smoothed curve | public (NOAA paleo study 6276) | yes; article DOI unverified |
| F15 | LIGO GW150914 strain | 2016 | 2-column multi-row time series, NR overlay, 90% bands, residual row, spectrogram | public (LIGO DCC G1600204 / GWOSC) | yes (PRL Fig. 1) |
| F16 | KamLAND survival probability vs L0/E | 2008 | points+stat errors + expectation curve/histogram | synthetic | yes (PRL Fig. 3) |
| F17 | LEP Z lineshape and N_ν = 2,3,4 | 2006 | data points (errors ×10) + 3 model curves | synthetic (published Z parameters) | yes (Phys. Rept. Fig. 1.13) |
| F18 | R ratio σ(e+e−→hadrons)/σ(μμ) | PDG | log-log points+errors, resonance labels, QCD/parton curves | public (PDG data files) | yes; current file URL unverified |
| F19 | Geiger–Marsden α scattering | 1913 | log-y counts vs angle + 1/sin⁴(φ/2) curve | needs transcription of scanned table / synthetic | citation yes; table values unverified |
| F20 | Moseley's law | 1913 | √ν vs Z points + linear fits (Kα, Lα) | public (NIST X-ray transition energies) or synthetic | citation yes; page range conflict |
| F21 | Leavitt period–luminosity | 1912 | magnitude vs log P scatter, two lines (max/min), inverted y | public (Circular 173 table, transcribe) | citation yes |
| F22 | HR diagram (Russell 1914 → Gaia DR2) | 1914/2018 | 2D density (log colour) of M_G vs BP−RP, inverted y | public (Gaia archive ADQL) | yes |
| F23 | Nightingale rose | 1858 | polar-area (coxcomb), stacked wedges by cause, 2 panels | public (R HistData::Nightingale) | yes |
| F24 | Minard's Napoleon march | 1869 | flow band (width ∝ troops) + aligned temperature line panel | public (R HistData::Minard.*) | yes |
| F25 | Anscombe's quartet + Datasaurus Dozen | 1973/2017 | small-multiple scatters + identical fit lines + stats table | public (R datasets / datasauRus) | yes |

Excluded on purpose: Snow's 1854 cholera map (needs a street-map basemap; data exist in R `HistData::Snow.deaths`, 578 deaths, but plotipus has no geographic layer), Millikan's oil drop (Phys. Rev. 2, 109 (1913), doi:10.1103/PhysRev.2.109 per a mirror; his key evidence is tabular, not one iconic figure), Super-K atmospheric zenith plots and top/W-mass ellipses (not researched in depth; LEP Phys. Rept. hep-ex/0509008 has the mt prediction figure, Fig. 1.16, if wanted).

---

### F01 ATLAS 2012 H→γγ diphoton mass spectrum

- **Source**: ATLAS Collaboration, "Observation of a new particle in the search for the Standard Model Higgs boson with the ATLAS detector at the LHC", Phys. Lett. B 716 (2012) 1, [arXiv:1207.7214](https://arxiv.org/abs/1207.7214). Figure 4.
- **Shows**: Diphoton invariant mass, 100–160 GeV, 7 TeV (4.8 fb⁻¹) + 8 TeV (5.9 fb⁻¹) combined, with the bump near 126.5 GeV.
- **Plot type**: Four stacked panels sharing x. (a) Events / 2 GeV, data points with errors, red "Sig+Bkg Fit" (signal fixed at m_H = 126.5 GeV), dashed "Bkg (4th order polynomial)", which is a fourth-order Bernstein polynomial. (b) Events − Bkg residual, y about ±200. (c) the same sample with each event weighted by ln(1+S/B) of its category ("Σ weights / 2 GeV"). (d) weighted residual, y about ±8.
- **Encodings**: linear axes; black points; solid (S+B) and dashed (B) curves.
- **Uncertainty**: Poisson-like vertical error bars on the data; no bands.
- **Annotations**: ATLAS label, √s and ∫L dt text for both energies, "H→γγ", panel letters (a)–(d).
- **Data**: The paper does not ship a table. Whether a HEPData record exists for 1207.7214 is **(unverified)**: hepdata.net was unreachable from this sandbox. Use synthetic data. Background ≈ exp(−m/τ) or a Bernstein polynomial normalised to about 3000 events/2 GeV at 100 GeV, falling to about 700 at 160 GeV (read from the axis range). Signal is a Gaussian, σ ≈ 1.6 GeV, at 126.5 GeV with about 200–300 events. Draw Poisson counts in 2 GeV bins. For (c)/(d), split into about 10 categories with different S/B and weight each one by ln(1+S/B).
- **plotipus requirement**: `line --plot_type errorbar` for data, plus a stored S+B fit curve and a dashed B curve (`--fit` or extra series), and **two** lower panels (`--lower residual` against the background component only). For the 4-panel layout: two independent upper panels in one figure, raw and weighted (**NEW**: stacked multi-main-panel layout, or two separate figures). Also needs a "residual w.r.t. a named component" option instead of the full fit.

### F02 CMS 2012 H→γγ weighted spectrum

- **Source**: CMS Collaboration, "Observation of a new boson at a mass of 125 GeV with the CMS experiment at the LHC", Phys. Lett. B 716 (2012) 30, [arXiv:1207.7235](https://arxiv.org/abs/1207.7235). Figure 3.
- **Shows**: m_γγ 110–150 GeV, each event weighted by S/(S+B) of its category, with an excess at about 125 GeV.
- **Plot type**: data points + "S+B Fit" (red line) + "B Fit Component" (dashed) + **±1σ (yellow-green) and ±2σ (yellow) bands on the background**. An **inset** shows the unweighted spectrum (120–130 GeV region, "Events / 1.5 GeV").
- **Encodings**: linear axes, "S/(S+B) Weighted Events / 1.5 GeV".
- **Uncertainty**: data error bars; two-level background uncertainty bands (the caption says "coloured bands represent the ±1 and ±2 standard deviation uncertainties in the background estimate").
- **Annotations**: CMS label, √s and L for 7 and 8 TeV.
- **Data**: synthetic, as for F01. Background is a power law in m_γγ; the bands are the fit-parameter uncertainty propagated (sample the covariance, take the 16/84 and 2.5/97.5 percentiles per bin).
- **plotipus requirement**: errorbar data + fitted curve + **nested ±1σ/±2σ filled bands around a curve** (Brazil-style colours) + **inset axes** (**NEW**: inset sub-plot from a second DataFrame selection).

### F03 H→ZZ*→4ℓ four-lepton mass

- **Sources**: ATLAS [arXiv:1207.7214](https://arxiv.org/abs/1207.7214) Fig. 2 (m_4ℓ 80–250 GeV, Events/5 GeV; legend: Data, Background ZZ(*), Background Z+jets/tt̄, Signal m_H = 125 GeV, Syst.Unc.). CMS [arXiv:1207.7235](https://arxiv.org/abs/1207.7235) Fig. 4 (m_4ℓ 80–180 GeV, Events/3 GeV; legend: Data, Z+X, Zγ*/ZZ, m_H = 125 GeV; inset with K_D > 0.5).
- **Shows**: Z peak at 91 GeV, ZZ continuum rising above 180 GeV, and a small cluster of events at 125 GeV.
- **Plot type**: **stacked filled background histograms** (ZZ and reducible), **signal stacked on top as an open/coloured histogram**, black data points with Poisson errors, and a hatched syst. band (ATLAS). CMS adds an inset.
- **Uncertainty**: Poisson errors on low counts (ideally asymmetric Garwood intervals), hatched systematic band on the total background.
- **Data**: **public**. CMS Open Data "Higgs-to-four-lepton analysis example using 2011-2012 data", [record 5500](https://opendata.cern.ch/record/5500) (DOI 10.7483/OPENDATA.CMS.JKB8.RR42), with ROOT inputs in [record 5501](https://opendata.cern.ch/record/5501) (DOI 10.7483/OPENDATA.CMS.JKB8.D634, 24 files, about 1.5 MiB). The record says it reproduces the reference plot at reduced significance (~2σ vs 3.2σ). Alternatively, synthesise: ZZ as a Breit–Wigner at 91 GeV plus a broad continuum turning on at 180 GeV, a Z+X Landau-like shape, and a signal Gaussian of about 7.5 events at 125 GeV, σ ≈ 2 GeV (CMS Table 3: 7.54 ± 0.78 expected signal in 110–160 GeV).
- **plotipus requirement**: `hist --stacked` backgrounds + signal stacked on top + data errorbar overlay with **Poisson (Garwood) asymmetric errors** + hatched total-uncertainty band + optional `--lower ratio` (data/bkg) and inset.

### F04 Higgs local p0 scan

- **Sources**: ATLAS [1207.7214](https://arxiv.org/abs/1207.7214) Fig. 9 (low-mass p0, 110–150 GeV) and Fig. 8 (per channel). CMS [1207.7235](https://arxiv.org/abs/1207.7235) Fig. 14 (7, 8 TeV, combined) and Fig. 15 (per decay mode).
- **Shows**: Local p-value of the background-only hypothesis vs hypothesised m_H. The minimum reaches about 6σ (ATLAS, 1.7×10⁻⁹ after systematics, quoted 5.9σ) or 5.0σ (CMS).
- **Plot type**: log-y line plot. Observed is solid, expected for a SM Higgs is dashed, and ATLAS adds a **±1σ band on the expected curve**. **Horizontal dashed lines at 1σ…6σ** (CMS up to 7σ) carry **right-margin σ labels**.
- **Encodings**: y log 10⁻¹¹…1 (ATLAS) or 10⁻¹²…1 (CMS). In the per-energy versions, 7 TeV is blue/dark, 8 TeV red/light, combined black.
- **Data**: synthetic. Compute expected Z(m) = Z_peak·exp(−(m−125)²/2w²) with w ≈ 3–4 GeV, plus a fluctuating observed curve. p0 = 1 − Φ(Z), and the σ lines sit at p = 1 − Φ(n).
- **plotipus requirement**: `line --logy` with `--style` obs/exp, a band around the expected curve, and **horizontal reference lines with text labels at the right edge** (`--horizontal` exists; labelled σ lines are **NEW**, a "significance gridlines" helper).

### F05 Brazil-band CLs exclusion

- **Sources**: ATLAS [1207.7214](https://arxiv.org/abs/1207.7214) Fig. 7(a) ("95% CL Limit on μ", 110–600 GeV, log y, observed solid, expected dashed, ±1σ and ±2σ bands; caption: "dark and light shaded bands"). CMS [1207.7235](https://arxiv.org/abs/1207.7235) Fig. 13 (CLs value itself, log y 10⁻⁷…1, observed with solid points, "green (dark) and yellow (light) bands", thick horizontal lines at CLs = 0.05, 0.01, 0.001 labelled 95%, 99%, 99.9%).
- **Plot type**: limit line + median expected + two nested bands; **x log-ish** (ATLAS uses a broken scale, 110–150 then 200–500) **(the axis-break detail is inferred from the tick labels, unverified)**.
- **Data**: synthetic. Expected median limit μ_95(m) ≈ smooth curve (0.5–1 near 125, about 0.3 at 200, rising at high mass). Bands from asymptotic formulas: μ_±Nσ = σ_μ(Φ⁻¹(1−0.05·Φ(∓N)) ± N), with σ_μ = μ_med/1.96. Observed = median + fluctuation + bump at 125.
- **plotipus requirement**: `line --logy` with observed/expected styles and **two-level filled bands with fixed green/yellow colours** (a "brazil" preset), plus labelled horizontal CL lines. An optional **broken x-axis** is **NEW**.

### F06 COBE FIRAS CMB blackbody spectrum

- **Sources**: Fixsen et al. 1996, "The Cosmic Microwave Background Spectrum from the full COBE FIRAS Data Set", ApJ 473, 576 (Table 4 residuals). Mather et al. 1994, ApJ 420, 439 ([NTRS 19950040015](https://ntrs.nasa.gov/citations/19950040015)): T = 2.726 ± 0.010 K (95% CL systematic). The search snippet of the NTRS abstract gives deviations "less than 0.30% of the peak brightness, with an rms value of 0.01%". I did not read the abstract itself, so the exact limit is **(unverified)**.
- **Shows**: CMB intensity vs frequency (about 2–21 cm⁻¹), a perfect 2.725 K Planck curve.
- **Plot type**: points with **error bars magnified** (a widely reproduced version shows "±400σ" error bars; confirmed only in the review [astro-ph/9705101](https://arxiv.org/abs/astro-ph/9705101), not in the original, **unverified for the original**) on a theory curve. The natural plotipus version adds a **residual lower panel in kJy/sr** (Fixsen Table 4 residuals ±1σ), which shows the 50 ppm-level agreement.
- **Encodings**: linear x in cm⁻¹ (top axis in GHz is common), y in MJy/sr.
- **Data**: **public**. NASA LAMBDA [FIRAS monopole spectrum](https://lambda.gsfc.nasa.gov/product/cobe/firas_monopole_spect.html), file `firas_monopole_spec_v1.txt` (about 2 KB): the 2.725 K blackbody plus Fixsen Table 4 residuals, 1σ uncertainties and Galaxy model. LAMBDA says the full 43×43 covariance is a separate FITS file. Exact column order **unverified** (I could not open the file).
- **plotipus requirement**: errorbar points with an **error-bar scale factor** (**NEW**: `--error_scale 400` with an automatic legend note) + analytic curve overlay (Planck function as a stored model column) + `--lower residual` (or `column:Residual`), plus a **secondary top x-axis with unit conversion** (**NEW**).

### F07 Planck 2018 TT angular power spectrum

- **Source**: Planck Collaboration, "Planck 2018 results. VI. Cosmological parameters", A&A 641, A6 (2020), [arXiv:1807.06209](https://arxiv.org/abs/1807.06209), Fig. 1. Spectra and likelihoods: Planck 2018 V, [arXiv:1907.12875](https://arxiv.org/abs/1907.12875).
- **Shows**: D_ℓ^TT [µK²] for ℓ = 2–2500, with the acoustic peaks and the best-fit ΛCDM curve.
- **Plot type**: points with error bars + theory curve (light blue) + **residual lower panel ΔD_ℓ**. **The x axis is logarithmic for 2 ≤ ℓ ≤ 29 and linear for ℓ ≥ 30**, and the residual panel's vertical scale also changes at ℓ = 30 (±600 below, ±60 above). This is all stated in the caption.
- **Uncertainty**: ±1σ diagonal errors including cosmic variance. Low-ℓ points are Commander, with asymmetric errors.
- **Data**: **public**. Planck Legacy Archive PR3 cosmology products: `COM_PowerSpect_CMB-TT-full_R3.01.txt` (unbinned, ℓ 2–2508) and a binned version. The ESA DOI page lists them, and a mirror is at [IRSA](https://irsaproxy4.ipac.caltech.edu/data/Planck/release_3/ancillary-data/). Columns are probably ℓ, D_ℓ, −dD_ℓ, +dD_ℓ (binned files add best-fit) **(unverified)**. The header starts with "#", which trips pandas.
- **plotipus requirement**: errorbar with **asymmetric errors** + model curve + `--lower residual` + **piecewise (hybrid log→linear) x-axis scale** (**NEW**: a custom matplotlib scale, or two side-by-side axes with a shared y and different widths, plus a lower panel that changes y-range at the split).

### F08 Hubble's 1929 velocity–distance relation

- **Source**: E. Hubble, "A Relation between Distance and Radial Velocity among Extra-Galactic Nebulae", PNAS 15, 168–173 (1929), [doi:10.1073/pnas.15.3.168](https://doi.org/10.1073/pnas.15.3.168). Single figure ("Figure 1"), read from the [Groningen PDF](https://www.astro.rug.nl/~weygaert/tim1publication/cosmo2007/literature/hubble.1929.pdf).
- **Shows**: Radial velocity (km/s, corrected for solar motion) vs distance (10⁶ pc).
- **Plot type, from the caption**: "The black discs and full line represent the solution for solar motion using the nebulae individually; the circles and broken line represent the solution combining the nebulae into groups; the cross represents the mean velocity corresponding to the mean distance of 22 nebulae whose distances could not be estimated individually."
- **Fits**: 24 objects give K = +465 ± 50 km/s/Mpc; 9 groups give K = +513 ± 60 (the model also fits solar-motion terms X, Y, Z).
- **Data**: **public, in Table 1**. 24 nebulae with r [Mpc] and v [km/s], transcribed from the PDF text:

```
object,r_Mpc,v_kms
SMC,0.032,170
LMC,0.034,290
NGC6822,0.214,-130
NGC598,0.263,-70
NGC221,0.275,-185
NGC224,0.275,-220
NGC5457,0.45,200
NGC4736,0.5,290
NGC5194,0.5,270
NGC4449,0.63,200
NGC4214,0.8,300
NGC3031,0.9,-30
NGC3627,0.9,650
NGC4826,0.9,150
NGC5236,0.9,500
NGC1068,1.0,920
NGC5055,1.1,450
NGC7331,1.1,500
NGC4258,1.4,500
NGC4151,1.7,960
NGC4382,2.0,500
NGC4472,2.0,850
NGC4486,2.0,800
NGC4649,2.0,1090
```
  Table 1 velocities are as measured. The plotted ones are solar-motion-corrected, so a straight fit through the table will not give exactly 465 (to get the plotted values you must apply the X, Y, Z solar-motion terms with each galaxy's RA/Dec). The 9-group membership is not listed in the paper **(unverified)**; group by equal r.
- **plotipus requirement**: `scatter` with two marker families (filled/open) + **two weighted linear fits with different line styles**, a single highlighted point (`--point`), and a fit-parameter annotation. Also: fit through the origin (**NEW** if `--fit` lacks constrained intercepts).

### F09 Supernova Hubble diagram (accelerating universe)

- **Sources**: Riess et al., "Observational Evidence from Supernovae for an Accelerating Universe and a Cosmological Constant", AJ 116, 1009 (1998), doi:10.1086/300499, [astro-ph/9805201](https://arxiv.org/abs/astro-ph/9805201), Fig. 4 (MLCS) and Fig. 5 (Δm15). Perlmutter et al., ApJ 517, 565 (1999), [astro-ph/9812133](https://arxiv.org/abs/astro-ph/9812133).
- **Shows**: Distance modulus m−M vs redshift for 27 nearby + high-z SNe Ia. High-z SNe are fainter than in an Ω_M = 0.2, Ω_Λ = 0 universe.
- **Plot type, from the caption**: upper panel m−M (34–44 mag) vs z on a **log x axis (0.01–1)**, with three cosmology curves overplotted: Ω_M = 0.24/Ω_Λ = 0.76 (best flat), 0.20/0, and 1.00/0. The **bottom panel Δ(m−M)** (±0.5 mag) shows data minus the Ω_M = 0.20, Ω_Λ = 0 model. The open symbol is SN 1997ck. Average offset 0.25 mag (MLCS) and 0.28 mag (Δm15).
- **Uncertainty**: vertical error bars on μ.
- **Data**: **public**. Supernova Cosmology Project Union2.1 (580 SNe), [supernova.lbl.gov/union](https://supernova.lbl.gov/Union/), file `SCPUnion2.1_mu_vs_z.txt` (name, z, μ, σ_μ, P(low-mass host)), plus a 580×580 covariance. Riess 1998's own distances are in its Tables 5, 6, 10 (could be transcribed). Model curves come from Riess eq. (2)–(3).
- **plotipus requirement**: errorbar points + several analytic model curves + `--lower subtract` relative to a *chosen* model series (not the data fit), `--logx`, and a per-point marker override (open marker for one flagged row: `--markerby` on a flag column).

### F10 Ω_M–Ω_Λ confidence contours

- **Sources**: Riess 1998 Fig. 6 (MLCS) and Fig. 7 (template). Read from the paper: x Ω_M 0–2.5, y Ω_Λ −1–3, contours labelled 68.3%, 95.4%, 99.7%. Regions are labelled "No Big Bang", "Expands to Infinity / Recollapses", "Open/Closed", "Accelerating/Decelerating", with lines Ω_tot = 1, Ω_Λ = 0, q0 = 0, ±0.5. Perlmutter 1999 Fig. 7 "Confidence Region on Omega_Mass vs. Omega_Lambda Plane" (per the [SCP figure page](https://www.supernova.lbl.gov/slides.html)). The modern CMB+BAO+SN version is in Planck 2018 VI; its figure number was not checked.
- **Plot type**: filled (or line) 2D confidence contours from a likelihood grid + straight reference lines + text labels inside regions + a shaded excluded ("No Big Bang") region.
- **Data**: build a chi² grid over (Ω_M, Ω_Λ) from Union2.1 (F09), marginalising H0 analytically. Contour levels for 2 d.o.f. are Δχ² = 2.30, 6.18, 11.83. Optional synthetic CMB ellipse (narrow along Ω_M + Ω_Λ = 1) and BAO band to show orthogonality.
- **plotipus requirement**: `map -z chi2 --contour --contour_sigmas 1 2 3 --fill_contours` (already present) + **arbitrary straight lines** (`--line` exists; slope lines needed), **text labels at data coords** (`--note` exists, so check positioning), and a **hatched/shaded polygon region** (**NEW**). Overlaying several datasets' contours (SN, CMB, BAO) in distinct colours via `--hue`.

### F11 Rubin, Ford & Thonnard 1980 flat rotation curves

- **Source**: V. C. Rubin, W. K. Ford Jr., N. Thonnard, "Rotational properties of 21 Sc galaxies with a large range of luminosities and radii, from NGC 4605 (R = 4 kpc) to UGC 2885 (R = 122 kpc)", ApJ 238, 471 (1980), [ADS PDF](https://articles.adsabs.harvard.edu/pdf/1980ApJ...238..471R).
- **Shows**: Rotation velocity vs radius for 21 Sc galaxies. Velocity rises fast to about 125 km/s by about 5 kpc, then stays flat or rises slowly. None fall in Keplerian fashion. H0 = 50 assumed.
- **Plot type**: many curves (one per galaxy) of V(R) on linear axes. Whether the paper's best-known figure is a superposition of all 21 or a grid of small panels is **(unverified)**; I did not view the figures.
- **Data**: **needs realistic synthetic data** (or digitising the ADS scan). Synthesise V(R) = V_flat·(1 − exp(−R/R_t)) + slope·R, with V_flat from 150–300 km/s scaled with luminosity, R_t ≈ 1–3 kpc, and R_max from 4 to 122 kpc. Add ±10 km/s scatter. Add a dotted Keplerian ∝ R^(−1/2) comparison curve.
- **plotipus requirement**: `line --hue Galaxy` with many series (palette cycling for 21 series) or **small multiples** (`--variables`-style grid), optional `--plot_type errorbar`, and an analytic overlay.

### F12 NGC 3198 dark-halo decomposition

- **Source**: T. S. van Albada, J. N. Bahcall, K. Begeman, R. Sancisi, "Distribution of dark matter in the spiral galaxy NGC 3198", ApJ 295, 305 (1985). The citation was confirmed only through citing papers (e.g. [astro-ph/9609068](https://arxiv.org/pdf/astro-ph/9609068)); I did not see the ADS record.
- **Shows**: HI rotation curve to 11 disk scale lengths (about 30 kpc), fitted with an exponential disk (maximum disk M/L_B = 3.6) + spherical isothermal halo. Dark/visible ≥ 4 inside 30 kpc (secondary-source abstract text).
- **Plot type**: data points with error bars + component curves (disk, halo, total; gas in later versions) on linear axes. The exact line styles in the 1985 figure are **(unverified)**.
- **Data**: synthetic. Exponential-disk curve via Freeman's Bessel formula, `V_d²(R) = 4πGΣ0 h y²[I0K0 − I1K1](y)`, y = R/2h, with h = 2.68 kpc (secondary source). Pseudo-isothermal halo V_h² = 4πGρ0 rc²[1 − (rc/R)·atan(R/rc)]. Total = quadrature sum. Data = total + noise, flat at about 150 km/s.
- **plotipus requirement**: errorbar data + multiple named model components with distinct styles (`--style Component`), with the **total = quadrature sum** computed upstream. Optional `--lower residual`.

### F13 Keeling curve (Mauna Loa CO2)

- **Source/data**: NOAA GML, [Trends in Atmospheric CO2](https://gml.noaa.gov/ccgg/trends/data.html), file [co2_mm_mlo.csv](https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.csv). Columns verified: `year,month,decimal date,average,deseasonalized,ndays,sdev,unc`. The first row is 1958-03 (315.71 ppm); the latest is 2026-09 (426.07 ppm). Missing months are interpolated, flagged by negative ndays/sdev (−1/−9.99/−0.99).
- **Shows**: Monthly mean CO2 (ppm) since 1958, with a seasonal sawtooth on a rising trend.
- **Plot type**: time-series line (red monthly) + smooth deseasonalised line (black). Often shown with an **inset of the annual cycle** (mean anomaly by month).
- **Uncertainty**: `unc` column (monthly mean uncertainty), plottable as a thin band. Negligible visually.
- **plotipus requirement**: `line -x "decimal date" -y average` + second series `deseasonalized` (melt to long form with `--hue`), filtering of flagged rows (`--remove_value -0.99`), and an inset of the per-month climatology (`--binned --estimator mean` over month), so **inset axes** (**NEW**, as in F02).

### F14 "Hockey stick" (Mann, Bradley & Hughes 1999)

- **Source**: M. E. Mann, R. S. Bradley, M. K. Hughes, "Northern Hemisphere temperatures during the past millennium: inferences, uncertainties, and limitations", GRL 26(6), 759–762 (1999), AGU id 1999GL900070 ([author PDF](https://michaelmann.net/sites/default/files/articles/MBH_GRL99.pdf)). DOI 10.1029/1999GL900070 is inferred from the AGU id **(unverified)**.
- **Shows**: Reconstructed NH temperature anomaly, AD 1000–1980, with the instrumental record to 1998. Cool slow decline, then a sharp 20th-century rise. The 1990s are the warmest decade.
- **Plot type**: annual reconstruction line + **uncertainty band (2σ, shaded)** + smoothed (e.g. 40-yr low-pass) curve + instrumental series in a different colour + zero line. Exact smoothing window and band level in the original figure are **(unverified)**.
- **Data**: **public**. NOAA/WDS Paleoclimatology study 6276, [doi:10.25921/r8ry-v538](https://doi.org/10.25921/r8ry-v538): "Reconstruction (AD 1000-1980) and associated error bars; instrumental series (1902-1998)". There is also a Penn State [mirror](https://www.meteo.psu.edu/holocene/public_html/shared/research/old/mbh99.html).
- **plotipus requirement**: `line` with an `--error_band`-style filled band from a stored σ column, an extra smoothed series (rolling mean computed upstream or a **`--smooth N` option, NEW**), `--horizontal 0`, and a second dataset (instrumental) as another `--hue`.

### F15 LIGO GW150914 strain

- **Source**: LIGO/Virgo, "Observation of Gravitational Waves from a Binary Black Hole Merger", PRL 116, 061102 (2016), [doi:10.1103/PhysRevLett.116.061102](https://doi.org/10.1103/PhysRevLett.116.061102), [arXiv:1602.03837](https://arxiv.org/abs/1602.03837), Fig. 1.
- **Shows**: Two columns (H1 left, L1 right), four rows sharing time (s after 09:50:45 UTC). Row 1: whitened/band-passed strain (35–350 Hz) ×10⁻²¹. The L1 panel also shows H1 shifted by 6.9 ms and inverted. Row 2: numerical-relativity waveform (solid) with **90% credible regions from two reconstructions (dark grey: BBH templates, light grey: sine-Gaussian wavelets)**. Row 3: residuals (data − NR). Row 4: **time–frequency map** (normalised amplitude, 32–512 Hz, log-frequency) showing the chirp.
- **Encodings**: H1 orange/red, L1 blue (colours from the common rendering; not stated in the caption, so **unverified**).
- **Data**: **public**. LIGO DCC [G1600204](https://dcc-backup.ligo.org/LIGO-G1600204-v6/public) "P150914 Figure 1" zip of ASCII files (`fig1-observed-H.txt`, `fig1-observed-L.txt`, NR waveform, residual, shifted-inverted, template/wavelet reconstructions; all already filtered). Raw strain: [GWOSC GW150914](https://gwosc.org/events/GW150914/), DOI 10.7935/K5MW2F23.
- **plotipus requirement**: a **grid of panels (rows × columns) with shared x** (**NEW** unless `--variables` supports 2D grids), lines + **two-level grey bands** + residual row, and the bottom row as `map` (spectrogram image, `--logz`/`--norm`) with a log-y frequency axis. Overlaying a time-shifted series is a preprocessing step.

### F16 KamLAND L0/E oscillation

- **Source**: KamLAND Collaboration (S. Abe et al.), "Precision Measurement of Neutrino Oscillation Parameters with KamLAND", PRL 100, 221803 (2008), [doi:10.1103/PhysRevLett.100.221803](https://doi.org/10.1103/PhysRevLett.100.221803), [arXiv:0801.4589](https://arxiv.org/abs/0801.4589), Fig. 3.
- **Shows, from the caption**: ratio of the background- and geo-ν-subtracted ν̄e spectrum to the no-oscillation expectation vs L0/E (km/MeV), L0 = 180 km flux-weighted. "Almost two cycles" of oscillation.
- **Plot type**: data points ("Data − BG − Geo") with **statistical-only error bars** in **equal-probability (variable-width) bins**, + histogram and curve "Expectation based on osci. parameters determined by KamLAND". x 20–100 km/MeV, y "Survival Probability" 0–1.
- **Data**: synthetic. P = 1 − sin²2θ·sin²(1.267 Δm² L/E) with Δm² = 7.58×10⁻⁵ eV², tan²θ = 0.56, so sin²2θ ≈ 0.92 (abstract values). Smear by the reactor distance distribution (L ∈ ~130–220 km, weighted) so the expectation is damped. About 1600 events total: draw E from the reactor spectrum × P, bin in L0/E with equal-content bins, and errors = sqrt(N)/N_exp.
- **plotipus requirement**: errorbar with **variable-width bins (x error bars as bin half-widths)** + model step histogram + smooth curve overlaid. `--rangey 0 1`.

### F17 LEP Z lineshape and the number of neutrinos

- **Source**: ALEPH, DELPHI, L3, OPAL, SLD, LEP EWWG, SLD groups, "Precision Electroweak Measurements on the Z Resonance", Phys. Rept. 427 (2006) 257, [hep-ex/0509008](https://arxiv.org/abs/hep-ex/0509008). Fig. 1.13 (N_ν = 2, 3, 4 curves); also Fig. 1.12 (σ_had and A_FB^μ vs √s) and Fig. 1.2 (hadronic σ, 10–220 GeV, log y, accelerator ranges).
- **Shows**: σ_had [nb] vs E_cm 86–94 GeV, average measurements of the four experiments, with **error bars increased by a factor 10** (caption), and predicted curves for 2ν, 3ν, 4ν.
- **Results to annotate**: m_Z = 91.1875 ± 0.0021 GeV, Γ_Z = 2.4952 ± 0.0023 GeV, N_ν = 2.9840 ± 0.0082, σ0_had (SM fit) ≈ 41.48 nb.
- **Data**: synthetic, physics-exact. Use a relativistic Breit–Wigner σ(s) = σ0·sΓ_Z²/((s−m_Z²)² + s²Γ_Z²/m_Z²) (paper eq. 1.40), with σ0 = 12π/m_Z²·Γ_ee Γ_had/Γ_Z². For N_ν variants, change Γ_Z by ±Γ_νν ≈ 167 MeV (Γ_inv/N_ν with Γ_inv ≈ 499 MeV) **(the Γ_νν value is inferred, unverified)**. Apply ISR as a convolution or a peak reduction to about 30 nb (the measured peak in Fig. 2.3 is about 30.4 nb). Take about 7 energy points near the peak, peak±1, peak±2 GeV, with relative errors ~0.1% scaled ×10 for display.
- **plotipus requirement**: errorbar points with an **error-scale factor and legend note** (as in F06) + three model curves with labels placed on the curves (**NEW**: inline curve labels) + optionally `--lower pull` against the 3ν model.

### F18 The R ratio

- **Source**: Particle Data Group, Review of Particle Physics, "Plots of Cross Sections and Related Quantities" ([2022 PDF](https://pdg.lbl.gov/2022/reviews/rpp2022-rev-cross-section-plots.pdf)). R = σ(e+e−→hadrons)/σ(e+e−→μ+μ−), corrected for ISR and vertex loops. Errors are total below 2 GeV and statistical above (2020 edition).
- **Shows**: R vs √s from 0.3 to about 200 GeV on **log-log axes**: ρ/ω/φ, J/ψ, ψ(2S), Υ resonances, continuum steps at the charm and bottom thresholds, the Z peak, and naive-quark-model (dashed) and 3-loop pQCD (solid) curves. Sub-plots zoom on the charm and beauty threshold regions.
- **Data**: **public**. PDG computer-readable R-ratio files (COMPAS group, IHEP Protvino), e.g. [2012 page](https://pdg.lbl.gov/2012/hadronic-xsections/hadron.html). The current-edition URL is **(unverified)**. Each row has √s, R, stat and syst errors.
- **plotipus requirement**: `scatter`/errorbar with `--logx --logy`, **thousands of points coloured by experiment** (`--hue Experiment`, many categories), model curves, **text labels at resonance positions** (rotated annotations), and zoom panels (**NEW**: inset or multi-panel with different x ranges).

### F19 Geiger–Marsden α-scattering (Rutherford formula)

- **Source**: H. Geiger and E. Marsden, "The Laws of Deflexion of α Particles through Large Angles", Phil. Mag. Ser. 6, 25, 604 (1913) (scan: [Saarland PDF](https://grundpraktikum.physik.uni-saarland.de/gpalt/Anleitungen/Ergaenzungen/J1_Papers/Rutherford%20-%20Geiger_Marsden.pdf)). Tests Rutherford 1911.
- **Shows**: number of scintillations N vs deflection angle φ (about 5°–150°) for gold and silver foils. N·sin⁴(φ/2) ≈ constant.
- **Plot type**: the 1913 paper reports mostly **tables**. The iconic figure is the modern log-y plot of counts vs angle with the 1/sin⁴(φ/2) curve **(no original figure confirmed)**.
- **Data**: needs transcription from the scan. The scan is image-only, and I could not extract the table, so the **counts are unverified**. Synthetic alternative: N(φ) = A/sin⁴(φ/2) with A chosen so N(150°) ≈ 30 and N(15°) ≈ 1.4×10⁵, Poisson noise, 12 angles. Gold and silver with different A.
- **plotipus requirement**: `line --plot_type errorbar --logy` + analytic curve via `--fit` with a user-defined function (**NEW** if `--fit` only does polynomials/gaussians) + a `--lower ratio` of data/model. A `table` of N·sin⁴(φ/2) per angle also fits the `table` kind.

### F20 Moseley's law

- **Source**: H. G. J. Moseley, "The High-Frequency Spectra of the Elements", Phil. Mag. 26, 1024 (1913), doi:10.1080/14786441308635052 (per [Wikipedia](https://en.wikipedia.org/wiki/Moseley%27s_law)). A bookseller listing gives pp. 854–860 for no. 156, and the volume is split across two papers (1913, 1914). **Page range conflict unresolved (unverified)**.
- **Shows**: √ν (or √(ν/ν0)) vs atomic number Z: straight lines for the Kα and Kβ (and La, Lβ) series. Gaps predicted missing elements (Z = 43, 61, 75).
- **Plot type**: points + straight-line fits, often with Z on the y-axis and √ν on x (Moseley's own orientation is **unverified**).
- **Data**: **public via modern values**: NIST X-ray transition energies database (Kα1 energies E → ν = E/h). Synthetic version: √ν = a(Z − 1) for Kα, with a = sqrt(3/4·R_∞c) ≈ 4.96×10⁷ Hz^½, and an L-series with screening ≈ 7.4.
- **plotipus requirement**: `scatter --hue Series` + `--fit pol1` per series with fit-parameter legend, highlighted gaps via `--vertical` lines at missing Z.

### F21 Leavitt's period–luminosity relation

- **Source**: H. S. Leavitt & E. C. Pickering, "Periods of 25 Variable Stars in the Small Magellanic Cloud", Harvard College Observatory Circular 173, 1–3 (1912), ADS bibcode 1912HarCi.173....1L.
- **Shows**: apparent magnitude vs period for 25 SMC Cepheids. Two graphs: magnitude vs period (1 to about 127 days), and magnitude vs **log period**, which is linear. Each has two sequences (maximum and minimum brightness) with fitted straight lines (per secondary descriptions; **line details unverified**).
- **Plot type**: scatter with **inverted y (magnitudes)**, log-x or log10(P) on a linear x, two series + linear fits.
- **Data**: **public** (25-row table in the circular). Needs transcription from the ADS scan **(not done; values unverified)**. Synthetic fallback: m_max = −2.1·log P + 15.5 ± 0.2, with m_min about 1.2 mag fainter **(slope illustrative, unverified)**.
- **plotipus requirement**: `scatter` + `--fit pol1` per series + **inverted y-axis** (`--rangey 17 11`; check that plotipus allows reversed ranges, else **NEW** `--invert_y`) + `--logx`.

### F22 Hertzsprung–Russell diagram (Russell 1914; Gaia DR2)

- **Sources**: H. N. Russell, "Relations between the spectra and other characteristics of the stars", Nature 93, 252–258 (1914), [doi:10.1038/093252a0](https://doi.org/10.1038/093252a0) (also Popular Astronomy 22, 275). Gaia Collaboration, Babusiaux et al., "Gaia Data Release 2. Observational Hertzsprung-Russell diagrams", A&A 616, A10 (2018), doi:10.1051/0004-6361/201832843, [arXiv:1804.09378](https://arxiv.org/abs/1804.09378).
- **Shows**: absolute magnitude vs colour (BP−RP) or spectral type: main sequence, giant branch, red clump, white-dwarf sequence.
- **Plot type**: Russell's version is a scatter of individual stars with the y-axis inverted. The Gaia version is a **2D density map (log colour scale)** of millions of stars, M_G inverted.
- **Data**: **public**. Gaia archive TAP/ADQL ([examples](https://gea.esac.esa.int/tap-server/tap/examples)). Template (from the DR2 HRD paper's style of cuts):
  ```
  SELECT phot_g_mean_mag + 5*LOG10(parallax) - 10 AS mg, bp_rp
  FROM gaiadr2.gaia_source
  WHERE parallax_over_error > 10 AND phot_bp_mean_flux_over_error > 10
    AND phot_rp_mean_flux_over_error > 10 AND bp_rp IS NOT NULL
  ```
  An ESA tutorial variant with parallax > 10 mas returns about 339k sources. The full DR2 paper uses extra excess-factor and astrometric cuts.
- **plotipus requirement**: `map` 2D histogram of point arrays with `--logz` (or `--norm log`), **inverted y**, `--square` off, fine bins (~0.01 mag colour, 0.05 mag M_G), and a perceptual colormap. A scatter fallback for the Russell 1914 look.

### F23 Nightingale's rose (coxcomb)

- **Source**: F. Nightingale, *Notes on Matters Affecting the Health, Efficiency, and Hospital Administration of the British Army* (1858). The "Diagram of the Causes of Mortality in the Army in the East" faces p. 311 (per [Eye Magazine](https://www.eyemagazine.com/feature/article/lady-with-the-diagram) and [Quaritch](https://www.quaritch.com/books/nightingale-florence/notes-on-matters-affecting-the-health-efficiency-a/G2644/)).
- **Shows**: monthly army mortality, April 1854 – March 1856, in **two linked polar charts** (two 12-month periods). Each month is a 30° wedge, and **wedge area (not radius) ∝ deaths**. Blue = preventable zymotic disease, red = wounds, black = other causes.
- **Data**: **public**. R `HistData::Nightingale` ([docs](https://search.r-project.org/CRAN/refmans/HistData/html/Nightingale.html)): monthly counts by cause and army size. Annual rate per 1000 = 12·1000·D/Army. Source is Pearson & Short (2007). Variable names **(unverified, help page not opened)**.
- **plotipus requirement**: **polar area chart with overlapping (not stacked) wedges, radius = sqrt(value)** (**NEW**: `cat --kind polar` or `--projection polar`). Fallback: `cat --kind bar` stacked monthly bars with the same colours, or `line --stacked`.

### F24 Minard's map of Napoleon's Russian campaign

- **Source**: C. J. Minard, *Carte figurative des pertes successives en hommes de l'Armée Française dans la campagne de Russie 1812–1813* (1869). Data from Friendly (2002) via Wilkinson's *Grammar of Graphics*.
- **Shows**: army size as **band width** along the route (tan advance, black retreat), with city labels, and **a temperature-on-the-retreat line chart aligned below** on the same longitude axis.
- **Data**: **public**. R `HistData` ([Minard docs](https://search.r-project.org/CRAN/refmans/HistData/html/Minard.html)): `Minard.troops` (51 rows: long, lat, survivors, direction A/R, group), `Minard.cities` (20 rows: long, lat, city), `Minard.temp` (9 rows: long, temp, days, date; the docs note the date year is stored as 1815, though the campaign is 1812).
- **plotipus requirement**: **variable-width line segments** (linewidth ∝ survivors, colour by direction; **NEW**: `line --widthby` or `scatter` with connected segments) + text labels from a second dataframe + a lower panel on the shared x (longitude) from a third dataframe (**NEW**: `--lower` sourced from a different datafile).

### F25 Anscombe's quartet and the Datasaurus Dozen

- **Sources**: F. J. Anscombe, "Graphs in Statistical Analysis", *The American Statistician* 27(1), 17–21 (1973), [doi:10.1080/00031305.1973.10478966](https://doi.org/10.1080/00031305.1973.10478966). J. Matejka & G. Fitzmaurice, "Same Stats, Different Graphs", CHI 2017 ([Autodesk Research](https://www.research.autodesk.com/publications/same-stats-different-graphs/)). The original Datasaurus is by Alberto Cairo.
- **Shows**: 4 (Anscombe, 11 points each) or 13 (Datasaurus) datasets with near-identical mean, variance, correlation and regression line, but wildly different scatterplots.
- **Plot type**: **small-multiple scatter grid** (2×2 or 4×4 minus 3), the same fitted line in each panel, shared axes, and summary-statistic text per panel.
- **Data**: **public**. R base `datasets::anscombe` (columns x1–x4, y1–y4), CRAN `datasauRus::datasaurus_dozen` (dataset, x, y; [README](https://cran.r-project.org/web/packages/datasauRus/readme/README.html)), and the CSV on the Autodesk page.
- **plotipus requirement**: `scatter --variables` (one panel per dataset) with **wrapping into a grid** + `--fit pol1` per panel + per-panel stats note. A companion `table --agg mean std` + correlation reproduces the "same stats" table (`table` kind, needs a correlation aggregator: **NEW** `--agg corr`).

---

### Cross-cutting feature gaps (for planning)

These recur across the figures, ordered by how many figures need them:

1. **Inset axes** (F02, F03, F13, F18).
2. **Nested ±1σ/±2σ bands with fixed colours** around a curve (F02, F04, F05, F14, F15); partly available via `--error_band`.
3. **Panel grids / wrap** beyond one row (F15, F25, F11).
4. **Error-bar magnification with legend note** (F06, F17).
5. **Labelled horizontal reference lines** (σ lines, CL lines) (F04, F05).
6. **Inverted axes** (F21, F22) and **hybrid log/linear or broken axes** (F07, F05).
7. **Variable-width bins as x-errors** (F16) and **Garwood Poisson intervals** (F03).
8. **User-defined analytic fit functions** (F06, F08 through origin, F17, F19).
9. Non-Cartesian/flow encodings: **polar area** (F23), **variable line width** (F24), **shaded polygon regions** (F10).

### Unverified items (consolidated)

- HEPData records for arXiv:1207.7214 / 1207.7235 (hepdata.net unreachable from here).
- ATLAS Fig. 7(a) broken x-axis (inferred from tick labels).
- COBE FIRAS: the "±400σ" error bars in the original Mather et al. figure (seen only in review astro-ph/9705101); the exact Mather 1994 deviation limit; column order of `firas_monopole_spec_v1.txt`.
- Column layout of Planck `COM_PowerSpect_CMB-TT-full_R3.01.txt`.
- Hubble 1929: group membership for the 9-group solution.
- Rubin et al. 1980 figure layout; van Albada et al. 1985 figure styles (and ADS record not viewed directly).
- MBH99 article DOI 10.1029/1999GL900070; smoothing window and band level in the original figure.
- GW150914 detector colours.
- Γ_νν ≈ 167 MeV used for the N_ν curves (derived, not read).
- Current-edition URL of PDG R-ratio data files.
- Geiger–Marsden count table values; whether any 1913 figure exists.
- Moseley page range (1024–1034 vs 854–860) and plot orientation.
- Leavitt table values and fitted-line details; synthetic slope.
- HistData::Nightingale variable names.
- Planck 2018 Ω_m–Ω_Λ figure number (not cited).
