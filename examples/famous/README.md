# Famous plots

Small datasets for reproducing famous figures from physics, astronomy,
climate science and statistics with plotipus (research
[F01–F25](../../docs/design/research.md#part-3-famous-plots-as-reproduction-targets),
decision D6). The command list shows how close plotipus gets to each figure
today.

```bash
cd examples/famous
python make_data.py            # 22 pickles in input/data (about 1 s, under 1 MB)
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

Physics formulas and fit models live in `models.py`. `plotipus.toml` loads it
as a plugin, so stored fits can name them (`FitFunction`).

The frames follow the plotipus conventions:

- one row per series, with whole arrays in the cells;
- `{y}Error`, or `{y}Error+`/`{y}Error-`, for errors;
- a hue column (`Component`, `Sample`, `Series`, …) and `Variable` for
  panels;
- stored fits as `FitFunction`, `FitFunctionLabel`, `Params`, `ParamsError`
  and `ParamsLabel`;
- for maps, one file per config and name (`Riess1998_SN_OmegaContours.pkl`).

## Status

✅ the command reproduces the figure's content. ◐ an approximation: the
missing pieces are listed, and the intended command is in
`input/plots/famous_scripts.txt`, commented out, under `# needs Txx`.

| figure | source | data | status | gap | closed by |
|---|---|---|---|---|---|
| F01 H→γγ m_γγ | ATLAS, PLB 716 (2012) 1, Fig. 4 | synthetic | ◐ | background component not drawn; residual is (data − fit)/fit, not data − background (stored as `DataMinusBackground` for a column panel); the raw and weighted spectra are two figures | T21, T22.14 |
| F03 H→ZZ*→4ℓ | ATLAS Fig. 2, CMS PLB 716 (2012) 30, Fig. 4 | synthetic | ◐ | no stack of steps with data on top, no Garwood bars, no MC band (the data rows already have `EventsLow`/`EventsHigh`) | T18, T19 |
| F04 local p₀ | ATLAS Fig. 9, CMS Fig. 14 | synthetic | ◐ | σ lines drawn with `--horizontal`, but their labels are misplaced | T20 |
| F05 Brazil band | ATLAS Fig. 7(a), CMS Fig. 13 | synthetic | ◐ | one band per figure; no green/yellow pair | T20 |
| F06 COBE FIRAS | Mather 1994; Fixsen 1996 | synthetic (LAMBDA has the real table) | ◐ | `--fit` residual is relative; the ×400 errors come from a stored column; no GHz top axis | T21; top axis: TODO.md |
| F08 Hubble 1929 | PNAS 15, 168, Fig. 1 | **real** (Table 1) | ◐ | `--fit` draws one of the two stored fits; the cross is not in the data | T21 |
| F09 SN Ia Hubble diagram | Riess 1998, Fig. 4 | synthetic | ◐ | cosmology curves drawn as markers | T21 |
| F10 Ω_M–Ω_Λ | Riess 1998, Fig. 6 | synthetic | ◐ | 1-dof levels and σ labels; no region labels or q₀ lines | T02, T22.8 |
| F11 rotation curves | Rubin, Ford & Thonnard 1980 | synthetic | ◐ | 21 series cycle the colour palette | T22.5 |
| F12 NGC 3198 | van Albada et al. 1985 | synthetic | ◐ | data joined by a line | T21 |
| F13 Keeling curve | NOAA GML co2_mm_mlo.csv | synthetic | ◐ | seasonal cycle is a second figure, not an inset | T22.7 |
| F14 hockey stick | Mann, Bradley & Hughes 1999 | synthetic | ✅ | smoothing computed upstream | (T22.10 optional) |
| F15 GW150914 | PRL 116, 061102, Fig. 1 | synthetic | ◐ | one detector per figure (no rows × columns grid); one band instead of two; linear frequency axis on the map | T22.6, T20; log axis: not planned |
| F16 KamLAND L₀/E | PRL 100, 221803, Fig. 3 | synthetic | ◐ | expectation drawn as markers, not steps; no x error bars | T21 |
| F17 LEP Z lineshape | Phys. Rept. 427 (2006) 257, Fig. 1.13 | synthetic (published Z parameters) | ◐ | ×10 errors come from a stored column; curves drawn as markers; no labels on the curves | T21, T22.8 |
| F19 Geiger–Marsden | Phil. Mag. 25, 604 (1913) | synthetic | ✅ | one foil's fit per figure (`--fitindex`) | — |
| F20 Moseley's law | Phil. Mag. 26, 1024 (1913) | synthetic | ◐ | one fitted line per figure (`--fitindex`) | — (T21 with stored line rows, as in F08) |
| F21 Leavitt | Harvard Circ. 173 (1912) | synthetic | ◐ | one fitted line per figure (`--fitindex`) | — (as F20) |
| F22 HR diagram | Russell 1914; Gaia DR2 HRD (A&A 616, A10) | synthetic | ✅ | — | — |
| F25 Anscombe's quartet | Am. Stat. 27, 17 (1973) | **real** | ◐ | no fitted line per panel; no shared axes; no same-statistics table (the stats are stored as columns) | T22.6, T22.11 |

F02, F07, F18, F23 and F24 have no dataset here. They are not in the T24
brief; polar and flow charts are out of scope (`docs/design/TODO.md`).
