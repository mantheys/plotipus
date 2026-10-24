"""Particle-physics figures: F01, F03, F04, F05 (Higgs discovery, 2012), F16
(KamLAND) and F17 (LEP Z lineshape).

Sources and the "Data" recipes are in docs/design/research.md, Part 3.
"""

import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import gaussian_filter1d
from scipy.stats import chi2, moyal, norm

import models
from _common import rng_for, stored_fit


def _garwood(n, cl=0.6827):
    """Exact (Garwood) Poisson interval of observed counts ``n``."""
    n = np.asarray(n, dtype=float)
    alpha = 1 - cl
    low = np.where(n > 0, chi2.ppf(alpha / 2, 2 * n) / 2, 0.0)
    high = chi2.ppf(1 - alpha / 2, 2 * (n + 1)) / 2
    return low, high


def higgs_diphoton():
    """F01: ATLAS 2012 H->gamma gamma diphoton mass spectrum.

    Source: ATLAS Collaboration, Phys. Lett. B 716 (2012) 1,
    arXiv:1207.7214, Figure 4 (panels a-d).

    From the paper: the 100-160 GeV range in 2 GeV bins, the fourth-order
    Bernstein background, a signal fixed at m_H = 126.5 GeV (the stored fit
    fixes m_H and sigma), and the
    ln(1 + S/B) category weights of the weighted panels.
    Synthetic: the background normalisation (about 3700 events/2 GeV at
    100 GeV falling to about 950 at 160 GeV, read from the figure), the
    signal (270 events, sigma = 1.6 GeV), the ten categories and their S/B,
    and the Poisson draws. Whether HEPData has the real spectrum is
    (unverified).

    Rows: ``Weighting`` (Unweighted, Weighted) x ``Component`` (Data,
    Sig+Bkg Fit, Bkg (4th order polynomial)). Data rows carry the stored
    S+B fit; ``DataMinusBackground`` is data minus the fitted background
    (panels b and d), and on the model rows the signal curve and zero.
    """
    rng = rng_for("F01")
    edges = np.arange(100, 162, 2.0)
    mass = (edges[:-1] + edges[1:]) / 2
    curve = np.linspace(100, 160, 301)
    background = np.array([3700.0, 2600.0, 1750.0, 1350.0, 950.0])
    n_signal, m_h, sigma = 270.0, 126.5, 1.6

    # Ten categories: fraction of the background and of the signal in each.
    background_share = np.array([0.02, 0.04, 0.05, 0.07, 0.08, 0.10, 0.12, 0.14, 0.18, 0.20])
    signal_share = np.array([0.06, 0.08, 0.08, 0.10, 0.10, 0.11, 0.11, 0.11, 0.12, 0.13])
    window = np.abs(mass - m_h) < 2 * sigma
    b_window = models.diphoton_background(mass[window], *background).sum()
    s_over_b = signal_share * 0.95 * n_signal / (background_share * b_window)
    weights = np.log1p(s_over_b)

    counts = np.zeros((len(weights), len(mass)))
    for k in range(len(weights)):
        expected = (background_share[k] * models.diphoton_background(mass, *background)
                    + signal_share[k] * (models.diphoton_signal_plus_background(mass, *np.zeros(5), n_signal, m_h, sigma)))
        counts[k] = rng.poisson(expected)

    spectra = {
        "Unweighted": (counts.sum(axis=0), np.sqrt(np.maximum(counts.sum(axis=0), 1))),
        "Weighted": ((weights[:, None] * counts).sum(axis=0),
                     np.sqrt((weights[:, None] ** 2 * np.maximum(counts, 1)).sum(axis=0))),
    }
    rows = []
    for weighting, (events, error) in spectra.items():
        scale = events.sum() / spectra["Unweighted"][0].sum()
        p0 = list(background * scale) + [n_signal * scale, m_h, sigma]
        fit = stored_fit(models.diphoton_signal_plus_background, mass, events, error, p0,
                         ["$c_0$", "$c_1$", "$c_2$", "$c_3$", "$c_4$", "$N_S$", "$m_H$", r"$\sigma$"],
                         "Sig+Bkg", units=["", "", "", "", "", "", "GeV", "GeV"], fixed=(6, 7))
        params = fit["Params"]
        rows.append({"Mass": mass, "Events": events, "EventsError": error, "Component": "Data",
                     "Weighting": weighting, "DataMinusBackground": events - models.diphoton_background(mass, *params[:5]),
                     "DataMinusBackgroundError": error, **fit})
        total = models.diphoton_signal_plus_background(curve, *params)
        background_curve = models.diphoton_background(curve, *params[:5])
        rows.append({"Mass": curve, "Events": total, "DataMinusBackground": total - background_curve,
                     "Component": "Sig+Bkg Fit", "Weighting": weighting})
        rows.append({"Mass": curve, "Events": background_curve, "DataMinusBackground": np.zeros_like(curve),
                     "Component": "Bkg (4th order polynomial)", "Weighting": weighting})
    return {"HiggsDiphoton": pd.DataFrame(rows)}


