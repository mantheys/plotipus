# Famous plots

Small datasets for reproducing famous figures from physics, astronomy,
climate science and statistics with plotipus (research
[F01–F25](../../docs/design/research.md#part-3-famous-plots-as-reproduction-targets),
decision D6). The command list shows how close plotipus gets to each figure
today.

> These figures are recreations made to demonstrate plotipus. They are not
> the original figures, nor official results of the ATLAS, CMS, LEP,
> KamLAND, LIGO/Virgo or Gaia collaborations or of the original authors,
> who do not endorse this project; the experiment headers say
> "recreation". Values come from public data releases or were read from
> the published figures, so small differences from the originals are
> expected: cite and use the original publications, linked from each
> image. Data sources, licences and credits are listed in
> [examples/famous/data](data/README.md); the HR diagram, made from Gaia
> data, is shared under CC BY-SA 3.0 IGO.

```bash
cd examples/famous
python make_data.py            # 22 pickles in input/data (about 3 s, 2.3 MB)
python make_data.py F08 F25    # only some figures
plotipus run famous            # figures in output/plots
```

Each figure has a seeded generator in a module per field: `hep.py`,
`cosmology.py`, `galaxies.py`, `climate.py`, `gravwaves.py`, `classics.py`
and `anscombe.py`. A generator's docstring:

- cites the source paper and figure;
- lists the values taken from the paper;
- says what is synthetic;
- keeps the "(unverified)" marks of research.md.

Two project plugins and a style file, all listed in `plotipus.toml`, show how
a project adapts plotipus without changing it:

- `models.py`: physics formulas and fit models, registered so that stored
  fits can name them (`FitFunction`);
- `colorscale.py`: `--zpower GAMMA` (a power-law colour scale, 0.5 for the
  square root of the Gaia diagrams), `--zcmap NAME` (the colour map, 2D
  histograms included), `--zmin VALUE` and `--zunder COLOUR` (the colour of
  the sparsest bins) for map panels;
- `style.json`: no automatic titles, a black-first colour cycle (data drawn
  black, as in the originals), one colour and label mapping per figure, and
  the paper gallery size (`widths.single`, 3.5 × 2.7 in).

`plotipus run famous` renders every command in slides (`output/plots`) and
in paper (`output/plots/paper`, `media` in `plotipus.toml`); `--medium paper`
renders only the paper figures. The experiment headers are `--experiment
atlas|cms` with `--label_position`, `--label_status` and `--label_right`
(T17). Multi-panel figures of the gallery pass `--single_panel_size`, so
every image has the same size. The README gallery is a selection of the
paper figures (`make -C examples famous`).

The frames follow the plotipus conventions:

- one row per series, with whole arrays in the cells;
- `{y}Error`, or `{y}Error+`/`{y}Error-`, for errors;
- a hue column (`Component`, `Sample`, `Series`, …) and `Variable` for
  panels;
- stored fits as `FitFunction`, `FitFunctionLabel`, `Params`, `ParamsError`
  and `ParamsLabel`;
- for maps, one file per config and name (`Riess1998_SN_OmegaContours.pkl`).

Real data (`data/`, sources, licences and citations in `data/README.md`):
the FIRAS spectrum (F06, NASA LAMBDA), the Union2.1 supernovae (F09, and the
F10 grid), SPARC rotation curves (F11, F12), the NOAA Mauna Loa CO2 record
(F13), the MBH99 reconstruction (F14, NOAA paleoclimatology), the data of
LIGO's GW150914 figure (F15, GWOSC), the Gaia DR2 star counts (F22, the
paper's archive query), Hubble's Table 1 (F08) and Anscombe's table (F25).
`fetch_data.py` and `fetch_gaia.py` refresh them.

Values extracted from the published figures (`data/extracted/`): the Higgs
figures (F01, F03, F04, F05), KamLAND (F16) and LEP (F17) have no public
tables, but their arXiv sources keep the figures as vector graphics, whose
drawing commands hold every marker, error bar, curve and band. `extract/run.py`
reads them back in physics units (method, precision and cross-checks:
`extract/README.md`). Only the 1912-1913 tables (F19-F21), which exist as
scans, stay synthetic.

## Status

The commands were compared with the original figures (fetched from the
arXiv sources and the papers). ✅ the figure's content and look are
reproduced. ◐ close, with the gaps listed under "Missing features" below;
the intended command for a planned option is in
`input/plots/famous_scripts.txt`, commented out.

The commands aim at the originals, not at plotipus's own style: the
originals' colours, line styles, markers, legend layout and annotations,
so the gallery shows that plotipus can draw what others drew. Fonts
and other rcParams are still the paper medium's for every figure (a
per-command style file is a follow-up request). The same figures redrawn
with plotipus's defaults are the style guide's before-and-after examples.

