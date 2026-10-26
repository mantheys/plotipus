"""Vector-figure data extraction helpers (PyMuPDF): axis calibration from tick
labels and tick marks, markers with error bars, and coloured polylines."""

import re

import numpy as np
import pymupdf

NUMBER = re.compile(r"^[−-]?\d+(\.\d+)?$")


def load(path):
    page = pymupdf.open(path)[0]
    return page, page.get_drawings(), page.get_text("words")


def number(text):
    return float(text.replace("−", "-"))


def same_colour(a, b, tolerance=0.006):
    """Whether colours a and b (tuples, possibly empty) match."""
    a, b = tuple(a or ()), tuple(b or ())
    return len(a) == len(b) and all(abs(x - y) <= tolerance for x, y in zip(a, b))


def lines(drawings, color=None):
    """All straight segments as (x0, y0, x1, y1, color, width)."""
    out = []
    for path in drawings:
        if color is not None and not same_colour(path.get("color"), color):
            continue
        for item in path["items"]:
            if item[0] == "l":
                out.append((item[1].x, item[1].y, item[2].x, item[2].y, path.get("color"), path.get("width")))
    return out


def calibrate_axis(labels, ticks, along):
    """Linear map from page coordinate to value: label centres snapped to the
    nearest tick mark, then least squares. ``labels``: [(position, value)]."""
    positions, values = [], []
    for position, value in labels:
        if ticks:
            nearest = min(ticks, key=lambda t: abs(t - position))
            if abs(nearest - position) < 3:
                position = nearest
        positions.append(position)
        values.append(value)
    slope, intercept = np.polyfit(positions, values, 1)
    residual = np.max(np.abs(np.polyval([slope, intercept], positions) - values)) if len(values) > 2 else 0
    return (lambda p: slope * np.asarray(p) + intercept), residual


def y_calibration(frame, words, drawings, log=False):
    """Map page y to value for a panel framed by ``frame`` from its left tick labels."""
    labels = []
    for x0, y0, x1, y1, text, *_ in words:
        # Tick labels end just left of the axis; axis titles sit further out.
        if frame.x0 - 8 <= x1 <= frame.x0 + 1 and frame.y0 - 4 <= (y0 + y1) / 2 <= frame.y1 + 4 and NUMBER.match(text):
            labels.append(((y0 + y1) / 2, number(text)))
    marks = [(y0, abs(x1 - x0)) for x0, y0, x1, y1, *_ in lines(drawings)
             if abs(y0 - y1) < 0.01 and min(x0, x1) <= frame.x0 + 0.5 and 1 < abs(x1 - x0) < 0.2 * frame.width
             and frame.y0 - 1 <= y0 <= frame.y1 + 1]
    longest = max((length for _, length in marks), default=0)
    ticks = [y for y, length in marks if length >= 0.8 * longest]
    if log:
        labels = [(p, np.log10(v)) for p, v in labels]
    return calibrate_axis(labels, ticks, "y")


def x_calibration(frame, words, drawings, below):
    """Map page x to value from the tick labels under ``below`` (the bottom of the lowest frame)."""
    labels = [((x0 + x1) / 2, number(text)) for x0, y0, x1, y1, text, *_ in words
              if below - 2 <= y0 <= below + 25 and NUMBER.match(text)]
    marks = [(x0, abs(y1 - y0)) for x0, y0, x1, y1, *_ in lines(drawings)
             if abs(x0 - x1) < 0.01 and 1 < abs(y1 - y0) < 0.2 * frame.height and frame.x0 - 1 <= x0 <= frame.x1 + 1
             and max(y0, y1) >= below - 0.5 >= min(y0, y1) - 20]
    longest = max((length for _, length in marks), default=0)
    ticks = [x for x, length in marks if length >= 0.8 * longest]
    return calibrate_axis(labels, ticks, "x")


def markers(drawings, kind, fill=(0.0, 0.0, 0.0)):
    """Centres (x, y) of filled markers: 'circle' (four Bezier curves) or
    'triangle' (two lines and a close)."""
    out = []
    for path in drawings:
        if not same_colour(path.get("fill"), fill):
            continue
        ops = [item[0] for item in path["items"]]
        if (kind == "circle" and ops == ["c"] * 4) or (kind == "triangle" and ops == ["l", "l"]):
            rect = path["rect"]
            centre_y = (rect.y0 + rect.y1) / 2 if kind == "circle" else rect.y0 + 2 * (rect.y1 - rect.y0) / 3
            if kind == "triangle":
                # The centroid of an upward triangle sits 2/3 down from its apex.
                centre_y = rect.y0 + 2 * (rect.y1 - rect.y0) / 3
            out.append(((rect.x0 + rect.x1) / 2, centre_y, rect.width))
    return out


