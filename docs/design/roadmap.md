# Implementation roadmap

An ordered list of the work that follows from [bugs.md](bugs.md),
[catalogue.md](catalogue.md) and [style_spec.md](style_spec.md). Nothing here
has been implemented; `src/` and `examples/` are unchanged.

**Effort** is for one person who knows the code base: S ≤ ½ day, M 1–2 days,
L 3–5 days.

**Risk** is the chance of breaking existing command lists or output file
names: low, med or high. High-risk items change defaults, so they are gated
behind the new style or announced in the changelog.

The order follows three rules:
1. Correctness bugs first.
2. The infrastructure that the style needs.
3. The new examples, built in step with the features they show.

Each step ends with `pytest` and `make -C examples` passing, and the
comparison sheets re-rendered.

## Step 0: decisions (maintainer)

Listed at the end of this file. Steps 1–2 do not depend on them; steps 3–5
do.

## Step 1: correctness bugs (no visual-identity change)

| # | item | fixes | effort | risk |
|---|---|---|---|---|
| 1.1 | One colour allocator per figure: mapping → next unused palette slot; cycle length read from rcParams; drop every `% 10`; `--combined_color` default "next free"; warn and add line styles past the palette | B01, B02 | M | med: series that relied on the C0/C1 accident change colour |
| 1.2 | Contours: `--contour_dof {1,2}` (default 2), coverage labels, inner-to-outer graded fills, solid/dashed/dotted outlines, best-fit marker, background off for Δχ² | B03 | M | high: the default levels change (1-dof users must add `--contour_dof 1`) |
| 1.3 | Estimators return (value, error): SEM etc.; correct error propagation; `--min_count` | B04 | M | med: error bars appear where there were none |
| 1.4 | `hist`: `ax.stairs`, range over all hues, no "None" legend | B09 | S | low |
| 1.5 | `scatter --hue` keeps all groups | B12 | S | low |
| 1.6 | `--fit` lower panel through `lower_model_series` (pull works) | B13 | S | low |
| 1.7 | `--errory_type` honoured for every plot type | B11 | S | low |
| 1.8 | `cat`: scalar cells, `Patch` handles, no fixed rotation or margin | B07 | S | low |
| 1.9 | `map`: label every colorbar; shared norm and one colorbar per row when panels share `-z`/counts | B08 | M | low |
| 1.10 | Box plots: dodge hues, format ticks, one legend entry per group | B16 | S | low |
| 1.11 | Tests: one regression test per bug, asserting on artists (colours, levels, error arrays, legend labels), not pixels | all | M | none |

## Step 2: style infrastructure (enables any identity)

| # | item | why | effort | risk |
|---|---|---|---|---|
| 2.1 | `"mplstyle"` key in style.json (a path or a matplotlib style name), applied before `rcparams` | the candidates are .mplstyle + style.json; today `render.py` copies rcParams by hand | S | low |
| 2.2 | Style roles `ink/muted/faint/paper`; replace the 20+ hard-coded colours | B14; dark/slides variants | M | low |
| 2.3 | Measured layout: draw, measure every tick, label and colorbar extent, grow the figure margins to fit, keeping the axes size fixed; one source for label sizes (rcParams) | B15; makes small physical sizes safe | L | med: figure sizes change by a few % |
| 2.4 | `--width single\|onehalf\|double\|nature\|slide\|<in>` and `--aspect`; panel rows share the width; lower panels add height instead of squeezing | spec §2.1 | M | med |
| 2.5 | Legend placement on an occupancy mask (filled areas count); headroom or outside placement when no corner is free; one legend when hue == style; ratio-panel legend rules; remove the hard-coded `loc`s | B06, B02 | M | med |
| 2.6 | Tick formatting: drop the threshold formatter; mathtext `ScalarFormatter`; power of ten moved into the label | B05 | S | low |
| 2.7 | Error bars: no joining lines for points with errors (`--connect` to join); `savefig.dpi: 300`; `--format pdf` documented as the paper default | B17 | S | low |

## Step 3: the new identity (after decision D1)

| # | item | effort | risk |
|---|---|---|---|
| 3.1 | Ship the chosen style (`paper` recommended) as `src/plotipus/data/plotipus.mplstyle` + `style.json`; keep the current look as a `classic` style so old projects can pin it (`style = ["classic"]`) | S | high: every figure changes; announce it, give `classic` |
| 3.2 | Ship the alternatives (`open`; `slides` and `dark` overlays; `aps`/`nature`/`elsevier` presets) as named styles selectable by name in `plotipus.toml` and with `--style_preset` on the CLI | S | low |
| 3.3 | Header label built in: `--label 'plotipus' --label_status Preliminary --label_right '13 TeV, 140 fb$^{-1}$'` (mplhep-style). The figure hook stays for logos | S | low |
| 3.4 | Store the resolved rcParams and style files next to each output (`<file>.style.json`) for reproducibility (research Part 1, lesson 10) | S | low |

## Step 4: kind and option additions (by catalogue value)

Ordered by the number of catalogue rows and famous figures each unlocks.

