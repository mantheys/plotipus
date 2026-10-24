# T05 `scatter --hue` keeps every group

**Wave 2 · effort S · risk low · depends on: T01 · parallel with T02–T04, T06–T08**

## Goal

`scatter --hue COL` on array cells draws every hue group.

## Read first

[bugs.md B12](../bugs.md#b12-scatter---hue-drops-all-but-the-first-group).

## Scope

- `src/plotipus/kinds/scatter.py`: `explode_points` and its callers.
- Tests: `tests/test_scatter.py`.

## Required behaviour

1. `explode_points` keeps one row per (Config, Name, hue column, style
   column), using whichever of those columns are present and requested,
   instead of one row per (Config, Name).
2. The warning about `--markerby` appears only when rows that differ in no
   requested encoding are still being dropped. Its text names the columns
   that would distinguish them.
3. Hue colours come from the T01 allocator, and the legend lists every
   group.

## Tests

- The B12 command with three groups draws three collections with three
  distinct colours, and the legend has three entries.
- Without `--hue`, the old behaviour (one row per Config/Name, with the
  warning) is unchanged.

## Done when

The common definition of done is met, and the B12 repro is inspected.
