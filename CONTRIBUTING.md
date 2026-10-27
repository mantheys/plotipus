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

New options follow the [style guide](docs/styleguide.md#for-contributors-keeping-plotipus-inside-the-guide).
