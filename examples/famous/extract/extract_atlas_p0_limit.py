"""ATLAS 2012 (arXiv:1207.7214): Fig. 9 (local p0) and Fig. 7(a) (95% CL limit on mu)."""

import sys

import numpy as np
import pymupdf

import vecx


def black_curves(d, frame, fx, fy):
    """Solid and dashed black polylines inside ``frame``, in data units."""
    solid, dashed = [], []
    for path in d:
        if not vecx.same_colour(path.get("color"), (0.0, 0.0, 0.0)) or path.get("fill"):
            continue
        items = [it for it in path["items"] if it[0] == "l"]
        if len(items) < 20:
            continue
        points = np.array([(items[0][1].x, items[0][1].y)] + [(it[2].x, it[2].y) for it in items])
        if np.mean([frame.contains(pymupdf.Point(*p)) for p in points]) < 0.8:
            continue
        curve = np.column_stack([fx(points[:, 0]), fy(points[:, 1])])
        is_dashed = bool(path.get("dashes")) and path.get("dashes") not in ("[] 0", "[] 0.0")
        (dashed if is_dashed else solid).append(curve)
    return _unique(solid), _unique(dashed)


def _unique(curves):
    """Curves drawn more than once, kept once."""
    out = []
    for curve in curves:
        if not any(len(c) == len(curve) and np.allclose(c, curve) for c in out):
            out.append(curve)
    return out


def p0(out):
    page, d, words = vecx.load("atlas_p0.pdf")
    frame = pymupdf.Rect(85.0, 20.25, 510.25, 345.25)
    fx, _ = vecx.x_calibration(frame, words, d, frame.y1)
    fy, _ = vecx.y_log_calibration(frame, words, d)
    _, dashed = black_curves(d, frame, fx, fy)
    band = vecx.polygons(d, (0.4, 0.8, 1.0))
    band = max(band, key=len)
    upper, lower = vecx.band_edges(band)
    # The observed p0 is drawn as dots at the computed masses (joined by a line).
    # (The legend's "Obs." symbol is a dot too, above p0 = 1.)
    observed = np.array(sorted((float(fx(x)), float(fy(y))) for x, y, _ in vecx.unique(vecx.markers(d, "circle"))
                               if frame.contains(pymupdf.Point(x, y)) and float(fy(y)) <= 0))
    with open(f"{out}/atlas_p0_fig9.csv", "w") as handle:
        handle.write("curve,mass,log10_p0\n")
        for label, curve in (("observed", observed), ("expected", max(dashed, key=len))):
            for mass, value in curve:
                handle.write(f"{label},{mass:.3f},{value:.4f}\n")
        for label, edge in (("band_a", upper), ("band_b", lower)):
            for mass, value in np.column_stack([fx(edge[:, 0]), fy(edge[:, 1])]):
                handle.write(f"{label},{mass:.3f},{value:.4f}\n")
    print("p0:", len(observed), [len(c) for c in dashed], len(band))


def limit(out):
    page, d, words = vecx.load("atlas_limit.pdf")
    frame = pymupdf.Rect(80.25, 12.5, 446.25, 239.25)
    fx, _ = vecx.x_log_calibration(pymupdf.Rect(80.25, 466.0, 446.25, 688.25), words, d, 688.25)
    fy, _ = vecx.y_log_calibration(frame, words, d)
    solid, dashed = black_curves(d, frame, fx, fy)
    with open(f"{out}/atlas_limit_fig7a.csv", "w") as handle:
        handle.write("curve,log10_mass,log10_mu\n")
        for label, curves in (("observed", solid), ("expected", dashed)):
            for curve in curves:  # long curves are split into several paths
                for mass, value in curve:
                    handle.write(f"{label},{mass:.5f},{value:.5f}\n")
        for label, colour in (("band1", (0.0, 1.0, 0.0)), ("band2", (1.0, 1.0, 0.0))):
            for polygon in vecx.polygons(d, colour):
                if np.mean([frame.contains(pymupdf.Point(*p)) for p in polygon]) < 0.5:
                    continue
                for name, edge in zip(("a", "b"), vecx.band_edges(polygon)):
                    for mass, value in np.column_stack([fx(edge[:, 0]), fy(edge[:, 1])]):
                        handle.write(f"{label}_{name},{mass:.5f},{value:.5f}\n")
    print("limit:", [len(c) for c in solid], [len(c) for c in dashed])


if __name__ == "__main__":
    p0(sys.argv[1])
    limit(sys.argv[1])
