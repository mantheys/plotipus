# T09 Shared, labelled colorbars

**Wave 3 · effort M · risk low · depends on: T02 (same file) · parallel with T10, T11**

## Goal

Every colorbar is labelled. Panels showing the same quantity share one
colour scale and one colorbar. Empty bins look empty.

## Read first

- [bugs.md B08](../bugs.md#b08-2d-histogram-colorbars).
- [style_spec.md §2.9](../style_spec.md): colorbars.

## Scope

- `src/plotipus/kinds/map.py`: the 2D-histogram and `-z` image paths
  (`draw_figure` around lines 200–290) and `draw_background`.
- `src/plotipus/kinds/scatter.py`: the `--colorby` colorbar (line ~516), for
  consistent sizing.
- Tests: `tests/test_map.py`.

## Required behaviour

1. **Labels.** Every colorbar gets its label: `--labelz`, else the norm
   label, else "Counts" or "Density", else the `-z` column label. Fix the
   label being set only after the loop.
2. **Shared colorbar.**
   - `--colorbar {shared,each}`, default `shared` when all panels show the
     same quantity. That is always the case for one `map` command, except
     with `--norm` per panel.
   - Shared means one norm with `vmin`/`vmax` over all panels and one
     colorbar to the right of the row (`fig.colorbar(mappable, ax=axes)`).
   - `each` keeps per-panel bars, each labelled.
3. **Log scales.** With `--logz`, `vmin` is the smallest non-zero bin.
   Empty bins are transparent (`set_bad`/masked), not the darkest colour.
4. **Linear count scales.** Empty bins are also masked; this is already
   partly done, so make it consistent.
5. **Colorbar geometry.** The colorbar is as tall as its axes and 4% of
   their width, with 2% padding. The scatter `--colorby` colorbar follows
   the same geometry.

## Backwards compatibility

`--colorbar each` restores per-panel bars, which are now labelled.

## Tests

- The B08 command gives one colorbar with the label "Counts", and both
  panels' mappables share one norm.
- `--colorbar each` gives two labelled colorbars.
- With `--logz`, zero bins are masked.

## Done when

The common definition of done is met. The B08 repro and example 06 are
inspected, and the sheet `compare/06_hist2d.png` is updated.
