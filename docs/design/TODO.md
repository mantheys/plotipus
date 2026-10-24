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

- **Hybrid log/linear or broken axes** (Planck TT, F07; ATLAS limit plot,
  F05). Catalogue H7, roadmap 4.16.
- **Secondary axis with unit conversion** (COBE FIRAS in GHz vs cm⁻¹, F06).
  Catalogue H6, roadmap 4.16.
- **Downloading public datasets** (NOAA Mauna Loa, Union2.1, Gaia,
  HEPData). Decision D6: synthetic data for now. The famous-plots dataset
  (tasks/T24) will synthesise realistic data first.
