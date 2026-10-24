# T16 Ship the styles; `classic` for compatibility

**Wave 6 · effort M · risk high · depends on: T01, T11, T12, T13, T14 (T15 recommended) · before T17**

## Goal

The new defaults land. `slides` (plotipus language, light) is the default.
`slides-dark`, `paper`, `open` and `open-dark` are available by name, and
`classic` pins today's look (decisions D1, D4, D5).

## Read first

- [style_spec.md](../style_spec.md), all of it, especially §0 and §4.
- The prototypes in [../styles/](../styles/) (`paper`, `open`, `hep`,
  `slides`) and their comparison sheets.

## Scope

- New `src/plotipus/data/styles/`:
  - languages: `plotipus.mplstyle`, `open.mplstyle`;
  - media: `slides.json`/`.mplstyle`, `paper.*`, `web.*`;
  - themes: `dark.*`;
  - `classic/` (today's `plotipus.mplstyle` + `style.json`, plus pins).
- `src/plotipus/style.py`: resolution by name; the defaults become the
  `slides` combination.
- `pyproject.toml`: package data glob.
- `docs/design/styles/render.py`: render every shipped name.
- `README.md`: the Styles section and release notes.
- Tests: `tests/test_styles.py`.

## Required behaviour

1. **Languages:**
   - `plotipus`: ticks in, mirrored, minor ticks, no grid, frameless legend,
     Petroff-10. Port from the `paper` prototype.
   - `open`: L-shaped frame, ticks out, faint y grid. Port from the `open`
     prototype, with Petroff-10 rather than Okabe–Ito, so colours are
     consistent across styles (spec §2.3).
2. **Media:**
   - `slides`: 8×4.5 in, 14 pt, sans text with matching math, lines 2.4,
     markers 7, titles allowed.
   - `paper`: single column, 8 pt, Computer Modern (`cmr10` + `cm`), lines
     1.2, PDF recommended, no titles.
   - `web`: 8 in at 96 dpi, 12 pt sans.
   - Values as in spec §2.1–2.6.
3. **Dark theme:**
   - Roles swap (T11).
   - Lightened twins of the dark Petroff colours, keeping the order (spec
     §2.11). Write a test that checks a WCAG contrast of at least 3:1 for
     every cycle colour against the background.
   - Diverging maps `berlin`/`vanimo`.
4. **Names.** `slides`, `slides-dark`, `paper`, `paper-dark` (for
   completeness), `open`, `open-dark` and `classic`. They are usable in
   `plotipus.toml` `style = ["paper"]`, by `--medium`/`--theme` (T14), and
   by `--style_preset NAME` on the CLI. The name `--style` is taken (it is
   the comparable alias).
5. **`classic`** reproduces the pre-redesign output:
   - today's mplstyle and style.json;
   - `palette: tab10`, `contours.dof: 1`, `fixed_margins: true`,
     `savefig.dpi: 100`, `auto_title: true`, `sci_in_label: false`;
   - red fit and zero lines through roles.

   Test that `classic` renders the examples with the same figure size and
   colours as `main` before the redesign. Compare artist properties, not
   pixels.
6. **Provenance.** `--save_style` (and `[project] save_style = true`) writes
   `<figure>.style.json` with the resolved style layers and rcParams next to
   each output.
7. **Renders.** `render.py` renders every name × the 8 examples into
   `docs/design/styles/<name>/png` and the comparison sheets. Open every
   sheet and check it.
8. **Release notes.** Collect the "Behaviour changes" of T01–T15 from the
   merged PRs into `README.md` (or a new `CHANGELOG.md`): what changed and
   how to restore it (mostly `style = ["classic"]`).

## Backwards compatibility

This is the breaking release, with one switch back: `style = ["classic"]`
(or `--style_preset classic`). Make that switch the first item of the
release notes.

## Done when

The common definition of done is met. The sheets show slides (light and
dark), paper, open (light and dark) and classic for all 8 examples, and the
maintainer has approved the sheets before merge.
