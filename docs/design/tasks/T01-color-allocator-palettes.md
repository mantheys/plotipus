# T01 Colour allocator and named palettes

**Wave 1 · effort M · risk med · depends on: — · run alone (touches every kind)**

## Goal

A category keeps one colour, never shares it by accident, and the cycle
never wraps silently. Named palettes can be selected (decision D2:
Petroff-10 default, plus the other common palettes).

## Read first

- [bugs.md B01](../bugs.md#b01-repeated-colour-in---by_config-the-maintainers-report)
  and [B02](../bugs.md#b02-colour-cycle-wraps-silently-past-10-series): root
  causes with line numbers.
- [style_spec.md §2.3–2.4](../style_spec.md): palette, overflow rule and line
  styles.

## Scope

- New: `src/plotipus/palettes.py`.
- Edit: `encodings.py`, `kinds/line.py`, `kinds/hist.py`, `kinds/cat.py`,
  `kinds/map.py` (colour choice only, not the contour code), `kinds/scatter.py`,
  `style.py`.
- Tests: `tests/test_palettes.py`, plus cases in `test_line.py`.

## Required behaviour

1. **`palettes.py`** defines named palettes as hex lists, each with a source
   URL in a comment:
   - `petroff10` (default), `petroff6`, `petroff8`. Take the hexes from
     matplotlib's style library (`plt.style.library["petroff10"]`).
   - `okabe-ito`.
   - `tol-bright`, `tol-muted`. Check them against Paul Tol's page.
   - `tab10` (matplotlib default), `seaborn-colorblind`,
     `tableau-colorblind10`.
   - `root`: the colour sequence ROOT users get. Check it against the
     ROOT TColor documentation. If ROOT's Petroff sets `kP6/kP8/kP10`
     differ in order from matplotlib's, also add `root-p10`. Mark anything
     you cannot verify.

   The research hexes are in
   [research.md Part 1](../research.md#part-1-default-styles-of-plotting-engines).
2. **Selecting a palette:**
   - option `--palette NAME` on every kind (add it with the common
     arguments);
   - style.json key `"palette": "NAME"` (read in `style._publish`);
   - the default is `petroff10`.

   The chosen palette sets `axes.prop_cycle` for the figure, so plain
   matplotlib calls follow it too.
3. **`ColorAllocator`**, one per figure, shared by all panels and lower
   panels of that figure:
   - `color_for(category, mapping=None)`:
     1. the colour from the user mapping (`--iterable_color_mapping`,
        `config_color`, `name_color`), if any;
     2. otherwise the colour already assigned to this category in this
        figure;
     3. otherwise the next palette slot not yet taken (mapped colours count
        as taken).
   - `next_free()`: for combined, sum and reference-sum series.
   - Overflow: when the categories outnumber the palette, return
     `(colour, linestyle)` pairs. Colour cycles fastest, and the line style
     advances on each wrap (`-`, `--`, `:`, `-.`).
   - Print one warning per figure suggesting `--hue_cmap` for ordered
     values. `--hue_cmap` itself is T22; just name it.
4. **Replace every `f"C{...}"` and every `% 10`** at the sites listed in B02,
   and the `two_lines` branch in `run_by_config` (line.py:1234). The cycle
   length always comes from the active palette.
5. **Defaults:**
   - `--combined_color` and `--sum_color` default to `None`, meaning
     `next_free()`.
   - An explicit value is still honoured.
   - `--reference_sum_color` gets the same treatment.
6. **One legend when `--hue` and `--style` name the same column.** Each
   entry carries both its colour and its line style (B02b).

## Backwards compatibility

- With the default palette, the first colours change: tab10 → Petroff-10.
  That is the intended new look. `--palette tab10` restores the old
  colours, and T16's `classic` style will set it.
- Command lines that relied on the B01 accident (Average = C0) now get a
  distinct colour. That was a bug; no restore option is needed.

## Tests

- B01 command: the three series have three distinct colours, and with the
  repro style the configs take `config_color` (C3/C4).
- 12 hues give 12 distinct (colour, linestyle) pairs, and the warning is
  printed once.
- `--palette okabe-ito` changes the first line's colour to `#E69F00`.
- A mapped colour is never reused for an unmapped category.
- The same hue value has the same colour in the upper and lower panels.
- `--hue X --style X` draws one legend.

## Done when

The common definition of done in [00-README.md](00-README.md) is met, and
B01/B02 are marked fixed in bugs.md.
