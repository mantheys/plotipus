"""Fetch the Gaia DR2 HR diagram counts used by F22 (needs network access).

    python fetch_gaia.py            # both selections, into data/
    python fetch_gaia.py 200pc      # only one

The query is the one printed in Babusiaux et al. (2018), A&A 616, A10,
Appendix A: absolute magnitude M_G = G + 5 log10(parallax) - 10 and the
paper's astrometric and photometric quality filters. The Gaia archive bins the
stars itself (0.02 mag in BP - RP, 0.05 mag in M_G) and returns only the
counts, so the repository stores a small table instead of the star list.

Selections:
- ``all``: the paper's filters only, the stars of its Fig. 1 (65,921,112
  stars, the number in its caption; reddened by interstellar extinction);
- ``200pc``: the same filters and parallax > 5 mas. The paper's low-extinction
  diagram (Fig. 5) also requires E(B - V) < 0.015 from the STILISM 3D map,
  which is not in the archive; within 200 pc the extinction is small, and the
  paper's source mentions this selection (810,134 stars with the extinction
  cut).

Gaia data: ESA/Gaia/DPAC, licensed CC BY-SA 3.0 IGO; see data/README.md.
"""

import gzip
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

TAP = "https://gea.esac.esa.int/tap-server/tap/async"
COLOUR_BIN, MAGNITUDE_BIN = 0.02, 0.05
FILTERS = """parallax_over_error > 10
      AND phot_g_mean_flux_over_error > 50
      AND phot_rp_mean_flux_over_error > 20
      AND phot_bp_mean_flux_over_error > 20
      AND phot_bp_rp_excess_factor < 1.3 + 0.06 * power(phot_bp_mean_mag - phot_rp_mean_mag, 2)
      AND phot_bp_rp_excess_factor > 1.0 + 0.015 * power(phot_bp_mean_mag - phot_rp_mean_mag, 2)
      AND visibility_periods_used > 8
      AND astrometric_chi2_al / (astrometric_n_good_obs_al - 5)
          < 1.44 * greatest(1, exp(-0.4 * (phot_g_mean_mag - 19.5)))"""
SELECTIONS = {"all": "", "200pc": "parallax > 5 AND "}
DATA = Path(__file__).parent / "data"


def query(selection):
    return f"""SELECT FLOOR(bp_rp / {COLOUR_BIN}) AS ix, FLOOR(mg / {MAGNITUDE_BIN}) AS iy, COUNT(*) AS n
FROM (SELECT phot_g_mean_mag + 5 * log10(parallax) - 10 AS mg, bp_rp FROM gaiadr2.gaia_source
      WHERE {SELECTIONS[selection]}{FILTERS}) AS s
GROUP BY ix, iy"""


def run(adql, poll=30):
    """Run an asynchronous TAP job and return its CSV result."""
    # MAXREC: the archive returns at most 50,000 rows unless asked for more.
    form = urllib.parse.urlencode({"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "PHASE": "RUN",
                                   "MAXREC": 2_000_000, "QUERY": adql}).encode()
    with urllib.request.urlopen(urllib.request.Request(TAP, data=form)) as response:
        job = response.url
    while True:
        with urllib.request.urlopen(f"{job}/phase") as response:
            phase = response.read().decode()
        if phase == "COMPLETED":
            break
        if phase in ("ERROR", "ABORTED"):
            raise RuntimeError(f"Gaia archive job {job} ended in {phase}")
        time.sleep(poll)
    with urllib.request.urlopen(f"{job}/results/result") as response:
        return response.read()


def main(selections=None):
    DATA.mkdir(exist_ok=True)
    for selection in selections or SELECTIONS:
        adql = query(selection)
        print(f"Querying the Gaia archive ({selection}); this takes several minutes...")
        csv = run(adql)
        header = "".join(f"# {line}\n" for line in adql.splitlines()).encode()
        with gzip.GzipFile(DATA / f"gaia_dr2_hrd_{selection}.csv.gz", "wb", mtime=0) as handle:
            handle.write(header + csv)
        print(f"data/gaia_dr2_hrd_{selection}.csv.gz written")


if __name__ == "__main__":
    main(sys.argv[1:])
