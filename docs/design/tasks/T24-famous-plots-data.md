# T24 Synthetic datasets for famous plots

**Independent (no `src/` changes): can start at wave 0 · effort M · risk none**

## Goal

A custom, synthetic, physically realistic dataset for reproducing the
famous figures of [research.md Part 3](../research.md#part-3-famous-plots-as-reproduction-targets)
(decision D6). It is written in plotipus's DataFrame conventions, with a
command list that marks which figures plotipus can draw today.

## Read first

- research Part 3, F01–F25. Each figure has a "Data" recipe and a "plotipus
  requirement".
- [catalogue.md, "Mapping of the famous figures"](../catalogue.md).
- The plotipus data conventions in `README.md` and `examples/make_data.py`:
  - one row per series, with arrays in cells;
  - `{y}Error`, or `{y}Error+`/`{y}Error-`;
  - `Variable` and hue columns;
  - stored fits as `FitFunctionLabel`, `Params`, `ParamsError` and
    `ParamsLabel` (see `src/plotipus/fits.py`, `kinds/_fit.py`).

## Scope

- New `examples/famous/`:
  - `make_data.py`;
  - one module per figure group;
  - `input/plots/famous_scripts.txt`;
  - `README.md`;
  - `plotipus.toml`.
- No changes to `src/`. If a figure needs a fit model, put the model in
  `examples/famous/models.py` and register it through a project plugin
  (`plugins = [...]` in `plotipus.toml`), as the README describes.

## Required behaviour

1. **Figures:**
   - F01 H→γγ: background + signal, Poisson data, a stored S+B fit with its
     background component.
   - F03 4ℓ: ZZ, Z+X, signal, Poisson data, MC stat errors.
   - F04 local p0, observed and expected.
   - F05 CLs limits with ±1σ/±2σ columns.
   - F06 FIRAS-like spectrum with residuals.
   - F08 Hubble 1929: the 24 rows of Table 1, as transcribed in research.md
     (this one is real data, so cite it).
   - F09 SN distance moduli plus three cosmology curves.
   - F10 Ω_M–Ω_Λ Δχ² grid.
   - F11 rotation curves, 21 galaxies.
   - F12 NGC 3198 components.
   - F13 Keeling-like monthly series.
   - F14 a proxy reconstruction with σ.
   - F15 a chirp strain for two detectors, with residuals.
   - F16 KamLAND L/E with variable-width bins.
   - F17 Z lineshape points with N_ν = 2, 3, 4 curves.
   - F19 Geiger–Marsden counts.
   - F20 Moseley √ν vs Z.
   - F21 Leavitt periods.
   - F22 HR diagram (synthetic main sequence, giants and white dwarfs).
   - F25 Anscombe's quartet (the published values, which are public
     domain).
2. **Generators.** Each one is seeded and documented. A docstring cites the
   source paper and figure (from research.md), lists which parameters were
   taken from the paper (e.g. m_Z, Γ_Z, Δm², tan²θ), and says what is
   synthetic. Physics formulas follow the research recipes. Where research
   marked a value "(unverified)", keep the mark in the docstring.
3. **Size.** Tiny datasets: the whole set builds in under 10 s and comes to
   less than 5 MB of pickles.
4. **`famous_scripts.txt`.** One command per figure, using what plotipus can
   do today. When the figure needs a feature from T18–T22, write the
   intended command commented out with `# needs Txx` above the best
   approximation that works now.
5. **`examples/famous/README.md`.** A table: figure, source, data
   (real/synthetic), command status (✅/◐/✗), and the tasks that close the
   gap.

## Tests

`tests/test_famous_data.py`:
- every generator runs;
- column conventions hold (array lengths match, errors are non-negative);
- every uncommented command in `famous_scripts.txt` renders.

## Done when

The definition of done in 00-README applies, except the src-related items.
The renders of every working command have been opened and compared with the
original figure, using research.md's description of each.
