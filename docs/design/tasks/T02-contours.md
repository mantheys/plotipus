# T02 Readable, correct confidence contours

**Wave 2 · effort M · risk high · depends on: T01 · parallel with T03–T08 (not T09: same file)**

## Goal

The contour example from the maintainer's report becomes readable and
statistically correct. The defaults are 2-dof levels with coverage labels
and graded fills. Backward compatibility follows decision D3.

## Read first

- [bugs.md B03](../bugs.md#b03-contour-plots-are-hard-to-read-the-maintainers-report):
  the four root causes.
- [style_spec.md §2.3](../style_spec.md), "Confidence regions", and §2.8,
  the last row of the uncertainty table.
- research F10 (Ω_M–Ω_Λ contours) for the target look.

## Scope

- Edit `kinds/map.py`: the contour functions `band_hues`, `contour_levels`,
  `sigma_labels`, `draw_filled`, `legend_lines`, `draw_contour_panel`,
  `draw_contour_figure`, the contour arguments, and the legacy translations
  at the bottom.
- `style.py`: read the `contours` section.
- Tests: `tests/test_map.py`.

## Required behaviour

1. **`--contour_dof {1,2}`**, default 2, in `sigma_probability` mode. Levels
   are the Δχ² thresholds whose χ²(dof) CDF equals the Gaussian two-sided
   coverage of each σ:
   - Use `scipy.stats.chi2.ppf(scipy.stats.chi2.cdf(s**2, 1), dof)`.
   - For dof 2 this gives 2.30, 6.18 and 11.83 for 1, 2 and 3σ.
   - `z_values` mode is unchanged: its levels are the significances
     themselves.
2. **Labels.** `--contour_label {cl,sigma}`, default `cl`, gives "68.3% CL",
   "95.4% CL", "99.7% CL". `sigma` gives "1σ", or "1σ (2 dof)" when the
   dof is not obvious from the levels.
3. **Fills** (`--fill_contours`):
   - Bands are ordered from the best fit outwards: the innermost region is
     the most opaque, each outer ring lighter, and the outside is unfilled.
   - Each dataset uses one hue (from the T01 allocator), mixed with the
     paper colour at `[1.0, 0.55, 0.25]`, configurable via
     style.json `contours.fill_mix`.
   - The existing `--fill_alpha`, `--fill_outer_alpha` and
     `--fill_inner_alpha` options keep working where they still apply.
4. **Outlines.**
   - Solid, dashed and dotted for successive levels by default
     (`--contour_linestyles` still overrides).
   - Legend handles show the level's line style and fill. Identical
     swatches are a regression.
5. **Best fit.** A `+` marker at the grid minimum in the dataset colour, on
   by default. `--no_best_fit` turns it off.
6. **Background** for Δχ² maps:
   - Default `none`.
   - When it is requested, clip it at the outermost level and label the
     colorbar `Δχ²` (or `--labelz`) instead of the column name.
   - Check the current `--background` default before changing it: the
     change is gated by the compatibility rules below.
7. **Style key** in style.json: `"contours": {"dof": 2, "fill_mix": [...],
   "linestyles": ["-", "--", ":"], "label": "cl", "background": "none"}`.
   The CLI overrides it.

## Backwards compatibility (decision D3)

- `--contour_dof 1 --contour_label sigma --background all` reproduces the
  old levels and labels. The old fills were the bug and are not restored.
- The legacy translations (`_legacy_*` functions in map.py, `legacy.py`)
  append `--contour_dof 1`.
- T16's `classic` style will set `contours.dof = 1`. Make sure the style key
  is honoured.
- When the user gave no `--contour_dof`, mode is `sigma_probability`, and the
  style does not set `dof`, print one notice per run: "contour levels now
  use 2 dof (Δχ² = 2.30, 6.18, 11.83); pass --contour_dof 1 for the previous
  levels".

## Tests

- The levels for dof 1 and dof 2 match the values above (to 0.01).
- Filled mode gives monotonic alphas or lightness from inside out.
- The legend has three distinct handles with the expected labels.
- A legacy-translated contour command contains `--contour_dof 1`.
- `classic`-style dof is honoured (set `style.configure(contours={"dof": 1})`).

## Done when

The common definition of done is met. The B03 repro and examples 07 are
re-rendered and inspected, and the sheet `compare/07_contour.png` is
updated.
