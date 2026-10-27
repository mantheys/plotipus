# plotipus

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/mascot/mascot-dark.png">
    <img src="docs/images/mascot/mascot.png" width="300"
         alt="The plotipus mascot: a cartoon platypus diving through a water disc, drawn by plotipus itself">
  </picture>
</p>

Publication plots and tables from pickled pandas DataFrames, driven by plain
text command lists.

* **You are a scientist, not a designer.** One short command per figure, and
  every figure comes out clean and consistent, with a look of your own.
* **Produce the data once, plot it without limits.** A well-built DataFrame
  is all you ever need to save: it is your immutable source, and every
  figure and table is redrawn from it.
* **Strict format requirements, unlimited versatility.** Journal styles,
  experiment-wide conventions and collaboration rules are a style file or a
  plugin away, without touching your analysis.

Analysis code writes its results as `.pkl` DataFrames (one row per series,
with whole arrays in the cells); plotipus turns them into figures and LaTeX
tables with one command each:

```bash
plotipus line --datafile Distributions -x Bin -y Counts --hue Sample --data_hue Data --lower ratio
plotipus run paper          # every command in input/plots/paper_scripts.txt
```

## Getting started

```bash
pipx install git+https://github.com/mantheys/plotipus.git   # Python ≥ 3.10
git clone https://github.com/mantheys/plotipus.git && cd plotipus/examples/mascot
python make_mascot.py        # input/data/Mascot.pkl: 97 shapes, one row each
plotipus run mascot          # five figures in output/plots, from points to the mascot above
```

The [tutorial](docs/tutorial.md) builds the mascot up one command at a time.
Then try the example project, common physics distributions as histograms,
fits, data/simulation comparisons and maps:

```bash
cd ..                        # examples/
python make_data.py          # toy pickles in input/data
plotipus run example         # figures in output/plots (--tables for the LaTeX tables)
```

`plotipus init my_project` creates an empty project (`plotipus.toml`,
`input/{data,plots,tables}`, `output/`). To work on plotipus itself, see
[Contributing](CONTRIBUTING.md).

## Your own data

plotipus reads pickled pandas DataFrames from `input/data/` (the project's
data root): `--datafile Spectrum` loads `input/data/Spectrum.pkl`. The
convention is one row per series, with binned quantities as arrays in the
cells:

```python
import numpy as np
import pandas as pd

x = np.arange(0.25, 10, 0.5)                     # bin centres (GeV)
expected = 200 * np.exp(-x / 3)                  # the simulation's prediction
observed = np.random.default_rng(1).poisson(expected)

pd.DataFrame([
    {"Sample": "Simulation", "Energy": x, "Counts": expected, "CountsError": 0.05 * expected},
    {"Sample": "Data",       "Energy": x, "Counts": observed},
]).to_pickle("input/data/Spectrum.pkl")
```

| Sample | Energy | Counts | CountsError |
|---|---|---|---|
| Simulation | [0.25, 0.75, …, 9.75] | [184.0, 155.8, …] | [9.2, 7.8, …] |
| Data | [0.25, 0.75, …, 9.75] | [184, 149, …] | — |

```bash
plotipus line --datafile Spectrum -x Energy -y Counts --hue Sample --data_hue Data --errory --lower ratio
```

- `-x`, `-y` name the columns to draw; `--hue` names the column that splits
  the rows into series (one colour each); `--data_hue Data` marks the data
  rows, drawn as points.
- Errors live next to the value: `{y}Error` (symmetric) or `{y}Error+` and
  `{y}Error-` (asymmetric). A row without them gets the standard interval
  where one applies: the data here are counts, so they get Poisson
  (Garwood) intervals.
