"""Extract the plotted values of six famous figures from their vector graphics.

    pip install pymupdf      # and Ghostscript (gs) on the PATH
    python extract/run.py    # writes data/extracted/*.csv

Downloads the arXiv sources (ATLAS 1207.7214, CMS 1207.7235, KamLAND
0801.4589, LEP hep-ex/0509008) into a temporary folder, converts the EPS
figures to PDF with Ghostscript, and reads the markers, error bars, curves and
bands from the PDF drawing commands; see README.md for the method and its
precision.
"""

import io
import importlib
import os
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "data" / "extracted"
# (arXiv id, file in the source, name used by the extractors)
FIGURES = [
    ("1207.7214", "mggweighted_panel_nonorm.eps", "atlas_hgg.pdf"),
    ("1207.7214", "disc3_0_sig_p0_zoom.eps", "atlas_p0.pdf"),
    ("1207.7214", "CombinedResults.eps", "atlas_limit.pdf"),
    ("1207.7235", "H4l_mass_v3.pdf", "cms_4l.pdf"),
    ("0801.4589", "LE.eps", "kamland.pdf"),
    ("hep-ex/0509008", "Nnu.eps", "lep_nnu.pdf"),
]


def source(arxiv_id, cache):
    """The arXiv source tarball of ``arxiv_id``, extracted under ``cache``."""
    folder = cache / arxiv_id.replace("/", "_")
    if not folder.exists():
        request = urllib.request.Request(f"https://arxiv.org/src/{arxiv_id}",
                                         headers={"User-Agent": "plotipus famous-plot examples"})
        with urllib.request.urlopen(request, timeout=300) as response:
            archive = response.read()
        folder.mkdir(parents=True)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(folder, filter="data")
    return folder


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as work:
        work = Path(work)
        for arxiv_id, name, target in FIGURES:
            path = source(arxiv_id, work / "src") / name
            if path.suffix == ".eps":
                subprocess.run(["gs", "-q", "-dSAFER", "-dBATCH", "-dNOPAUSE", "-sDEVICE=pdfwrite", "-dEPSCrop",
                                f"-sOutputFile={work / target}", str(path)], check=True)
            else:
                (work / target).write_bytes(path.read_bytes())
        sys.path.insert(0, str(HERE))
        os.chdir(work)
        for module, calls in (("extract_atlas_hgg", ["write"]), ("extract_atlas_p0_limit", ["p0", "limit"]),
                              ("extract_cms_4l", ["main"]), ("extract_kamland_lep", ["kamland", "lep"])):
            loaded = importlib.import_module(module)
            for call in calls:
                getattr(loaded, call)(str(OUT))
    print(f"written to {OUT}")


if __name__ == "__main__":
    main()
