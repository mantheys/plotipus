# T22 Breadth backlog

**Wave 8 · depends on: T16 (new defaults), plus each item's own dependencies**

Each item below is small enough for one session. Start a session with:

> Read `docs/design/tasks/00-README.md` and item T22.N in
> `docs/design/tasks/T22-backlog.md`, then implement it on branch
> `task/T22-N-<name>`.

Every item follows the common rules and definition of done in
[00-README.md](00-README.md), and updates its catalogue rows. Items in
different kinds can run in parallel. Struck through: done.

| item | option(s) | kind / files | catalogue | effort |
|---|---|---|---|---|
| T22.1 | `cat --orient h`, `--sort asc\|desc`, `--stacked`, `--kind lollipop` | `kinds/cat.py` | D4–D7, F6 | M |
| T22.2 | `cat --kind box\|violin\|strip`: array cells kept as distributions (not integrated) | `kinds/cat.py` | A10 | M |
| ~~T22.3~~ | ~~`map --annotate [FMT]`; string x/y become categorical ticks; `--norm` for `-z` grids; y inverted for matrices (`--matrix`)~~ | ~~`kinds/map.py`~~ | ~~D8, F5~~ | ~~S~~ |
| T22.4 | `hist --hist_type kde\|ecdf` (`--bw`), `--cumulative`, `--rug`, `--ridge [OVERLAP]` | `kinds/hist.py` | A7, A8, A11, A12 | M |
| ~~T22.5~~ | ~~`--hue_cmap CMAP` for numeric or ordered hues: a colorbar instead of a legend (the T01 overflow warning points here)~~ | ~~`encodings.py`, `kinds/line.py`, `kinds/hist.py`~~ | ~~C10~~ | ~~S~~ |
| T22.6 | `--sharex/--sharey` for every kind; `--facet_row COL --facet_col COL` | `panels.py`, every kind's panel loop | H2, H3 | M |
| T22.7 | `--inset X0 X1 [Y0 Y1] --inset_pos x y w h`: zoom of the same series, with a connector box | `panels.py`, `plot.py` | H5 | M |
| ~~T22.8~~ | ~~`--text X Y 'TEXT' [--arrow X2 Y2]` (repeatable), `--region 'x,y x,y …' [--region_hatch]`, `--contour_labels`, `--direct_labels`~~ | ~~`plot.py`, `panel_lines.py`, `kinds/map.py`~~ | ~~I5, I6, I8, I9~~ | ~~M~~ |
| T22.9 | `map --map_type hexbin`; `map --corner X1 X2 X3` (N×N grid, `hist` on the diagonal) | `kinds/map.py` | B5, B8 | M |
| ~~T22.10~~ | ~~`--smooth N [--smooth_kind rolling\~~ | ~~savgol]`; datetime x with `ConciseDateFormatter`~~ | ~~`kinds/line.py`, `transforms.py`~~ | ~~C8, C9~~ | ~~S~~ |
| T22.11 | `table --agg std\|median\|corr`, `--cutflow`, `--fit_params` | `kinds/table.py` | J5–J7 | M |
| ~~T22.12~~ | ~~`--lower_plot_type bar` for `column:` lower panels (calibration counts)~~ | ~~`kinds/line.py`~~ | ~~F4~~ | ~~S~~ |
| ~~T22.13~~ | ~~`hist --overlay_gaussian` (unit normal over a pull distribution)~~ | ~~`kinds/hist.py`~~ | ~~E8~~ | ~~S~~ |
| ~~T22.14~~ | ~~`--lower residual:COMPONENT` (residual against one component of a stored fit)~~ | ~~`kinds/_fit.py`, `lower.py`~~ | ~~E6~~ | ~~S~~ |
| ~~T22.15~~ | ~~`--reference` accepts a hue value as well as an index (the most common stumble)~~ | ~~`kinds/line.py`~~ | — | ~~S~~ |

Postponed items (polar, geographic, flow, hybrid or broken axes, secondary
axes) are in [../TODO.md](../TODO.md).
