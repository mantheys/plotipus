# Task briefs

Each `Txx-*.md` file is a self-contained brief for one agent session (or one
person). The briefs implement [../roadmap.md](../roadmap.md) under the
maintainer's decisions (roadmap § "Decisions").

## How to start a session

Paste this, replacing the id and name:

> Read `docs/design/tasks/00-README.md` and `docs/design/tasks/T05-scatter-hue.md`,
> then implement T05 on a new branch `task/T05-scatter-hue`. Follow the
> brief's scope and definition of done, and finish with a summary and a
> PR description.

The session only needs the brief and the documents it links to. It does
not need the conversation that produced them.

## Order and parallelism

The order is set by which files each task edits, not by task size. Tasks in
the same wave touch disjoint files and can run in parallel sessions, each
on its own branch (or `git worktree`). A task can start when the tasks it
depends on are merged.

| wave | tasks (parallel within a wave) | why this order |
|---|---|---|
| 0 | ~~merge `design/examples-and-style` into `main`~~ | every brief links into `docs/design/` |
| 1 | ~~**T01** colour allocator and palettes~~ | touches every kind; everything else conflicts with it |
| 2 | ~~T02 contours~~ · ~~T03 estimator errors~~ · ~~T04 hist~~ · ~~T05 scatter hue~~ · T06 fit pull · ~~T07 error display~~ · T08 cat · **T24** famous-plot data (no `src/` changes; can start at wave 0) | disjoint files |
| 3 | ~~T09 map colorbars (after T02)~~ · ~~T10 box plots (after T03, T07)~~ · ~~T11 style infrastructure~~ | T09 shares `map.py` with T02; T11 edits colours in every kind |
| 4 | ~~T12 ticks and output~~ → T13 measured layout | both edit `plot.py`/`panels.py`; in sequence |
| 5 | T14 media, widths and themes → T15 legends | both build on T13's layout |
| 6 | T16 ship the styles → T17 experiments and watermarks | the new defaults land here |
| 7 | T18 stacking/overlay → T19 Poisson/CP errors · T21 series type → T20 bands and σ lines | the HEP essentials; T18–T21 all edit `line.py`/`plot.py`, so overlap them only with care |
| 8 | T22 backlog items (each item can be its own session) · T23 examples gallery (grows from wave 2 on) | breadth |

```
T̶0̶1̶ ─┬─ T̶0̶2̶ ── T̶0̶9̶
     ├─ T̶0̶3̶ ─┐
     ├─ T̶0̶7̶ ─┴─ T̶1̶0̶
     ├─ T̶0̶4̶, T̶0̶5̶, T06, T08
     └─ T̶1̶1̶ ── T̶1̶2̶ ── T13 ── T14 ── T15 ── T16 ── T17
                                         └── T18 ── T19, T21 ── T20 ── T22 …
T24 (independent; open until the famous plots match)   T23 (incremental, after wave 2)
```

Struck through: done and merged into `main`.

## Rules for every task

- **Base.** Branch from the latest `main`. Branch name: `task/Txx-short-name`.
- **Git identity.** Git on this machine has no user identity configured, so
  commits fail until one is set. Set it with `git config user.name` /
  `git config user.email` before starting.
- **Scope.**
  - Edit only the files the brief lists.
  - If another file must change, keep the change minimal and say why in the
    PR description.
  - Do not reformat code you are not changing.
  - Match the surrounding style: comment density, naming, the `rprint`
    warnings.
- **Compatibility.**
  - No CLI option is removed or renamed. Changed behaviour gets an option
    that restores the old one, unless the old behaviour was a plain bug
    (e.g. dropped series).
  - Behaviour changes are listed in the PR description under "Behaviour
    changes"; T16 compiles them into release notes.
  - Command lines translated from the legacy scripts (`legacy.py`,
    `plotipus translate`) keep producing the same output file names.
- **Reproduce first.** Run the bug's command from
  [../repro/repro_scripts.txt](../repro/repro_scripts.txt)
  (`cd docs/design/repro && python make_data.py && plotipus run repro`)
  and look at the PNG before changing code. Look at it again afterwards.
