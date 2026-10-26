"""Particle-physics figures: F01, F03, F04, F05 (Higgs discovery, 2012), F16
(KamLAND) and F17 (LEP Z lineshape).

No public data tables exist for these figures (HEPData has no records for
the papers); their values are read from the figures' vector graphics in the
arXiv sources by extract/run.py, into data/extracted (method and precision:
extract/README.md).

Sources and the "Data" recipes are in docs/design/research.md, Part 3.
"""

import numpy as np
import pandas as pd

import models
from _common import DATA, stored_fit

EXTRACTED = DATA / "extracted"


def _read(name):
    return pd.read_csv(EXTRACTED / name)


def _sorted(frame, x, y):
    frame = frame.sort_values(x)
    return frame[x].to_numpy(), frame[y].to_numpy()


def _midpoints(frame):
    """Values and symmetric errors from the extracted error bars: the bar's
    midpoint and half length (the drawn marker centre is less exact)."""
    value = frame["value"].to_numpy() + (frame["error_up"].to_numpy() - frame["error_down"].to_numpy()) / 2
    return value, (frame["error_up"].to_numpy() + frame["error_down"].to_numpy()) / 2


def higgs_diphoton():
    """F01: ATLAS 2012 H->gamma gamma diphoton mass spectrum (values from the figure).

    Source: ATLAS Collaboration, Phys. Lett. B 716 (2012) 1,
    arXiv:1207.7214, Figure 4 (panels a-d).

    Extracted from the figure (data/extracted/atlas_hgg_fig4_*.csv): the 30
    data points per panel with their error bars (unweighted events, panel a;
    ln(1 + S/B)-weighted events, panel c), data minus the fitted background
    (panels b and d), and the drawn signal + background and background
    curves. Precision about 2 events in (a), 0.5 in (b); (a) minus the
    background curve reproduces (b) to 1.5 events rms.
    Ours: the stored fit (the paper's model, a fourth-order Bernstein
    background plus a Gaussian with m_H = 126.5 GeV and sigma = 1.6 GeV fixed,
    fitted to the extracted points; the paper's sigma is not quoted on the
    figure).

    Rows: ``Weighting`` (Unweighted, Weighted) x ``Component`` (Data,
    Sig+Bkg Fit, Bkg (4th order polynomial)). Data rows carry the stored
    S+B fit (``FitComponents`` names its background); ``DataMinusBackground``
    is panel b or d, and on the model rows the drawn signal curve and zero.
    """
    data, curves = _read("atlas_hgg_fig4_data.csv"), _read("atlas_hgg_fig4_curves.csv")
    rows = []
    for weighting, (top, bottom) in (("Unweighted", ("a", "b")), ("Weighted", ("c", "d"))):
        points = data[data.panel == top].sort_values("mass")
        mass = points["mass"].to_numpy()
        events, error = _midpoints(points)
        residual, residual_error = _midpoints(data[data.panel == bottom].sort_values("mass"))
        scale = events.sum() / 59000
        p0 = [3700 * scale, 2600 * scale, 1750 * scale, 1350 * scale, 950 * scale, 300 * scale, 126.5, 1.6]
        fit = stored_fit(models.diphoton_signal_plus_background, mass, events, error, p0,
                         ["$c_0$", "$c_1$", "$c_2$", "$c_3$", "$c_4$", "$N_S$", "$m_H$", r"$\sigma$"],
                         "Sig+Bkg", units=["", "", "", "", "", "", "GeV", "GeV"], fixed=(6, 7))
        rows.append({"Mass": mass, "Events": events, "EventsError": error, "Component": "Data",
                     "Weighting": weighting, "DataMinusBackground": residual,
                     "DataMinusBackgroundError": residual_error, **fit,
                     "FitComponents": {"Bkg (4th order polynomial)": ["diphoton_background", [0, 1, 2, 3, 4]]}})
        total_mass, total = _sorted(curves[(curves.panel == top) & (curves.curve == "sig+bkg")], "mass", "value")
        background_mass, background = _sorted(curves[(curves.panel == top) & (curves.curve == "bkg")], "mass", "value")
        signal_mass, signal = _sorted(curves[(curves.panel == bottom) & (curves.curve == "sig+bkg")], "mass", "value")
        rows.append({"Mass": total_mass, "Events": total,
                     "DataMinusBackground": np.interp(total_mass, signal_mass, signal),
                     "Component": "Sig+Bkg Fit", "Weighting": weighting})
        rows.append({"Mass": background_mass, "Events": background, "DataMinusBackground": np.zeros_like(background),
                     "Component": "Bkg (4th order polynomial)", "Weighting": weighting})
    return {"HiggsDiphoton": pd.DataFrame(rows)}


