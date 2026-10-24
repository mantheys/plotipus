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
  letters and region labels;
- `style.json`: no automatic titles, a black-first colour cycle (data drawn
  black, as in the originals), smaller legends, and one colour and label
  mapping per figure.

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

Workarounds the commands use today:

- **Points and lines in one figure.** `--style` on the hue column with
  `--comparable_linestyles none solid dashed`, `--plot_type line --errory
  --errory_type bars`. The data rows keep their error bars without a line;
  the model rows have no errors and draw as lines. The data points have no
  markers.
- **A band in its own colour.** The band is a row of its own: the median
  with the band as its errors, drawn with linewidth 0
  (`--comparable_linewidths`). Used for the ±1σ/±2σ bands (F04, F05) and the
  grey reconstructions (F15).
- **Fitted straight lines with marker plots.** The line rows end outside
  `--rangex`, so `--plot_type plot` clips their end markers (F08, F20, F21,
  F25).
- **A histogram outline among lines.** The KamLAND expectation is stored as
  its step polyline.

| figure | source | data | status | missing (task) |
|---|---|---|---|---|
| F01 H→γγ m_γγ | ATLAS, PLB 716 (2012) 1, Fig. 4 | synthetic | ◐ | data markers (T21); 4 panels in one figure (T22.6); residual vs a fit component (T22.14) |
| F03 H→ZZ*→4ℓ | CMS, PLB 716 (2012) 30, Fig. 4 | synthetic | ◐ | data on top of the stack (T18); Garwood bars (T19); inset (T22.7) |
| F04 local p₀ | ATLAS, Fig. 9 | synthetic | ◐ | markers on the observed curve (T21); σ-line labels and band legend swatch (T20) |
| F05 Brazil band | ATLAS, Fig. 7(a) | synthetic | ◐ | saturated band colours and swatches (T20); log-axis tick labels (T12) |
| F06 COBE FIRAS | Fixsen et al. 1996, Figs. 4-5 | synthetic | ◐ | data markers and an error scale option (T21) |
| F08 Hubble 1929 | PNAS 15, 168, Fig. 1 | **real** (Table 1) | ◐ | per-series markers: discs, circles, cross (T21) |
| F09 SN Ia Hubble diagram | Riess et al. 1998, Fig. 4 | synthetic | ◐ | data markers, an open one for SN 1997ck (T21) |
| F10 Ω_M–Ω_Λ | Riess et al. 1998, Fig. 6 | synthetic | ◐ | reference lines and 2-dof CL levels need T02 merged (done on `task/T02-contours`, 62e018f); shaded region (T22.8) |
| F11 rotation curves | Rubin, Ford & Thonnard 1980 | synthetic | ◐ | an ordered colour map for 21 hues (T22.5); figure layout unverified |
| F12 NGC 3198 | van Albada et al. 1985 | synthetic | ◐ | data markers (T21) |
| F13 Keeling curve | NOAA GML plot | synthetic | ✅ | the seasonal-cycle inset of other versions (T22.7) |
| F14 hockey stick | Mann, Bradley & Hughes 1999, Fig. 3(a) | synthetic | ✅ | a legend outside the axes (T15) |
| F15 GW150914 | PRL 116, 061102, Fig. 1 | synthetic | ◐ | 4 × 2 grid (T22.6); a legend per panel (T15); log frequency axis on the map (T22.3) |
| F16 KamLAND L₀/E | PRL 100, 221803, Fig. 3 | synthetic | ◐ | data markers and x error bars (T21) |
| F17 LEP Z lineshape | Phys. Rept. 427 (2006) 257, Fig. 1.13 | synthetic | ◐ | data markers, error scale (T21); labels on curves (T22.8) |
| F19 Geiger–Marsden | Phil. Mag. 25, 604 (1913) | synthetic | ✅ | (no original figure) data markers in the two-foil version (T21) |
| F20 Moseley's law | Phil. Mag. 26, 1024 (1913) | synthetic | ✅ | (no original figure) |
| F21 Leavitt | Harvard Circ. 173 (1912) | synthetic | ✅ | (table not transcribed) |
| F22 HR diagram | Gaia DR2 HRD (A&A 616, A10), Fig. 1 | synthetic | ✅ | `--cmap` for 2D histograms (T22.3); temperature and luminosity axes (TODO.md) |
| F25 Anscombe's quartet | Am. Stat. 27, 17 (1973) | **real** | ✅ | shared axes (T22.6); statistics table (T22.11) |

## Missing features, by task

| task | missing feature | figures |
|---|---|---|
| T02 | ~~`--line`/`--square` in contour mode; 2-dof levels labelled 68.3/95.4/99.7% CL~~ done in 62e018f, effective once merged | F10 |
| T12 | readable tick labels on log axes (`2×10²` instead of 200) | F05, F09 |
| T15 | a legend in every panel; a legend below the axes | F15, F14 |
| T17 | experiment labels as a style feature (here `--text`) | F01, F03, F04, F05 |
| T18 | data points on top of a stack (`--stacked` stacks every hue) | F03 |
| T19 | Garwood bars from the counts | F03 |
| T20 | band colours independent of the line, saturated fills, band legend swatches; labelled σ lines | F04, F05, F15 |
| T21 | per-series plot type: markers on data drawn with lines; per-series markers; `--error_scale` | F01, F04, F06, F08, F09, F12, F16, F17, F19 |
| T22.3 | `--cmap` for 2D histograms; log y axis for `-z` images | F22, F15 |
| T22.5 | an ordered colour map for many hues | F11 |
| T22.6 | panel grids with shared axes (rows × columns) | F01, F15, F25 |
| T22.7 | insets | F03, F13 |
| T22.8 | `--text`/`--region`/`--direct_labels`/`--contour_labels` in the core | F10, F17 |
| T22.11 | `table --agg corr` | F25 |
| T22.14 | `--lower residual:COMPONENT` | F01 |

F02, F07, F18, F23 and F24 have no dataset here. They are not in the T24
brief; polar and flow charts are out of scope (`docs/design/TODO.md`).
