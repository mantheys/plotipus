# T07 Bands for every plot type; points not joined

**Wave 2 · effort S · risk med · depends on: T01 · parallel with T02–T06, T08**

## Goal

`--errory_type bands` works whatever the plot type. Measured points with
error bars are not joined by lines unless the user asks.

## Read first

- [bugs.md B11](../bugs.md#b11---errory_type-bands-ignored-unless---plot_type-line).
- [B17](../bugs.md#b17-points-joined-by-lines-and-low-resolution-output),
  first point only. Output resolution belongs to T12.

## Scope

- `src/plotipus/plot.py`: `plot_data`, the `line`/`errorbar`/`step`
  branches.
- `src/plotipus/kinds/line.py`: `draw_series`, `_error_kwargs`.
- Remove the workaround comment in `kinds/_fit.py:_data_style` if it
  becomes unnecessary.
- Tests: `tests/test_line.py`.

## Required behaviour

1. **Error type before plot type.** `--errory_type` is resolved before
   dispatching on the plot type:
   - `bands`: `fill_between` (stepwise, `step="mid"`, for step plots) plus
     the central line or step.
   - `bars`: error bars.
   - The default is `bars` for points and `bands` for `--plot_type
     line|step`.
2. **No joining lines.**
   - Error bars on points (`--plot_type errorbar`, or the default with
     `--errory`) use `linestyle="none"` unless `--connect` is given.
   - `--plot_style` still applies to lines.
3. **Band look.** The band takes the series colour at alpha 0.2 with no
   edge. Configurable through style.json
   `plot_settings.band_alpha`.

## Backwards compatibility

- Points that used to be joined are no longer joined. `--connect` restores
  the old look; list it under behaviour changes.
- `--errory_type bars` with `--plot_type line` keeps today's bars on a line.

## Tests

- The B11 command gives a `PolyCollection` (band) for the expected series
  and no `ErrorbarContainer`.
- The B04/example-05 command gives errorbar containers whose data line has
  linestyle `"None"`. With `--connect`, it has a visible line.

## Done when

The common definition of done is met, and the B11 repro and example 05 are
inspected.
