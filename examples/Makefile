# Regenerate the example project from scratch:
#   make          clean, then toy data, plots and tables
#   make clean    delete generated data and outputs (both gitignored)
#   make docs     render the figures of docs/options.md into docs/images/options
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

# Each figure is named after the last word of its --output_suffix.
docs: data
	rm -rf output/docs
	$(PLOTIPUS) run docs
	mkdir -p ../docs/images/options
	for f in output/docs/*.png; do cp "$$f" "../docs/images/options/$${f##*_}"; done

# The five steps of the tutorial, named after the last word of their --output_suffix.
mascot:
	cd mascot && $(PYTHON) make_mascot.py && rm -rf output && $(PLOTIPUS) run mascot
	mkdir -p ../docs/images/mascot
	for f in mascot/output/plots/*.png; do cp "$$f" "../docs/images/mascot/$${f##*_}"; done

clean:
	rm -rf output mascot/output
	rm -f input/data/*.pkl mascot/input/data/*.pkl
