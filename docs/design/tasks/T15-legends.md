# T15 Legends that never cover data

**Wave 5 · effort M · risk med · depends on: T13, T14 · before T16**

## Goal

A legend never sits on data, including filled bars, bands and filled
contours. Entries are ordered like the data. Redundant legends disappear.

## Read first

- [bugs.md B06](../bugs.md#b06-legends-cover-data).
- [style_spec.md §2.7](../style_spec.md): legends.
- [research.md Part 2 §3](../research.md#part-2-common-complaints): legend
  complaints.
- In the code: `plot.py` (`sample_axes_data_points`,
  `sample_axes_drawn_points`, `apply_legend_style_clear_of_data`,
  `apply_legend_style_free`, `_legend_obstruction_score`) and
  `encodings.py` (`draw_legends`).

## Scope

- `plot.py`, `encodings.py`.
- Remove the hard-coded locations in `kinds/line.py:976–979` (stacked).
  The `cat` location was removed in T08.
- The lower-panel legend in `kinds/line.py` (`_finish_lower`, line 874).
- Tests: a new `tests/test_legends.py`.

## Required behaviour

1. **Occupancy.**
   - Render the axes once to an occupancy mask: an Agg buffer of the
     axes with only data artists visible, thresholded at alpha > 0.
   - Score candidate legend boxes by the fraction of occupied pixels they
     cover.
   - Filled patches, `fill_between` bands, images and filled contours then
     count as occupied.
   - This replaces the point sampling, or complements it if a benchmark
     shows the mask is too slow (budget: below 50 ms per legend on the
     examples).
2. **Placement order.**
   1. The best inside corner or free position with a score below a
      threshold.
   2. Otherwise, headroom: extend the y limits by the legend height. Log
      axes are extended in decades, and only when `--rangey` is not given.
   3. Otherwise, or with more than 6 entries, or with `--legend_loc
      outside`: above the axes, in as many columns as fit, inside the
      figure margin reserved through T13's hook.
3. **Order.**
   - For stacks: top of the stack first.
   - For lines: the order of their values at the right edge, unless
     `--legend_order data` keeps the draw order.
4. **Lower panels.**
   - No legend when every lower series has the same colour as an upper
     series.
   - Otherwise one entry per series, "X / reference".
   - Fix the "Ratio" single entry (line.py:874).
5. **Single legend.** One legend when `--hue` equals `--style`. If T01
   already did this, keep it.
6. **`--legend_loc`.** It accepts every matplotlib location, plus `outside`
   and `none`.

## Backwards compatibility

- `--legend_loc` keeps forcing a location.
- `--legend_free` keeps working, using the new scoring.

## Tests

- In the B06a stacked command, the legend box does not intersect any bar.
- Example 08 (bars): the same.
- A 12-entry legend goes outside, above the axes.
- The B06b ratio panel has two labelled entries, or no legend.

## Done when

The common definition of done is met. Sheets 03 and 08 show no legend over
data, and B06 is marked fixed.
