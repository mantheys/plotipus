"""Mock-ups for docs/design/corner-plots.md: three layouts of a posterior
corner plot that use the upper triangle. Plain matplotlib on toy samples, not
plotipus code: the figures show where things would go, not how plotipus would
draw them.

    python3 docs/design/corner_mockups.py     # writes docs/design/corner/*.png
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from scipy.ndimage import gaussian_filter, gaussian_filter1d

OUT = Path(__file__).parent / "corner"
OUT.mkdir(exist_ok=True)
rng = np.random.default_rng(7)

BLUE, ORANGE, RED, GREY, INK = "#3f90da", "#ffa90e", "#bd1f01", "#717581", "black"
plt.rcParams.update({
    "font.size": 9, "axes.labelsize": 10, "xtick.direction": "in", "ytick.direction": "in",
    "xtick.top": True, "ytick.right": True, "legend.frameon": False, "savefig.dpi": 170,
    "axes.titlesize": 8.5, "xtick.labelsize": 8, "ytick.labelsize": 8,
})
SIZE = (10, 7.3)  # two facets of the slide medium, at one plot's aspect
P1, P2 = 0.6827, 0.9545


def mix(color, t):
    """The colour mixed towards white (t = 0: the colour, 1: white)."""
    rgb = np.array(matplotlib.colors.to_rgb(color))
    return tuple(rgb + (1 - rgb) * t)


def thresholds(density, fractions):
    """Density thresholds of the smallest regions holding each fraction."""
    flat = np.sort(density.ravel())[::-1]
    cumulative = np.cumsum(flat) / flat.sum()
    return [flat[min(np.searchsorted(cumulative, f), len(flat) - 1)] for f in fractions]


def density2d(x, y, xe, ye, w=None, sigma=1.0, wrap=(False, False)):
    counts, _, _ = np.histogram2d(x, y, bins=[xe, ye], weights=w)
    return gaussian_filter(counts, sigma, mode=["wrap" if wrap[0] else "nearest", "wrap" if wrap[1] else "nearest"])


def regions(ax, x, y, xe, ye, color, w=None, fill=True, wrap=(False, False), lw=0.9, ls="solid", sigma=1.0):
    d = density2d(x, y, xe, ye, w, sigma, wrap)
    t2, t1 = thresholds(d, [P2, P1])
    xc, yc = 0.5 * (xe[1:] + xe[:-1]), 0.5 * (ye[1:] + ye[:-1])
    if fill:
        ax.contourf(xc, yc, d.T, levels=[t2, t1, np.inf], colors=[mix(color, 0.5), mix(color, 0.0)])
    ax.contour(xc, yc, d.T, levels=[t2, t1], colors=[color], linewidths=lw, linestyles=ls)


def marginal(ax, x, e, color, w=None, shade=None):
    """Step density; ``shade`` is a list of (low, high) pieces to fill."""
    d, _ = np.histogram(x, bins=e, weights=w, density=True)
    ax.stairs(d, e, color=color, linewidth=1.2)
    centres = 0.5 * (e[1:] + e[:-1])
    for low, high in shade or []:
        inside = (centres >= low) & (centres <= high)
        ax.fill_between(e, np.r_[np.where(inside, d, 0), 0], step="post", color=color, alpha=0.25, linewidth=0)
    ax.set_ylim(0, 1.18 * d.max())
    ax.set_yticks([])
    return d


def grid(n, upper_ticks=False):
    fig = plt.figure(figsize=SIZE)
    gs = fig.add_gridspec(n, n, wspace=0.06, hspace=0.06, left=0.08, right=0.97 if not upper_ticks else 0.92,
                          bottom=0.09, top=0.90)
    return fig, gs


def finish(ax, r, c, n, labels, lims):
    ax.set_xlim(*lims[c])
    if r != c:
        ax.set_ylim(*lims[r])
    if r == n - 1:
        ax.set_xlabel(labels[c])
    else:
        ax.tick_params(labelbottom=False)
    if c == 0 and r > 0:
        ax.set_ylabel(labels[r])
    else:
        ax.tick_params(labelleft=False)
    ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(4, prune="both"))
    if r != c:
        ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(4, prune="both"))


# --------------------------------------------------------------------------------------------------------------
# Mock-up A: reading aids. Correlations with their Monte Carlo error in the mirrored cells, the scatter of the
# outer contour under resampling, and a legend that states the conventions and the sample size.
# --------------------------------------------------------------------------------------------------------------
def mockup_a():
    n_draws = 2500
    truth = np.array([1.0, 125.0, np.log(2.4)])
    sig = np.array([0.22, 0.25, 0.16])
    corr = np.eye(3)
    corr[0, 2] = corr[2, 0] = 0.55
    draws = rng.multivariate_normal(truth + [0.06, -0.05, 0.03], corr * np.outer(sig, sig), n_draws)
    draws[:, 2] = np.exp(draws[:, 2])
    labels = [r"$\mu$", r"$m$ (GeV)", r"$\Gamma$ (GeV)"]
    names, units = [r"$\mu$", r"$m$", r"$\Gamma$"], ["", " GeV", " GeV"]
    lims = [(0.3, 1.85), (124.1, 125.8), (1.4, 4.2)]
    edges = [np.linspace(*lims[i], 33) for i in range(3)]
    n = 3
    fig, gs = grid(n)
    for r in range(n):
        for c in range(n):
            if c > r:
                ax = fig.add_subplot(gs[r, c])
                rho = np.corrcoef(draws[:, c], draws[:, r])[0, 1]
                err = (1 - rho**2) / np.sqrt(n_draws - 1)
                ax.set_facecolor(plt.get_cmap("RdBu_r")(0.5 + 0.5 * rho * 0.6))
                ax.text(0.5, 0.5 if (r, c) != (0, 2) else 0.2, rf"$\rho = {rho:+.2f} \pm {err:.2f}$", ha="center", va="center",
                        transform=ax.transAxes, fontsize=13)
                ax.text(0.04, 0.05, f"{names[c]}, {names[r]}", transform=ax.transAxes, fontsize=8, color=GREY)
                ax.set_xticks([]), ax.set_yticks([])
                for spine in ax.spines.values():
                    spine.set_visible(False)
                if (r, c) == (0, 2):
                    handles = [
                        Patch(facecolor=mix(BLUE, 0), edgecolor=BLUE, label="68.3% (2D region)"),
                        Patch(facecolor=mix(BLUE, 0.5), edgecolor=BLUE, label="95.4% (2D region)"),
                        Line2D([0], [0], color=BLUE, lw=0.5, alpha=0.6, label="95.4%, 30 resamplings"),
                        Patch(facecolor=mix(BLUE, 0.75), edgecolor="none", label="median, central 68.3% (1D)"),
                        Line2D([0], [0], color="none", label=f"N = {n_draws}, ESS = {n_draws}"),
                    ]
                    ax.legend(handles=handles, loc="upper right", fontsize=8, borderaxespad=0.3, handlelength=1.6)
                continue
            ax = fig.add_subplot(gs[r, c])
            if r == c:
                lo, med, hi = np.percentile(draws[:, r], [15.87, 50, 84.13])
                marginal(ax, draws[:, r], edges[r], BLUE, shade=[(lo, hi)])
                ax.axvline(med, color=BLUE, lw=1, ymax=0.8)
                ax.set_title(f"{names[r]} = ${med:.2f}^{{+{hi - med:.2f}}}_{{-{med - lo:.2f}}}${units[r]}")
            else:
                regions(ax, draws[:, c], draws[:, r], edges[c], edges[r], BLUE, sigma=1.3)
                xc, yc = 0.5 * (edges[c][1:] + edges[c][:-1]), 0.5 * (edges[r][1:] + edges[r][:-1])
                for _ in range(30):  # the outer contour of bootstrap resamplings of the draws
                    pick = rng.integers(0, n_draws, n_draws)
                    d = density2d(draws[pick, c], draws[pick, r], edges[c], edges[r], sigma=1.3)
                    ax.contour(xc, yc, d.T, levels=[thresholds(d, [P2])[0]], colors=[BLUE], linewidths=0.4, alpha=0.45)
            finish(ax, r, c, n, labels, lims)
    fig.suptitle("Mock-up A: correlations, contour scatter and the conventions in the upper triangle", y=0.97, fontsize=12)
    fig.savefig(OUT / "mockup_a_reading_aids.png")
    plt.close(fig)


# --------------------------------------------------------------------------------------------------------------
# Mock-up B: posterior below, profile likelihood above. A toy with a prior-volume effect: the location m is
# unconstrained when the amplitude f goes to 0, so the marginal posterior of f piles up at 0 while the
# likelihood peaks at f = 0.07.
# --------------------------------------------------------------------------------------------------------------
def mockup_b():
    n_prior = 3_000_000
    f = rng.uniform(0, 0.25, n_prior)
    m = rng.uniform(3.0, 4.3, n_prior)
    h = rng.uniform(62, 80, n_prior)
    chi2 = ((f - 0.07) / 0.04) ** 2 + (f / 0.02) ** 2 * ((m - 3.55) / 0.4) ** 2 + ((h - 68 - 45 * f) / 0.9) ** 2
    weight = np.exp(-0.5 * chi2)
    keep = weight > 1e-7
    cols = [f[keep], m[keep], h[keep]]
    weight, chi2 = weight[keep], chi2[keep]
    labels = [r"$f$", r"$m$", r"$h$"]
    lims = [(0, 0.22), (3.0, 4.3), (65, 78)]
    nb = 36
    edges = [np.linspace(*lims[i], nb + 1) for i in range(3)]
    n = 3

    def profile2d(x, y, xe, ye):
        ix = np.clip(np.digitize(x, xe) - 1, 0, nb - 1)
        iy = np.clip(np.digitize(y, ye) - 1, 0, nb - 1)
        best = np.full((nb, nb), np.inf)
        np.minimum.at(best, (ix, iy), chi2)
        return gaussian_filter(np.where(np.isfinite(best), best, 60) - chi2.min(), 0.8)

    def profile1d(x, e):
        ix = np.clip(np.digitize(x, e) - 1, 0, nb - 1)
        best = np.full(nb, np.inf)
        np.minimum.at(best, ix, chi2)
        return gaussian_filter1d(best - chi2.min(), 0.8, mode="nearest")

    fig, gs = grid(n, upper_ticks=True)
    for r in range(n):
        for c in range(n):
            ax = fig.add_subplot(gs[r, c])
            if r == c:
                d = marginal(ax, cols[r], edges[r], BLUE, w=weight)
                centres = 0.5 * (edges[r][1:] + edges[r][:-1])
                dchi2 = profile1d(cols[r], edges[r])
                ax.plot(centres, d.max() * np.exp(-0.5 * dchi2), color=INK, lw=1.1, ls="--")
            elif c < r:
                regions(ax, cols[c], cols[r], edges[c], edges[r], BLUE, w=weight)
            else:
                dchi2 = profile2d(cols[c], cols[r], edges[c], edges[r])
                xc, yc = 0.5 * (edges[c][1:] + edges[c][:-1]), 0.5 * (edges[r][1:] + edges[r][:-1])
                ax.contourf(xc, yc, dchi2.T, levels=[0, 2.30, 6.18], colors=[mix(GREY, 0.45), mix(GREY, 0.75)])
                ax.contour(xc, yc, dchi2.T, levels=[2.30, 6.18], colors=[INK], linewidths=0.9, linestyles=["--", "--"])
                best = np.argmin(chi2)
                ax.plot(cols[c][best], cols[r][best], marker="*", color=INK, ms=7, ls="none")
            finish(ax, r, c, n, labels, lims)
            if c > r:  # the mirrored panels carry their y ticks on the right
                ax.yaxis.tick_right(), ax.yaxis.set_label_position("right")
                ax.tick_params(labelright=c == n - 1, labelleft=False, left=True)
                if c == n - 1:
                    ax.set_ylabel(labels[r])
    handles = [
        Patch(facecolor=mix(BLUE, 0), edgecolor=BLUE, label="Posterior: 68.3% credible region"),
        Patch(facecolor=mix(BLUE, 0.5), edgecolor=BLUE, label="95.4%"),
        Patch(facecolor=mix(GREY, 0.45), edgecolor=INK, ls="--", label=r"Profile likelihood: $\Delta\chi^2 < 2.30$ (68.3% CL, 2 dof)"),
        Patch(facecolor=mix(GREY, 0.75), edgecolor=INK, ls="--", label=r"$< 6.18$ (95.4% CL)"),
        Line2D([0], [0], marker="*", color=INK, ls="none", ms=7, label="Best fit"),
    ]
    fig.legend(handles=handles, loc="upper center", ncols=5, bbox_to_anchor=(0.5, 0.955), fontsize=8, columnspacing=1.2,
               handlelength=1.5)
    fig.suptitle("Mock-up B: marginal posterior below the diagonal, profile likelihood of the same samples above", y=0.985,
                 fontsize=12)
    fig.savefig(OUT / "mockup_b_profile_upper.png")
    plt.close(fig)


# --------------------------------------------------------------------------------------------------------------
# Mock-up C: a multimodal, cyclic and bounded posterior (an oscillation-like toy), with a block of the upper
# triangle given to the derived parameter and the probabilities of the modes.
# --------------------------------------------------------------------------------------------------------------
def hdi_pieces(x, e, fraction, wrap=False):
    d, _ = np.histogram(x, bins=e, density=True)
    d = gaussian_filter1d(d, 1.0, mode="wrap" if wrap else "nearest")
    order = np.argsort(d)[::-1]
    inside = np.zeros(len(d), bool)
    inside[order[: np.searchsorted(np.cumsum(d[order]) / d.sum(), fraction) + 1]] = True
    pieces, start = [], None
    for i, flag in enumerate(np.r_[inside, False]):
        if flag and start is None:
            start = i
        if not flag and start is not None:
            pieces.append((e[start], e[i]))
            start = None
    return pieces, 0.5 * (e[1:] + e[:-1])[np.argmax(d)]


def mockup_c():
    n_draws = 120_000
    upper = rng.random(n_draws) < 0.71
    s23 = np.where(upper, rng.normal(0.565, 0.017, n_draws), rng.normal(0.458, 0.015, n_draws))
    delta = rng.normal(np.where(upper, 0.84, 0.96) * np.pi, 0.21 * np.pi, n_draws)
    delta = (delta + np.pi) % (2 * np.pi) - np.pi  # cyclic: stored in [-pi, pi)
    dm = rng.normal(2.45 + 0.6 * (s23 - 0.52), 0.035, n_draws)
    eps = np.abs(rng.normal(0, 0.055, n_draws))  # a parameter that runs into its boundary at 0
    cols = [s23, delta / np.pi, dm, eps]
    derived = 0.0333 * np.sqrt(s23 * (1 - s23)) * 2 * np.sin(delta)  # a Jarlskog-like combination
    prior_delta = rng.uniform(-np.pi, np.pi, n_draws)
    prior_s23 = rng.uniform(0.38, 0.64, n_draws)
    derived_prior = 0.0333 * np.sqrt(prior_s23 * (1 - prior_s23)) * 2 * np.sin(prior_delta)
    labels = [r"$\sin^2\theta_{23}$", r"$\delta/\pi$ (cyclic)", r"$\Delta m^2$ ($10^{-3}$ eV$^2$)", r"$\epsilon$"]
    lims = [(0.40, 0.62), (-1, 1), (2.32, 2.58), (0, 0.2)]
    nb = 40
    edges = [np.linspace(*lims[i], nb + 1) for i in range(4)]
    wrap = [False, True, False, False]
    n = 4
    fig, gs = grid(n)
    for r in range(n):
        for c in range(r + 1):
            ax = fig.add_subplot(gs[r, c])
            if r == c:
                if r == 3:  # one-sided: the density is highest at the boundary
                    limit = np.percentile(cols[3], 95.45)
                    marginal(ax, cols[3], edges[3], BLUE, shade=[(0, limit)])
                    ax.annotate("", xy=(limit, 0), xytext=(limit, 6), arrowprops=dict(arrowstyle="-|>", color=BLUE, lw=1))
                    ax.set_title(rf"$\epsilon < {limit:.2f}$ (95.4%, at the bound 0)")
                else:
                    pieces, mode = hdi_pieces(cols[r], edges[r], P1, wrap[r])
                    marginal(ax, cols[r], edges[r], BLUE, shade=pieces)
                    if r == 0:
                        ax.set_title(r"$0.565$, HDI $[%.3f, %.3f] \cup [%.3f, %.3f]$" % (pieces[0] + pieces[1]), fontsize=7.5)
                        ax.axvline(0.5, color=GREY, lw=0.8, ls=":")
                    elif r == 1:
                        low = [p for p in pieces if p[1] >= 1 - 1e-9][0][0]
                        high = [p for p in pieces if p[0] <= -1 + 1e-9][0][1]
                        ax.set_title(rf"$\delta/\pi = {mode:.2f}$, HDI $[{low:.2f}, {high + 2:.2f}]$ (wraps)", fontsize=7.5)
                    else:
                        lo, hi = pieces[0]
                        ax.set_title(rf"$\Delta m^2 = {mode:.3f}^{{+{hi - mode:.3f}}}_{{-{mode - lo:.3f}}}$", fontsize=7.5)
            else:
                regions(ax, cols[c], cols[r], edges[c], edges[r], BLUE, wrap=(wrap[c], wrap[r]))
                if c == 0:
                    ax.axvline(0.5, color=GREY, lw=0.8, ls=":")
            finish(ax, r, c, n, labels, lims)

    # The upper-right block (rows 0-1, columns 2-3): a panel of its own for the derived parameter.
    block = fig.add_subplot(gs[0:2, 2:4])
    box = block.get_position()
    block.set_position([box.x0 + 0.045, box.y0 + 0.075, box.width - 0.045, box.height - 0.11])
    e = np.linspace(-0.036, 0.036, 49)
    d_prior, _ = np.histogram(derived_prior, bins=e, density=True)
    block.stairs(d_prior, e, color=GREY, lw=1.0, ls="--")
    pieces, mode = hdi_pieces(derived, e, P1)
    marginal(block, derived, e, RED, shade=pieces)
    block.axvline(0, color=GREY, lw=0.8, ls=":")
    block.set_xlim(e[0], e[-1])
    block.set_xlabel(r"$J = f(\theta_{23}, \delta)$   (derived)")
    block.set_title("Derived parameter, with the prior the sampling priors imply", fontsize=8.5)
    block.legend(handles=[Line2D([0], [0], color=RED, lw=1.2, label="Posterior, 68.3% HDI shaded"),
                          Line2D([0], [0], color=GREY, lw=1, ls="--", label="Implied prior"),
                          Line2D([0], [0], color="none", label=rf"$P(J < 0) = {np.mean(derived < 0):.3f} \pm {np.sqrt(np.mean(derived < 0) * np.mean(derived > 0) / n_draws):.3f}$")],
                 loc="upper left", fontsize=8, handlelength=1.5)

    # The two remaining upper cells: the legend, and the probabilities of the modes.
    cell = fig.add_subplot(gs[0, 1])
    cell.set_axis_off()
    cell.legend(handles=[Patch(facecolor=mix(BLUE, 0), edgecolor=BLUE, label="68.3% (2D), HDI (1D)"),
                         Patch(facecolor=mix(BLUE, 0.5), edgecolor=BLUE, label="95.4% (2D)"),
                         Line2D([0], [0], color=GREY, lw=0.8, ls=":", label="split value")],
                loc="center", fontsize=8, handlelength=1.5)
    cell = fig.add_subplot(gs[2, 3])
    cell.set_axis_off()
    p = upper.mean()
    err = np.sqrt(p * (1 - p) / n_draws)
    cell.text(0.5, 0.5, "Posterior probability\n"
              rf"$\sin^2\theta_{{23}} > 0.5$: ${p:.3f} \pm {err:.3f}$" "\n"
              rf"$\sin^2\theta_{{23}} < 0.5$: ${1 - p:.3f} \pm {err:.3f}$" "\n"
              rf"odds ${p / (1 - p):.2f} \pm {err / (1 - p) ** 2:.2f}$",
              ha="center", va="center", transform=cell.transAxes, fontsize=8.5, linespacing=1.5)
    fig.suptitle("Mock-up C: disjoint and wrapped intervals, a limit at a bound, and a block for a derived parameter",
                 y=0.97, fontsize=12)
    fig.savefig(OUT / "mockup_c_modes_block.png")
    plt.close(fig)


if __name__ == "__main__":
    mockup_a()
    mockup_b()
    mockup_c()
    print(f"Mock-ups written to {OUT}")