- **Tests.**
  - Add tests in `tests/` that assert on matplotlib artists (line colours,
    contour levels, error arrays, legend texts, colorbar labels), not on
    pixels.
  - Follow `tests/conftest.py` and the existing `test_<kind>.py` files.

## Definition of done (all tasks)

1. The brief's required behaviour is implemented, with tests.
2. `pytest` passes.
3. `make -C examples` runs without errors, and every changed figure has been
   opened and looked at.
4. The reproduction for the task's bugs (`plotipus run repro`, the `*_Bnn.png`
   outputs) shows the fix.
5. For visual changes, `python docs/design/styles/render.py` is re-run and
   the sheets in `docs/design/styles/compare/` are committed.
6. Documentation is updated:
   - `README.md` options and `--help` texts for new options;
   - in [../bugs.md](../bugs.md), a "**Fixed in Txx.**" line under each
     fixed bug;
   - in [../catalogue.md](../catalogue.md), the status of the rows the task
     moves (✗/◐ → ✅) and the summary counts.
7. The PR description has: summary, behaviour changes, the restore option
   for each change, tests added, and before/after image paths.

## Index

| id | title | wave | effort | risk |
|---|---|---|---|---|
| ~~[T01](T01-color-allocator-palettes.md)~~ | ~~Colour allocator and named palettes~~ | 1 | M | med |
| ~~[T02](T02-contours.md)~~ | ~~Readable, correct confidence contours~~ | 2 | M | high |
| ~~[T03](T03-estimator-uncertainty.md)~~ | ~~Uncertainties for binned estimators~~ | 2 | M | med |
| ~~[T04](T04-hist.md)~~ | ~~`hist` edges, range and labels~~ | 2 | S | low |
| ~~[T05](T05-scatter-hue.md)~~ | ~~`scatter --hue` keeps every group~~ | 2 | S | low |
| [T06](T06-fit-pull.md) | `--fit` lower panel: residual and pull | 2 | S | low |
| ~~[T07](T07-error-display.md)~~ | ~~Bands for every plot type; points not joined~~ | 2 | S | med |
| [T08](T08-cat.md) | `cat` fixes | 2 | S | low |
| ~~[T09](T09-map-colorbars.md)~~ | ~~Shared, labelled colorbars~~ | 3 | M | low |
| ~~[T10](T10-box-plots.md)~~ | ~~Box plots~~ | 3 | S | low |
| ~~[T11](T11-style-infrastructure.md)~~ | ~~`mplstyle` key and colour roles~~ | 3 | M | low |
| ~~[T12](T12-ticks-and-output.md)~~ | ~~Tick labels and output resolution~~ | 4 | S | low |
| [T13](T13-measured-layout.md) | Measured layout | 4 | L | med |
| [T14](T14-media-widths-themes.md) | Media (slides/paper/web), widths, themes | 5 | L | med |
| [T15](T15-legends.md) | Legends that never cover data | 5 | M | med |
| [T16](T16-ship-styles.md) | Ship the styles; `classic` for compatibility | 6 | M | high |
| [T17](T17-experiments-watermarks.md) | Experiment presets and watermarks | 6 | M | low |
| [T18](T18-stacking-overlay.md) | Stacked simulation with overlaid data | 7 | M | med |
| [T19](T19-poisson-cp-errors.md) | Poisson and Clopper–Pearson intervals in plots | 7 | M | low |
| [T20](T20-bands-sigma-lines.md) | Nested bands, Brazil plots, σ lines | 7 | M | low |
| [T21](T21-series-type.md) | Per-series plot type | 7 | S | low |
| [T22](T22-backlog.md) | Breadth backlog (one session per item) | 8 | — | low |
| [T23](T23-examples-gallery.md) | New examples and gallery | 2→8 | M | low |
| [T24](T24-famous-plots-data.md) | Synthetic datasets for famous plots | 0→ | M | none |