def higgs_four_lepton():
    """F03: H->ZZ*->4l four-lepton invariant mass (values from the figure).

    Sources: CMS arXiv:1207.7235 Fig. 4 (main panel); ATLAS arXiv:1207.7214
    Fig. 2 shows the same channel.

    Extracted from the figure (data/extracted/cms_4l_fig4.csv): the 3 GeV
    bins from 70.5 to 181.5 GeV, the Z+X, ZZ and signal (m_H = 125 GeV)
    histograms (stacked in the figure, unstacked here), and the 58 events in
    26 non-empty bins with their error bars, which are exact Garwood (Poisson)
    intervals. The signal holds 7.42 events in 110-160 GeV (CMS Table 3: 7.54).
    The real events are also public in CMS Open Data records 5500/5501.

    Rows: ``Sample`` (Data, ZZ, Z+X, Signal). The data row has the
    asymmetric errors as ``EventsError+``/``EventsError-`` and the interval
    edges ``EventsLow``/``EventsHigh``.
    """
    table = _read("cms_4l_fig4.csv")
    data = table[table.kind == "data"].sort_values("mass")
    events = data["value"].to_numpy()
    up, down = data["error_up"].to_numpy(), data["error_down"].to_numpy()
    rows = [{"Mass": data["mass"].to_numpy(), "Events": events, "EventsError+": up, "EventsError-": down,
             "EventsLow": events - down, "EventsHigh": events + up, "Sample": "Data"}]
    for kind, sample in (("ZZ", "ZZ"), ("Z+X", "Z+X"), ("signal", "Signal")):
        mass, values = _sorted(table[table.kind == kind], "mass", "value")
        rows.append({"Mass": mass, "Events": np.clip(values, 0, None), "Sample": sample})
    return {"FourLepton": pd.DataFrame(rows)}


def higgs_local_p0():
    """F04: local p0 of the background-only hypothesis vs m_H (values from the figure).

    Source: ATLAS arXiv:1207.7214 Fig. 9 (CMS arXiv:1207.7235 Fig. 14 is the
    analogue).

    Extracted from the figure (data/extracted/atlas_p0_fig9.csv): the 52
    observed points (their minimum, 1.2e-9 at 126.5 GeV, sits just above the
    6 sigma line; the text quotes 1.7e-9), the expected curve (drawn down to
    1e-11.6, at 139 GeV) and the edges of its +-1 sigma band (clipped at the
    frame, as drawn).

    Rows: ``Hypothesis`` (Observed, Expected, and Expected +-1 sigma, the
    band as ``P0Error+``/``P0Error-`` around the middle of its edges and
    ``Width`` 0, so that it is drawn in its own colour without a line). The
    sigma lines of the figure sit at p = 1 - Phi(n): 0.159, 0.0228, 1.35e-3,
    3.17e-5, 2.87e-7 and 9.87e-10 for n = 1-6.
    """
    table = _read("atlas_p0_fig9.csv")
    observed_mass, observed = _sorted(table[table.curve == "observed"], "mass", "log10_p0")
    expected_mass, expected = _sorted(table[table.curve == "expected"], "mass", "log10_p0")
    edge_a = _sorted(table[table.curve == "band_a"], "mass", "log10_p0")
    edge_b = _sorted(table[table.curve == "band_b"], "mass", "log10_p0")
    mass = np.linspace(max(edge_a[0][0], edge_b[0][0]), min(edge_a[0][-1], edge_b[0][-1]), 200)
    a, b = np.interp(mass, *edge_a), np.interp(mass, *edge_b)
    upper, lower, middle = 10 ** np.maximum(a, b), 10 ** np.minimum(a, b), 10 ** ((a + b) / 2)
    rows = [
        {"Mass": observed_mass, "P0": 10**observed, "Hypothesis": "Observed"},
        {"Mass": expected_mass, "P0": 10**expected, "Hypothesis": "Expected"},
        {"Mass": mass, "P0": middle, "Hypothesis": "Expected +-1 sigma", "Width": 0.0,
         "P0Error+": upper - middle, "P0Error-": middle - lower},
    ]
    return {"HiggsLocalP0": pd.DataFrame(rows)}


