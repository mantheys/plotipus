# T13 Measured layout

**Wave 4 · effort L · risk med · depends on: T12 · before T14**

## Goal

At any figure size (a 3.4 in paper column or an 8 in slide), nothing is
clipped and no space is wasted. Margins are measured from what was drawn,
not set in fixed inches.

## Read first

- [bugs.md B15](../bugs.md#b15-layout-in-fixed-inches-clips-labels).
- The comparison sheet [compare/05_binned_mean.png](../styles/compare/05_binned_mean.png),
  where long tick labels clip the y label at column width.
- [research.md Part 2 §1](../research.md#part-2-common-complaints): the
  layout complaints.
- In the code: `plot.py` (`get_common_figsize`,
  `apply_common_figure_margins`, `create_common_subplots`,
  `create_common_two_panel_figure`, the title/note placement around
  lines 960–1060, and the margin deficit code near line 1431) and
  `panels.py` (`create_panels`, `_stacked_figure`, `grow_for_tick_labels`,
  `add_title_and_note`).

## Scope

- `src/plotipus/plot.py`, `src/plotipus/panels.py`.
- Remove explicit `fontsize=` arguments for axis labels in `kinds/*.py` (see
  item 4 below).
- Tests: a new `tests/test_layout.py`.

## Required behaviour

1. **Fixed figure size.** The figure size is the print size and never
   changes during layout (T14 will set it from `--width`). The axes area is
   what adapts.
2. **One layout pass before saving:**
   - Draw, then measure the tight bounding box of every axis: tick labels,
     axis labels, offset texts, titles and colorbars.
   - Set the left, right, bottom and top margins to the measured extents
     plus a padding (style.json `figure_layout.pad_inches`, default 0.04).
   - Account for the figure title and the experiment header (T17 will add
     it; leave a hook).
   - Account for outside legends (T15 will add them; leave a hook).
   - Iterate at most twice.
3. **Alignment.**
   - Panels in a row share the left/right margins.
   - Upper and lower panels share x and stay aligned
     (`fig.align_ylabels`).
   - `hspace` between upper and lower panels stays 0.
4. **Label sizes.**
   - Axis labels take their size from rcParams `axes.labelsize` in every
     kind. Remove the per-call `fontsize=style.xlabelfontsize` etc.
   - Lower panels may use `ysublabelfontsize`.
   - style.json `font_sizes` keeps working by writing into rcParams.
5. **Evaluate first.** Compare matplotlib's `constrained` layout engine with
   a fixed figure size. If it handles lower panels with `hspace` 0, shared
   colorbars (T09) and suptitles, use it, and keep the custom code for what
   it misses. Record the decision in the PR description.
6. **Fallback.** `figure_layout.margins_inches` becomes a minimum (or, with
   `"fixed_margins": true`, the old exact behaviour).

## Backwards compatibility

- Figures keep their size. Axes areas change by a few percent.
- `"figure_layout": {"fixed_margins": true}` restores the exact old
  geometry, and T16's `classic` style sets it.

## Tests

- At 3.4×2.6 in with the candidate `paper` style, for every example
  command: every text artist's window extent lies inside the figure, and
  the left spines of the upper and lower axes have the same x.
- At 8×6 in: the axes area is at least as large as before (no needless
  shrinking).

## Done when

The common definition of done is met. All candidate styles are
re-rendered; no label is clipped in any sheet. B15 is marked fixed.