def higgs_four_lepton():
    """F03: H->ZZ*->4l four-lepton invariant mass.

    Sources: ATLAS arXiv:1207.7214 Fig. 2 and CMS arXiv:1207.7235 Fig. 4.

    From the papers: the CMS binning (70-181 GeV, 3 GeV bins), the
    components (Z+X, Z gamma*/ZZ, signal at m_H = 125 GeV) and the expected
    signal of about 7.5 events (CMS Table 3: 7.54 +- 0.78 in 110-160 GeV).
    Read off CMS Fig. 4: the Z->4l peak (about 11 events in the 91 GeV
    bin), the ZZ continuum (about 1 event per bin, rising to 2 near
    180 GeV) and a small Z+X (0.1-0.3 per bin).
    Synthetic: the shapes that give those levels (Gaussian Z peak, flat
    continuum with the on-shell ZZ turn-on, Landau-like (Moyal) Z+X), the
    MC weights behind the MC statistical errors, and the Poisson data. The
    real events are public in CMS Open Data records 5500/5501.

    Rows: ``Sample`` (Data, ZZ, Z+X, Signal). Data rows carry sqrt(N)
    errors and the Garwood interval edges ``EventsLow``/``EventsHigh``.
    """
    rng = rng_for("F03")
    edges = np.arange(70, 182, 3.0)
    mass = (edges[:-1] + edges[1:]) / 2
    width = np.diff(edges)

    def gaussian(n, mean, sigma):
        return n * width * norm.pdf(mass, mean, sigma)

    turn_on = 1 / (1 + np.exp(-(mass - 100) / 4))
    expected = {
        "ZZ": gaussian(22.0, 91.2, 2.3) + 0.08 + 0.85 * turn_on + 1.1 / (1 + np.exp(-(mass - 178) / 2.5)),
        "Z+X": 7.0 * width * moyal.pdf(mass, 125, 25),
        "Signal": gaussian(7.5, 125.0, 2.0),
    }
    mc_weight = {"ZZ": 0.02, "Z+X": 0.3, "Signal": 0.005}
    data = rng.poisson(sum(expected.values()))
    low, high = _garwood(data)
    rows = [{"Mass": mass, "Events": data.astype(float), "EventsError": np.sqrt(data), "EventsLow": low,
             "EventsHigh": high, "Sample": "Data"}]
    for sample, values in expected.items():
        # MC statistical error of a sample of weight w: sqrt(N_mc) w = sqrt(n w).
        rows.append({"Mass": mass, "Events": values, "EventsError": np.sqrt(values * mc_weight[sample]),
                     "Sample": sample})
    return {"FourLepton": pd.DataFrame(rows)}