def higgs_cls_limit():
    """F05: expected and observed 95% CL limits on mu, the "Brazil band" (values from the figure).

    Sources: ATLAS arXiv:1207.7214 Fig. 7(a) (CMS arXiv:1207.7235 Fig. 13 is
    the CLs analogue).

    Extracted from the figure (data/extracted/atlas_limit_fig7a.csv): the
    observed and median expected limits and the edges of the green (+-1
    sigma) and yellow (+-2 sigma) bands, 110-600 GeV on the figure's log axes.
    The broken x axis of the ATLAS figure is (unverified) and not reproduced.

    Rows: ``Limit`` (Observed, Expected, Expected +-1 sigma, Expected +-2
    sigma). The band rows run along the middle of their edges with the band
    as ``MuLimitError+``/``-`` and ``Width`` 0 (no line). The Expected row has
    every band as sizes (``MuLimit1Sigma+``/``-``, ``MuLimit2Sigma+``/``-``) and
    edges (``MuLimit1SigmaLow``, ``MuLimit1SigmaHigh``, ``MuLimit2SigmaLow``,
    ``MuLimit2SigmaHigh``).
    """
    table = _read("atlas_limit_fig7a.csv")
    observed_mass, observed = _sorted(table[table.curve == "observed"], "log10_mass", "log10_mu")
    expected_mass, expected = _sorted(table[table.curve == "expected"], "log10_mass", "log10_mu")
    median = 10**expected
    rows = [{"Mass": 10**observed_mass, "MuLimit": 10**observed, "Limit": "Observed"}]
    expected_row = {"Mass": 10**expected_mass, "MuLimit": median, "Limit": "Expected"}
    for n in (2, 1):
        edge_a = _sorted(table[table.curve == f"band{n}_a"], "log10_mass", "log10_mu")
        edge_b = _sorted(table[table.curve == f"band{n}_b"], "log10_mass", "log10_mu")
        grid = np.linspace(max(edge_a[0][0], edge_b[0][0]), min(edge_a[0][-1], edge_b[0][-1]), 300)
        a, b = np.interp(grid, *edge_a), np.interp(grid, *edge_b)
        high, low, middle = 10 ** np.maximum(a, b), 10 ** np.minimum(a, b), 10 ** ((a + b) / 2)
        rows.append({"Mass": 10**grid, "MuLimit": middle, "Limit": f"Expected +-{n} sigma", "Width": 0.0,
                     "MuLimitError+": high - middle, "MuLimitError-": middle - low})
        at_high = 10 ** np.interp(expected_mass, grid, np.maximum(a, b))
        at_low = 10 ** np.interp(expected_mass, grid, np.minimum(a, b))
        expected_row.update({f"MuLimit{n}Sigma+": np.clip(at_high - median, 0, None),
                             f"MuLimit{n}Sigma-": np.clip(median - at_low, 0, None),
                             f"MuLimit{n}SigmaLow": at_low, f"MuLimit{n}SigmaHigh": at_high})
    rows.append(expected_row)
    return {"HiggsLimit": pd.DataFrame(rows)}


