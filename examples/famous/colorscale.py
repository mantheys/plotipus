"""Colour scales of map panels for the famous-plot reproductions (a project plugin).

Adds two options to every kind, applied by a figure hook just before the figure
is saved, to the 2D histograms and images of every panel (colorbars follow):

- ``--zpower GAMMA``: a power-law colour scale, value**GAMMA; 0.5 is the
  square root of the density of the Gaia DR2 HR diagrams (F22);
- ``--zcmap NAME``: the colour map, also for 2D histograms (``--cmap`` reaches
  only ``-z`` images).

plotipus has no built-in equivalent yet: both belong to T22.3.
"""

from matplotlib.collections import QuadMesh
from matplotlib.colors import PowerNorm
from matplotlib.image import AxesImage


def setup(registry):
    registry.add_argument("--zpower", type=float, default=None, metavar="GAMMA",
                          help="Power-law colour scale of map panels, e.g. 0.5 for sqrt (famous-plot plugin).")
    registry.add_argument("--zcmap", type=str, default=None, metavar="NAME",
                          help="Colour map of map panels, 2D histograms included (famous-plot plugin).")
    registry.add_figure_hook(apply_colour_scale)


def apply_colour_scale(fig, args):
    gamma, cmap = getattr(args, "zpower", None), getattr(args, "zcmap", None)
    if gamma is None and cmap is None:
        return
    for ax in fig.axes:
        if ax.get_label() == "<colorbar>":
            continue
        for mappable in [*ax.collections, *ax.images]:
            if not isinstance(mappable, (QuadMesh, AxesImage)):
                continue
            if gamma is not None:
                low, high = mappable.get_clim()
                mappable.set_norm(PowerNorm(gamma, vmin=max(low, 0), vmax=high))
            if cmap is not None:
                mappable.set_cmap(cmap)
            if mappable.colorbar is not None:
                mappable.colorbar.update_normal(mappable)
