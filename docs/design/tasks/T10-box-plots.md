# T10 Box plots

**Wave 3 · effort S · risk low · depends on: T03, T07 · parallel with T09, T11**

## Goal

`line --binned --plot_type box` gives readable box plots per bin and per
hue.

## Read first

[bugs.md B16](../bugs.md#b16-box-plots) (reproduce with the `B16` command).

## Scope

- `src/plotipus/plot.py`: the `boxplot` branch (line ~855).
- `src/plotipus/kinds/_estimator.py`: where box data per bin is assembled.
- Tests: `tests/test_line_estimator.py`.

## Required behaviour

1. **Dodging.** Hue groups are dodged within each bin: width
   0.8 × bin width / n_hues, centred on the bin.
2. **Box colours.**
   - Edge and median line in the hue colour (T01 allocator).
   - Face at alpha 0.25 of the same colour.
   - Fliers as small hollow markers in the hue colour.
3. **Ticks.**
   - Ticks are numeric, at the bin centres, with the axis formatter (not
     printed positions with many decimals). For categorical x, use the
     category labels.
   - `--box_tick_labels {centres,ranges}` shows "[a, b)" ranges.
4. **Legend.** One entry per hue (a `Patch` in the hue colour). No "Median
   …" entries.
5. **Whiskers.** `--whis` passes through to matplotlib (default 1.5).

## Tests

- 3 hues × 12 bins give 36 boxes with 3 distinct x offsets per bin.
- The legend has 3 entries.
- The tick label texts are short numbers.

## Done when

The common definition of done is met, and the B16 repro is inspected.
