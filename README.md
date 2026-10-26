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

## Install

```bash
# use the CLI
pipx install git+https://github.com/mantheys/plotipus.git

# development
git clone https://github.com/mantheys/plotipus.git && cd plotipus
python3 -m venv .venv && source .venv/bin/activate   # Debian/Ubuntu: apt install python3-venv
pip install -e ".[dev]"
pytest                                               # run the tests
```

Python ≥ 3.10; depends on numpy, pandas, matplotlib, scipy, rich and jinja2.

## Quick start

Your first plot is the mascot above. It is a DataFrame of 97 shapes, one row
each, drawn by `plotipus line`:

```bash
cd examples/mascot
python make_mascot.py        # input/data/Mascot.pkl
plotipus run mascot          # five figures in output/plots, from points to the finished mascot
```

The [tutorial](docs/tutorial.md) builds it up one command at a time. Then,
from the repository root, try the example project: common physics
distributions as histograms, fits, data/simulation comparisons and maps:

```bash
cd examples
python make_data.py          # toy pickles in input/data
plotipus run example         # figures in output/plots
plotipus run example --tables
```

To regenerate the examples from scratch after a change (`examples/Makefile`;
it uses `.venv/bin/python` when present):

```bash
make -C examples             # delete generated data and outputs, then rebuild all
make -C examples clean       # only delete them (input/data/*.pkl, output/)
make -C examples plots       # rebuild data and plots without deleting first
make -C examples docs        # re-render the figures of docs/options.md
make -C examples mascot      # re-render the mascot and the tutorial figures
```

`plotipus init my_project` creates an empty project (`plotipus.toml`,
`input/{data,plots,tables}`, `output/`).

## Famous plots

Famous figures from particle physics, cosmology, astronomy and climate
science, redrawn by plotipus from datasets built to match the
originals: public data where it exists (Gaia, NOAA, SPARC, LIGO, Hubble's
table), values read back from the published figures' vector graphics for the
Higgs, KamLAND and LEP plots, and synthetic data only for the 1912-1913 tables. Each
one was compared with the published figure. The data generators, the
commands and what is still missing are in
[examples/famous](examples/famous/README.md); `make -C examples famous`
renders them all and refreshes these images. The images use the paper
style: serif text, a 3.5 in column width and one figure size for all.

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
  <a href="https://doi.org/10.1073/pnas.15.3.168"><img src="docs/images/famous/hubble-1929.png" width="32%" alt="Velocity against distance of 24 nebulae with Hubble's two fitted lines"></a>
  <a href="https://arxiv.org/abs/1804.09378"><img src="docs/images/famous/hr-diagram.png" width="32%" alt="Hertzsprung-Russell diagram of 66 million Gaia DR2 stars on a square-root colour scale"></a>
  <br><sub><a href="https://arxiv.org/abs/astro-ph/9805201">Ω<sub>M</sub>–Ω<sub>Λ</sub>, Riess et al. 1998 (Union2.1 data)</a> · <a href="https://doi.org/10.1073/pnas.15.3.168">Hubble 1929 (real data)</a> · <a href="https://arxiv.org/abs/1804.09378">HR diagram, Gaia DR2 2018 (real data)</a></sub><br><br>
  <a href="https://gml.noaa.gov/ccgg/trends/"><img src="docs/images/famous/keeling.png" width="32%" alt="Monthly atmospheric CO2 at Mauna Loa since 1958 with the deseasonalised trend"></a>
  <a href="https://doi.org/10.1029/1999GL900070"><img src="docs/images/famous/hockey-stick.png" width="32%" alt="Northern Hemisphere temperature reconstruction since AD 1000 with its uncertainty band and the instrumental record"></a>
  <a href="https://ui.adsabs.harvard.edu/abs/1985ApJ...295..305V"><img src="docs/images/famous/ngc3198.png" width="32%" alt="Rotation curve of the galaxy NGC 3198: flat HI data explained by disk, gas and dark halo components"></a>
  <br><sub><a href="https://gml.noaa.gov/ccgg/trends/">Keeling curve, NOAA (real data)</a> · <a href="https://doi.org/10.1029/1999GL900070">hockey stick, Mann et al. 1999 (real data)</a> · <a href="https://ui.adsabs.harvard.edu/abs/1985ApJ...295..305V">dark halo of NGC 3198, van Albada et al. 1985 (SPARC data)</a></sub><br><br>
</p>

## Plot kinds

Kinds follow the data relationship (as in seaborn/plotly), not the use case.

| Kind | Draws | Typical options |
|---|---|---|
| `line` | y against an ordered x, one series per `--hue` value, line style per `--style` value | `--plot_type step\|stepmid\|line\|errorbar\|plot\|bar\|barh\|box\|fill` (closed shapes, with `--color_column`, `--edgecolor_column`, `--linewidth_column`, `--plot_type_column`, `--axis equal off`; see the [tutorial](docs/tutorial.md)), `--lower`, `--stacked`, `--data_hue` (see [Data and simulation](docs/options.md#data-and-simulation)), `--sum_iterables`, `--merge_iterables`, `--rebin`, `--by_config`, `--fit` (see [Fits](docs/options.md#fits)), `--binned --estimator mean\|median\|std\|rms\|sum\|max\|min` (see [Binned estimators](docs/options.md#binned-estimators)) |
| `scatter` | observations: exploded points with colour/size/marker encodings, or pairs of metrics (`--x_from Variable=Purity --y_from Variable=Completeness`) | `--colorby`, `--sizeby`, `--markerby`, `--aggregate` |
| `hist` | 1D histograms of per-event arrays | `--bins`, `--weight`, `--density`, `--hist_combine`, `--flow none\|hint\|show` |
| `map` | 2D: histogram of point arrays, image of a grid (`-z`), contour layer (`--contour`) | `--norm`, `--diagonal`, `--logz`, `--colorbar`, `--contour_sigmas`, `--contour_dof`, `--contour_label`, `--fill_contours`, `--background`, `--no_best_fit` |
| `cat` | one value per category (integrated arrays, or one scalar per row) | `--integrate_over`, `--kind point\|line\|bar`, `--xtick_rotation` |
| `table` | aggregated values as LaTeX (and HTML) tables | `--variables`, `--agg`, `--error_band`, `--clopper_pearson`, `--siunitx`, `--caption_file` |

`plotipus <kind> --help` lists every option. Figures are saved as PNG at
300 dpi; for papers use `--format pdf` (vector, at the printed size).

## Further reading

* [Tutorial](docs/tutorial.md): draw the mascot, from its points to the
  finished figure, one command at a time.
* [Famous plots](examples/famous/README.md): the reproductions above, their
  data, commands and remaining gaps.
* [Options](docs/options.md): shared options, lower panels, colorbars,
  contours and binned estimators.
* [Projects](docs/projects.md): `plotipus.toml`, style files, plugins and
  command lists.
* [Python](docs/python.md): using plotipus from Python code.

## License

MIT
