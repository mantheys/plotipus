"""KamLAND 2008 (arXiv:0801.4589) Fig. 3 and LEP (hep-ex/0509008) Fig. 1.13."""

import sys

import numpy as np
import pymupdf

import vecx


def axis(words, d, select, along, ticks_from=None):
    """Linear map from the page coordinate ``along`` ('x' or 'y') to value,
    from the numeric words chosen by ``select(word)``, snapped to ticks."""
    labels = []
    for w in words:
        if vecx.NUMBER.match(w[4]) and select(w):
            centre = (w[0] + w[2]) / 2 if along == "x" else (w[1] + w[3]) / 2
            labels.append((centre, vecx.number(w[4])))
    return vecx.calibrate_axis(labels, ticks_from or [], along)


def segments_near(d, x, y, radius):
    """Bars through or touching a marker: (orientation, low, high) in page units."""
    out = []
    for x0, y0, x1, y1, *_ in vecx.lines(d):
        if abs(x0 - x1) < 0.01 and abs(x0 - x) < 0.6 and min(y0, y1) - radius <= y <= max(y0, y1) + radius:
            out.append(("v", min(y0, y1), max(y0, y1)))
        if abs(y0 - y1) < 0.01 and abs(y0 - y) < 0.6 and min(x0, x1) - radius <= x <= max(x0, x1) + radius:
            out.append(("h", min(x0, x1), max(x0, x1)))
    for path in d:
        r = path["rect"]
        if path["items"][0][0] == "re" and path.get("fill"):
            if r.width < 1.5 <= r.height and abs((r.x0 + r.x1) / 2 - x) < 0.6 and r.y0 - radius <= y <= r.y1 + radius:
                out.append(("v", r.y0, r.y1))
            if r.height < 1.5 <= r.width and abs((r.y0 + r.y1) / 2 - y) < 0.6 and r.x0 - radius <= x <= r.x1 + radius:
                out.append(("h", r.x0, r.x1))
    return out


def kamland(out):
    page, d, words = vecx.load("kamland.pdf")
    # Rotated figure: L0/E runs along page y (labels near x = 420), the probability along page x (labels near y = 550).
    f_le, r_le = axis(words, d, lambda w: 405 < w[0] < 440, "y")
    f_p, r_p = axis(words, d, lambda w: 540 < w[1] < 560 or 540 < (w[1] + w[3]) / 2 < 580, "x")
    print("kamland calibration residuals", r_le, r_p)
    points = vecx.unique(vecx.markers(d, "circle"))
    rows = []
    for x, y, width in points:
        bars = segments_near(d, x, y, width / 2 + 1)
        probability_bars = [b for b in bars if b[0] == "h"]
        le_bars = [b for b in bars if b[0] == "v"]
        if not probability_bars and not le_bars:
            continue  # legend symbol
        p, le = float(f_p(x)), float(f_le(y))
        p_lo = min(b[1] for b in probability_bars) if probability_bars else x
        p_hi = max(b[2] for b in probability_bars) if probability_bars else x
        le_lo = min(b[1] for b in le_bars) if le_bars else y
        le_hi = max(b[2] for b in le_bars) if le_bars else y
        errors = sorted([abs(float(f_p(p_lo)) - p), abs(float(f_p(p_hi)) - p)])
        widths = sorted([float(f_le(le_lo)), float(f_le(le_hi))])
        rows.append((le, p, abs(float(f_p(p_hi)) - p), abs(float(f_p(p_lo)) - p), widths[0], widths[1]))
    rows.sort()
    curves = []
    for colour, label in (((0.4, 0.4, 1.0), "histogram"), ((0.709, 0.729, 1.0), "curve")):
        for line in vecx.polylines(d, colour, min_points=10):
            curves.append((label, np.column_stack([f_le(line[:, 1]), f_p(line[:, 0])])))
    with open(f"{out}/kamland_fig3.csv", "w") as handle:
        handle.write("kind,l_over_e,survival,error_a,error_b,le_low,le_high\n")
        for row in rows:
            handle.write("data," + ",".join(f"{v:.4f}" for v in row) + "\n")
        for label, curve in curves:
            for le, p in curve:
                handle.write(f"{label},{le:.4f},{p:.4f},,,,\n")
    print("kamland data", len(rows), [tuple(round(v, 3) for v in r) for r in rows[:4]])


def lep(out):
    page, d, words = vecx.load("lep_nnu.pdf")
    f_e, r_e = axis(words, d, lambda w: w[1] > 455 and w[3] < 490, "x")
    f_s, r_s = axis(words, d, lambda w: w[2] < 80, "y")
    print("lep calibration residuals", r_e, r_s)
    rows = []
    for x, y, width in vecx.unique(vecx.markers(d, "circle", fill=(1.0, 0.0, 0.0))):
        bars = [b for b in segments_near(d, x, y, width / 2 + 1) if b[0] == "v"]
        energy, value = float(f_e(x)), float(f_s(y))
        low = max(b[2] for b in bars) if bars else y
        high = min(b[1] for b in bars) if bars else y
        rows.append((energy, value, float(f_s(high)) - value, value - float(f_s(low))))
    # The legend symbol sits left of the scan (below 86 GeV); the error bars are drawn x10.
    rows = sorted((e, v, up / 10, down / 10) for e, v, up, down in rows if e > 86)
    red = vecx.polylines(d, (1.0, 0.0, 0.0), min_points=10)
    green = vecx.polylines(d, (0.0, 1.0, 0.0), min_points=10)
    # Each curve is drawn as five consecutive pieces: the 2 nu curve first, then 4 nu.
    curves = {"2nu": red[:5], "3nu": green, "4nu": red[5:10]}
    with open(f"{out}/lep_nnu_fig1_13.csv", "w") as handle:
        handle.write("kind,energy,sigma_had,error_up,error_down\n")
        for row in rows:
            handle.write("data," + ",".join(f"{v:.4f}" for v in row) + "\n")
        for name, pieces in curves.items():
            points = np.concatenate([np.column_stack([f_e(p[:, 0]), f_s(p[:, 1])]) for p in pieces])
            points = points[(points[:, 0] >= 85) & (points[:, 0] <= 94.5)]
            for energy, value in np.unique(points.round(4), axis=0):
                handle.write(f"{name},{energy:.4f},{value:.4f},,\n")
    print("lep data", [tuple(round(v, 3) for v in r) for r in rows])


if __name__ == "__main__":
    kamland(sys.argv[1])
    lep(sys.argv[1])
