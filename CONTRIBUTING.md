# Contributing

## Development install

```bash
git clone https://github.com/mantheys/plotipus.git && cd plotipus
python3 -m venv .venv && source .venv/bin/activate   # Debian/Ubuntu: apt install python3-venv
pip install -e ".[dev]"
pytest                                               # run the tests
```

`pytest` runs one worker per core (pytest-xdist, `addopts` in
`pyproject.toml`); `pytest -n 0` runs serially, `pytest -m 'not slow'` skips
the gallery. `plotipus run` and the gallery fork every command from one
preloaded server process instead of starting a Python each.

Python ≥ 3.10; plotipus depends on numpy, pandas, matplotlib, scipy, rich
and jinja2.

## Regenerating the examples

After a change, rebuild the examples from scratch with `examples/Makefile`
(it uses `.venv/bin/python` when present):

```bash
make -C examples             # delete generated data and outputs, then rebuild all
make -C examples clean       # only delete them (input/data/*.pkl, output/)
make -C examples plots       # rebuild data and plots without deleting first
make -C examples docs        # re-render the figures of docs/options.md
make -C examples mascot      # re-render the mascot and the tutorial figures
make -C examples famous      # re-render the famous plots and the README images
make -C examples gallery     # build the gallery page (examples/gallery)
```

## Missing features

To ask for a chart or an option plotipus cannot draw yet, or to report a
bug, [open an issue](https://github.com/mantheys/plotipus/issues). Include:

- what you want to draw, ideally with a published figure to aim at;
- a small example of your data (the
  [DataFrame convention](README.md#your-own-data));
- the closest command you tried and what it drew instead.

Missing features are tracked in a few places. A pull request that adds a
feature or finds a new gap updates them:

| where | what goes there |
|---|---|
| [docs/design/catalogue.md](docs/design/catalogue.md) | Every chart people routinely need, marked ✅ (works), ◐ (partly) or ✗ (missing), with the smallest change that would cover it. A new chart gets a row there; a change that makes a row work updates its status and the summary table. |
| [docs/design/tasks/T22-backlog.md](docs/design/tasks/T22-backlog.md) | Options that are planned and sized, one item per pull request. Finished items are struck through. |
| [docs/design/TODO.md](docs/design/TODO.md) | Charts left out of scope on purpose (polar, geographic, broken axes, ...), each with what it would need. |
| [docs/styleguide.md](docs/styleguide.md#what-plotipus-does-not-do-yet) | Rules of the style guide that the code does not enforce yet. |
| [examples/gallery/input/plots/gallery_scripts.txt](examples/gallery/input/plots/gallery_scripts.txt) | The command each missing chart should run, as a `# needs <task>: <command>` line. Uncomment it when the feature lands, so the gallery and its test cover it. |

New options follow the [style guide](docs/styleguide.md#for-contributors-keeping-plotipus-inside-the-guide).
