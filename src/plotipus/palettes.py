"""Named categorical palettes and the per-figure colour allocator.

A palette is a list of hex colours. :func:`apply` makes one the colour cycle
(``axes.prop_cycle``), so ``Cn`` colours and plain matplotlib calls follow
it. :class:`ColorAllocator` hands out the colours of one figure: a category
keeps its colour in every panel, a user-mapped colour is never given to
another category, and past the end of the palette the colours repeat with a
warning instead of silently.
"""

import matplotlib.pyplot as plt
from matplotlib import cycler
from matplotlib.colors import to_hex
from rich import print as rprint

DEFAULT = "petroff10"

PALETTES = {
    # Petroff, "Accessible Color Sequences for Data Visualization" (arXiv:2107.02270), as shipped by
    # matplotlib (plt.style.library["petroff10"] / ["petroff8"] / ["petroff6"]).
    # https://github.com/matplotlib/matplotlib/blob/main/lib/matplotlib/mpl-data/stylelib/petroff10.mplstyle
    # ROOT 6.34's kP10Blue..kP10Cyan are the same colours in the same order (TColor.cxx), so `root-p10`
    # is not needed: https://root.cern/doc/master/TColor_8cxx_source.html
    "petroff10": ["#3f90da", "#ffa90e", "#bd1f01", "#94a4a2", "#832db6",
                  "#a96b59", "#e76300", "#b9ac70", "#717581", "#92dadd"],
    # petroff10 for dark backgrounds (#1b1d22): the same order, with lightened twins (same hue and
    # saturation) of its darkest entries #bd1f01, #832db6 and #717581, so every colour reaches a WCAG
    # contrast of at least 3.5:1 (style_spec 2.11).
    "petroff10-dark": ["#3f90da", "#ffa90e", "#e12501", "#94a4a2", "#a04bd3",
                       "#a96b59", "#e76300", "#b9ac70", "#7b7f8b", "#92dadd"],
    # DUNE's plot style: Okabe-Ito with black first (dune_plot_style, SetOkabeItoColors).
    # https://github.com/DUNE/dune_plot_style
    "dune": ["#000000", "#D55E00", "#56B4E9", "#E69F00", "#009E73", "#CC79A7", "#0072B2", "#F0E442"],
    # https://github.com/matplotlib/matplotlib/blob/main/lib/matplotlib/mpl-data/stylelib/petroff8.mplstyle
    "petroff8": ["#1845fb", "#ff5e02", "#c91f16", "#c849a9", "#adad7d", "#86c8dd", "#578dff", "#656364"],
    # https://github.com/matplotlib/matplotlib/blob/main/lib/matplotlib/mpl-data/stylelib/petroff6.mplstyle
    "petroff6": ["#5790fc", "#f89c20", "#e42536", "#964a8b", "#9c9ca1", "#7a21dd"],
    # Okabe & Ito, "Color Universal Design" (2008); Wong, Nat. Methods 8, 441 (2011).
    # https://jfly.uni-koeln.de/color/ -- black, first in the original, is moved last so the
    # first series is not drawn in the colour of text and data points.
    "okabe-ito": ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7", "#000000"],
    # Paul Tol's qualitative schemes (checked 2026-10-24); muted's "bad data" grey #DDDDDD is left out.
    # https://sronpersonalpages.nl/~pault/
    "tol-bright": ["#4477AA", "#EE6677", "#228833", "#CCBB44", "#66CCEE", "#AA3377", "#BBBBBB"],
    "tol-muted": ["#CC6677", "#332288", "#DDCC77", "#117733", "#88CCEE", "#882255", "#44AA99", "#999933",
                  "#AA4499"],
    # matplotlib's default cycle (plotipus before T01).
    # https://matplotlib.org/stable/users/explain/colors/colors.html#color-cycle
    "tab10": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
              "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"],
    # seaborn's 10-colour `colorblind` palette (matplotlib's seaborn-v0_8-colorblind style has only 6).
    # https://github.com/mwaskom/seaborn/blob/master/seaborn/palettes.py
    "seaborn-colorblind": ["#0173B2", "#DE8F05", "#029E73", "#D55E00", "#CC78BC",
                           "#CA9161", "#FBAFE4", "#949494", "#ECE133", "#56B4E9"],
    # https://github.com/matplotlib/matplotlib/blob/main/lib/matplotlib/mpl-data/stylelib/tableau-colorblind10.mplstyle
    "tableau-colorblind10": ["#006BA4", "#FF800E", "#ABABAB", "#595959", "#5F9ED1",
                             "#C85200", "#898989", "#A2C8EC", "#FFBC79", "#CFCFCF"],
    # ROOT has no colour cycle: users number their colours 1, 2, 3, ... (kBlack, kRed, kGreen, kBlue,
    # kYellow, kMagenta, kCyan, 8, 9), whose RGB values TColor::InitializeColors sets.
    # https://root.cern/doc/master/TColor_8cxx_source.html
    "root": ["#000000", "#ff0000", "#00ff00", "#0000ff", "#ffff00", "#ff00ff", "#00ffff", "#59d454", "#5954d9"],
}

