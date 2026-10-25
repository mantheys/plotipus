"""The plotipus mascot as a DataFrame: a cartoon platypus diving through a
water disc, one row per shape, drawn in row order.

    python make_mascot.py            # writes input/data/Mascot.pkl
    plotipus run mascot              # draws it (see docs/tutorial.md)

Columns: X, Y (the outline, arrays), Part (a unique name), Layer (water,
silhouette, base, shade, texture or detail), Mode (fill for a closed shape,
line for a stroke), Face (fill or stroke colour), Edge (edge colour of a
filled shape, or none), Width (edge or stroke width in points).

The body and tail are one shape swept along a curved spine with a width
profile, so light and shade follow the body as bands (a lit back, a shaded
underside). The far limbs are smaller, darker and behind the body; the near
limbs are larger and in front. The bold outline is the silhouette layer: ink
copies of the body and head with a thick edge, drawn under their fills.
"""

import numpy as np
import pandas as pd
from matplotlib.path import Path

INK = "#2b1d18"
FUR = "#9a6650"
FUR_LIGHT = "#b8806a"
FUR_SHADE = "#7b4c3c"
FUR_DEEP = "#633d31"
MUZZLE = "#c99a83"
BILL = "#7f7369"
BILL_LIGHT = "#9b8f85"
BILL_DARK = "#5a5049"
FEET = "#6e4d43"
FEET_FAR = "#583c34"
CLAW = "#e9dccf"
WATER = "#2fc4ee"
WATER_LIGHT = "#5fd3f3"
WHITE = "#ffffff"


# --- curves -----------------------------------------------------------------------


def catmull_rom(points, k=60):
    """Smooth curve through ``points`` (Catmull-Rom), ``k`` samples per segment."""
    p = np.asarray(points, float)
    p = np.vstack([2 * p[0] - p[1], p, 2 * p[-1] - p[-2]])
    out = []
    for i in range(1, len(p) - 2):
        t = np.linspace(0, 1, k, endpoint=False)[:, None]
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t ** 2
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(p[-2][None, :])
    return np.vstack(out)


class Sweep:
    """A shape swept along a spine: centre c(s), unit normal n(s), half-width w(s)."""

    def __init__(self, spine_points, width_knots):
        c = catmull_rom(spine_points)
        seg = np.hypot(*np.diff(c, axis=0).T)
        s = np.concatenate([[0], np.cumsum(seg)])
        self.s = s / s[-1]
        tangent = np.gradient(c, axis=0)
        tangent /= np.hypot(*tangent.T)[:, None]
        self.c, self.t = c, tangent
        self.n = np.column_stack([-tangent[:, 1], tangent[:, 0]])  # left of the direction of travel
        ks, kw = np.array(width_knots, float).T
        w = np.interp(self.s, ks, kw)
        self.w = np.convolve(np.pad(w, 6, mode="edge"), np.ones(13) / 13, mode="valid")  # soften the knots

    def side(self, k, lo=0.0, hi=1.0):
        """Points at offset ``k`` (in half-widths; may be an array over s) for s in [lo, hi]."""
        sel = (self.s >= lo) & (self.s <= hi)
        k = np.broadcast_to(np.asarray(k, float), self.s.shape)[sel]
        return self.c[sel] + self.n[sel] * (self.w[sel] * k)[:, None]

    def outline(self):
        left = self.side(1.0)
        right = self.side(-1.0)[::-1]
        cap_head = self._cap(-1, +1)
        cap_tail = self._cap(0, -1)
        return np.vstack([left, cap_head, right, cap_tail])

    def _cap(self, i, sign):
        """Half circle closing the end ``i`` (sign +1 forwards at the head, -1 backwards at the tail)."""
        centre, w, n, t = self.c[i], self.w[i], self.n[i], self.t[i] * sign
        a = np.linspace(0, np.pi, 40)
        start = n if sign > 0 else -n
        return centre + w * (np.cos(a)[:, None] * start + np.sin(a)[:, None] * t)

    def band(self, k_lo, k_hi, lo, hi):
        """Region between offsets k_lo(s) and k_hi(s) over [lo, hi]."""
        sel = (self.s >= lo) & (self.s <= hi)
        u = (self.s[sel] - lo) / (hi - lo)
        k_lo = k_lo(u) if callable(k_lo) else np.full(u.shape, k_lo)
        k_hi = k_hi(u) if callable(k_hi) else np.full(u.shape, k_hi)
        full_lo = np.zeros(self.s.shape); full_lo[sel] = k_lo
        full_hi = np.zeros(self.s.shape); full_hi[sel] = k_hi
        a = self.c[sel] + self.n[sel] * (self.w[sel] * k_hi)[:, None]
        b = self.c[sel] + self.n[sel] * (self.w[sel] * k_lo)[:, None]
        return np.vstack([a, b[::-1]])

    def at(self, s, k=0.0):
        i = np.argmin(np.abs(self.s - s))
        return self.c[i] + self.n[i] * self.w[i] * k, self.t[i], self.n[i]


