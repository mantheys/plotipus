import numpy as np
import pymupdf

import vecx

page, d, words = vecx.load("atlas_hgg.pdf")
frames = sorted({(r.x0, r.y0, r.x1, r.y1) for r in (p["rect"] for p in d
                if p.get("fill") == (1.0, 1.0, 1.0) and p.get("color") == (0.0, 0.0, 0.0))}, key=lambda f: f[1])
frames = [pymupdf.Rect(*f) for f in frames]
fx, _ = vecx.x_calibration(frames[-1], words, d, frames[-1].y1)
centres = np.arange(101, 160, 2.0)


def points(kind, frame):
    fy, _ = vecx.y_calibration(frame, words, d)
    found = vecx.unique([m for m in vecx.markers(d, kind) if frame.contains(pymupdf.Point(m[0], m[1]))])
    bars = vecx.error_bars(d, found, frame)
    rows = []
    for (x, y, _), (lo, hi) in zip(found, bars):
        mass = float(fx(x))
        if abs(mass - centres[np.argmin(abs(centres - mass))]) > 0.08:
            continue  # legend symbol
        value, up, down = float(fy(y)), float(fy(lo)), float(fy(hi))
        rows.append((mass, value, up - value, value - down))
    return np.array(sorted(rows))


def curves(color, frame):
    fy, _ = vecx.y_calibration(frame, words, d)
    out = []
    for line in vecx.polylines(d, color, min_points=20):
        inside = [frame.contains(pymupdf.Point(*p)) for p in line]
        if np.mean(inside) > 0.9:
            out.append(np.column_stack([fx(line[:, 0]), fy(line[:, 1])]))
    return out


def write(out):
    """Data of the four panels and the fit curves, as CSV."""
    with open(f"{out}/atlas_hgg_fig4_data.csv", "w") as handle:
        handle.write("panel,mass,value,error_up,error_down\n")
        for name, kind, frame in (("a", "circle", frames[0]), ("b", "circle", frames[1]),
                                  ("c", "triangle", frames[2]), ("d", "triangle", frames[3])):
            for row in points(kind, frame):
                handle.write(f"{name}," + ",".join(f"{v:.3f}" for v in row) + "\n")
    with open(f"{out}/atlas_hgg_fig4_curves.csv", "w") as handle:
        handle.write("panel,curve,mass,value\n")
        for name, colour, frame in (("a", (1.0, 0.0, 0.0), frames[0]), ("b", (1.0, 0.0, 0.0), frames[1]),
                                    ("c", (0.0, 0.0, 1.0), frames[2]), ("d", (0.0, 0.0, 1.0), frames[3])):
            found = curves(colour, frame)
            # The signal + background curve rises above the background at 126.5 GeV.
            found.sort(key=lambda c: -np.interp(126.5, c[:, 0], c[:, 1]))
            for curve, label in zip(found, ("sig+bkg", "bkg")):
                for mass, value in curve:
                    handle.write(f"{name},{label},{mass:.3f},{value:.3f}\n")


if __name__ == "__main__":
    import sys
    write(sys.argv[1])