def kamland():
    """F16: KamLAND survival probability vs L0/E (values from the figure).

    Source: KamLAND Collaboration (S. Abe et al.), PRL 100, 221803 (2008),
    arXiv:0801.4589, Figure 3.

    Extracted from the figure (data/extracted/kamland_fig3.csv): the 20 data
    points (Data - BG - Geo nu_e) with their statistical errors and their
    equal-probability L0/E bins (the ends of their horizontal bars), the
    expectation histogram (its step outline) and the expectation curve for
    Delta m^2 = 7.58e-5 eV^2, tan^2 theta = 0.56.

    Rows: ``Component`` (Data - BG - Geo nu, Expectation (histogram),
    Expectation (curve)). ``LOverEBinEdges`` holds the 21 bin edges of the
    data row.
    """
    table = _read("kamland_fig3.csv")
    data = table[table.kind == "data"].sort_values("l_over_e")
    probability = data["survival"].to_numpy() + (data["error_a"].to_numpy() - data["error_b"].to_numpy()) / 2
    error = (data["error_a"].to_numpy() + data["error_b"].to_numpy()) / 2
    edges = np.unique(np.round(np.concatenate([data["le_low"], data["le_high"]]), 2))
    histogram = table[table.kind == "histogram"]
    curve_le, curve = _sorted(table[table.kind == "curve"], "l_over_e", "survival")
    rows = [
        {"LOverE": data["l_over_e"].to_numpy(), "SurvivalProbability": probability,
         "SurvivalProbabilityError": error, "LOverEBinEdges": edges, "Component": "Data - BG - Geo $\\nu_e$"},
        # The expectation histogram as its outline, in drawing order (a step polyline).
        {"LOverE": histogram["l_over_e"].to_numpy(), "SurvivalProbability": histogram["survival"].to_numpy(),
         "Component": "Expectation (histogram)"},
        {"LOverE": curve_le, "SurvivalProbability": curve, "Component": "Expectation (curve)", "Width": 4.0},
    ]
    return {"KamLAND": pd.DataFrame(rows)}


def z_lineshape():
    """F17: LEP hadronic cross section near the Z and N_nu = 2, 3, 4 (values from the figure).

    Source: ALEPH, DELPHI, L3, OPAL, SLD et al., Phys. Rept. 427 (2006) 257,
    hep-ex/0509008, Fig. 1.13.

    Extracted from the figure (data/extracted/lep_nnu_fig1_13.csv): the seven
    average measurements with their errors (drawn x10 in the figure; divided
    back here) and the 2, 3 and 4 neutrino curves (peaks 35.05, 30.76 and
    27.22 nb).
    The data row stores the figure's 3 nu curve as its model (``lep_curve``),
    so --lower pull compares the measurements with it. (``z_lineshape_isr``,
    our Breit-Wigner with a leading-log ISR radiator and the paper's m_Z and
    Gamma_Z, peaks at 30.7 nb but is 0.3% off the figure's curve, ten times
    the measurement errors.)

    Rows: ``Model`` (Data, 2 nu, 3 nu, 4 nu). The data row stores the 3 nu
    curve and the errors x10 as ``CrossSectionErrorX10``.
    """
    table = _read("lep_nnu_fig1_13.csv")
    data = table[table.kind == "data"].sort_values("energy")
    error = (data["error_up"].to_numpy() + data["error_down"].to_numpy()) / 2
    rows = [{"Energy": data["energy"].to_numpy(), "CrossSection": data["sigma_had"].to_numpy(),
             "CrossSectionError": error, "CrossSectionErrorX10": 10 * error, "Model": "Data",
             "FitFunction": "lep_curve", "FitFunctionLabel": "3 neutrinos", "Params": [3],
             "ParamsError": [0], "ParamsLabel": [r"$N_\nu$"]}]
    for kind, n_nu in (("2nu", 2), ("3nu", 3), ("4nu", 4)):
        energy, sigma = _sorted(table[table.kind == kind], "energy", "sigma_had")
        rows.append({"Energy": energy, "CrossSection": sigma, "Model": f"{n_nu}$\\nu$",
                     "Width": 3.0 if n_nu == 3 else 1.2})
    return {"ZLineshape": pd.DataFrame(rows)}


GENERATORS = {"F01": higgs_diphoton, "F03": higgs_four_lepton, "F04": higgs_local_p0, "F05": higgs_cls_limit,
              "F16": kamland, "F17": z_lineshape}
