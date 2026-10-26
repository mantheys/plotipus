# Public data behind the famous plots

The generators read these files; `make_data.py` runs offline. Refresh them with
`python fetch_data.py` (direct downloads) and `python fetch_gaia.py` (Gaia
archive queries, several minutes each). Each source keeps its own terms; the
files here are copies or counts derived from them, redistributed under those
terms with the acknowledgements they ask for.

| figure | file | source | terms |
|---|---|---|---|
| F06 | `firas_monopole_spec_v1.txt` | COBE/FIRAS monopole spectrum, Fixsen et al. 1996, ApJ 473, 576, Table 4; NASA LAMBDA | NASA data, public domain; cite Fixsen et al. 1996 |
| F09, F10 | `SCPUnion2.1_mu_vs_z.txt` | Union2.1 compilation, Suzuki et al. 2012, ApJ 746, 85; Supernova Cosmology Project | public; cite Suzuki et al. 2012 |
| F11, F12 | `sparc/` | SPARC, Lelli, McGaugh & Schombert 2016, AJ 152, 157 (NGC 3198 and 21 SBc-Scd galaxies of `Rotmod_LTG.zip`, and the galaxy table) | public; cite Lelli et al. 2016 |
| F13 | `co2_mm_mlo.csv` | Mauna Loa monthly mean CO2, Dr. Xin Lan, NOAA/GML (gml.noaa.gov/ccgg/trends/) and Dr. Ralph Keeling, Scripps Institution of Oceanography (scrippsco2.ucsd.edu) | NOAA data, public; credit NOAA GML and Scripps as above |
| F14 | `mann99-nhem-noaa.txt` | Mann, Bradley & Hughes 1999, GRL 26, 759; NOAA NCEI Paleoclimatology (study 6276) | NOAA data, public; cite Mann et al. 1999 |
| F15 | `gw150914/` | the data of Fig. 1 of Abbott et al. 2016, PRL 116, 061102 (LIGO Scientific Collaboration and Virgo Collaboration), from GWOSC (gwosc.org) | CC BY 4.0; cite Abbott et al. 2016 and GWOSC |
| F22 | `gaia_dr2_hrd_all.csv.gz`, `gaia_dr2_hrd_200pc.csv.gz` | Gaia DR2 star counts from the query of Babusiaux et al. 2018, A&A 616, A10, Appendix A | CC BY-SA 3.0 IGO; acknowledgement below |

## Gaia DR2 star counts (F22)

`gaia_dr2_hrd_all.csv.gz` and `gaia_dr2_hrd_200pc.csv.gz` count the Gaia DR2
stars in bins of 0.02 mag in G_BP - G_RP (`ix`) and 0.05 mag in absolute G
magnitude (`iy`): a bin covers `[ix, ix + 1) × 0.02` and `[iy, iy + 1) × 0.05`.
Each file starts with the ADQL query that produced it (`#` lines): the query
of Babusiaux et al. (2018), binned by the archive, with parallax > 5 mas
added for `200pc`. `all` holds 65,921,112 stars, the number in the caption of
the paper's Fig. 1; `200pc` holds 1,322,033.

This work has made use of data from the European Space Agency (ESA) mission
Gaia (https://www.cosmos.esa.int/gaia), processed by the Gaia Data Processing
and Analysis Consortium (DPAC,
https://www.cosmos.esa.int/web/gaia/dpac/consortium). Funding for the DPAC has
been provided by national institutions, in particular the institutions
participating in the Gaia Multilateral Agreement. The Gaia data are
© ESA/Gaia/DPAC and licensed under CC BY-SA 3.0 IGO
(https://creativecommons.org/licenses/by-sa/3.0/igo/); these count tables are
derived from them and are distributed under the same licence.

## GW150914 (F15)

This research has made use of data obtained from the Gravitational Wave Open
Science Center (gwosc.org), a service of the LIGO Scientific Collaboration,
the Virgo Collaboration and KAGRA.