# Name of the palette set by apply(); None when the cycle came from elsewhere (an rcParams key).
active = None


def names():
    return list(PALETTES)


def get(name):
    """Hex colours of the named palette (case-insensitive)."""
    key = str(name).lower()
    if key not in PALETTES:
        raise ValueError(f"Unknown palette '{name}'. Choose one of: {', '.join(PALETTES)}.")
    return list(PALETTES[key])


def apply(name):
    """Make the named palette the colour cycle (``axes.prop_cycle``)."""
    global active
    plt.rcParams["axes.prop_cycle"] = cycler(color=get(name))
    active = str(name).lower()


def current_colors():
    """Colours of the active cycle."""
    return list(plt.rcParams["axes.prop_cycle"].by_key().get("color", [])) or get(DEFAULT)


def _key(color):
    try:
        return to_hex(color)
    except (TypeError, ValueError):
        return str(color)


class ColorAllocator:
    """Colours of one figure, shared by all its panels and lower panels.

    Past the end of the palette the colours repeat (line styles are left to
    the encodings that ask for them) and one warning is printed.
    """

    def __init__(self, colors=None):
        self.colors = list(colors) if colors is not None else current_colors()
        self._assigned = {}  # category -> colour
        self._slots = set()  # taken slots; slot k is colour k % n
        self._mapped = set()  # hex of user-mapped colours, kept away from unmapped categories
        self._warned = False

    def __len__(self):
        return len(self.colors)

    def reserve(self, categories, mapping):
        """Assign the user-mapped colours first, so no unmapped category drawn
        before them takes one. ``mapping(category)`` gives a colour or None."""
        for category in categories:
            color = mapping(category)
            if color is not None:
                self.color_for(category, color)

    def color_for(self, category, mapping=None):
        """Colour of ``category``: ``mapping`` (the user's colour) when
        given, else its colour so far, else the next free slot."""
        if mapping is not None:
            self._assigned[category] = mapping
            key = _key(mapping)
            self._mapped.add(key)
            self._slots.update(k for k, c in enumerate(self.colors) if _key(c) == key)
            return self._assigned[category]
        if category not in self._assigned:
            self._assigned[category] = self._take()
        return self._assigned[category]

    def next_free(self, category=None):
        """A colour no category has: for combined, sum and reference-sum
        series. Given a ``category``, it is remembered like any other."""
        if category is not None:
            return self.color_for(category)
        return self._take()

    def _take(self):
        n = len(self.colors)
        usable = [k for k in range(n) if _key(self.colors[k]) not in self._mapped] or list(range(n))
        slot = 0
        while slot in self._slots or slot % n not in usable:
            slot += 1
        self._slots.add(slot)
        if slot >= n and not self._warned:
            self._warned = True
            palette = f"the '{active}' palette" if active else "the colour cycle"
            rprint(f"[yellow]Warning:[/yellow] More categories than the {n} colours of {palette}: colours repeat. "
                   "For ordered values (runs, energies) a sequential colormap reads better "
                   "(--hue_cmap); --palette picks a longer palette.")
        return self.colors[slot % n]