def ellipse(centre, a, b, angle=0.0, k=200, n=2.0):
    t = np.linspace(0, 2 * np.pi, k)
    x = a * np.sign(np.cos(t)) * np.abs(np.cos(t)) ** (2 / n)
    y = b * np.sign(np.sin(t)) * np.abs(np.sin(t)) ** (2 / n)
    ca, sa = np.cos(angle), np.sin(angle)
    return np.column_stack([centre[0] + ca * x - sa * y, centre[1] + sa * x + ca * y])


def cut_away(outer, cut):
    """The part of closed outline ``outer`` outside closed outline ``cut``, as one closed outline."""
    def arc(points, keep):
        # The kept points as one contiguous run: start just after the first dropped point.
        start = int(np.argmax(~keep & np.roll(keep, -1))) + 1
        points, keep = np.roll(points, -start, axis=0), np.roll(keep, -start)
        return points[keep]

    outer_arc = arc(outer, ~Path(cut).contains_points(outer))
    cut_arc = arc(cut, Path(outer).contains_points(cut))
    if np.hypot(*(cut_arc[0] - outer_arc[-1])) > np.hypot(*(cut_arc[-1] - outer_arc[-1])):
        cut_arc = cut_arc[::-1]
    return np.vstack([outer_arc, cut_arc, outer_arc[:1]])


def taper(u, edge=0.12):
    """0 at both ends of [0, 1], 1 in the middle (smooth)."""
    return np.clip(np.minimum(u, 1 - u) / edge, 0, 1) ** 0.7


# --- parts ------------------------------------------------------------------------


def limb_and_foot(origin, angle_deg, length, scale, far):
    """An arm (fur) ending in a webbed foot with claws. Returns (arm, foot, claws, webs)."""
    a = np.radians(angle_deg)
    d = np.array([np.cos(a), np.sin(a)])
    nrm = np.array([-d[1], d[0]])
    o = np.asarray(origin, float)
    end = o + d * length * scale
    w0, w1 = 0.40 * scale, 0.26 * scale
    bend = nrm * 0.12 * length * scale * (1 if far else -1)
    arm_sweep = Sweep([o, (o + end) / 2 + bend, end], [(0, w0), (0.5, 0.82 * w0), (1, w1)])
    arm = arm_sweep.outline()
    # The foot: a fan of four rounded toes, wider than the wrist.
    spread = np.radians(110)
    u = np.linspace(0, 1, 160)
    fan = -spread / 2 + spread * u
    toes = 4
    scallop = np.abs(np.cos(np.pi * (toes - 1) * u))
    r = scale * 0.92 * (0.70 + 0.30 * scallop ** 0.45)
    fx = end[0] + r * np.cos(a + fan)
    fy = end[1] + r * np.sin(a + fan)
    foot = np.vstack([end + nrm * w1 * 1.1, np.column_stack([fx, fy])[::-1], end - nrm * w1 * 1.1])
    tips = [int(round(i * 159 / (toes - 1))) for i in range(toes)]
    claws, webs = [], []
    for i in tips:
        tip = np.array([fx[i], fy[i]])
        out = np.array([np.cos(a + fan[i]), np.sin(a + fan[i])])
        side = np.array([-out[1], out[0]])
        claws.append(np.array([tip - side * 0.06 * scale, tip + out * 0.16 * scale, tip + side * 0.06 * scale]))
        webs.append(np.array([end + (tip - end) * 0.35, end + (tip - end) * 0.78]))
    return arm, foot, claws, webs


