"""Colour scales of map panels for the famous-plot reproductions (a project plugin).

Adds four options to every kind, applied by a figure hook just before the figure
is saved, to the 2D histograms and images of every panel (colorbars follow):

- ``--zpower GAMMA``: a power-law colour scale, value**GAMMA; 0.5 is the
  square root of the density of the Gaia DR2 HR diagrams (F22). The colorbar
  is ticked at the powers of ten, as Gaia's is;
- ``--zcmap NAME``: the colour map, also for 2D histograms (``--cmap`` reaches
  only ``-z`` images);
- ``--zmin VALUE`` and ``--zunder COLOUR``: the bottom of the scale, and the
  colour of the values below it (Gaia draws its sparsest bins as black dots).

plotipus has no built-in equivalent yet: they belong to T22.3.
"""

import numpy as np
from matplotlib.collections import QuadMesh
from matplotlib.colors import PowerNorm
from matplotlib.image import AxesImage


def setup(registry):
    registry.add_argument("--zpower", type=float, default=None, metavar="GAMMA",
                          help="Power-law colour scale of map panels, e.g. 0.5 for sqrt (famous-plot plugin).")
    registry.add_argument("--zcmap", type=str, default=None, metavar="NAME",
                          help="Colour map of map panels, 2D histograms included (famous-plot plugin).")
    registry.add_argument("--zmin", type=float, default=None, metavar="VALUE",
                          help="Bottom of the colour scale of map panels (famous-plot plugin).")
    registry.add_argument("--zunder", type=str, default=None, metavar="COLOUR",
                          help="Colour of map values below --zmin (famous-plot plugin).")
    registry.add_figure_hook(apply_colour_scale)


def apply_colour_scale(fig, args):
    gamma, cmap = getattr(args, "zpower", None), getattr(args, "zcmap", None)
    minimum, under = getattr(args, "zmin", None), getattr(args, "zunder", None)
    if gamma is None and cmap is None and minimum is None and under is None:
        return
    for ax in fig.axes:
        if ax.get_label() == "<colorbar>":
            continue
        for mappable in [*ax.collections, *ax.images]:
            if not isinstance(mappable, (QuadMesh, AxesImage)):
                continue
            low, high = mappable.get_clim()
            low = minimum if minimum is not None else max(low, 0)
            if gamma is not None:
                mappable.set_norm(PowerNorm(gamma, vmin=low, vmax=high))
            elif minimum is not None:
                mappable.set_clim(low, high)
            if cmap is not None:
                mappable.set_cmap(cmap)
            if under is not None:
                mappable.set_cmap(mappable.get_cmap().with_extremes(under=under))
            if mappable.colorbar is not None:
                _update_colorbar(mappable.colorbar, mappable, gamma)


def _update_colorbar(colorbar, mappable, gamma):
    """Redraw the colorbar for the new scale: on a power scale, ticks at the
    powers of ten (linear ticks would crowd its top). The --zunder colour is
    not shown on the bar: its extension is chosen when plotipus creates it."""
    colorbar.update_normal(mappable)
    if gamma is not None:
        low, high = mappable.norm.vmin, mappable.norm.vmax
        decades = 10.0 ** np.arange(np.ceil(np.log10(max(low, 1e-12))), np.floor(np.log10(high)) + 1)
        # From the top down, drop a decade that would sit within 6% of the bar of the one above.
        kept = []
        for value in decades[::-1]:
            if not kept or mappable.norm(kept[-1]) - mappable.norm(value) >= 0.06:
                kept.append(value)
        colorbar.set_ticks(kept[::-1], labels=[f"{d:g}" for d in kept[::-1]])
        colorbar.ax.minorticks_off()
