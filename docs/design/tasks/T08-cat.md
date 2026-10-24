# T08 `cat` fixes

**Wave 2 · effort S · risk low · depends on: T01 · parallel with T02–T07**

## Goal

`cat` handles one value per row, draws legends that match the marks, and
uses no fixed layout hacks.

## Read first

[bugs.md B07](../bugs.md#b07-cat-legend-handles-layout-and-scalar-crash).

## Scope

- `src/plotipus/kinds/cat.py`.
- Tests: `tests/test_cat.py`.

## Required behaviour

1. **Scalar cells.** `integrate_row` treats a scalar `-y` cell as already
   integrated (value, error from the `{y}Error` scalar if present).
   `--integrate_over` is then optional.
2. **Legend handles.**
   - `--kind bar` uses `matplotlib.patches.Patch` handles in the bar colour.
   - `point` uses markers only.
   - `line` uses a line with a marker.
3. **Tick labels.** Rotate them only when they overlap: measure the tick
   label extents after drawing and rotate by 30° if any two overlap.
   `--xtick_rotation DEG` forces it.
4. **Layout.**
   - Remove `fig.subplots_adjust(bottom=0.22)`.
   - Rely on `grow_for_tick_labels`, which already exists, and later T13,
     for room.
5. **Grid.** Remove the kind-specific y grid (`ax.grid(True, axis="y", …)`).
   The grid is a style decision (rcParams `axes.grid`).
6. **Legend location.**
   - Remove the hard-coded `loc="lower left"`.
   - Use the shared automatic placement (`apply_legend_style_clear_of_data`)
     unless `--legend_loc` is given. T15 will improve that placement for
     filled bars.
7. **Colours.** Colours come from the T01 allocator.

## Backwards compatibility

- Short labels are no longer rotated, and there is no extra bottom margin.
- `--xtick_rotation 20` restores the old rotation.

## Tests

- The B07b command (scalar importances) renders 6 bars.
- Legend handles for `--kind bar` are `Patch` instances.
- Two short categories are not rotated; 12 long ones are.

## Done when

The common definition of done is met, and the B07a/B07b repro images and
example 08 are inspected.