def mascot(angle=-30.0, seed=11, span=10.6, centre=(0.1, 0.25)):
    rng = np.random.default_rng(seed)
    rows = []

    def add(part, xy, mode, face=None, edge=INK, width=0.0, animal=True):
        xy = np.asarray(xy, float)
        rows.append({"X": xy[:, 0], "Y": xy[:, 1], "Part": part, "Mode": mode,
                     "Face": face, "Edge": edge, "Width": width, "Animal": animal})

    # Body + tail along one S-shaped spine: tail tip (s=0) up and behind, head end (s=1).
    body = Sweep(
        [(-5.3, 2.25), (-4.4, 1.45), (-3.2, 0.55), (-1.6, -0.05), (0.2, -0.20), (1.9, 0.05), (2.7, 0.30)],
        [(0.00, 0.78), (0.10, 0.98), (0.22, 0.86), (0.33, 0.58), (0.42, 0.95), (0.58, 1.38),
         (0.78, 1.22), (0.94, 0.92), (1.00, 0.86)],
    )
    head_c, head_t, head_n = body.at(1.0)
    head_angle = np.arctan2(head_t[1], head_t[0]) - 0.10
    head_centre = head_c + head_t * 0.35 + head_n * 0.05
    head = ellipse(head_centre, 1.30, 1.08, head_angle)

    # Limbs: far ones behind the body (smaller, darker), near ones in front.
    p_ff, _, _ = body.at(0.80, +0.75)
    p_fb, _, _ = body.at(0.44, +0.70)
    p_nf, _, _ = body.at(0.78, -0.70)
    p_nb, _, _ = body.at(0.45, -0.72)
    far_front = limb_and_foot(p_ff, 70, 0.95, 0.74, True)
    far_back = limb_and_foot(p_fb, 128, 0.85, 0.70, True)
    near_front = limb_and_foot(p_nf, -62, 1.10, 1.05, False)
    near_back = limb_and_foot(p_nb, -118, 1.00, 0.98, False)

    # 1. Far limbs (drawn first: the body hides their roots).
    for name, (arm, foot, claws, webs) in (("far_front", far_front), ("far_back", far_back)):
        add(f"{name}_arm", arm, "fill", face=FUR_SHADE, width=2.4)
        add(f"{name}_foot", foot, "fill", face=FEET_FAR, width=2.4)
        for j, c in enumerate(claws):
            add(f"{name}_claw{j}", c, "fill", face=CLAW, width=1.2)

    # 2. The silhouette: ink copies with a thick edge, then the fills.
    add("body_outline", body.outline(), "fill", face=INK, edge=INK, width=5.5)
    add("head_outline", head, "fill", face=INK, edge=INK, width=5.5)
    add("body", body.outline(), "fill", face=FUR, edge="none")

    # 3. Light and shade along the body: shaded underside, deep shade under the tail root,
    #    a lit band along the back, a softer one on the tail.
    add("shade", body.band(-1.0, lambda u: -1.0 + 0.62 * taper(u, 0.18), 0.30, 1.0), "fill", face=FUR_SHADE, edge="none")
    add("tail_shade", body.band(-1.0, lambda u: -1.0 + 0.55 * taper(u, 0.25), 0.02, 0.36), "fill", face=FUR_SHADE, edge="none")
    add("tail_root_shade", body.band(-1.0, lambda u: -1.0 + 0.9 * taper(u, 0.5), 0.30, 0.42), "fill", face=FUR_DEEP, edge="none")
    add("back_light", body.band(lambda u: 0.30 + 0.25 * (1 - taper(u, 0.3)), lambda u: 0.30 + 0.45 * taper(u, 0.3), 0.46, 0.92),
        "fill", face=FUR_LIGHT, edge="none")
    add("tail_light", body.band(lambda u: 0.20 + 0.3 * (1 - taper(u, 0.4)), lambda u: 0.20 + 0.45 * taper(u, 0.4), 0.05, 0.28),
        "fill", face=FUR_LIGHT, edge="none")

    # 4. Fur strokes following the spine (fewer on the lit back, none near the outline).
    strokes = 0
    for attempt in range(4000):
        if strokes >= 40:
            break
        s0 = rng.uniform(0.04, 0.93)
        k0 = rng.uniform(-0.62, 0.62)
        if 0.30 < s0 < 0.40 and abs(k0) > 0.3:
            continue  # the narrow tail root
        p, t, n = body.at(s0, k0)
        if any(np.hypot(*(p - q)) < 0.48 for q in (r["_centre"] for r in rows if "_centre" in r)):
            continue
        tilt = np.radians(rng.normal(14, 7)) * np.sign(k0 + 1e-9)
        d = t * np.cos(tilt) + n * np.sin(tilt)
        u = np.linspace(-0.5, 0.5, 8)[:, None]
        pts = p - d * 0.34 * u * -1 + n * 0.05 * u ** 2
        colour = FUR_DEEP if k0 < -0.2 else FUR_SHADE
        add(f"fur{strokes}", pts, "line", edge=colour, width=1.7)
        rows[-1]["_centre"] = p
        strokes += 1

    # 5. Head over the body front, with a neck crease, lit crown and lighter muzzle.
    add("head", head, "fill", face=FUR, edge="none")
    neck = np.array([head_centre + (head_n * np.cos(a) - head_t * np.sin(a)) * 1.02
                     for a in np.linspace(1.25, 2.05, 16)])
    add("neck_crease", neck, "line", edge=FUR_SHADE, width=2.4)
    outer = ellipse(head_centre, 1.30, 1.08, head_angle, k=200)
    inner = ellipse(head_centre + head_n * 0.30, 1.22, 0.98, head_angle, k=200)
    lower = (outer - head_centre) @ head_n < -0.15
    crescent = np.vstack([outer[lower], inner[lower][::-1]])
    add("head_shade", crescent, "fill", face=FUR_SHADE, edge="none")
    add("crown_light", ellipse(head_centre + head_n * 0.48 - head_t * 0.15, 0.62, 0.24, head_angle + 0.1), "fill", face=FUR_LIGHT, edge="none")
    add("muzzle", ellipse(head_centre + head_t * 0.78 - head_n * 0.18, 0.48, 0.62, head_angle), "fill", face=MUZZLE, edge="none")

    # 6. Bill: thick rim (darker), lit top surface, nostrils, mouth corner.
    bill_angle = head_angle - 0.22
    bdir = np.array([np.cos(bill_angle), np.sin(bill_angle)])
    bnrm = np.array([-bdir[1], bdir[0]])
    bill_centre = head_centre + head_t * 1.70 - head_n * 0.32
    rim = ellipse(bill_centre - bnrm * 0.12, 1.25, 0.82, bill_angle, n=2.5)
    top = ellipse(bill_centre + bnrm * 0.08 - bdir * 0.05, 1.17, 0.66, bill_angle, n=2.5)
    add("bill_rim", rim, "fill", face=BILL_DARK, width=3.0)
    add("bill_top", top, "fill", face=BILL, width=2.0)
    add("bill_light", ellipse(bill_centre + bnrm * 0.25 - bdir * 0.15, 0.55, 0.16, bill_angle), "fill", face=BILL_LIGHT, edge="none")
    for j, off in enumerate((-0.16, 0.16)):
        add(f"nostril{j}", ellipse(bill_centre + bdir * 0.78 + bnrm * (0.20 + off), 0.08, 0.05, bill_angle), "fill",
            face=BILL_DARK, edge="none")

    # 7. Eye: white, pupil looking ahead and down, shine, upper lid.
    eye_c = head_centre + head_t * 0.30 + head_n * 0.32
    add("eye_white", ellipse(eye_c, 0.27, 0.32, head_angle + 0.2), "fill", face=WHITE, width=2.2)
    add("pupil", ellipse(eye_c + head_t * 0.07 - head_n * 0.04, 0.15, 0.20, head_angle + 0.2), "fill", face=INK, edge="none")
    add("shine", ellipse(eye_c + head_t * 0.11 + head_n * 0.06, 0.055, 0.055), "fill", face=WHITE, edge="none")
    lid = np.array([eye_c + (head_n * np.cos(a) + head_t * np.sin(a)) * 0.36 for a in np.linspace(-1.1, 1.1, 20)])
    add("lid", lid, "line", edge=INK, width=2.2)

    # 8. Near limbs, in front of the body.
    for name, (arm, foot, claws, webs) in (("near_back", near_back), ("near_front", near_front)):
        add(f"{name}_arm", arm, "fill", face=FUR, width=2.6)
        add(f"{name}_foot", foot, "fill", face=FEET, width=2.6)
        for j, w in enumerate(webs[1:-1]):
            add(f"{name}_web{j}", w, "line", edge=FEET_FAR, width=1.5)
        for j, c in enumerate(claws):
            add(f"{name}_claw{j}", c, "fill", face=CLAW, width=1.2)

    # Rotate the animal into the dive and fit it into the frame.
    a = np.radians(angle)
    ca, sa = np.cos(a), np.sin(a)
    animal = [r for r in rows if r["Animal"]]
    for r in animal:
        x, y = r["X"], r["Y"]
        r["X"], r["Y"] = x * ca - y * sa, x * sa + y * ca
    xs = np.concatenate([r["X"] for r in animal])
    ys = np.concatenate([r["Y"] for r in animal])
    mid = np.array([(xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2])
    k = min(1.0, span / max(np.ptp(xs), np.ptp(ys)))
    for r in animal:
        r["X"] = centre[0] + k * (r["X"] - mid[0])
        r["Y"] = centre[1] + k * (r["Y"] - mid[1])

    # Water disc, a light rim for depth, and bubbles (behind the animal).
    back = []

    def add_back(part, xy, face, edge="none", width=0.0):
        xy = np.asarray(xy, float)
        back.append({"X": xy[:, 0], "Y": xy[:, 1], "Part": part, "Mode": "fill", "Face": face,
                     "Edge": edge, "Width": width, "Animal": False})

    add_back("water", ellipse((0.0, 0.0), 4.7, 4.7), WATER)
    add_back("water_light", cut_away(ellipse((-1.2, 1.5), 2.6, 2.4, k=400), ellipse((-0.75, 1.05), 2.75, 2.65, k=400)),
             WATER_LIGHT)
    for i, (cx, cy, r) in enumerate([(3.6, 3.4, 0.36), (4.35, 2.6, 0.22), (-3.7, -3.2, 0.30), (-4.45, -2.1, 0.17)]):
        add_back(f"bubble_back_{i}", ellipse((cx, cy), r, r), WHITE, WATER, 2.2)

    # Bubbles rising from the bill tip, in front.
    tip = bill_centre + bdir * 1.25
    tx, ty = tip @ np.array([[ca, sa], [-sa, ca]])
    tx, ty = centre[0] + k * (tx - mid[0]), centre[1] + k * (ty - mid[1])
    for i, (dx, dy, r) in enumerate([(0.30, 0.45, 0.12), (0.55, 1.05, 0.19), (0.38, 1.80, 0.11), (0.70, 2.55, 0.30)]):
        cx, cy = min(tx + dx, 5.2 - r), ty + dy
        add(f"bubble_{i}", ellipse((cx, cy), r, r), "fill", face=WHITE, edge=WATER, width=2.2, animal=False)

    frame = pd.DataFrame(back + rows)
    frame["Layer"] = frame["Part"].map(layer_of)
    return frame.drop(columns=[c for c in ("Animal", "_centre") if c in frame.columns])


SHADE_PARTS = {"shade", "tail_shade", "tail_root_shade", "back_light", "tail_light", "head_shade",
               "crown_light", "muzzle", "bill_light", "water_light"}
BASE_PARTS = {"body", "head", "bill_rim", "bill_top", "eye_white"}


def layer_of(part):
    """water, silhouette, base, shade, texture or detail."""
    if part in SHADE_PARTS:
        return "shade"
    if part == "water" or part.startswith("bubble"):
        return "water"
    if part.endswith("_outline"):
        return "silhouette"
    if part in BASE_PARTS or part.endswith("_arm") or part.endswith("_foot"):
        return "base"
    if part.startswith("fur") or part == "neck_crease":
        return "texture"
    return "detail"


def as_frame(frame):
    """plotipus columns: strokes carry their colour in Face, unedged fills say so in Edge."""
    frame = frame.copy()
    lines = frame["Mode"] == "line"
    frame.loc[lines, "Face"] = frame.loc[lines, "Edge"]
    frame.loc[lines, "Edge"] = "none"
    frame.loc[(frame["Mode"] == "fill") & (frame["Width"] == 0), "Edge"] = "none"
    frame["Variable"] = "Mascot"
    assert frame["Part"].is_unique
    return frame


if __name__ == "__main__":
    import pathlib

    out = pathlib.Path(__file__).resolve().parent / "input" / "data"
    out.mkdir(parents=True, exist_ok=True)
    frame = as_frame(mascot())
    frame.to_pickle(out / "Mascot.pkl")
    print(f"Mascot written to {out / 'Mascot.pkl'}: {len(frame)} shapes")
