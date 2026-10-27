# plotipus style language

Phase 4: a visual identity of our own. The principles come first, each
justified by a complaint theme from [research.md](research.md) (Part 2).
Concrete values follow, then the three prototyped candidates and what
remains for code rather than style files.

## 0. Decisions that shape this spec (2026-10-24)

> The [style guide](../styleguide.md) (2026-10-27) is the enforceable
> summary and wins where the two differ: side-by-side panels keep the
> proportions of a single plot (the figure widens, rule L3), and a lower
> panel takes its height from the plot in every medium (L2).

The maintainer chose the `paper` visual language, with **slides as the
default medium** (decision D1 in [roadmap.md](roadmap.md)). A style is
therefore the combination of three choices:

| axis | values | default |
|---|---|---|
| language | `plotipus` (the `paper` candidate: ticks in, mirrored, no grid), `open` (web), `classic` (the pre-redesign look, pinned for compatibility) | `plotipus` |
| medium | `slides`, `paper`, `web` | `slides` |
| theme | `light`, `dark` | `light` |

Plus optional layers: an experiment preset (ATLAS, CMS, LHCb, ALICE, DUNE,
…) and a watermark/status label.

The user-facing names are combinations of these:

| name | language | medium | theme |
|---|---|---|---|
| `slides` | plotipus | slides | light |
| `slides-dark` | plotipus | slides | dark |
| `paper` | plotipus | paper | light |
| `open` | open | web | light |
| `open-dark` | open | web | dark |
| `classic` | — | — | — |

One command list renders to any medium: `plotipus run analysis` writes
slides, and `plotipus run analysis --medium paper` writes the publication
versions next to them.

The prototypes in §3 predate this decision. Their `slides` overlay sits on
`open`; the shipped `slides` style uses the plotipus language with
sans-serif type for projection.

## 1. Principles

1. **Draw at the printed size.** A figure is defined by its target width and
   a base font size in points, and is never rescaled in LaTeX.
   - Why: figure size and font size are the two largest complaint clusters
     (Part 2 §1–2).
   - Today: the current 8×6 in canvas with `xx-large` (19.8 pt) labels is
     shrunk 2.35× into a 3.4 in column, so its tick labels (`large`,
     13.2 pt) print at about 5.6 pt.
2. **Text in a figure matches the text of the paper.** Body, tick labels and
   math use one family, and no TeX installation is needed for it.
   - Why: the matplotlib 2.0 mathtext change and the `usetex` breakage
     questions (Part 2 §2).
3. **A colour belongs to a category, never to a draw position.**
   - The same hue value keeps its colour across panels, lower panels and
     files.
   - The cycle never wraps silently: past its end, a second channel (line
     style, marker) is added and a warning is printed.
   - Why: Part 2 §6; bugs B01, B02.
4. **Accessible by default.**
   - CVD-tested categorical colours.
   - Sequential maps monotonic in lightness.
   - Redundant coding when a figure must survive greyscale printing.
   - Why: Part 2 §7, §9.
5. **Low ink, but data never floats.**
   - No titles inside paper figures (the caption is the title).
   - No legend frames and no stats boxes.
   - A grid only where it helps read values.
   - Why: Part 2 §8, Wilke's "within reason".
6. **Legends never cover data.** They go in measured empty space, outside
   with reserved room, or are replaced by direct labels. Why: Part 2 §3;
   bug B06.
7. **Every uncertainty says what it is.** One default interval per data kind,
   shown the same way everywhere and named in the legend. Why: Part 2 §10;
   Part 1 §3 (no engine labels its intervals).
8. **One scale, one colorbar.** Panels that share a quantity share the norm
   and the colorbar, and every colorbar has a label with units. Why: Part 2
   §5; bug B08.
9. **Lower panels are part of the plot.**
   - They share x with no gap.
   - They have a reference line, a symmetric range and few ticks.
   - Their colours match the upper panel.
   - Why: Part 2 §1 (ratio panels).