def higgs_local_p0():
    """F04: local p0 of the background-only hypothesis vs m_H.

    Sources: ATLAS arXiv:1207.7214 Fig. 9, CMS arXiv:1207.7235 Fig. 14.

    From the papers: the 110-150 GeV range, the observed minimum of
    1.7e-9 (5.9 sigma) at 126.5 GeV, the +-1 sigma band on the expected
    curve, and p0 = 1 - Phi(Z). Read off ATLAS Fig. 9: the expected
    significance rising with mass (about 2.5 sigma at 110 GeV, 4.9 at
    126.5 GeV, 6.7 at 139 GeV) and the observed width (p0 = 1e-3 about
    4 GeV from the minimum).
    Synthetic: the observed curve Z_obs = 5.9 exp(-(m - 126.5)^2 / 2w^2),
    w = 3.7 GeV, plus a positive correlated fluctuation (0.4 +- 0.5 sigma,
    white noise smoothed over 2 GeV) fading out at the peak; the expected
    curve interpolated through the values read off the figure.

    Rows: ``Hypothesis`` (Observed, Expected, and Expected +-1 sigma, the
    same curve carrying the band as ``P0Error+``/``P0Error-`` so that it can
    be drawn in its own colour). The sigma lines of the figure sit at
    p = 1 - Phi(n): 0.159, 0.0228, 1.35e-3, 3.17e-5, 2.87e-7 and 9.87e-10
    for n = 1-6.
    """
    rng = rng_for("F04")
    mass = np.arange(110, 150.01, 0.5)
    noise = gaussian_filter1d(rng.normal(size=mass.size), 2 / 0.5)
    noise /= noise.std()
    peak = np.exp(-0.5 * ((mass - 126.5) / 3.7) ** 2)
    z_observed = 5.9 * peak + (0.4 + 0.5 * noise) * (1 - peak)
    z_expected = PchipInterpolator([110, 115, 120, 123, 126.5, 129, 132, 135, 139, 150],
                                   [2.45, 2.55, 2.9, 3.4, 4.9, 5.1, 5.4, 6.0, 6.7, 8.5])(mass)
    p_expected = norm.sf(z_expected)
    rows = [
        {"Mass": mass, "P0": norm.sf(z_observed), "Significance": z_observed, "Hypothesis": "Observed"},
        {"Mass": mass, "P0": p_expected, "Significance": z_expected, "Hypothesis": "Expected"},
        {"Mass": mass, "P0": p_expected, "Hypothesis": "Expected +-1 sigma",
         "P0Error+": norm.sf(z_expected - 1) - p_expected, "P0Error-": p_expected - norm.sf(z_expected + 1)},
    ]
    return {"HiggsLocalP0": pd.DataFrame(rows)}


def higgs_cls_limit():
    """F05: expected and observed 95% CL limits on mu ("Brazil band").

    Sources: ATLAS arXiv:1207.7214 Fig. 7(a), CMS arXiv:1207.7235 Fig. 13.

    From the papers: the 110-600 GeV range, the observed/expected curves
    and the +-1/2 sigma bands. Read off ATLAS Fig. 7(a): the median
    expected limit (0.62 at 110 GeV, a minimum of 0.14 near 160 GeV,
    0.2-0.3 from 200 to 400 GeV, 1.1 at 600 GeV) and the observed excess
    (1.6 at 126 GeV). The bands use the asymptotic formula of Cowan,
    Cranmer, Gross & Vitells (2011), arXiv:1007.1727:
    mu_N = sigma_mu (Phi^-1(1 - 0.05 Phi(N)) + N), N = -2..2, with
    sigma_mu = mu_med / 1.96 (edges 0.53, 0.72, 1.39, 1.87 x the median).
    The research recipe's form, Phi(-+N), gives a negative -2 sigma edge.
    Synthetic: the observed fluctuation. The broken x axis of the ATLAS
    figure is (unverified).

    Rows: ``Limit`` (Observed, Expected, Expected +-1 sigma, Expected +-2
    sigma). The band rows repeat the median with their band as
    ``MuLimitError+``/``-``. The Expected row has every band as sizes
    (``MuLimit1Sigma+``/``-``, ``MuLimit2Sigma+``/``-``) and edges
    (``MuLimit1SigmaLow``, ``MuLimit1SigmaHigh``, ``MuLimit2SigmaLow``,
    ``MuLimit2SigmaHigh``).
    """
    rng = rng_for("F05")
    mass = np.concatenate([np.arange(110, 150, 1.0), np.arange(150, 601, 5.0)])
    anchors_m = [110, 120, 130, 145, 160, 175, 200, 250, 300, 350, 385, 420, 470, 530, 600]
    anchors_mu = [0.62, 0.5, 0.36, 0.22, 0.14, 0.17, 0.21, 0.27, 0.29, 0.29, 0.26, 0.29, 0.42, 0.65, 1.1]
    median = np.exp(PchipInterpolator(np.log(anchors_m), np.log(anchors_mu))(np.log(mass)))
    sigma_mu = median / 1.96

    def band(n):
        return sigma_mu * (norm.ppf(1 - 0.05 * norm.cdf(n)) + n)

    noise = gaussian_filter1d(rng.normal(size=mass.size), 2)
    noise /= noise.std()
    observed = median * np.exp(0.2 * noise) * (1 + 2.6 * np.exp(-0.5 * ((mass - 126) / 3) ** 2))
    rows = [{"Mass": mass, "MuLimit": observed, "Limit": "Observed"}]
    expected = {"Mass": mass, "MuLimit": median, "Limit": "Expected"}
    for n in (2, 1):
        low, high = band(-n), band(n)
        expected.update({f"MuLimit{n}Sigma+": high - median, f"MuLimit{n}Sigma-": median - low,
                         f"MuLimit{n}SigmaLow": low, f"MuLimit{n}SigmaHigh": high})
        rows.append({"Mass": mass, "MuLimit": median, "Limit": f"Expected +-{n} sigma",
                     "MuLimitError+": high - median, "MuLimitError-": median - low})
    rows.append(expected)
    return {"HiggsLimit": pd.DataFrame(rows)}


