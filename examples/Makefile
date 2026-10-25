# Regenerate the example project from scratch:
#   make          clean, then toy data, plots and tables
#   make clean    delete generated data and outputs (both gitignored)
#   make docs     the example figures, copied to docs/images/options for docs/options.md
#   make mascot   draw the mascot (docs/tutorial.md) into docs/images/mascot
PYTHON ?= $(if $(wildcard ../.venv/bin/python),$(abspath ../.venv/bin/python),python3)
PLOTIPUS ?= $(PYTHON) -m plotipus

.PHONY: all data plots tables docs mascot clean

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

# The five steps of the tutorial, named after the last word of their --output_suffix.
mascot:
	cd mascot && $(PYTHON) make_mascot.py && rm -rf output && $(PLOTIPUS) run mascot
	mkdir -p ../docs/images/mascot
	for f in mascot/output/plots/*.png; do cp "$$f" "../docs/images/mascot/$${f##*_}"; done

clean:
	rm -rf output mascot/output
	rm -f input/data/*.pkl mascot/input/data/*.pkl
