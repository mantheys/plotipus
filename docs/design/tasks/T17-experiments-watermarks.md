# T17 Experiment presets and watermarks

**Wave 6 · effort M · risk low · depends on: T16**

## Goal

Every medium (slides, paper, web) can carry an experiment's look and header
label, and an optional status watermark ("Work In Progress", "Preliminary",
…). Decision D1, last point.

## Read first

- [research.md Part 1 §2.9](../research.md#part-1-default-styles-of-plotting-engines):
  mplhep's experiment styles and `exp_label`.
- [catalogue.md row I4](../catalogue.md).
- The figure-hook mechanism in the README (Plugins); it stays for logos.

## Scope

- New `src/plotipus/header.py`.
- New `src/plotipus/data/styles/experiments/*.json` (and `.mplstyle` where
  an experiment changes fonts or ticks).
- `args.py`: common options.
- `panels.py` and `plot.py`: call the header before the layout pass, using
  T13's hook.
- Tests: a new `tests/test_header.py`.

## Required behaviour

1. **Header label**, drawn above the axes on the left, with the right-hand
   text on the right:
   - `--label TEXT`: e.g. the experiment name, bold.
   - `--label_status TEXT`: e.g. "Preliminary", regular or italic per
     preset.
   - `--label_right TEXT`: e.g. "13.6 TeV, 140 fb$^{-1}$" or the detector
     configuration.
   - The same keys can be set in style.json `"header": {...}` and in
     `plotipus.toml`, so a whole project gets them.
   - The layout (T13) reserves room for the header.
2. **Experiment presets** (`--experiment NAME` or style name
   `experiment-NAME`), layered on top of the medium and theme:
   - Start with `atlas`, `cms`, `lhcb`, `alice` and `dune`. Add others
     (`belle2`, `icecube`, `lz`, …) only with a cited style guide.
   - A preset sets the label text and its typography, and optionally fonts,
     tick lengths and palette, when the experiment's public guidelines or
     mplhep's implementation specify them. Cite the source in the preset
     file.
   - CMS's palette guideline may be behind a login; mplhep's CMS style uses
     Petroff-6.
   - Check whether mplhep (or an official DUNE plot-style repository) has a
     DUNE style before inventing one. Anything you cannot verify gets a
     `"_unverified": [...]` note in the preset file and a mention in the PR.
   - Text only: no logos or trademarked artwork. Logos can be added by
     projects through the figure hook.
3. **Watermark**, `--watermark TEXT`:
   - Presets: `wip` → "Work In Progress", `preliminary`, `internal`,
     `simulation`, `draft`.
   - `--watermark_style corner|diagonal`. `corner` (default) puts it inside
     the axes under the header in the `muted` role. `diagonal` draws large
     faint text across the axes at `faint` alpha, behind the data.
   - It can be set per project (`plotipus.toml`) and removed per command
     with `--watermark none`.
   - With `--medium paper`, print a reminder when a watermark is still on.
4. **Combinations.** Presets combine with every medium and theme: the header
   size follows the medium's font sizes, and its colours follow the roles.

## Tests

- `--experiment atlas --label_status Internal` draws "ATLAS" in the
  preset's font with "Internal" next to it, and the header box sits inside
  the figure and above the axes.
- `--watermark wip --watermark_style diagonal` adds a text artist with
  zorder below the data.
- Every preset file loads, and the `_unverified` entries are listed by a
  test helper.

## Done when

The common definition of done is met. The comparison sheets include
`slides + atlas + wip` and `paper + dune + preliminary` renders of examples
01 and 03.
