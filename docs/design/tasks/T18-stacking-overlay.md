# T18 Stacked simulation with overlaid data

**Wave 7 · effort M · risk med · depends on: T01, T07, T11, T15 · before T19**

## Goal

The canonical HEP control plot (research F03): stacked simulation
histograms as steps or filled steps, data points on top, the MC uncertainty
as a hatched band, and a data/MC ratio panel.

## Read first

- [bugs.md B10](../bugs.md#b10---stacked-only-works-for-bars-and-stacks-everything).
- [catalogue.md rows A3, C7, E3, G6](../catalogue.md).
- research F03 (ATLAS/CMS 4ℓ figure).
- [style_spec.md §2.8](../style_spec.md): the weighted counts and
  unweighted counts rows.

## Scope

- `src/plotipus/kinds/line.py`: `draw_series`, the stack loop around
  lines 610–670, and `_finish_upper` (legend order).
- `src/plotipus/plot.py`: stairs/fill helpers.
- Tests: `tests/test_line.py`.

## Required behaviour

1. **Stacking in data space** for `--plot_type step` (outlines),
   `--plot_type fill` (new: filled steps with a darker edge), `bar` (as
   today) and `line` (`fill_between`, i.e. a stacked area).
   - Cumulative sums are drawn with `ax.stairs(cum, edges, baseline=prev,
     fill=...)`.
   - `--stack_reverse` keeps its meaning.
2. **`--overlay VALUE [VALUE ...]`.** Hue values excluded from the stack and
   drawn on top:
   - unstacked, as `ink` points with error bars, no x error for uniform
     bins;
   - their error column (or Poisson errors once T19 lands; until then the
     stored error).
3. **`--stack_total_error`.**
   - A hatched band (`////`, `ink` at 40%) around the stack total, from √Σ
     of the stacked series' stored errors.
   - `--stack_total_error_column COL` takes a precomputed total instead
     (for systematics).
4. **Ratio panel.** `--lower ratio` with `--overlay data` defaults to
   data / stack total (the `--reference_sum` machinery), drawn as points
   with error bars, plus the relative MC band around 1.
5. **Legend.** Overlays first (the HEP convention, switchable), then the
   stack from top to bottom, then the uncertainty band. This builds on T15's
   ordering.

## Backwards compatibility

- `--stacked` without `--plot_type` still gives bars.
- `--stacked --plot_type step` used to be silently unstacked; it now stacks
  (listed under behaviour changes).

## Tests

- On the repro `Spectrum` data with `--stacked --plot_type fill --overlay
  data --stack_total_error --lower ratio`:
  - the top of the stack equals the sum of the MC;
  - the data are drawn as an ErrorbarContainer;
  - the ratio values equal data/sum;
  - the legend order is as specified.

## Done when

The common definition of done is met. B10 is marked fixed, and the
catalogue rows A3, C7, E3 and G6 are updated.
