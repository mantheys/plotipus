"""plotipus's own sequential colour maps, registered with matplotlib.

``plotipus`` (the default ``image.cmap`` of the plotipus and open styles)
runs from a pale cream through teal to the blue of petroff10 and a dark ink
blue, with CIELAB lightness falling linearly (L* 96 to 16), so:

* it is ordered by lightness alone: it reads in greyscale and for every
  colour-vision deficiency, which keep lightness;
* the hue turns from yellow through green to blue (like ColorBrewer's
  YlGnBu) for more steps to tell apart than a single hue would give;
* its lightest end is a tint, not white, so masked (empty) bins on the
  white paper stay distinguishable from the lowest values;
* its blue sits at the palette's first colour, so maps and lines of one
  figure look like one family.

``plotipus_dark`` (the dark theme's) climbs from a dark blue just above the
#1b1d22 paper to the cream, so low values recede into the background there
as they fade into the paper in the light map. Both have ``_r`` reverses.
"""

import matplotlib
import numpy as np
from matplotlib.colors import ListedColormap

# CIE D65 white, for Lab <-> XYZ.
_WHITE = np.array([0.95047, 1.0, 1.08883])
_SRGB_TO_XYZ = np.array([[0.4124564, 0.3575761, 0.1804375],
                         [0.2126729, 0.7151522, 0.0721750],
                         [0.0193339, 0.1191920, 0.9503041]])

# (L*, C*, hue in degrees) anchors; L* is replaced by a linear ramp, C* and
# hue are interpolated between anchors.
_LIGHT = [(96, 20, 95), (76, 28, 160), (56, 32, 230), (36, 34, 258), (16, 24, 268)]


def _linear(rgb):
    rgb = np.asarray(rgb, dtype=float)
    return np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)


def _gamma(lin):
    lin = np.clip(lin, 0, 1)
    return np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * lin ** (1 / 2.4) - 0.055)


def srgb_to_lab(rgb):
    """CIELAB (D65) of sRGB colours in [0, 1], shape (..., 3)."""
    xyz = _linear(rgb) @ _SRGB_TO_XYZ.T / _WHITE
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def lab_to_srgb(lab):
    """sRGB in [0, 1] of CIELAB colours, shape (..., 3); out-of-gamut
    colours are pulled towards grey at the same lightness until they fit."""
    lab = np.array(lab, dtype=float)
    out = np.empty_like(lab)
    for index in np.ndindex(lab.shape[:-1]):
        L, a, b = lab[index]
        rgb = _lab_to_linear(L, a, b)
        if not _inside(rgb):
            # The largest chroma (by bisection) that fits, at the same lightness and hue.
            low, high = 0.0, 1.0
            for _ in range(30):
                mid = (low + high) / 2
                low, high = (mid, high) if _inside(_lab_to_linear(L, a * mid, b * mid)) else (low, mid)
            rgb = _lab_to_linear(L, a * low, b * low)
        out[index] = _gamma(rgb)
    return out


def _inside(rgb):
    return bool(np.all(rgb >= -1e-9) and np.all(rgb <= 1 + 1e-9))


def _lab_to_linear(L, a, b):
    fy = (L + 16) / 116
    f = np.array([fy + a / 500, fy, fy - b / 200])
    xyz = np.where(f > 6 / 29, f ** 3, 3 * (6 / 29) ** 2 * (f - 4 / 29)) * _WHITE
    return np.linalg.solve(_SRGB_TO_XYZ, xyz)


def _ramp(anchors, lightness, n=256):
    """``n`` sRGB colours: lightness ``lightness`` (L* from, to) linear, chroma
    and hue interpolated through ``anchors``."""
    t = np.linspace(0, 1, n)
    stops = np.linspace(0, 1, len(anchors))
    chroma = np.interp(t, stops, [c for _, c, _ in anchors])
    hue = np.radians(np.interp(t, stops, [h for _, _, h in anchors]))
    L = np.linspace(*lightness, n)
    return lab_to_srgb(np.stack([L, chroma * np.cos(hue), chroma * np.sin(hue)], axis=-1))


def _maps():
    light = ListedColormap(_ramp(_LIGHT, (96, 16)), name="plotipus")
    # Dark theme: from a blue just above the dark paper (L* about 10) up to the cream.
    dark = ListedColormap(_ramp(_LIGHT[::-1], (24, 96)), name="plotipus_dark")
    return [light, light.reversed(), dark, dark.reversed()]


def register():
    """Register the maps with matplotlib (once)."""
    for cmap in _maps():
        if cmap.name not in matplotlib.colormaps:
            matplotlib.colormaps.register(cmap)


register()
