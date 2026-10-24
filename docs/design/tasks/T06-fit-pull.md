# T06 `--fit` lower panel: residual and pull

**Wave 2 · effort S · risk low · depends on: T01 · parallel with T02–T05, T07, T08**

## Goal

With `--fit`, `--lower pull` draws pulls, `--lower residual` draws relative
residuals, and the y label matches what is drawn.

## Read first

[bugs.md B13](../bugs.md#b13---fit---lower-pull-draws-the-relative-residual).

## Scope

- `src/plotipus/kinds/_fit.py` (`_draw_fit_rows` and the figure assembly
  around line 248–320).
- Read `src/plotipus/lower.py` (`model_series`, `lower_model_series`); edit
  it only if needed.
- Tests: `tests/test_line_fit.py`.

## Required behaviour

1. **Computation.** Compute the lower-panel series with
   `lower.model_series(y, model, error, operation)`. The operation comes
   from the `--lower` spec: `residual` or `pull`.
2. **Several panels.** Several `--lower` entries with `--fit` give several
   panels, as in the non-fit path.
3. **Default labels** (overridable with `--lower_labely`):
   - "(Data − Fit) / Fit" for a residual;
   - "Pull" with the subtitle "(Data − Fit) / σ" for a pull.
4. **Pull panels:**
   - A symmetric range of ±max(3, 1.2·max|pull|) by default.
   - Light bands at ±1 and ±2. Use grey for now; T11 replaces it with the
     `faint` role.
5. **Missing errors.** A pull without errors prints a warning and draws
   nothing; it never draws NaNs silently.
6. **Residual divergence.** For residuals, bins where |fit| is below 1e-3 of
   the fit maximum are masked. This removes the divergence in the Gaussian
   tails.

Leave the fit and residual colours (red/black) to T11; it replaces them
with roles.

## Tests

- On the repro `Fit` data, the pull values equal (y − f)/σ.
- The label of the pull panel is "Pull".
- `--lower residual --lower pull` gives two lower axes.

## Done when

The common definition of done is met, and the B13 repro is inspected.