Scalar rows, file prefixes and what else a pickle may hold are in the
[style guide](docs/styleguide.md#f-data-conventions).

## Media and styles

One command list renders for every medium at the size it is shown at:
slides first, then a paper column or the web, with no change to the
commands. File names stay the same in every folder, so a LaTeX
`\includegraphics` only changes its directory.

```toml
# plotipus.toml
[project]
medium = "slides"             # what plotipus run draws by default
media = ["slides", "paper"]   # what --medium all draws
style = ["config/style.json"] # your own style files on top
```

```bash
plotipus run analysis                  # slides, in output/plots/
plotipus run analysis --medium paper   # the same figures for the paper, in output/plots/paper/
plotipus run analysis --theme dark     # dark slides, in output/plots/slides-dark/
```

| style | look | size and type |
|---|---|---|
| `slides` (default) | ticks in on four sides, no grid, frameless legends, Petroff-10 colours | 8 × 5.84 in, 14 pt sans |
| `slides-dark` | the same on `#1b1d22`, with lightened twins of the darkest colours | 8 × 5.84 in, 14 pt sans |
| `paper`, `paper-dark` | no titles (the caption is the title) | a 3.4 in column, 8 pt Computer Modern; save as PDF |
| `open`, `open-dark` | L-shaped frame, ticks out, a faint y grid | 8 in at 96 dpi, 12 pt sans |
| `classic` | plotipus before the redesign ([changelog](CHANGELOG.md)) | 8 × 6 in |

![The ratio example in every style](docs/design/styles/compare/02_ratio.png)

Sizes, layers, experiment headers and watermarks: [Projects](docs/projects.md#styles-media-and-themes).

## Famous plots

Famous figures from particle physics, cosmology, astronomy and climate
science, redrawn by plotipus in the paper style from public data or values
read from the published figures. Their data, commands and remaining gaps
are in [examples/famous](examples/famous/README.md); the
[style guide](docs/styleguide.md#before-and-after-famous-figures) redraws
five of them with plotipus's defaults, side by side.

<p align="center">
  <a href="https://arxiv.org/abs/1207.7214"><img src="docs/images/famous/higgs-diphoton.png" width="32%" alt="Diphoton mass spectrum with the Higgs boson bump, a signal plus background fit and the data minus background"></a>
  <a href="https://arxiv.org/abs/1207.7235"><img src="docs/images/famous/four-lepton.png" width="32%" alt="Four-lepton mass: data points over stacked Z+X, ZZ and Higgs signal histograms"></a>
  <a href="https://arxiv.org/abs/1207.7214"><img src="docs/images/famous/local-p0.png" width="32%" alt="Local p-value against the Higgs mass, observed and expected with a ±1σ band and σ lines"></a>
  <br><sub><a href="https://arxiv.org/abs/1207.7214">H→γγ, ATLAS 2012</a> · <a href="https://arxiv.org/abs/1207.7235">H→ZZ*→4ℓ, CMS 2012</a> · <a href="https://arxiv.org/abs/1207.7214">local p₀, ATLAS 2012</a></sub><br><br>
  <a href="https://arxiv.org/abs/1207.7214"><img src="docs/images/famous/brazil-band.png" width="32%" alt="Observed and expected 95% CL limits on the signal strength with green and yellow ±1σ/±2σ bands"></a>
  <a href="https://arxiv.org/abs/hep-ex/0509008"><img src="docs/images/famous/z-lineshape.png" width="32%" alt="Hadronic cross section at the Z peak with curves for two, three and four neutrino species"></a>
  <a href="https://arxiv.org/abs/0801.4589"><img src="docs/images/famous/kamland.png" width="32%" alt="Reactor antineutrino survival probability against L/E with the oscillation expectation"></a>
  <br><sub><a href="https://arxiv.org/abs/1207.7214">Brazil band, ATLAS 2012</a> · <a href="https://arxiv.org/abs/hep-ex/0509008">Z lineshape, LEP 2006</a> · <a href="https://arxiv.org/abs/0801.4589">neutrino oscillation, KamLAND 2008</a></sub><br><br>
  <a href="https://arxiv.org/abs/astro-ph/9805201"><img src="docs/images/famous/omega-contours.png" width="32%" alt="Confidence regions in the matter and dark-energy densities with deceleration and geometry lines"></a>
  <a href="https://doi.org/10.1073/pnas.15.3.168"><img src="docs/images/famous/hubble-1929.png" width="32%" alt="Velocity against distance of 24 nebulae and 9 groups with Hubble's two fitted lines on his grid"></a>
  <a href="https://arxiv.org/abs/1804.09378"><img src="docs/images/famous/hr-diagram.png" width="32%" alt="Hertzsprung-Russell diagram of 66 million Gaia DR2 stars on a square-root colour scale"></a>
  <br><sub><a href="https://arxiv.org/abs/astro-ph/9805201">Ω<sub>M</sub>–Ω<sub>Λ</sub>, Riess et al. 1998 (Union2.1 data)</a> · <a href="https://doi.org/10.1073/pnas.15.3.168">Hubble 1929 (real data)</a> · <a href="https://arxiv.org/abs/1804.09378">HR diagram, Gaia DR2 2018 (real data)</a></sub><br><br>
  <a href="https://gml.noaa.gov/ccgg/trends/"><img src="docs/images/famous/keeling.png" width="32%" alt="Monthly atmospheric CO2 at Mauna Loa since 1958 with the deseasonalised trend"></a>
  <a href="https://doi.org/10.1029/1999GL900070"><img src="docs/images/famous/hockey-stick.png" width="32%" alt="Northern Hemisphere temperature reconstruction since AD 1000 with its uncertainty band and the instrumental record"></a>
  <a href="https://ui.adsabs.harvard.edu/abs/1985ApJ...295..305V"><img src="docs/images/famous/ngc3198.png" width="32%" alt="Rotation curve of the galaxy NGC 3198: flat HI data explained by disk, gas and dark halo components"></a>
  <br><sub><a href="https://gml.noaa.gov/ccgg/trends/">Keeling curve, NOAA (real data)</a> · <a href="https://doi.org/10.1029/1999GL900070">hockey stick, Mann et al. 1999 (real data)</a> · <a href="https://ui.adsabs.harvard.edu/abs/1985ApJ...295..305V">dark halo of NGC 3198, van Albada et al. 1985 (SPARC data)</a></sub><br><br>
</p>

> Recreations made to demonstrate plotipus, not the original figures or
> official results; cite the originals, linked from each image. Sources and
> licences: [examples/famous/data](examples/famous/data/README.md).

## Gallery

`make -C examples gallery` draws one example for every working row of the
[chart catalogue](docs/design/catalogue.md), for slides and paper, on the page
`examples/gallery/output/gallery.md` ([more](examples/gallery/README.md)).

## Plot kinds

Kinds follow the data relationship (as in seaborn/plotly), not the use case.

| Kind | Draws | Typical options |
|---|---|---|
| `line` | y against an ordered x, one series per `--hue` value | `--plot_type`, `--data_hue`, `--lower`, `--stacked`, `--fit`, `--binned`, `--facet_row`/`--facet_col`, `--inset` ([options](docs/options.md#data-and-simulation)) |
| `scatter` | observations with colour/size/marker encodings, or pairs of metrics | `--colorby`, `--sizeby`, `--markerby` ([options](docs/options.md#categories-and-scatter)) |
| `hist` | 1D histograms of per-event arrays | `--bins`, `--weight`, `--density` ([options](docs/options.md#histograms)) |
| `map` | 2D histograms, images of a grid, contours | `--norm`, `--logz`, `--contour` ([options](docs/options.md#contours)) |
| `cat` | one value per category | `--integrate_over`, `--kind point\|line\|lollipop\|bar`, `--orient h`, `--sort` ([options](docs/options.md#categories-and-scatter)) |
| `table` | aggregated values as LaTeX (and HTML) tables | `--variables`, `--agg`, `--stats`, `--fit_params`, `--siunitx` |

Every kind also takes `--text X Y 'TEXT'` (with `--arrow X2 Y2`) and `--region 'x,y x,y ...'` annotations
(see [Shared options](docs/options.md#shared-options)).

`plotipus <kind> --help` lists every option. Figures are saved as PNG at
300 dpi; for papers use `--format pdf` (vector, at the printed size).

## Further reading

* [Tutorial](docs/tutorial.md): draw the mascot, from its points to the
  finished figure, one command at a time.
* [Famous plots](examples/famous/README.md): the reproductions above, their
  data, commands and remaining gaps.
* [Gallery](examples/gallery/README.md): one figure per chart-catalogue row.
* [Style guide](docs/styleguide.md): the conventions plotipus applies by
  default (data, simulation, fits, sizes, uncertainties) and those it does
  not enforce yet.
* [Options](docs/options.md): shared options, lower panels, colorbars,
  contours and binned estimators.
* [Projects](docs/projects.md): `plotipus.toml`, style files, plugins and
  command lists.
* [Python](docs/python.md): using plotipus from Python code.
* [Contributing](CONTRIBUTING.md): development install, tests and
  regenerating the examples.

## License

MIT
