# T23 New examples and gallery

**Starts in wave 2 and grows with each feature · effort M (initial) · risk low · depends on: T01–T08 for the first entries**

## Goal

Replace the 10-command smoke test with a gallery in which:
- every ✅ catalogue row has a realistic example;
- every example renders in the default style (slides) and in paper;
- every example is also a test.

## Read first

- [roadmap.md Step 5](../roadmap.md): the data themes and the example list.
- [catalogue.md](../catalogue.md).
- The current `examples/` (`make_data.py`, `input/plots/example_scripts.txt`,
  `Makefile`, `style.json`, `plotipus.toml`).
- T24, which provides the famous-plot datasets.

## Scope

- `examples/`: data generators, command lists, Makefile, style.
- `tests/test_gallery.py`.
- `README.md`: the gallery section.

## Required behaviour

1. **Data.**
   - `examples/data/` with one seeded generator per theme: `detector.py`,
     `collider.py`, `cosmo.py`, `ml.py`, `classics.py`.
   - `examples/make_data.py` calls them all.
   - Keep the current pickles (`Spectra`, `Events`, `Efficiency`, `Contour`,
     `Summary`) unchanged, so existing tests and `example_scripts.txt` keep
     working.
   - Synthetic data only (decision D6). Famous-plot data comes from T24's
     generators; import them, don't duplicate them.
2. **Commands.**
   - `examples/input/plots/gallery_scripts.txt` is grouped by catalogue
     section, with a `# <catalogue id> <title>` comment above each command.
   - Commands whose feature has not landed yet stay in the file, commented
     out with `# needs Txx`, so the list doubles as a progress tracker.
   - `example_scripts.txt` stays (continuity).
3. **Makefile.**
   - `make gallery` renders the gallery for `--medium all` (slides and
     paper, T14). Until T14 lands, use the default medium only.
   - It then writes `examples/output/gallery.md`: a Markdown grid of the
     PNGs with the command under each.
4. **Tests.** `tests/test_gallery.py` parses `gallery_scripts.txt` and
   renders every uncommented command to a temp directory. Each command must
   exit 0 and produce one file. Mark the test `slow` if it takes more than
   ~30 s.
5. **README.** A short gallery section links `examples/output/gallery.md`.
   Its instructions regenerate the outputs; the outputs themselves are not
   committed.

## Done when

The common definition of done is met. Every uncommented gallery command
renders, and the gallery page has been opened and checked by eye. Each
later feature task adds or uncomments its gallery entries.