10. **Media and themes are overlays.** Slides, paper, web, dark, experiment
    presets and journal presets change sizes, type and colours only. The
    visual language and the colour of each category stay the same, so a
    slide and its published figure read as the same plot.

## 2. Concrete rules

### 2.1 Sizes: tied to journal column widths

Widths are confirmed from the publishers' pages:
- APS: 8.6 cm single column, 17.2 cm double column, capital letters at
  least 2 mm high ([Physical Review Word
  template](https://res.cloudinary.com/apsphysics/raw/upload/v1722521536/PhysRev-template_zysvy0.docx)).
- Nature: 89 mm single column, 183 mm double column, 120/136 mm for 1.5
  columns, all text between 5 and 7 pt ([Nature figure
  guide](https://research-figure-guide.nature.com/figures/building-and-exporting-figure-panels/)).
- Elsevier: 90 mm single column, 140 mm for 1.5 columns, 190 mm full width,
  about 7 pt text ([Elsevier artwork
  sizing](https://www.elsevier.com/authors/policies-and-guidelines/artwork-and-media-instructions/artwork-sizing)).

| preset (`--width`) | width | height (default aspect 0.75) | base font | use |
|---|---|---|---|---|
| `single` (default for `--medium paper`) | 3.4 in (8.6 cm) | 2.55 in | 8 pt | APS/Elsevier column |
| `onehalf` | 5.3 in (13.5 cm) | 3.6 in | 8 pt | 1.5 column |
| `double` | 6.8 in (17.2 cm) | 3.0 in per row | 8 pt | full width; 2–3 panels |
| `nature` | 3.5 in (89 mm) | 2.6 in | 7 pt | Nature-family limits |
| `slide` (default; `--medium slides`) | 8 in (1280 px wide) | 5.84 in (aspect 0.73 on slides) | 14 pt | talks; `half-slide` is 4 in wide, for two plots side by side |

- **Panels.** A row of N panels keeps the preset's total width, so the
  panels get narrower, and the row gets shorter: about square panels, at
  least 3.2 in tall, never taller than one plot (`facet_rows`; decided
  2026-10-27, after the example review). Text is never scaled to
  compensate; this replaces `panel_font_scale`.
- **Ratio panels.** On paper, adding a lower panel adds 30% of the upper
  height instead of squeezing the upper panel. On slides (8 in at aspect
  0.73), the lower panel shares the figure's height, so every single plot
  has one size (`lower_panels: share`; decided 2026-10-27).
- **Output.**
  - PDF (vector) for papers.
  - PNG at `savefig.dpi: 300`, or 600 for line art in APS journals.
  - `savefig.pad_inches: 0.02`. Never `bbox_inches="tight"`: it changes the
    printed size.

### 2.2 Typography

| element | size (rel. to 8 pt base) | notes |
|---|---|---|
| axis labels | `large` (9.6 pt) | sentence case, unit in parentheses: "Energy (MeV)"; ROOT/HEP brackets `[MeV]` accepted |
| tick labels, legend, colorbar ticks | `medium` (8 pt) | APS: 8 pt gives about 2 mm capitals |
| legend title, panel titles | `medium`, regular weight | panel titles only for facets |
| figure title | none in `paper`; `large` when `--title` is explicit | `auto_title: false` |
| notes, line labels | `small` (6.9 pt) | never below 6 pt (Elsevier) |

- **paper family.** Text and math in Computer Modern: `font.serif: cmr10`
  with `mathtext.fontset: cm` and `axes.formatter.use_mathtext: True`, so
  minus signs and exponents come from the same font. All three are bundled
  with matplotlib, so no TeX is needed.
  - Journals typeset in Times (Elsevier, some APS) use the STIX variant:
    `font.serif: STIXGeneral` with `mathtext.fontset: stix`.
  - `text.usetex` stays an opt-in.
- **sans family.** The ATLAS/CMS look uses TeX Gyre Heros or Nimbus Sans
  with `mathtext.fontset: custom` mapped to the same face (mplhep's
  approach, Part 1 §2.9). Otherwise use DejaVu Sans with
  `mathtext.fontset: dejavusans`.
- **Numbers.**
  - Labels are `ScalarFormatter(useMathText=True)`, with
    `axes.formatter.limits: -3, 5`. 12 000 prints as 12000, and 0.04 as 0.04.
  - Log axes use decade labels 10ⁿ with unlabelled minor ticks.
  - A common power of ten goes in the axis label ("Density (10⁻²)"), never as
    floating offset text.
  - Never `4e-2` (B05).

### 2.3 Colour

- **Categorical cycle: Petroff-10**, in published order:
  `#3f90da #ffa90e #bd1f01 #94a4a2 #832db6 #a96b59 #e76300 #b9ac70 #717581 #92dadd`.
  - It is CVD-tested, has a lightness spread chosen for greyscale, and its
    order is optimised (Part 1 §2.10).
  - It ships as matplotlib's `petroff10`, and the same palettes are ROOT
    6.34's `kP10*` and mplhep CMS's choice, which suits a physics-first
    tool.
  - For 6 or fewer series, use Petroff-6 (`#5790fc #f89c20 #e42536 #964a8b
    #9c9ca1 #7a21dd`). It has stronger contrast.
  - For 11 or more series: colours repeat, with a printed warning. Line
    styles are not added automatically; they are reserved for `--style` and
    mapped configs (maintainer's decision, T01). If the hue is numeric or ordered (runs, energies), use a
    sequential colormap with a colorbar instead (`--hue_cmap`).
  - Named alternatives: `okabe-ito` (8, used by the "open" candidate) and
    `tol-bright` (7, used by the "hep" candidate).
- **Semantic roles**, new style.json keys that replace hard-coded colours
  (B14):

  | role | paper (light) | dark/slides | used for |
  |---|---|---|---|
  | `ink` | `#1a1a1a` | `#e8eaed` | text, data points, totals, the fit line, reference lines |
  | `muted` | `#7f7f7f` | `#8b9099` | guides (y = 1, Δχ² lines, diagonals), minor annotations |
  | `faint` | `#e6e6e6` | `#33363d` | grids, bands for "expected" |
  | `paper` | `#ffffff` | `#1b1d22` | backgrounds, the "lighter" end of graded fills |

  Data points ("data" in data/MC plots) are always `ink` circles. The
  simulation takes palette colours.
- **Sequential maps.**
  - Default: `plotipus` (`src/plotipus/colormaps.py`): cream → teal → the
    palette's blue → dark ink blue, CIELAB L* linear from 96 to 16, a tint
    (not white) at the low end so empty bins stay visible; `plotipus_dark`
    (dark blue → cream) in the dark theme. `classic` keeps `viridis`.
  - `cividis` when the plot must be read under CVD with fine detail.
  - Counts: log norm when the range spans more than 2 decades. Empty bins
    are transparent (not the darkest colour, B08).
- **Diverging maps.**
  - Default: `RdBu_r` with a centred `TwoSlopeNorm`, only for signed
    quantities with a meaningful zero (pulls, differences, correlations).
  - On dark backgrounds, use matplotlib 3.10's `berlin` or `vanimo`.
- **Never** jet, rainbow or turbo for ordered data. Observable's turbo
  default is the counter-example (Part 1 §2.6).
- **Confidence regions (contours).** No colormap. Each dataset is one hue in
  graded fills: 68% at 100% hue, 95% at 55%, 99.7% at 25% mixed with
  `paper`. Outlines are solid, dashed and dotted, and the best fit of a Δχ²
  map is an `ink` point with its 1σ profile intervals as error bars (in the
  set's hue when several maps share a panel); significance maps keep a `+`
  (B03).
- **Brazil bands.** `brazil` preset: ±1σ `#4daf4a`-like green, ±2σ
  `#ffdd00`-like yellow (HEP convention). The default is `graded`, two
  lightness steps of `muted`, because green and yellow are close in
  lightness (Part 2 §9, flagged unverified).

### 2.4 Line styles, markers and hatches (for `--style`)

| index | line style | marker | hatch |
|---|---|---|---|
| 0 | `-` solid | `o` circle | none |
| 1 | `--` (dash 4,2) | `s` square | `////` |
| 2 | `:` (dot 1,1.5) | `^` triangle | `\\\\` |
| 3 | `-.` | `D` diamond | `xxx` |
| 4 | `(0,(5,1,1,1,1,1))` dash-dot-dot | `v` | `...` |
| 5 | `(0,(1,3))` loose dots | `P` plus | `---` |

- `--style` never changes colour, and `--hue` never changes line style.
- When `--hue` and `--style` are the same column, there is one legend whose
  entries carry both (B02).
- Hatches are drawn in the series colour at full opacity
  (`hatch.linewidth: 0.5`), over a fill at 15% alpha.

### 2.5 Axes: spines, ticks, grid, margins

The "paper" family (physics convention, Part 1 §3):
- Four spines at 0.6 pt.
- Ticks point in and are mirrored on all four sides, with minor ticks;
  major 3.5 pt, minor 1.8 pt.
- No grid.

The "open" family (data-science convention):
- Left and bottom spines only.
- Ticks out, no minor ticks.
- A y grid only, `#e6e6e6` at 0.6 pt, drawn behind the data.

Margins in both:
- `axes.xmargin: 0` for binned data (histograms and steps touch the frame).
- For points and lines the kind adds a 2% margin, so no marker is cut by
  the frame (examples 05).

### 2.6 Lines and markers

`lines.linewidth: 1.2` (paper, single column) or 1.4 (sans). Markers are
3.5 pt circles. Error bars have no caps (`errorbar.capsize: 0`), 0.8 pt wide,
in the series colour. Measured points with error bars are never joined by
lines unless `--connect` is given (B17).

### 2.7 Legends

- Frameless, font size `medium`, handle length 1.8, label spacing 0.3.
- Placement:
  1. The emptiest corner, measured on an occupancy mask that counts filled
     areas (B06).
  2. If none is free, add headroom above the data (`--legend_headroom`).
  3. With more than 6 entries, or when `--legend_loc outside` is given, put
     the legend above the axes in N columns, inside the reserved figure
     margin.
- Entry order follows the data:
  - Stacks: top of the stack first.
  - Lines: the order of their right-hand ends.
  - Data last for data/MC plots; the HEP convention puts it first, so this
    is configurable.
- No legend for a single unnamed series. No legend in lower panels when the
  colours repeat the upper panel's; the y label says what is shown.
- Legend titles only when the hue column name adds information (the
  existing `redundant_legend_titles`).

### 2.8 Uncertainty conventions

| data | default interval | drawn as | legend wording |
|---|---|---|---|
| unweighted counts | Garwood (exact Poisson) 68.3% | vertical bars, no caps; x bars only for variable-width bins | "Data" (interval named in the caption) |
| weighted counts / MC | √Σw² | hatched band on the stack total (`////`, ink 40%) | "MC stat. unc." |
| efficiencies | Clopper–Pearson 68.3% (shared code with the table kind) | bars or a band, clipped to [0, 1] | "68% CL (Clopper–Pearson)" |
| binned mean / median | standard error of the statistic (B04) | bars on markers | "mean ± s.e.m." |
| curve ± σ (theory, systematics) | stored | 20% alpha band of the series colour, line on top | from the stored label |
| expected limits | stored ±1σ/±2σ | nested bands (graded or brazil) | "Expected ±1σ", "±2σ" |
| 2D confidence regions | Δχ² for 2 dof by default: 2.30, 6.18, 11.83 | graded fills + solid/dashed/dotted outlines | "68.3%, 95.4%, 99.7% CL" |

### 2.9 Colorbars

- Same height as the axes, 4% of the axes width, padding 2%.
- Label on the right with units, in the axis-label size.
- Log norm: ticks at decades.
- Shared across panels that show the same quantity: one bar to the right of
  the row.
- Δχ² maps have no colorbar by default; the contours carry the
  information.

### 2.10 Lower panels

- Height ratio 3:1 (one lower panel) or 3:1:1 (two). `hspace: 0`, with the
  x tick labels of the upper panel hidden.
- Reference line (1 for a ratio, 0 for a difference or pull) in `muted`, 0.6
  pt, dashed.
- Y range symmetric around the reference, with 3–4 major ticks. The
  outermost tick label is dropped where it would collide with the panel
  above.
- Pull panels: ±1σ and ±2σ bands in `faint`.
- The y label is short ("Data / MC", "Pull") and set at the same size as
  the upper label. Labels are aligned (`fig.align_ylabels`).

### 2.11 Media and themes

- **slides** (the default medium):
  - 8×4.5 in, 14 pt base, line width 2.4, markers 7 pt.
  - Sans type (DejaVu Sans, or Nimbus Sans/Heros when present), with math in
    the same face.
  - The plotipus frame: ticks in, mirrored, no grid. Titles are allowed.
  - The cycle stays Petroff-10, in the same order, so a category keeps its
    colour between the light slide, the dark slide and the paper.
  - On a dark background, the darkest entries (#bd1f01, #832db6, #717581)
    are replaced by lightened twins of the same hue rather than reordered.
    Their contrast against `#1b1d22` must be at least 3:1, a check that T16
    automates.
- **dark**: the `paper`/`ink` roles swap. Background `#1b1d22`. The
  categorical cycle keeps its order, with the lightened twins described
  above. Diverging maps become `berlin`/`vanimo`. (Prototyped together with slides
  in [styles/slides/](styles/slides/).)
- **Journal presets** (`nature`, `aps`, `elsevier`) only set width, base
  font and family.

## 3. Prototype candidates

Three contrasting identities were prototyped as overlays. Each folder holds
`plotipus-<name>.mplstyle` (the rcParams) and `style.json` (plotipus
settings).

| candidate | idea | type | frame | cycle |
|---|---|---|---|---|
| [`paper`](styles/paper/) | the physics-paper look, matching a LaTeX article | Computer Modern, math in CM | boxed, ticks in on 4 sides, minor ticks, no grid | Petroff-10 |
| [`open`](styles/open/) | the modern data-science look (ggplot2 `theme_minimal`, Wilke) | DejaVu Sans | L-shaped, ticks out, light y grid | Okabe–Ito |
| [`hep`](styles/hep/) | the collider-experiment look (mplhep ATLAS/CMS) | Nimbus Sans / Heros, math in the same face | boxed, long ticks in, axis labels at the axis ends | Tol bright |
| [`slides`](styles/slides/) (overlay on `open`) | talks, dark background | — | — | Okabe–Ito, lightest colours first |

All three render the same 8 example commands at the same printed size
(single column, 8 pt). Reproduce with `python docs/design/styles/render.py`.
Comparison sheets (current look, then each candidate) are in
[styles/compare/](styles/compare/):

| example | sheet |
|---|---|
| hue + style spectra | [01](styles/compare/01_spectra_hue_style.png) |
| ratio panel | [02](styles/compare/02_ratio.png) |
| stacked + S/√B | [03](styles/compare/03_stacked_significance.png) |
| efficiency bands | [04](styles/compare/04_efficiency_bands.png) |
| binned mean | [05](styles/compare/05_binned_mean.png) |
| 2D histograms | [06](styles/compare/06_hist2d.png) |
| Δχ² contours | [07](styles/compare/07_contour.png) |
| category bars | [08](styles/compare/08_cat_bars.png) |

**What the renders show.**
- **Typography.** All three candidates fix the size problem: text is
  readable at column width, while the current look shrinks to ~5 pt.
- **`paper`.** Reads as part of a LaTeX document, and is the most
  restrained.
- **`open`.** The friendliest for reports and notebooks. Its grid helps
  read bar heights (08) and efficiency levels (04), and adds little on the
  log-scale spectra (01).
- **`hep`.** End-of-axis labels are familiar to collider physicists, and
  awkward on short axes such as the 2D panels.
- **Palettes.** All three keep the three samples distinct in every sheet.
  The differences between Petroff-10, Okabe–Ito and Tol bright only matter
  beyond 4–5 series, which these examples do not exercise. The 12-hue
  reproduction (bugs.md B02) is the one to judge them on once B02 is fixed.
- **Slides overlay.** Works, except where the code hard-codes black (the
  line-style legend in 01 is invisible on the dark background, B14).

**Recommendation.**
- Make `paper` the default.
- Ship `open` as the named alternative for data-science users.
- Keep the `hep` features as options rather than a third identity: a
  label-at-end switch and the header label.
- Reason: plotipus's users write LaTeX physics papers. `paper` is the only
  candidate whose text matches the paper's body font, and the physics
  convention (ticks in, mirrored, no grid) is what every physics style
  surveyed converges on (Part 1 §3).

### What the styles cannot fix

Several problems in the comparison sheets are the same in every candidate,
because they come from the code, not from rcParams:
- the repeated colour in 04 (B01);
- the contour bands in 07 (B03);
- the legend over the stacked bars in 03 and over the bars in 08 (B06, B07);
- the `4e-2` ticks in 05 (B05);
- the missing error bars in 05 (B04);
- the clipped y labels with long tick labels in 05 (B15);
- the per-panel colorbars in 06 (B08).

[roadmap.md](roadmap.md) orders the code work that has to come before or
with the style.

## 4. Proposed values for the default (`paper`)

The complete files are [styles/paper/plotipus-paper.mplstyle](styles/paper/plotipus-paper.mplstyle)
and [styles/paper/style.json](styles/paper/style.json). Key rcParams:

```
font.family: serif           font.serif: cmr10, Latin Modern Roman, DejaVu Serif
font.size: 8                 mathtext.fontset: cm      axes.formatter.use_mathtext: True
axes.labelsize: large        xtick/ytick.labelsize: medium   legend.fontsize: medium
axes.linewidth: 0.6          lines.linewidth: 1.2      lines.markersize: 3.5
xtick/ytick.direction: in    xtick.top / ytick.right: True   x/ytick.minor.visible: True
x/ytick.major.size: 3.5      x/ytick.minor.size: 1.8   errorbar.capsize: 0
axes.prop_cycle: petroff10   axes.formatter.limits: -3, 5    axes.grid: False
legend.frameon: False        image.cmap: plotipus      figure.figsize: 3.5, 2.6
savefig.dpi: 300             savefig.pad_inches: 0.02
```

style.json (plotipus settings):

```json
{
  "plot_settings": {
    "auto_title": false,
    "default_linewidth": 1.2,
    "figure_layout": {"base_width": 3.5, "panel_width": 3.2, "height": 2.7,
                      "margins_inches": {"left": 0.62, "right": 0.12, "bottom": 0.42, "top": 0.22}},
    "legend_style": {"fontsize": "medium", "title_fontsize": "medium", "frameon": false}
  },
  "font_sizes": {"xlabelfontsize": "large", "ylabelfontsize": "large", "legendfontsize": "medium", "...": "medium"}
}
```

Keys proposed for style.json, which need code (roadmap S-items):

```json
{
  "mplstyle": "plotipus-paper.mplstyle",
  "roles": {"ink": "#1a1a1a", "muted": "#7f7f7f", "faint": "#e6e6e6", "paper": "#ffffff"},
  "widths": {"single": 3.4, "onehalf": 5.3, "double": 6.8, "nature": 3.5, "slide": 8.0},
  "aspect": 0.75,
  "lower_panel": {"height_fraction": 0.3, "reference_style": "--"},
  "uncertainty": {"counts": "garwood", "efficiency": "clopper_pearson", "estimator": "sem"},
  "contours": {"dof": 2, "fill_mix": [1.0, 0.55, 0.25], "linestyles": ["-", "--", ":"]},
  "cycle_overflow": "linestyle"
}
```
