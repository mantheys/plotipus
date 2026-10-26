# Regenerate the example project from scratch:
#   make          clean, then toy data, plots and tables
#   make clean    delete generated data and outputs (both gitignored)
#   make docs     the example figures, copied to docs/images/options for docs/options.md
#   make mascot   draw the mascot (docs/tutorial.md, and on black for the README) into docs/images/mascot
#   make famous   the famous-plot reproductions, also in the paper style; the README gallery (paper) goes to docs/images/famous
PYTHON ?= $(if $(wildcard ../.venv/bin/python),$(abspath ../.venv/bin/python),python3)
PLOTIPUS ?= $(PYTHON) -m plotipus

.PHONY: all data plots tables docs mascot famous clean

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
	cd mascot/dark && rm -rf output && $(PLOTIPUS) run mascot
	cp mascot/dark/output/plots/*_dark.png ../docs/images/mascot/mascot-dark.png

# The famous plots (examples/famous, and famous/paper in the paper style at one figure size);
# the README gallery is a selection of the paper renders, renamed.
FAMOUS_GALLERY = \
	higgsdiphoton_mass_events_error_component_weighting_unweighted_dataminusbackground_atlas.png:higgs-diphoton.png \
	fourlepton_mass_events_sample_stacked_line.png:four-lepton.png \
	higgslocalp0_mass_p0_error_hypothesis_logy_line.png:local-p0.png \
	higgslimit_mass_mulimit_error_limit_logx_logy_line.png:brazil-band.png \
	zlineshape_energy_crosssection_error_model_line.png:z-lineshape.png \
	kamland_lovere_survivalprobability_error_component_line.png:kamland.png \
	omegacontours_sn_riess1998_omegam_omegalambda_deltachi2_riess.png:omega-contours.png \
	hubble1929_distance_velocity_sample_line.png:hubble-1929.png \
	hrdiagram_bprp_mg_logz_hist2d.png:hr-diagram.png \
	keeling_decimaldate_co2_series_line.png:keeling.png \
	hockeystick_year_anomaly_error_series_line.png:hockey-stick.png \
	ngc3198_radius_velocity_error_component_line.png:ngc3198.png

famous:
	cd famous && $(PYTHON) make_data.py && rm -rf output && $(PLOTIPUS) run famous
	cd famous/paper && rm -rf output && $(PLOTIPUS) run famous
	rm -rf ../docs/images/famous && mkdir -p ../docs/images/famous
	for pair in $(FAMOUS_GALLERY); do cp "famous/paper/output/plots/$${pair%%:*}" "../docs/images/famous/$${pair##*:}"; done

clean:
	rm -rf output mascot/output mascot/dark/output famous/output famous/paper/output
	rm -f input/data/*.pkl mascot/input/data/*.pkl famous/input/data/*.pkl