def kamland():
    """F16: KamLAND survival probability vs L0/E.

    Source: KamLAND Collaboration (S. Abe et al.), PRL 100, 221803 (2008),
    arXiv:0801.4589, Figure 3.

    From the paper: Delta m^2 = 7.58e-5 eV^2 and tan^2 theta = 0.56
    (abstract; sin^2 2theta = 0.92), L0 = 180 km, the 20-100 km/MeV range,
    equal-probability bins and statistical-only errors; about 2179 events
    expected without oscillation and about 1600 observed.
    Synthetic: the reactor distance mixture (94% near reactors around
    170 km, 6% far ones at 300-600 km), the antineutrino energy spectrum
    (1.8 MeV + Gamma(3, 0.75 MeV)), the events; no energy resolution and no
    background subtraction.

    Rows: ``Component`` (Data - BG - Geo nu, Expectation (histogram),
    Expectation (curve)). ``LOverEBinEdges`` holds the 21 variable bin
    edges of the data row; the histogram row is its step outline (two
    points per bin).
    """
    rng = rng_for("F16")
    delta_m2, sin2_2theta, l0, n_expected = 7.58e-5, 4 * 0.56 / (1 + 0.56) ** 2, 180.0, 2179
    n_mc = 400_000
    near = rng.random(n_mc) < 0.94
    distance = np.where(near, np.clip(rng.normal(170, 20, n_mc), 120, 230), rng.uniform(300, 600, n_mc))
    energy = 1.8 + rng.gamma(3, 0.75, n_mc)
    survival = models.survival_probability(distance / energy, delta_m2, sin2_2theta)
    l_over_e = l0 / energy

    inside = (l_over_e > 20) & (l_over_e < 100)
    edges = np.quantile(l_over_e[inside], np.linspace(0, 1, 21))
    no_oscillation = np.histogram(l_over_e[inside], edges)[0] / n_mc * n_expected
    expectation = np.histogram(l_over_e[inside], edges, weights=survival[inside])[0] / n_mc * n_expected

    n_observed = rng.poisson(n_expected * survival.mean())
    observed = rng.choice(n_mc, n_observed, replace=False, p=survival / survival.sum())
    data = np.histogram(l_over_e[observed], edges)[0]
    centres = (edges[:-1] + edges[1:]) / 2

    fine = np.linspace(20, 100, 400)
    sample = distance[:20_000]
    curve = np.array([models.survival_probability(sample * x / l0, delta_m2, sin2_2theta).mean() for x in fine])
    rows = [
        {"LOverE": centres, "SurvivalProbability": data / no_oscillation,
         "SurvivalProbabilityError": np.sqrt(data) / no_oscillation, "LOverEBinEdges": edges,
         "Component": "Data - BG - Geo $\\nu_e$"},
        # The expectation histogram as its outline: a step polyline over the bin edges.
        {"LOverE": np.repeat(edges, 2)[1:-1], "SurvivalProbability": np.repeat(expectation / no_oscillation, 2),
         "Component": "Expectation (histogram)"},
        {"LOverE": fine, "SurvivalProbability": curve, "Component": "Expectation (curve)"},
    ]
    return {"KamLAND": pd.DataFrame(rows)}


