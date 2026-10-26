"""CMS 2012 (arXiv:1207.7235) Fig. 4: four-lepton mass, main panel."""

import sys

import numpy as np
import pymupdf

import vecx

page, d, words = vecx.load("cms_4l.pdf")
# The panel frames are the black-stroked rectangles: the main panel, then the inset.
frames = sorted((p["rect"] for p in d if p["items"][0][0] == "re" and p.get("color") == (0.0, 0.0, 0.0)),
                key=lambda r: -r.width)
frame = frames[0]
fx, rx = vecx.x_calibration(frame, words, d, frame.y1)
fy, ry = vecx.y_calibration(frame, words, d)


def horizontal_top(polygon, x):
    """Page y of the highest horizontal edge of ``polygon`` spanning ``x``."""
    tops = [min(a[1], b[1]) for a, b in zip(polygon[:-1], polygon[1:])
            if abs(a[1] - b[1]) < 0.01 and min(a[0], b[0]) < x < max(a[0], b[0])]
    return min(tops) if tops else None


def inside(points):
    """Share of ``points`` inside the main frame."""
    return np.mean([frame.contains(pymupdf.Point(*q)) for q in points])


def histogram(polygon, centres, to_page):
    values = []
    for centre in centres:
        top = horizontal_top(polygon, to_page(centre))
        values.append(float(fy(top)) if top is not None else 0.0)
    return np.array(values)


def outline(colour):
    """The step outline (stroke) of ``colour`` inside the main frame, as a polygon."""
    for path in d:
        if tuple(round(c, 3) for c in (path.get("color") or ())) == colour and len(path["items"]) > 20:
            first = path["items"][0][1]
            points = np.array([(first.x, first.y)] + [(it[2].x, it[2].y) for it in path["items"]])
            if np.mean([frame.contains(pymupdf.Point(*p)) for p in points]) > 0.8:
                return points
    return None


def main(out):
    print("calibration residuals", rx, ry, "x range", fx(frame.x0), fx(frame.x1), "y range", fy(frame.y1), fy(frame.y0))
    blue = max((p for p in vecx.polygons(d, (0.6, 0.8, 1.0)) if inside(p) > 0.8), key=len)
    # The histogram steps are 3 GeV bins from 70.5 GeV; the axis labels put them
    # a little higher (no label at the axis ends), so shift x by that offset.
    steps = np.unique(np.round(fx(blue[:, 0]), 3))
    shift = float(np.median((steps - 70.5) % 3.0))
    shift = shift - 3.0 if shift > 1.5 else shift
    edges = np.arange(70.5, 181.5 + 1e-6, 3.0)
    centres = (edges[:-1] + edges[1:]) / 2
    print("x shift", round(shift, 3))

    def to_page(mass):
        return float(np.interp(mass + shift, [fx(frame.x0), fx(frame.x1)], [frame.x0, frame.x1]))

    green = max((p for p in vecx.polygons(d, (0.4, 0.6, 0.4)) if inside(p) > 0.8), key=len)
    red = outline((1.0, 0.2, 0.0))
    zx = histogram(green, centres, to_page)
    zz_plus_zx = histogram(blue, centres, to_page)
    total = histogram(red, centres, to_page)
    found = vecx.unique([m for m in vecx.markers(d, "circle") if frame.contains(pymupdf.Point(m[0], m[1]))
                         and not frames[1].contains(pymupdf.Point(m[0], m[1]))])
    bars = vecx.error_bars(d, found, frame)
    data = sorted((float(fx(x)) - shift, float(fy(y)), float(fy(top)) - float(fy(y)), float(fy(y)) - float(fy(bottom)))
                  for (x, y, _), (top, bottom) in zip(found, bars))
    # Data sit at bin centres (the legend symbol does not); counts are integers.
    data = [(centres[np.argmin(abs(centres - m))], round(v), up, down) for m, v, up, down in data
            if np.min(abs(centres - m)) < 0.2]
    with open(f"{out}/cms_4l_fig4.csv", "w") as handle:
        handle.write("kind,mass,value,error_up,error_down\n")
        for mass, value, up, down in data:
            handle.write(f"data,{mass:.3f},{value:.3f},{up:.3f},{down:.3f}\n")
        for kind, values in (("Z+X", zx), ("ZZ", zz_plus_zx - zx), ("signal", total - zz_plus_zx)):
            for mass, value in zip(centres, values):
                handle.write(f"{kind},{mass:.3f},{value:.4f},,\n")
    print("edges", edges[0], edges[-1], len(centres), "data points", len(data))
    print("totals: Z+X", zx.sum().round(2), "ZZ", (zz_plus_zx - zx).sum().round(2),
          "signal", (total - zz_plus_zx).sum().round(2),
          "signal 110-160", (total - zz_plus_zx)[(centres > 110) & (centres < 160)].sum().round(2),
          "data", sum(v for _, v, _, _ in data))


if __name__ == "__main__":
    main(sys.argv[1])
