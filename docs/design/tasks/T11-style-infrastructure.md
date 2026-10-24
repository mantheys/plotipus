# T11 `mplstyle` key and colour roles

**Wave 3 · effort M · risk low · depends on: T01 · parallel with T09, T10 (it edits colour literals in many files, so merge it early in the wave)**

## Goal

A style is a `.mplstyle` file plus a `style.json` file, both loaded by
plotipus. Nothing in the code hard-codes black, red, grey or white, so dark
themes and experiment presets work.

## Read first

- [bugs.md B14](../bugs.md#b14-hard-coded-colours-ignore-the-style): the
  list of colour literals.
- [style_spec.md §2.3](../style_spec.md): the roles table, and §4 for the
  proposed style.json keys.
- `src/plotipus/style.py` and `project.py` (how styles are merged and
  applied).

## Scope

- `src/plotipus/style.py`, `project.py`.
- The colour literals in `encodings.py`, `plot.py`, `panels.py`,
  `kinds/*.py`. Change only the colour argument at each site.
- `docs/design/styles/render.py`: drop its rcParams-copying workaround.
- Tests: `tests/test_core.py` (style section).

## Required behaviour

1. **`"mplstyle"` key in style.json.** It takes a path (relative to the
   style file) or a list of paths or matplotlib style names, and is applied
   with `plt.style.use` before the file's `rcparams` section. Merging stays
   in order: earlier style files, then later ones.
2. **Roles.**
   - The `"roles"` section in style.json has `ink`, `muted`, `faint`,
     `paper` and `accent`.
   - Defaults are derived from rcParams when absent: `ink` = `text.color`,
     `paper` = `axes.facecolor`; `muted` and `faint` are mixes of the two.
   - Expose `style.role(name)`.
   - Mapping colours may use `"role:ink"`.
3. **Replace every colour literal** listed in B14 with roles:
   - data/reference lines, fit lines and residual markers → `ink`;
   - guides (y = 1, Δχ² lines, the 100% efficiency line, mean bands) →
     `muted`;
   - pull bands and grids → `faint`;
   - outlines on images → `paper`.

   The line-style legend handles (`encodings.py:281`, `cat.py:159`,
   `scatter.py:351`) use `ink`.
4. **Zero lines in lower panels.** These are drawn in red today
   (`--lower_zero_line`). They become `muted` dashed. `--lower_zero_color`
   restores red if wanted.
5. **Docs.** Document the new keys in the README "Style files" section.

## Backwards compatibility

- The default roles reproduce today's look as closely as possible (ink
  black, muted grey).
- The one visible change is the red zero and fit lines, which become ink.
  The fit stays distinguishable through line style: the fit is a solid
  line, the data points are markers.
- `classic` (T16) can pin `"roles": {"accent": "red"}` and fit colour red if
  needed.

## Tests

- A style.json with `"mplstyle": "dark_background"` changes
  `axes.facecolor`.
- With `"roles": {"ink": "#ff00ff"}`, the line-style legend handles and the
  fit line are magenta.
- `grep -rnE 'color="(black|k|r|red|gray|grey|white)"' src/plotipus` returns
  nothing (make this a test).

## Done when

The common definition of done is met. The slides overlay sheet
(`styles/slides/png/01_*.png`) shows visible line-style legend handles,
and B14 is marked fixed.
