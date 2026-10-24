# T03 Uncertainties for binned estimators

**Wave 2 · effort M · risk med · depends on: T01 · parallel with T02, T04–T08**

## Goal

`line --binned --estimator X` draws the statistic with its uncertainty,
computed correctly, and says which uncertainty it is.

## Read first

- [bugs.md B04](../bugs.md#b04-binned-estimators-carry-no-uncertainty).
- [style_spec.md §2.8](../style_spec.md): the "binned mean / median" row.

## Scope

- `src/plotipus/transforms.py`: `_ESTIMATORS`, `bin_reduce`.
- `src/plotipus/kinds/_estimator.py`: `_reduce_cell` and the panel/compact
  drawing that uses its result.
- Tests: `tests/test_line_estimator.py`.

## Required behaviour

1. **Estimators return `(value, error)` per bin:**
   - mean: σ/√n (sample std, ddof=1);
   - median: 1.2533·σ/√n;
   - std: σ/√(2(n−1));
   - rms: delta method, `std(x²)/(2·rms·√n)`;
   - sum: √n for unweighted counts, √Σw² when per-event weights exist;
   - max/min: no error (`nan`).

   Keep the old plain-value API available, for `--plot_type box` (T10) and
   any other caller.
2. **Stored per-event errors** (`--errory` with an error column) are
   propagated, not averaged: for the mean, √Σe²/n. For the others,
   document what is done, and use the statistical error when the
   propagation is undefined.
3. **`--estimator_error {sem,std,none}`**, default `sem`. `std` draws the
   spread (the bin's σ) instead of the error of the statistic.
4. **Small bins.** `--min_count N`, default 5. Bins with fewer entries are
   dropped (not drawn), and a one-line note says how many were dropped.
5. **Labelling.** When errors are drawn and `--note` is not given, append
   "(mean ± s.e.m.)" (or the matching words) to the y label. Make this
   switchable with `--no_error_label`.
6. **Defaults.** Without `--plot_type`, the binned estimator now draws error
   bars on markers, not joined.

## Backwards compatibility

- Bars appear where none were drawn before; that is the fix.
  `--estimator_error none` restores the bare values.
- `--min_count 1` restores drawing every non-empty bin.

## Tests

- On a seeded normal sample, the drawn error of each bin mean matches
  σ/√n to 1e-12.
- The std estimator's error matches its formula.
- A bin with 3 entries is dropped at the default and kept with
  `--min_count 1`.
- Errors propagated from a stored column use √Σe²/n.

## Done when

The common definition of done is met. Example 05 and the B04 repro show
error bars.
