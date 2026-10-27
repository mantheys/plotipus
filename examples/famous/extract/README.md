# Values extracted from vector figures

The Higgs (ATLAS, CMS), KamLAND and LEP figures have no public data tables
(HEPData has no records for these papers), but the arXiv sources keep them as
vector graphics, where every marker, error bar, curve and band is a drawing
command with exact page coordinates. `run.py` reads those commands with PyMuPDF
and maps them to physics units:

- **Axes:** each panel's tick labels are text with positions; their centres are
  snapped to the major tick marks and fitted linearly (or in log10 for log
  axes). Residuals: below 0.01 GeV on mass axes, 0.5 events (ATLAS 2 GeV
  panels), below 0.001 decade on the CMS/ATLAS log axes.
- **Data:** filled circles and triangles; their vertical error bars are
  stroked segments or thin filled rectangles through or touching the marker.
  Legend symbols are dropped (they are off the bin centres).
- **Curves and bands:** stroked polylines and filled polygons by colour; a
  band polygon is split into its two edges at its rightmost point.

Precision is set by the figures themselves: ROOT wrote coordinates in 0.25 pt
steps, about 2 events in ATLAS Fig. 4(a), 0.5 events in 4(b), 0.01 in CMS
Fig. 4. Cross-checks that pass: ATLAS 4(a) minus the background curve equals
4(b) (rms 1.5 events); the CMS data errors are exact Garwood intervals and its
signal histogram holds 7.42 events in 110-160 GeV (CMS Table 3: 7.54); the LEP
curves peak at 35.05, 30.76 and 27.22 nb. The CMS inset (K_D > 0.5) holds
the 13 events of its 10 points. CMS's x axis is shifted by
0.16 GeV onto its 3 GeV bin edges from 70.5 GeV.

These are values read from published figures, not the collaborations' data;
the figures and their source files are the papers' (arXiv:1207.7214,
1207.7235, 0801.4589, hep-ex/0509008).

Requirements: `pip install pymupdf` and Ghostscript (`gs`).