Patterns the commands use:

- **Data and models in one figure.** `--data_hue` draws the measured series
  as points with error bars (in the ink colour, or the colour mapped to
  it); the models are lines (`--plot_type line`). With `--style` on the hue
  column, `--comparable_linestyles` follows the hue order (the key order of
  the colour mapping).
- **A band in its own colour.** The band is a row of its own: the median
  with the band as its errors and `Width` 0 (`--linewidth_column Width`).
  Used for the ±1σ/±2σ bands (F04, F05) and the grey reconstructions (F15).
- **Fitted straight lines.** Rows whose end points lie outside `--rangex`
  (F08, F20, F21, F25).
- **A histogram outline among lines.** The KamLAND expectation is stored as
  its step polyline.

| figure | source | data | status | missing (task) |
|---|---|---|---|---|
| F01 H→γγ m_γγ | ATLAS, PLB 716 (2012) 1, Fig. 4 | **extracted** (figure) | ◐ | (ATLAS header inside: `--experiment atlas --label_position inside`) (data − background under the S+B fit: `--fit --lower residual:Bkg`) 4 panels in one figure (T22.6); the Sig+Bkg − Bkg curve in the lower panel, drawn by T21 and lost in the example-feedback-3 merge (follow-up); the ATLAS header inside, which an explicit `--legend_loc` overlaps (T15/T17 follow-up; drawn above here) |
| F03 H→ZZ*→4ℓ | CMS, PLB 716 (2012) 30, Fig. 4 | **extracted** (figure) | ◐ | (CMS header above: `--experiment cms`; Garwood bars from the counts: `--errory_type poisson`; the signal as an open outline on the filled stack: `--series_type Signal=step --plot_type fill`) inset (T22.7) |
| F04 local p₀ | ATLAS, Fig. 9 | **extracted** (figure) | ✅ | (ATLAS header with two right lines; small markers on the observed curve: `--series_marker Observed=o:2.5`; dotted σ lines labelled outside the frame: `--sigma_lines 0 1 2 3 4 5 6 --sigma_line_style dotted --horizontal_label_pos outside`; the band in its own colour with a legend swatch: `--band_colors '#66ccff'`) |
| F05 Brazil band | ATLAS, Fig. 7(a) | **extracted** (figure) | ◐ | (ATLAS header; nested green and yellow bands from the expected row: `--errory_column MuLimit1Sigma MuLimit2Sigma --band_colors brazil`; dotted expected and μ = 1 lines) the swatches beside the line entries in two columns (legend follow-up); the broken x axis (TODO.md, postponed) |
| F06 COBE FIRAS | Fixsen et al. 1996, Figs. 4-5 | **real** (NASA LAMBDA) | ✅ | (errors ×400 with `--error_scale 400`) a top axis in GHz (TODO.md, postponed) |
| F08 Hubble 1929 | PNAS 15, 168, Fig. 1 | **real** (Table 1) | ✅ | (discs, open circles and a cross: `--series_marker ... Groups=o_open ...`; no legend, Hubble's grid lines: `--horizontal`/`--vertical`) a bold title (paper font, follow-up) |
| F09 SN Ia Hubble diagram | Riess et al. 1998, Fig. 4 | **real** (Union2.1) | ◐ | (plain log tick labels: T12 follow-up) the cosmologies' residual curves in the lower panel, lost in the example-feedback-3 merge (follow-up) |
| F10 Ω_M–Ω_Λ | Riess et al. 1998, Fig. 6 | **real** (Union2.1), synthetic CMB | ◐ | (no best-fit marker, as in the original: `--no_best_fit`; black contours: `config_color`; the shaded "No Big Bang" region: `--region`) labels beside the contours (too small for `--contour_labels` inline) |
| F11 rotation curves | Rubin, Ford & Thonnard 1980 | **real** (SPARC) | ◐ | an ordered colour map for 21 hues (T22.5); `--panel_title` on `line` panels (follow-up; the size classes are all-math labels so the title case leaves `kpc` alone) |
| F12 NGC 3198 | van Albada et al. 1985 | **real** (SPARC); fitted halo | ✅ | (figure styles unverified) |
| F13 Keeling curve | NOAA GML plot | **real** (NOAA GML) | ✅ | the seasonal-cycle inset of other versions (T22.7) |
| F14 hockey stick | Mann, Bradley & Hughes 1999, Fig. 3(a) | **real** (NOAA paleo) | ✅ | (the legend below the axes: `--legend_loc below`; the uncertainty as a light-grey row of its own; the 1998 arrow: `--text ... --arrow 1996 0.8`) |
| F15 GW150914 | PRL 116, 061102, Fig. 1 | **real** (GWOSC); synthetic band widths | ◐ | 4 × 2 grid (T22.6); log frequency axis on the map (T22.3); `--legend_panel all` collapses the H1 panels and `--title` is not drawn (T15 follow-up) |
| F16 KamLAND L₀/E | PRL 100, 221803, Fig. 3 | **extracted** (figure) | ✅ | (x error bars from each point's bin: `--errorx_column LOverELow LOverEHigh`; one two-line legend entry for both expectations, the curve labelled `_nolegend_`) |
| F17 LEP Z lineshape | Phys. Rept. 427 (2006) 257, Fig. 1.13 | **extracted** (figure) | ✅ | (errors ×10 with `--error_scale 10`; thin curves; labels at the peaks with `--text`) blue frame, bold sans labels (per-figure style, follow-up) |
| F19 Geiger–Marsden | Phil. Mag. 25, 604 (1913) | synthetic | ✅ | (no original figure) |
| F20 Moseley's law | Phil. Mag. 26, 1024 (1913) | synthetic | ✅ | (no original figure) |
| F21 Leavitt | Harvard Circ. 173 (1912) | synthetic | ✅ | (table not transcribed) |
| F22 HR diagram | Gaia DR2 HRD (A&A 616, A10), Fig. 1 | **real** (Gaia archive, the paper's query) | ✅ | square-root colour scale, colour map and no colorbar for maps (`colorscale.py` plugin, T22.3); Fig. 5 needs the STILISM extinction cut (a 200 pc stand-in is drawn) |
| F25 Anscombe's quartet | Am. Stat. 27, 17 (1973) | **real** | ✅ | shared axes (T22.6); statistics table (T22.11) |

## Missing features, by task

| task | missing feature | figures |
|---|---|---|
| T22.3 | a power (square-root) colour scale, a colour below the scale, `--cmap` for 2D histograms, `--colorbar none`; log y axis for `-z` images | F22, F15 |
| T22.5 | an ordered colour map for many hues | F11 |
| T22.6 | panel grids with shared axes (rows × columns) | F01, F15, F25 |
| T22.7 | insets | F03, F13 |
| T22.11 | `table --agg corr` | F25 |

F02, F07, F18, F23 and F24 have no dataset here. They are not in the T24
brief; polar and flow charts are out of scope (`docs/design/TODO.md`).