| # | option (kind) | catalogue rows | figures | effort | risk |
|---|---|---|---|---|---|
| 4.1 | Stacking in data space for step/filled/line; `--overlay VALUES` (unstacked, drawn as data points); `--stack_total_error` hatched band | A3, C7, E3, G6 | F03, F23 | M | med (stacked output changes from bars to steps when `--plot_type step`) |
| 4.2 | `--errory_type poisson` (Garwood; sumw2 when weighted) for `line` and `hist`; `clopper_pearson` for efficiencies, sharing the table code | A6, G2, G3 | F01, F03, F16 | M | low |
| 4.3 | Several bands per series: `--errory_column C1 C2`, darker inside; `--band_colors graded\|brazil` | G5 | F02, F04, F05, F15 | M | low |
| 4.4 | `--sigma_lines 1 2 3 4 5` (p-value lines labelled at the right edge); right-edge labels for `--horizontal` | E7, G7 | F04, F05 | S | low |
| 4.5 | Per-hue plot type `--series_type VALUE=errorbar` (data as points, models as lines) | C6 | F09, F12, F17 | S | low |
| 4.6 | `cat`: `--orient h`, `--sort`, `--stacked`, `--kind lollipop\|box\|violin\|strip` (array cells as distributions) | A10, D2, D4–D7, F6 | F25 | M | low |
| 4.7 | `map --annotate`, categorical ticks from string arrays, `--norm` for `-z` grids | D8, F5 | — | S | low |
| 4.8 | `hist --hist_type kde\|ecdf`, `--rug`, `--ridge` | A7, A8, A11, A12 | — | M | low |
| 4.9 | `--hue_cmap` for numeric or ordered hues (colorbar instead of legend) | C10 | F11, F18 | S | low |
| 4.10 | `--sharex/--sharey` for every kind; `--facet_row/--facet_col` | H2, H3 | F15, F25 | M | low |
| 4.11 | `--inset X0 X1 [Y0 Y1]` (zoom of the same series) | H5 | F02, F13, F18 | M | low |
| 4.12 | `--text X Y 'TEXT' [--arrow]`, `--region` polygons, `--contour_labels`, `--direct_labels` | I5, I6, I8, I9 | F10, F17, F18 | M | low |
| 4.13 | `map --map_type hexbin`, `map --corner X1 X2 X3` | B5, B8 | — | M | low |
| 4.14 | `--error_scale K` with a legend note; `--smooth N`; datetime x | G9, C9, C8 | F06, F13, F14, F17 | S | low |
| 4.15 | `table`: `--agg std\|median\|corr`, `--cutflow`, `--fit_params` | J5–J7 | F25 | M | low |
| 4.16 | (optional) `--secondary_x`, hybrid/broken x scale | H6, H7 | F06, F07 | M | low |

## Step 5: new examples dataset and command list

The current examples are a smoke test: 10 commands on 6 toy pickles,
several of them showing bugs. Replace them with a gallery that has three
properties:
- every ✅ catalogue row has an example;
- every example is a realistic physics or data-science figure, mostly the
  famous ones;
- every example renders in the chosen style at column width.

**Data.** `examples/make_data.py` becomes `examples/data/*.py`, one generator
per theme. All of it is synthetic and seeded, built with the recipes in
research Part 3. Public datasets are fetched only by an optional
`make fetch` target, with a checksum, and are never needed for the build:
- NOAA Mauna Loa CSV (F13);
- Union2.1 (F09/F10);
- the Hubble 1929 table, transcribed and committed (F08).

| theme | file | rows |
|---|---|---|
| collider | `higgs.py` | binned m_γγ data + background/signal curves + stored S+B fit (F01); 4ℓ backgrounds, signal and data (F03); p0 scan observed/expected (F04); CLs limits with ±1σ/±2σ (F05) |
| cosmology | `cosmo.py` | SN distance moduli + model curves (F09); Ω_M–Ω_Λ Δχ² grid (F10); FIRAS-like spectrum + residuals (F06) |
| detector | `detector.py` | the current Spectra/Events/Efficiency data (kept, so existing tests survive); resolution vs energy; efficiencies with N, k for Clopper–Pearson |
| ml | `ml.py` | classifier scores per class; ROC/PR/calibration curves; learning curves; feature importances; confusion matrix |
| classics | `classics.py` | Anscombe quartet (public domain values, committed); Hubble 1929 table; Moseley (NIST-like values); Keeling-like synthetic series |

**Command list** (`examples/input/plots/gallery_scripts.txt`): one command
per row, grouped like the catalogue. The step column says which step must
land first ("now" = works today).