def error_bars(drawings, centres, frame=None, tolerance=0.6):
    """Lowest and highest page y of the vertical bars through each marker
    centre: stroked vertical segments or thin filled rectangles (ROOT draws
    error bars both ways), inside ``frame`` when given."""
    bars = [(x0, min(y0, y1), max(y0, y1)) for x0, y0, x1, y1, *_ in lines(drawings) if abs(x0 - x1) < 0.01]
    for path in drawings:
        rect = path["rect"]
        if path["items"][0][0] == "re" and path.get("fill") and rect.width < 1.5 and rect.height > rect.width:
            bars.append(((rect.x0 + rect.x1) / 2, rect.y0, rect.y1))
    if frame is not None:
        bars = [(x, max(lo, frame.y0), min(hi, frame.y1)) for x, lo, hi in bars
                if frame.x0 <= x <= frame.x1 and hi >= frame.y0 and lo <= frame.y1]
    out = []
    for x, y, width in centres:
        # A bar passes through the centre, or starts at the marker's edge.
        reach = width / 2 + 1.0
        through = [(lo, hi) for bx, lo, hi in bars if abs(bx - x) < tolerance and lo - reach <= y <= hi + reach]
        out.append((min(lo for lo, _ in through), max(hi for _, hi in through)) if through else (y, y))
    return out


def unique(markers, digits=2):
    """Markers drawn more than once, kept once."""
    seen, out = set(), []
    for x, y, w in markers:
        key = (round(x, digits), round(y, digits))
        if key not in seen:
            seen.add(key)
            out.append((x, y, w))
    return out


def polylines(drawings, color, min_points=10):
    """Polylines (lists of points) of the given stroke colour with at least ``min_points``."""
    out = []
    for path in drawings:
        if not same_colour(path.get("color"), color) or path.get("fill"):
            continue
        points = []
        for item in path["items"]:
            # Straight segments, and Bezier pieces by their end points (dense enough here).
            if item[0] in ("l", "c"):
                start, end = item[1], item[-1]
                if not points:
                    points.append((start.x, start.y))
                points.append((end.x, end.y))
        if len(points) >= min_points:
            out.append(np.array(points))
    return out


def log_labels(words, x_min, x_max, y_min, y_max):
    """Values and page positions of log tick labels written as '10' with a
    superscript exponent word (or a bare number) whose right edge lies in
    [x_min, x_max] and centre in [y_min, y_max]."""
    out = []
    for x0, y0, x1, y1, text, *_ in words:
        centre = (y0 + y1) / 2
        if not (x_min <= x1 <= x_max and y_min <= centre <= y_max) or not NUMBER.match(text):
            continue
        if text == "10":
            exponents = [w for w in words
                         if abs(w[0] - x1) < 3 and NUMBER.match(w[4]) and -10 < (w[1] + w[3]) / 2 - centre < -1.5]
            if exponents:
                out.append((centre, 10.0 ** number(exponents[0][4])))
                continue
        is_exponent = any(w[4] == "10" and abs(x0 - w[2]) < 3 and -10 < centre - (w[1] + w[3]) / 2 < -1.5
                          for w in words)
        if not is_exponent:
            out.append((centre, number(text)))
    return out


def y_log_calibration(frame, words, drawings):
    """Map page y to log10(value) for a log axis left of ``frame``."""
    labels = log_labels(words, frame.x0 - 30, frame.x0 + 1, frame.y0 - 4, frame.y1 + 4)
    marks = [(y0, abs(x1 - x0)) for x0, y0, x1, y1, *_ in lines(drawings)
             if abs(y0 - y1) < 0.01 and min(x0, x1) <= frame.x0 + 0.5 and 1 < abs(x1 - x0) < 0.2 * frame.width
             and frame.y0 - 1 <= y0 <= frame.y1 + 1]
    longest = max((length for _, length in marks), default=0)
    ticks = [y for y, length in marks if length >= 0.8 * longest]
    return calibrate_axis([(p, np.log10(v)) for p, v in labels if v > 0], ticks, "y")


def x_log_calibration(frame, words, drawings, below):
    """Map page x to log10(value) from the numbers under ``below`` (no tick snapping:
    minor ticks of a log axis are as long as the labelled ones)."""
    labels = [((x0 + x1) / 2, np.log10(number(text))) for x0, y0, x1, y1, text, *_ in words
              if below - 2 <= y0 <= below + 25 and NUMBER.match(text) and number(text) > 0]
    ticks = [x0 for x0, y0, x1, y1, *_ in lines(drawings)
             if abs(x0 - x1) < 0.01 and 1 < abs(y1 - y0) < 0.2 * frame.height and frame.x0 - 1 <= x0 <= frame.x1 + 1
             and max(y0, y1) >= below - 0.5 >= min(y0, y1) - 20]
    return calibrate_axis(labels, ticks, "x")


def polygons(drawings, fill):
    """Point arrays of the filled polygons of colour ``fill``."""
    out = []
    for path in drawings:
        if not same_colour(path.get("fill"), fill) or path["items"][0][0] != "l":
            continue
        points = [(path["items"][0][1].x, path["items"][0][1].y)] + [(it[2].x, it[2].y) for it in path["items"]]
        out.append(np.array(points))
    return out


def band_edges(polygon):
    """Split a closed band polygon (out along one edge, back along the other)
    at its rightmost point into two edges, each sorted by x."""
    turn = int(np.argmax(polygon[:, 0]))
    first, second = polygon[:turn + 1], polygon[turn:]
    return first[np.argsort(first[:, 0])], second[np.argsort(second[:, 0])]
