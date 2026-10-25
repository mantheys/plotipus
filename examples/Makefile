# Regenerate the example project from scratch:
#   make          clean, then toy data, plots and tables
#   make clean    delete generated data and outputs (both gitignored)
#   make docs     render the figures of docs/options.md into docs/images/options
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

# Each figure is named after the last word of its --output_suffix.
docs: data
	rm -rf output/docs
	$(PLOTIPUS) run docs
	mkdir -p ../docs/images/options
	for f in output/docs/*.png; do cp "$$f" "../docs/images/options/$${f##*_}"; done

clean:
	rm -rf output
	rm -f input/data/*.pkl
