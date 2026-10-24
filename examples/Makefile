# Regenerate the example project from scratch:
#   make          clean, then toy data, plots and tables
#   make clean    delete generated data and outputs (both gitignored)
PYTHON ?= $(if $(wildcard ../.venv/bin/python),../.venv/bin/python,python3)
PLOTIPUS ?= $(PYTHON) -m plotipus

.PHONY: all data plots tables clean

all: clean plots tables

data:
	$(PYTHON) make_data.py

plots: data
	$(PLOTIPUS) run example

tables: data
	$(PLOTIPUS) run example --tables

clean:
	rm -rf output
	rm -f input/data/*.pkl
