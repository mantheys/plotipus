# Famous plots

Small datasets for reproducing famous figures from physics, astronomy,
climate science and statistics with plotipus (research
[F01–F25](../../docs/design/research.md#part-3-famous-plots-as-reproduction-targets),
decision D6). The command list shows how close plotipus gets to each figure
today.

```bash
cd examples/famous
python make_data.py            # 22 pickles in input/data (about 1 s, 1.4 MB)
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
- `annotations.py`: `--text X Y TEXT` (repeatable, with `--text_coords`,
  `--text_axes`, `--text_color`, `--text_size`, `--text_rotation`,
  `--text_weight`, `--text_style`, `--text_ha`), drawn by a figure hook. The
  figures use it for experiment labels, energies and luminosities, panel
  letters and region labels. The project setting `text_scale` scales every
  text, and `--single_panel_size` gives a grid of panels the size of a
  single-panel figure;
- `style.json`: no automatic titles, a black-first colour cycle (data drawn
  black, as in the originals), smaller legends, and one colour and label
  mapping per figure.

`paper/` renders the same commands in the paper style: its `paper.json`
loads the prototype `docs/design/styles/paper/plotipus-paper.mplstyle` (serif
Computer Modern, 8 pt, 3.5 × 2.7 in) over `style.json`, and its
`plotipus.toml` sets `text_scale = 0.75`. `cd paper && plotipus run famous`
writes them to `paper/output/plots`; the README gallery is a selection of
these (`make -C examples famous`).

The frames follow the plotipus conventions:

- one row per series, with whole arrays in the cells;
- `{y}Error`, or `{y}Error+`/`{y}Error-`, for errors;
- a hue column (`Component`, `Sample`, `Series`, …) and `Variable` for
  panels;
- stored fits as `FitFunction`, `FitFunctionLabel`, `Params`, `ParamsError`
  and `ParamsLabel`;
- for maps, one file per config and name (`Riess1998_SN_OmegaContours.pkl`).

## Status

The commands were compared with the original figures (fetched from the
arXiv sources and the papers). ✅ the figure's content and look are
reproduced. ◐ close, with the gaps listed under "Missing features" below;
the intended command for a planned option is in
`input/plots/famous_scripts.txt`, commented out.

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
| F01 H→γγ m_γγ | ATLAS, PLB 716 (2012) 1, Fig. 4 | synthetic | ◐ | data drawn as a line in the `column:` lower panel (T21); 4 panels in one figure (T22.6); residual vs a fit component (T22.14) |
| F03 H→ZZ*→4ℓ | CMS, PLB 716 (2012) 30, Fig. 4 | synthetic | ◐ | Garwood bars (T19); signal as an open outline on the stack (T18); inset (T22.7) |
| F04 local p₀ | ATLAS, Fig. 9 | synthetic | ◐ | markers on the observed curve (T21); band legend swatch and σ-line labels (T20) |
| F05 Brazil band | ATLAS, Fig. 7(a) | synthetic | ◐ | saturated band colours and swatches (T20); log-axis tick labels (T12) |
| F06 COBE FIRAS | Fixsen et al. 1996, Figs. 4-5 | synthetic | ◐ | an error scale option (T21); data drawn as a line in the lower panel (T21) |
| F08 Hubble 1929 | PNAS 15, 168, Fig. 1 | **real** (Table 1) | ◐ | per-series markers: discs, circles, cross (T21) |
| F09 SN Ia Hubble diagram | Riess et al. 1998, Fig. 4 | synthetic | ◐ | an open marker for SN 1997ck; data drawn as a line in the lower panel (T21); log tick labels (T12) |
| F10 Ω_M–Ω_Λ | Riess et al. 1998, Fig. 6 | synthetic | ◐ | the shaded "No Big Bang" region (T22.8) |
| F11 rotation curves | Rubin, Ford & Thonnard 1980 | synthetic | ◐ | an ordered colour map for 21 hues (T22.5); figure layout unverified |
| F12 NGC 3198 | van Albada et al. 1985 | synthetic | ✅ | (figure styles unverified) |
| F13 Keeling curve | NOAA GML plot | synthetic | ✅ | the seasonal-cycle inset of other versions (T22.7) |
| F14 hockey stick | Mann, Bradley & Hughes 1999, Fig. 3(a) | synthetic | ✅ | a legend outside the axes (T15) |
| F15 GW150914 | PRL 116, 061102, Fig. 1 | synthetic | ◐ | 4 × 2 grid (T22.6); a legend per panel (T15); log frequency axis on the map (T22.3) |
| F16 KamLAND L₀/E | PRL 100, 221803, Fig. 3 | synthetic | ◐ | x error bars from the bin widths (T21) |
| F17 LEP Z lineshape | Phys. Rept. 427 (2006) 257, Fig. 1.13 | synthetic | ✅ | an error scale option instead of a stored column (T21); labels on curves are `--text` (T22.8) |
| F19 Geiger–Marsden | Phil. Mag. 25, 604 (1913) | synthetic | ✅ | (no original figure) |
| F20 Moseley's law | Phil. Mag. 26, 1024 (1913) | synthetic | ✅ | (no original figure) |
| F21 Leavitt | Harvard Circ. 173 (1912) | synthetic | ✅ | (table not transcribed) |
| F22 HR diagram | Gaia DR2 HRD (A&A 616, A10), Fig. 1 | synthetic | ✅ | `--cmap` for 2D histograms (T22.3); temperature and luminosity axes (TODO.md) |
| F25 Anscombe's quartet | Am. Stat. 27, 17 (1973) | **real** | ✅ | shared axes (T22.6); statistics table (T22.11) |

## Missing features, by task

| task | missing feature | figures |
|---|---|---|
| T12 | readable tick labels on log axes (`2×10²` instead of 200) | F05, F09 |
| T15 | a legend in every panel; a legend below the axes | F15, F14 |
| T17 | experiment labels as a style feature (here `--text`) | F01, F03, F04, F05 |
| T18 | the signal as an open outline on top of a filled stack | F03 |
| T19 | Garwood bars from the counts | F03 |
| T20 | band colours independent of the line, saturated fills, band legend swatches; labelled σ lines | F04, F05, F15 |
| T21 | `column:` lower panels following `--data_hue`/`--plot_type_column` (data as points); per-series markers; `--error_scale`; x error bars from bin widths for data points | F01, F04, F06, F08, F09, F16, F17 |
| T22.3 | `--cmap` for 2D histograms; log y axis for `-z` images | F22, F15 |
| T22.5 | an ordered colour map for many hues | F11 |
| T22.6 | panel grids with shared axes (rows × columns) | F01, F15, F25 |
| T22.7 | insets | F03, F13 |
| T22.8 | `--text`/`--region`/`--direct_labels`/`--contour_labels` in the core | F10, F17 |
| T22.11 | `table --agg corr` | F25 |
| T22.14 | `--lower residual:COMPONENT` | F01 |

F02, F07, F18, F23 and F24 have no dataset here. They are not in the T24
brief; polar and flow charts are out of scope (`docs/design/TODO.md`).
