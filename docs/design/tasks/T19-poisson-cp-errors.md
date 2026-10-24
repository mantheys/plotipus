# T19 Poisson and Clopper–Pearson intervals in plots

**Wave 7 · effort M · risk low · depends on: T18 (shares line.py) · parallel with T21**

## Goal

Counts and efficiencies get correct, bounded intervals without the user
precomputing them. The plots then match the table kind's
`--clopper_pearson`.

## Read first

- [style_spec.md §2.8](../style_spec.md): the uncertainty conventions table.
- [catalogue.md rows A6, G2, G3](../catalogue.md).
- The Clopper–Pearson code of the table kind (`kinds/table.py`, look for
  `clopper`).
- mplhep's Poisson interval implementation, as cited in research Part 1
  §2.9.

## Scope

- New `src/plotipus/intervals.py`. Move the Clopper–Pearson helper there
  from `table.py` and import it back.
- `src/plotipus/kinds/line.py` and `kinds/hist.py`: error selection.
- `src/plotipus/plot.py`: asymmetric errors.
- Tests: a new `tests/test_intervals.py`.

## Required behaviour

1. **`intervals.py`:**
   - `garwood(n, cl=0.6827)` → (low, high), exact Poisson with `scipy.stats`
     chi2. For n = 0 the lower bound is 0.
   - `clopper_pearson(k, n, cl)`.
   - `sumw2(w)`.
2. **`--errory_type poisson`** (line and hist):
   - asymmetric Garwood bars computed from the y values (counts);
   - in `hist`, from the bin counts, or √Σw² when `--weight` is given;
   - `--errory_type poisson` is the default for overlay data (T18) when no
     error column exists.
3. **`--errory_type clopper_pearson --count_column N`** (line):
   - y is an efficiency (0–1, or 0–100 with `--efficiency_scale`), and k is
     taken as y·N.
   - Bands or bars, which never cross 0 or 1.
4. **`--confidence_level`.** Shared with the table kind; default 0.6827.
5. **Labels.** The legend or the y label names the interval when
   `--error_label` is on (default off in paper, on in slides). For example
   "68% CL (Clopper–Pearson)".

## Tests

- Garwood for n = 0, 1, 10 matches published values (cite them in the test).
- CP for k = 0 and k = n is bounded at 0 and 1.
- A `hist --errory_type poisson` artist has asymmetric errors matching
  `garwood`.

## Done when

The common definition of done is met, and the catalogue rows A6, G2 and G3
are updated.
