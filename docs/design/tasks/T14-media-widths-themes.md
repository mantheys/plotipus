# T14 Media (slides/paper/web), widths and themes

**Wave 5 · effort L · risk med · depends on: T13 · before T15, T16**

## Goal

This builds the engine around decision D1: one command list renders for
slides first and for the paper later, with no change to the commands.

- `plotipus run analysis` writes the slide versions.
- `plotipus run analysis --medium paper` writes the publication versions
  next to them.

This task adds the plumbing: media, widths, themes and output folders. T16
ships the style files that the plumbing selects.

## Read first

- [style_spec.md §0](../style_spec.md): language × medium × theme, §2.1
  (sizes, column widths) and §2.11 (media and themes).
- [roadmap.md](../roadmap.md): decisions D1 and D4.
- `src/plotipus/project.py`, `runner.py`, `cli.py`, `args.py` (the common
  args) and `style.py`.

## Scope

- `project.py`, `runner.py`, `cli.py`, `args.py`, `style.py`, `plot.py`
  (`get_common_figsize`) and `panels.py` (figure creation).
- Tests: a new `tests/test_media.py`.

## Required behaviour

1. **Medium** (`slides`, `paper`, `web`):
   - Set by `--medium` on every kind and on `plotipus run`, or by
     `[project] medium = "slides"` in `plotipus.toml`.
   - The default is `slides`, through the default style T16 ships. Until
     T16 lands, keep today's look as the fallback when no medium is set
     anywhere, so this task can merge on its own.
   - `--medium all`, or `[project] media = ["slides", "paper"]` with
     `plotipus run`, renders every listed medium in one run.
2. **Theme.** `light` or `dark`, set by `--theme` or `[project] theme`.
3. **Style resolution.** A medium/theme pair selects style layers by name
   (`<language>`, `<medium>`, `<theme>`), resolved from
   `plotipus/data/styles/` (T16) and then the project's own `style` files,
   which keep the last word.
   - Define the lookup and the merge order here.
   - Use stub style files with only figure sizes until T16 lands.
4. **Width.**
   - `--width single|onehalf|double|nature|slide|half-slide|<inches>` and
     `--aspect` (height/width), on every kind.
   - Each medium has a default width (slides → `slide`, paper → `single`,
     web → `slide` at 96 dpi).
   - The preset table lives in style.json (`"widths"`, `"aspect"`), as in
     [style_spec.md §4](../style_spec.md).
   - A row of N panels shares the width, and lower panels add height (30%
     of the upper panel each) instead of squeezing.
   - Remove `panel_font_scale`. Text is never scaled to compensate (spec
     §2.1). With `fixed_margins` (classic), keep the old behaviour.
5. **Output folders.**
   - The project's default medium writes where it does today
     (`output/plots/...`), so existing paths stay valid.
   - Any other medium writes to `output/plots/<medium>/...`, and the theme
     adds `-dark` (`output/plots/slides-dark/`).
   - `[outputs.plots]` targets get the same sub-folder.
   - File names are unchanged.
6. **Titles.** `auto_title` defaults to false in every medium (decision D4).
   An explicit `--title` is drawn in slides and web, and is dropped in paper
   with a one-line note, unless `--keep_title` is given.
7. **Printing.** `plotipus run --dry_run` prints the resolved medium, theme,
   width and style layers for each command.

## Backwards compatibility

- Projects that set no medium and use `style = [...]` files keep today's
  geometry until T16 changes the default style. After that, `classic` pins
  it.
- Output paths for the default medium are unchanged.
- Legacy-translated commands are unaffected.

## Tests

- `--medium paper --width single` gives a figure 3.4 in wide; `--width 5`
  gives 5 in.
- `[project] media = ["slides", "paper"]` writes two files per command, in
  `output/plots/` and `output/plots/paper/`.
- A two-panel figure at `double` is 6.8 in wide.
- Adding `--lower ratio` increases the height by 30% of the upper panel.

## Done when

The common definition of done is met. The README has a "Slides first, paper
later" section showing the workflow.
