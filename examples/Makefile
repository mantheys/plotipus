# Regenerate the example project from scratch:
#   make          clean, then toy data, plots and tables
#   make clean    delete generated data and outputs (both gitignored)
#   make docs     the example figures, copied to docs/images/options for docs/options.md
PYTHON ?= $(if $(wildcard ../.venv/bin/python),../.venv/bin/python,python3)
PLOTIPUS ?= $(PYTHON) -m plotipus

.PHONY: all data plots tables docs clean

all: clean plots tables

data:
	$(PYTHON) make_data.py

plots: data
	$(PLOTIPUS) run example

tables: data
	$(PLOTIPUS) run example --tables

# The example figures, renamed after the last word of their --output_suffix.
docs: data
	rm -rf output/plots
	$(PLOTIPUS) run example
	rm -rf ../docs/images/options && mkdir -p ../docs/images/options
	for f in output/plots/*.png; do cp "$$f" "../docs/images/options/$${f##*_}"; done

clean:
	rm -rf output
	rm -f input/data/*.pkl