def z_lineshape():
    """F17: LEP hadronic cross section near the Z and N_nu = 2, 3, 4.

    Source: ALEPH, DELPHI, L3, OPAL, SLD et al., Phys. Rept. 427 (2006) 257,
    hep-ex/0509008, Fig. 1.13.

    From the paper: m_Z = 91.1875 GeV, Gamma_Z = 2.4952 GeV, the Born
    formula (eq. 1.40), the measured peak of about 30.4 nb after ISR, the
    86-94 GeV range and the errors magnified x10. Gamma_ee = 83.91 MeV and
    Gamma_had = 1744.4 MeV are the LEP averages as recalled (not re-read).
    The N_nu = 2, 4 curves change Gamma_Z by -+Gamma_nunu = 166.9 MeV
    (inferred from Gamma_inv / 3, unverified).
    Read off Fig. 1.13: the seven scan energies (88.4-93.9 GeV).
    Synthetic: the relative errors (0.1% at the peak, 0.2-0.4% off peak) and their draws.
    ISR is a leading-log radiator convolution, not the full LEP treatment.

    Rows: ``Model`` (Data, 2 nu, 3 nu, 4 nu). The data row stores the
    3 nu model (``z_lineshape_isr``) for --lower pull and the errors x10 as
    ``CrossSectionErrorX10``.
    """
    rng = rng_for("F17")
    m_z, gamma_z, gamma_ee, gamma_had, gamma_nunu = 91.1875, 2.4952, 0.08391, 1.7444, 0.1669
    energy = np.array([88.38, 89.38, 90.22, 91.23, 92.05, 93.00, 93.90])
    relative = np.array([0.004, 0.003, 0.002, 0.001, 0.002, 0.003, 0.004])
    truth = models.z_lineshape_isr(energy, m_z, gamma_z, gamma_ee, gamma_had)
    cross_section = truth * (1 + relative * rng.normal(size=energy.size))
    error = relative * truth
    curve = np.linspace(85, 94.5, 191)
    rows = [{"Energy": energy, "CrossSection": cross_section, "CrossSectionError": error,
             "CrossSectionErrorX10": 10 * error, "Model": "Data",
             "FitFunction": "z_lineshape_isr", "FitFunctionLabel": "3 neutrinos",
             "Params": [m_z, gamma_z, gamma_ee, gamma_had], "ParamsError": [0.0021, 0.0023, 0.00012, 0.0020],
             "ParamsLabel": ["$m_Z$", r"$\Gamma_Z$", r"$\Gamma_{ee}$", r"$\Gamma_{had}$"],
             "ParamsUnit": ["GeV", "GeV", "GeV", "GeV"]}]
    for n_nu in (2, 3, 4):
        width = gamma_z + (n_nu - 3) * gamma_nunu
        rows.append({"Energy": curve, "CrossSection": models.z_lineshape_isr(curve, m_z, width, gamma_ee, gamma_had),
                     "Model": f"{n_nu}$\\nu$"})
    return {"ZLineshape": pd.DataFrame(rows)}


GENERATORS = {"F01": higgs_diphoton, "F03": higgs_four_lepton, "F04": higgs_local_p0, "F05": higgs_cls_limit,
              "F16": kamland, "F17": z_lineshape}
