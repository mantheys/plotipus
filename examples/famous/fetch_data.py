"""Fetch the public datasets behind the real-data famous plots (needs network access).

    python fetch_data.py              # every source, into data/
    python fetch_data.py firas sparc  # only these

The files are small and committed, so make_data.py runs offline; this script
refreshes them. Sources, licences and citations: data/README.md. The Gaia
counts (F22) come from fetch_gaia.py, which runs archive queries.
"""

import io
import sys
import urllib.request
import zipfile
from pathlib import Path

DATA = Path(__file__).parent / "data"
SPARC = "https://astroweb.case.edu/SPARC"
LIGO = "https://gwosc.org/GW150914data/P150914"
# Rubin, Ford & Thonnard's galaxies in SPARC; the other Sc galaxies are chosen by sparc_selection().
RUBIN_IN_SPARC = ["NGC0801", "NGC2998", "UGC02885"]


def download(url):
    request = urllib.request.Request(url, headers={"User-Agent": "plotipus famous-plot examples"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def save(name, content):
    path = DATA / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    print(f"data/{name} ({len(content):,} bytes)")


def firas():
    """F06: COBE FIRAS monopole spectrum (Fixsen et al. 1996, Table 4), NASA LAMBDA."""
    save("firas_monopole_spec_v1.txt",
         download("https://lambda.gsfc.nasa.gov/data/cobe/firas/monopole_spec/firas_monopole_spec_v1.txt"))


def union():
    """F09, F10: Union2.1 supernova distance moduli (Suzuki et al. 2012)."""
    save("SCPUnion2.1_mu_vs_z.txt", download("https://supernova.lbl.gov/Union/figures/SCPUnion2.1_mu_vs_z.txt"))


def sparc_selection(table, n=21):
    """Rubin's galaxies found in SPARC, then quality-1 SBc-Scd galaxies
    (Hubble types 4-6; SPARC has only ten quality-1 Sc) spread evenly in flat
    velocity, ``n`` galaxies in all (NGC 3198, F12's galaxy, left out)."""
    rows = []
    for line in table.decode().splitlines():
        fields = line.split()
        if len(fields) >= 18 and fields[1].isdigit():
            rows.append((fields[0], int(fields[1]), float(fields[15]), int(fields[17])))
    candidates = sorted((r for r in rows if r[1] in (4, 5, 6) and r[3] == 1 and r[2] > 0
                         and r[0] not in RUBIN_IN_SPARC + ["NGC3198"]), key=lambda r: r[2])
    others = n - len(RUBIN_IN_SPARC)
    picks = [candidates[round(i * (len(candidates) - 1) / (others - 1))][0] for i in range(others)]
    assert len(set(picks)) == others, "not enough SPARC candidates"
    return RUBIN_IN_SPARC + picks


def sparc():
    """F11, F12: SPARC rotation curves (Lelli, McGaugh & Schombert 2016)."""
    table = download(f"{SPARC}/SPARC_Lelli2016c.mrt")
    save("sparc/SPARC_Lelli2016c.mrt", table)
    with zipfile.ZipFile(io.BytesIO(download(f"{SPARC}/Rotmod_LTG.zip"))) as archive:
        for galaxy in ["NGC3198"] + sparc_selection(table):
            save(f"sparc/{galaxy}_rotmod.dat", archive.read(f"{galaxy}_rotmod.dat"))


def keeling():
    """F13: Mauna Loa monthly mean CO2, NOAA GML and Scripps."""
    save("co2_mm_mlo.csv", download("https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.csv"))


def mbh99():
    """F14: Mann, Bradley & Hughes (1999) reconstruction, NOAA NCEI paleoclimatology."""
    save("mann99-nhem-noaa.txt",
         download("https://www.ncei.noaa.gov/pub/data/paleo/contributions_by_author/mann1999/mann99-nhem-noaa.txt"))


def gw150914():
    """F15: the filtered strain, numerical-relativity waveform and residual of
    PRL 116, 061102, Fig. 1 (LIGO/Virgo, GWOSC)."""
    for kind in ("observed", "waveform", "residual"):
        for detector in ("H", "L"):
            name = f"fig1-{kind}-{detector}.txt"
            save(f"gw150914/{name}", download(f"{LIGO}/{name}"))


SOURCES = {"firas": firas, "union": union, "sparc": sparc, "keeling": keeling, "mbh99": mbh99,
           "gw150914": gw150914}


def main(names=None):
    for name in names or SOURCES:
        SOURCES[name]()


if __name__ == "__main__":
    main(sys.argv[1:])
