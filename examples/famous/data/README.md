# Gaia DR2 star counts (F22)

`gaia_dr2_hrd_all.csv.gz` and `gaia_dr2_hrd_200pc.csv.gz` count the Gaia DR2
stars in bins of 0.02 mag in G_BP - G_RP (`ix`) and 0.05 mag in absolute G
magnitude (`iy`): a bin covers `[ix, ix + 1) × 0.02` and `[iy, iy + 1) × 0.05`.
Each file starts with the ADQL query that produced it (`#` lines): the query
of Babusiaux et al. (2018), A&A 616, A10, Appendix A, binned by the archive,
with parallax > 5 mas added for `200pc`. `python fetch_gaia.py` refreshes
them (network access; several minutes per query).

`all` holds 65,921,112 stars, the number in the caption of the paper's Fig. 1;
`200pc` holds 1,322,033.

This work has made use of data from the European Space Agency (ESA) mission
Gaia (https://www.cosmos.esa.int/gaia), processed by the Gaia Data Processing
and Analysis Consortium (DPAC,
https://www.cosmos.esa.int/web/gaia/dpac/consortium). Funding for the DPAC has
been provided by national institutions, in particular the institutions
participating in the Gaia Multilateral Agreement.

The Gaia data are © ESA/Gaia/DPAC and licensed under CC BY-SA 3.0 IGO
(https://creativecommons.org/licenses/by-sa/3.0/igo/); these count tables are
derived from them and are distributed under the same licence.
