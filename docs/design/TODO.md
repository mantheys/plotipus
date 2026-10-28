# TODO: out of scope for now

Charts and features deliberately left out of the current redesign (decision
D7 in [roadmap.md](roadmap.md)). Each entry says what would be needed, so it
can be picked up later.

## Charts

- **Polar-area chart (Nightingale's rose, F23).**
  - Wedges on a polar axis whose radius is √value, so area ∝ value.
  - Overlapping (not stacked) wedges per cause.
  - Likely shape: `cat --projection polar` or `--kind polar`.
  - Public data: R `HistData::Nightingale`.
  - Until then, stacked monthly bars are the fallback (catalogue D4).
- **Geographic maps (Snow's cholera map, Minard's route).**
  - Needs a basemap layer (street map or coastline) and longitude/latitude
    axes. That means a new dependency (cartopy or geopandas), which plotipus
    avoids today.
  - Public data: `HistData::Snow.deaths`, `HistData::Minard.*`.
- **Flow lines with variable width (Minard, F24).**
  - Line segments whose width encodes a value (`--widthby`), coloured by
    direction.
  - Labels from a second DataFrame.
  - A lower panel fed by a third DataFrame on the shared x.
- **3D surfaces and interactive output.** Not planned. plotipus writes
  static publication figures.

## Related features also postponed

- **Broken axes with a gap** (the ATLAS Brazil plot, F05).
  - Two ranges of one axis side by side, with the break drawn as slanted
    marks on both frames.
  - Likely shape: `--xbreak LOW HIGH`: two panels sharing y, sized by the
    ranges they show, their facing spines hidden.
  - The hybrid log/linear axis (Planck TT, F07) and the secondary axis
    (COBE FIRAS, F06) are done: `--xscale 'log<B<linear'` and
    `--secondary_x` (catalogue H6, H7).

The famous plots no longer wait on public datasets (decision D6 is
superseded): `examples/famous/fetch_data.py` and `fetch_gaia.py` download
FIRAS, Union2.1, SPARC, NOAA Mauna Loa, Mann et al. 1999, GWOSC and Gaia
DR2 data into `examples/famous/data/`, and `examples/famous/extract/`
reads the Higgs, KamLAND and LEP values from the published vector figures.
Only F19–F21 (1912–1913 tables, kept as scans) stay synthetic.
