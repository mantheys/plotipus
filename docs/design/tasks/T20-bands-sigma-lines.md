# T20 Nested bands, Brazil plots and σ lines

**Wave 7 · effort M · risk low · depends on: T07, T11, T21**

## Goal

Expected-limit "Brazil" plots, local p0 scans with labelled σ lines, and
likelihood scans with labelled Δχ² lines (research F04, F05; catalogue E7,
G5, G7).

## Read first

- [catalogue.md rows E7, G5, G7](../catalogue.md).
- research F04 and F05.
- [style_spec.md §2.3](../style_spec.md): "Brazil bands".
- The `--horizontal*` options in `args.py` and their drawing in `plot.py`.

## Scope

- `src/plotipus/plot.py`: band drawing and reference lines.
- `src/plotipus/kinds/line.py`.
- `src/plotipus/args.py`.
- Tests: `tests/test_line.py`.

## Required behaviour

1. **Several bands per series.**
   - `--errory_column C1 [C2 ...]`: each column (or `C+`/`C-` pair) is one
     band. The first is the innermost and darkest, drawn on top.
   - `--band_colors graded|brazil|<c1,c2>`:
     - `graded` (default): two lightness steps of the series colour, or of
       `muted` for an "expected" series;
     - `brazil`: green #00cc00-like for ±1σ and yellow #ffcc00-like for
       ±2σ. Check the hexes against an ATLAS/CMS figure or mplhep and cite
       the source.
   - Legend entries "Expected ±1σ" and "±2σ", overridable with
     `--band_labels`.
2. **`--sigma_lines 1 2 3 4 5`** on log-y p-value plots:
   - horizontal lines at the one-sided p-values of nσ (`scipy.stats.norm.sf`);
   - `muted` dashed, labelled "1σ" … at the right edge, inside the axes.
3. **`--horizontal` labels.** `--horizontal_label` texts are placed
   consistently: right edge, just above the line. `--horizontal_label_pos
   left|right` chooses the side. This fixes the P07 misplacement in the
   catalogue.
4. **Δχ² lines.** `--delta_chi2_lines 1 4` (or `--cl_lines 68 95` with a dof
   option) for 1D likelihood scans, labelled "1σ" and "2σ" or "68% CL".

## Tests

- A Brazil command gives two `PolyCollection`s with the brazil colours in
  the right z order and the legend labels above.
- `--sigma_lines 1 2 3` gives lines at p = 0.1587, 0.02275 and 0.00135.
- The two `--horizontal` labels are both at the right edge.

## Done when

The common definition of done is met, and the catalogue rows E7, G5 and G7
are updated. The gallery (T23) gets the Brazil and p0 examples.
