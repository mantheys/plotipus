# T21 Per-series plot type

**Wave 7 · effort S · risk low · depends on: T18 (shares line.py) · parallel with T19**

## Goal

Data drawn as points with error bars and models as lines in the same
figure, chosen per hue value. Needed by the SN Hubble diagram, NGC 3198 and
the LEP lineshape (research F09, F12, F17; catalogue C6). Also the
error-bar magnification of F06/F17 (catalogue G9).

## Read first

- [catalogue.md rows C6, G9](../catalogue.md).
- `draw_series` in `kinds/line.py`.

## Scope

- `src/plotipus/kinds/line.py`, `src/plotipus/args.py`.
- Tests: `tests/test_line.py`.

## Required behaviour

1. **`--series_type VALUE=TYPE [VALUE=TYPE ...]`.**
   - TYPE is any `--plot_type` value.
   - Unlisted hue values use `--plot_type`.
   - A style.json mapping (`"series_types": {"data": "errorbar"}`) can set
     it project-wide, addressed with `--series_type_mapping NAME`, like the
     other mappings.
2. **Data drawing.** Series drawn as `errorbar` are drawn after the lines
   (on top), in their allocated colour, or `ink` when the value is in
   `--overlay`/`--data_values` (shared with T18).
3. **`--error_scale K`.** Multiplies drawn errors only, not values, and
   appends "(errors ×K)" to that series' legend label.

## Tests

- `--series_type data=errorbar` with models as lines: one
  ErrorbarContainer and N−1 Line2D.
- With `--error_scale 10`, the drawn error equals 10× the stored error, and
  the label contains "×10".

## Done when

The common definition of done is met, and the catalogue rows C6 and G9 are
updated.