| example | command (abridged) | rows | needs |
|---|---|---|---|
| H→γγ with fit and pulls | `line --datafile Diphoton -x Mass -y Counts --fit --plot_type errorbar --errory --lower pull` | C3, C5 | 1.6 |
| 4ℓ data/MC with ratio | `line --datafile FourLepton -x Mass -y Counts --hue Sample --stacked --plot_type step --overlay data --stack_total_error --lower ratio --reference_sum ...` | E3, G6 | 4.1, 4.2 |
| Local p0 | `line --datafile P0 -x Mass -y P0 --style Kind --logy --sigma_lines 1 2 3 4 5` | E7 | 4.4 |
| Brazil plot | `line --datafile Limits -x Mass -y Limit --style Kind --errory_column Band1 Band2 --band_colors brazil --logy` | G5 | 4.3 |
| Ω_M–Ω_Λ contours | `map --datafile OmegaGrid -x OmegaM -y OmegaL -z Chi2 --contour --fill_contours --region ...` | B7, G8 | 1.2 (4.12 for regions) |
| SN Hubble diagram | `line --datafile SN -x z -y mu --series_type data=errorbar --logx --lower subtract --reference_value 'Ω_M=0.2'` | C6 | 4.5 |
| Spectra by sample and stage | existing example 1 | C1 | now |
| Efficiency vs energy (CP intervals) | `line --datafile Efficiency --by_config --errory_type clopper_pearson` | G3 | 1.1, 4.2 |
| Resolution profile | existing example 5 | B9 | 1.3 |
| Reco vs true 2D | existing example 6 | B4 | 1.9 |
| Distributions | `hist --hue Group --hist_type kde --rug`; `hist --hist_type ecdf` | A7, A8, A12 | 4.8 |
| Box/violin per category | `cat --kind violin` | A10 | 4.6 |
| ROC / PR / learning / calibration | probes P08, P09 + calibration | F1–F4 | now (F4 needs `--lower_plot_type bar`) |
| Confusion matrix | `map -z Frac --annotate '{:.0f}%'` | F5, D8 | 4.7 |
| Feature importance | `cat --kind bar --orient h --sort` | F6 | 1.8, 4.6 |
| Anscombe quartet | `line --variables I II III IV --plot_type errorbar --fit --sharex --sharey` (linear fits stored per dataset) | H1, H2 | 4.10 |
| Hubble 1929 | `line --plot_type errorbar --fit` (stored fits through the origin) | B2, C3 | now |
| Keeling curve with inset | `line -x Date -y CO2 --hue Series --inset ...` | C8, H5 | 4.11, 4.14 |
| Results table | existing table + `--clopper_pearson` + `--fit_params` | J1, J2, J7 | 4.15 |

Each gallery entry also becomes a test: render it in the default style and
assert the artist-level properties from step 1.11. The README links a
gallery page, generated by a `make gallery` target that writes a Markdown
grid of the PNGs.

| # | item | effort | risk |
|---|---|---|---|
| 5.1 | Data generators and the `fetch` target | M | low |
| 5.2 | Gallery command list, as features land; keep the existing 10 commands for continuity | M | low |
| 5.3 | `make gallery` + README gallery section | S | low |

## Suggested sequencing

| milestone | contents | approx. effort |
|---|---|---|
| M1 "correct" | 1.1–1.11, 2.6, 2.7 | ~2 weeks |
| M2 "layout" | 2.1–2.5 | ~1.5 weeks |
| M3 "identity" | 3.1–3.4 + re-render the gallery for what already works | ~3 days |
| M4 "HEP essentials" | 4.1–4.5 + their gallery entries | ~1.5 weeks |
| M5 "breadth" | 4.6–4.15 + remaining gallery | ~3 weeks |

## Decisions (maintainer, 2026-10-24)

These decisions supersede the recommendations above where they differ.
They are implemented by the briefs in [tasks/](tasks/).

- **D1 Identity and default medium.**
  - **Slides first.** Most workflows present plots in talks before
    publishing them, so the engine is built around rendering the same
    command list for several media.
  - **Default medium:** `slides`, with the `paper` visual language (ticks
    in, mirrored, no grid). It comes as `slides` (light) and `slides-dark`.
  - **Publication:** `paper` re-renders the same commands at column width
    with LaTeX-matching type.
  - **Web pages:** `open` and `open-dark`, provided in parallel. They are
    not the first priority.
  - **Later, in each category:** experiment presets (ATLAS, CMS, LHCb,
    ALICE, DUNE, …) and optional watermarks ("Work In Progress",
    "Preliminary", …).
  - Briefs: T14, T16, T17.
- **D2 Palettes.** Petroff-10 is the default, with line-style overflow past
  the palette. Ship the other common palettes by name: Petroff-6/8,
  Okabe–Ito, Tol bright/muted, matplotlib tab10, seaborn colorblind,
  tableau-colorblind10, and ROOT. Brief: T01.
- **D3 Contours.** 2-dof levels are the default, **with backwards
  compatibility**:
  - `--contour_dof 1` restores the old levels;
  - the `classic` style pins 1 dof;
  - command lines translated from the legacy scripts keep 1 dof;
  - a one-line notice is printed when an old-looking command now gets
    different levels.
  - Brief: T02.
- **D4 Physical sizing.** Accepted. Figures are drawn at their target size,
  and paper figures carry no titles. Brief: T14.
- **D5 Compatibility.** Accepted. Defaults change in one release, and a
  `classic` style pins the current look. Brief: T16.
- **D6 Data.** Synthetic data only for now. A custom dataset for reproducing
  famous plots will follow. Briefs: T23, T24.
- **D7 Scope.** Polar, geographic and flow charts are out of scope for now,
  recorded in [TODO.md](TODO.md).
