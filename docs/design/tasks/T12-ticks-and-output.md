# T12 Tick labels and output resolution

**Wave 4 · effort S · risk low · depends on: T11 · before T13**

## Goal

Tick labels read like a paper (no `4e-2`). Saved files have publication
resolution.

## Read first

- [bugs.md B05](../bugs.md#b05-tick-labels-like-4e-2).
- [B17](../bugs.md#b17-points-joined-by-lines-and-low-resolution-output),
  second point.
- [style_spec.md §2.2](../style_spec.md): the "Numbers" paragraph.

## Scope

- `src/plotipus/plot.py`: `_make_threshold_formatter`,
  `apply_scientific_threshold_formatter`, and the saving code.
- Its call sites in `kinds/hist.py`, `kinds/line.py`, `kinds/_estimator.py`
  and `kinds/map.py`.
- `src/plotipus/data/plotipus.mplstyle` (savefig keys only).
- Tests: `tests/test_core.py`.

## Required behaviour

1. **Formatter.**
   - Replace the threshold formatter with
     `ScalarFormatter(useMathText=True)`, honouring `axes.formatter.limits`
     from the style.
   - Keep `apply_scientific_threshold_formatter` as a thin, deprecated
     wrapper, in case plugins import it.
2. **Offset into the label.**
   - Option `--sci_in_label` (style.json `plot_settings.sci_in_label`,
     default true).
   - After drawing, if an axis formatter produced an offset or multiplier
     (e.g. ×10⁻²), append it to the axis label ("Density (×10⁻²)") and hide
     the offset text.
   - With the option off, matplotlib's offset text stays.
3. **Log axes.** Keep matplotlib's `LogFormatterSciNotation` (10ⁿ).
   Unlabelled minor ticks.
4. **Output.** `savefig.dpi: 300` in the default mplstyle. In the README,
   document `--format pdf` as the recommended format for papers.

## Backwards compatibility

- Tick text changes, and PNG files get more pixels.
- `"plot_settings": {"sci_in_label": false}` keeps the offset text.
- T16's `classic` style pins `savefig.dpi: 100`.

## Tests

- The example `hist` with density: no tick label contains "e-", and the y
  label ends with "(×10⁻²)".
- `savefig.dpi` is 300 by default.

## Done when

The common definition of done is met. The examples' hist and 05 are
inspected, and B05 is marked fixed.
