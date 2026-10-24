# T04 `hist` edges, range and labels

**Wave 2 · effort S · risk low · depends on: T01 · parallel with T02, T03, T05–T08**

## Goal

1D histograms show every bin at full width and every sample in full, and
add no spurious legend.

## Read first

[bugs.md B09](../bugs.md#b09-hist-edge-bins-range-and-label).

## Scope

- `src/plotipus/kinds/hist.py`.
- Tests: `tests/test_hist.py`.

## Required behaviour

1. **Drawing.** Draw with `ax.stairs(counts, edges)` (linestyle, colour and
   label as before), not with `steps-mid` on bin centres.
2. **Range.**
   - Compute it once per panel, over all hue values drawn in that panel.
   - `--rangex`, `--percentile` and `--panel_rangex` keep their precedence.
   - Pass the same edges to every hue.
3. **Overflow.**
   - `--flow {none,hint,show}`, default `none`.
   - `hint`: a small marker beyond the last edge when values fall outside
     the range (mplhep's `flow="hint"`).
   - `show`: add the under- and overflow counts to the first and last bins.
   - In every mode, print the number of entries outside the range.
4. **Legend.** No legend for a single series without `--hue`. Never use the
   label "None".
5. **Colours.** Colours come from the T01 allocator.

## Backwards compatibility

The outlines change shape at the outer bins, which is the fix. File names
are unchanged.

## Tests

- A flat sample with 10 bins: the drawn outline spans exactly
  [edge0, edge10].
- Two hues with disjoint ranges: both are fully inside the drawn range.
- No legend without `--hue`.
- `--flow show` puts the outside counts into the edge bins.

## Done when

The common definition of done is met, and the B09a/B09b repro images are
inspected.
