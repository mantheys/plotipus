"""Cosmology figures: F06 (COBE FIRAS), F08 (Hubble 1929), F09 (SN Ia Hubble
diagram) and F10 (Omega_M-Omega_Lambda contours).

Sources and the "Data" recipes are in docs/design/research.md, Part 3.
"""

import numpy as np
import pandas as pd

import models
from _common import DATA, stored_fit


def firas():
    """F06: COBE FIRAS cosmic microwave background spectrum (real data).

    Sources: Mather et al. 1994, ApJ 420, 439 (T = 2.726 +- 0.010 K);
    Fixsen et al. 1996, ApJ 473, 576 (Table 4).

    Real: the FIRAS monopole spectrum of Fixsen et al. Table 4 as published on
    NASA LAMBDA (data/firas_monopole_spec_v1.txt, fetch_data.py): 43
    frequencies, the spectrum (a 2.725 K blackbody plus the residual, MJy/sr),
    the residual and its 1 sigma uncertainty (kJy/sr). The stored fit of the
    temperature is ours (statistical errors only). The "x400" error bars of the
    widely reproduced figure are (unverified for the original);
    ``IntensityErrorX400`` holds them.

    Rows: ``Component`` (FIRAS data, Blackbody). The data row stores the fitted
    ``planck_spectrum`` and ``Residual`` (kJy/sr).
    """
    wavenumber, intensity, residual, sigma, _ = np.loadtxt(DATA / "firas_monopole_spec_v1.txt", unpack=True)
    fit = stored_fit(models.planck_spectrum, wavenumber, intensity, sigma / 1000, [2.7], ["$T$"], "Blackbody",
                     units=["K"], formats=[".5f"], formula=r"$B_\nu(T)$")
    curve = np.linspace(1, 23, 300)
    rows = [
        {"Wavenumber": wavenumber, "Frequency": wavenumber * 29.9792458, "Intensity": intensity,
         "IntensityError": sigma / 1000, "IntensityErrorX400": 400 * sigma / 1000, "Residual": residual,
         "ResidualError": sigma, "Component": "FIRAS data", **fit},
        {"Wavenumber": curve, "Frequency": curve * 29.9792458,
         "Intensity": models.planck_spectrum(curve, fit["Params"][0]), "Residual": np.zeros_like(curve),
         "Component": "Blackbody"},
    ]
    return {"FIRAS": pd.DataFrame(rows)}


# Hubble (1929), Table 1: distance r (Mpc) and measured radial velocity v (km/s).
HUBBLE_TABLE = [
    ("SMC", 0.032, 170), ("LMC", 0.034, 290), ("NGC 6822", 0.214, -130), ("NGC 598", 0.263, -70),
    ("NGC 221", 0.275, -185), ("NGC 224", 0.275, -220), ("NGC 5457", 0.45, 200), ("NGC 4736", 0.5, 290),
    ("NGC 5194", 0.5, 270), ("NGC 4449", 0.63, 200), ("NGC 4214", 0.8, 300), ("NGC 3031", 0.9, -30),
    ("NGC 3627", 0.9, 650), ("NGC 4826", 0.9, 150), ("NGC 5236", 0.9, 500), ("NGC 1068", 1.0, 920),
    ("NGC 5055", 1.1, 450), ("NGC 7331", 1.1, 500), ("NGC 4258", 1.4, 500), ("NGC 4151", 1.7, 960),
    ("NGC 4382", 2.0, 500), ("NGC 4472", 2.0, 850), ("NGC 4486", 2.0, 800), ("NGC 4649", 2.0, 1090),
]
# Our nine groups (consecutive distances); Hubble's membership is not listed.
HUBBLE_GROUPS = [2, 4, 3, 1, 1, 4, 3, 2, 4]


def hubble_1929():
    """F08: Hubble's velocity-distance relation (real data).

    Source: E. Hubble, "A Relation between Distance and Radial Velocity
    among Extra-Galactic Nebulae", PNAS 15, 168-173 (1929),
    doi:10.1073/pnas.15.3.168, Table 1 and Figure 1.

    Real: the 24 distances and velocities of Table 1, as transcribed in
    research.md. They are the measured velocities; the figure plots them
    corrected for solar motion, so the points differ somewhat from the
    figure. The stored fits are the paper's: K = 465 +- 50 km/s/Mpc
    (individual nebulae) and K = 513 +- 60 km/s/Mpc (9 groups), drawn as
    lines through the origin (the solar-motion terms are left out).
    Ours: the 9-group membership (consecutive distances; the paper does not
    list it, unverified). The cross of the figure: 745 km/s at 1.4 Mpc, the
    mean of 22 further nebulae (read from the paper's text, p. 172).

    Rows: ``Sample`` (Individual nebulae, Groups, Mean of 22 nebulae, and
    the two fitted lines), ``Type`` (Data, Fit).
    """
    names, distance, velocity = (np.array(v) for v in zip(*HUBBLE_TABLE))
    distance, velocity = distance.astype(float), velocity.astype(float)
    bounds = np.cumsum([0] + HUBBLE_GROUPS)
    group_distance = np.array([distance[a:b].mean() for a, b in zip(bounds[:-1], bounds[1:])])
    group_velocity = np.array([velocity[a:b].mean() for a, b in zip(bounds[:-1], bounds[1:])])

    def fit(k, error, label):
        return {"FitFunction": "proportional", "FitFunctionLabel": label, "Params": [k], "ParamsError": [error],
                "ParamsLabel": ["$K$"], "ParamsUnit": ["km/s/Mpc"], "ParamsFormat": [".0f"]}

    # The fitted lines reach past the axis range (0-2.2 Mpc) on both sides.
    line = np.array([-1.0, 3.0])
    rows = [
        {"Distance": distance, "Velocity": velocity, "Object": names, "Sample": "Individual nebulae",
         "Type": "Data", **fit(465.0, 50.0, "Individual")},
        {"Distance": group_distance, "Velocity": group_velocity, "Object": np.arange(1, 10), "Sample": "Groups",
         "Type": "Data", **fit(513.0, 60.0, "Groups")},
        {"Distance": line, "Velocity": 465.0 * line, "Sample": "K = 465 (individual)", "Type": "Fit"},
        {"Distance": line, "Velocity": 513.0 * line, "Sample": "K = 513 (groups)", "Type": "Fit"},
        # No error bars (NaN): a velocity, not a count, so not the Poisson default of --data_hue points.
        {"Distance": np.array([1.4]), "Velocity": np.array([745.0]), "VelocityError": np.array([np.nan]),
         "Sample": "Mean of 22 nebulae", "Type": "Data"},
    ]
    return {"Hubble1929": pd.DataFrame(rows)}


COSMOLOGIES = {
    r"$\Omega_M$=0.24, $\Omega_\Lambda$=0.76": (0.24, 0.76),
    r"$\Omega_M$=0.20, $\Omega_\Lambda$=0": (0.20, 0.0),
    r"$\Omega_M$=1.00, $\Omega_\Lambda$=0": (1.00, 0.0),
}


def _supernovae():
    """The Union2.1 supernovae shared by F09 and F10: redshift, distance
    modulus (h = 0.7) and its error."""
    z, mu, sigma = np.loadtxt(DATA / "SCPUnion2.1_mu_vs_z.txt", usecols=(1, 2, 3), unpack=True)
    order = np.argsort(z)
    return z[order], mu[order], sigma[order]


def supernova_hubble_diagram():
    """F09: SN Ia Hubble diagram with three cosmologies (real data).

    Sources: Riess et al., AJ 116, 1009 (1998), astro-ph/9805201, Fig. 4;
    Perlmutter et al., ApJ 517, 565 (1999); data: the Union2.1 compilation,
    Suzuki et al., ApJ 746, 85 (2012).

    From the paper: the log z axis, the three cosmologies
    (Omega_M, Omega_Lambda) = (0.24, 0.76), (0.20, 0), (1.00, 0) and the lower
    panel Delta(m - M) relative to (0.20, 0).
    Real: the 580 Union2.1 distance moduli and errors
    (data/SCPUnion2.1_mu_vs_z.txt, fetch_data.py; diagonal errors only, the
    covariance matrix is not used), the modern successor of Riess's 50
    supernovae. The model curves use h = 0.7, as the Union2.1 moduli do.

    Rows: ``Series`` (Union2.1 SNe and the three cosmologies), ``Type`` (Data,
    Model). ``DeltaMu`` is m - M minus the (0.20, 0) model.
    """
    z, mu, sigma = _supernovae()
    reference = models.distance_modulus(z, 0.20, 0.0, h0=70.0)
    rows = [{"Redshift": z, "DistanceModulus": mu, "DistanceModulusError": sigma, "DeltaMu": mu - reference,
             "DeltaMuError": sigma, "Series": "Union2.1 SNe", "Type": "Data"}]
    curve = np.logspace(np.log10(0.005), np.log10(1.6), 200)
    curve_reference = models.distance_modulus(curve, 0.20, 0.0, h0=70.0)
    for series, (omega_m, omega_lambda) in COSMOLOGIES.items():
        model = models.distance_modulus(curve, omega_m, omega_lambda, h0=70.0)
        rows.append({"Redshift": curve, "DistanceModulus": model, "DeltaMu": model - curve_reference,
                     "Series": series, "Type": "Model"})
    return {"SupernovaHubble": pd.DataFrame(rows)}


def omega_contours():
    """F10: Omega_M-Omega_Lambda confidence regions.

    Sources: Riess et al. 1998, Fig. 6; Perlmutter et al. 1999, Fig. 7; data:
    Union2.1 (Suzuki et al. 2012).

    From the papers: the axes (Omega_M 0-2.5, Omega_Lambda -1-3) and the
    2-dof levels Delta chi^2 = 2.30, 6.18, 11.83.
    Real data, our grid: the SN Delta chi^2 of the 580 Union2.1 supernovae
    (as in F09, diagonal errors), H0 marginalised analytically
    (chi^2 = A - B^2/C); grid points without a big bang are NaN.
    Synthetic: the CMB row, an illustrative ellipse narrow along
    Omega_M + Omega_Lambda = 1 (sigma 0.03 across, 0.25 along, centred on
    0.3/0.7).

    Datafiles ``{config}_{name}_OmegaContours`` (configs SN and CMB, so that
    each gets its own ``config_color``; name Riess1998), one row each with the
    grid columns ``OmegaM``, ``OmegaLambda`` and ``DeltaChi2`` (shape
    len(OmegaLambda) x len(OmegaM)).
    """
    z, mu, sigma = _supernovae()
    omega_m = np.linspace(0, 2.5, 126)
    omega_lambda = np.linspace(-1, 3, 201)
    weight = 1 / sigma**2
    om, ol = np.meshgrid(omega_m, omega_lambda)
    supernova = np.empty(om.size)
    for start in range(0, om.size, 5000):
        part = slice(start, start + 5000)
        delta = mu - models.distance_modulus_grid(z, om.ravel()[part], ol.ravel()[part])
        supernova[part] = np.sum(delta**2 * weight, axis=1) - np.sum(delta * weight, axis=1) ** 2 / np.sum(weight)
    supernova = supernova.reshape(om.shape)
    supernova -= np.nanmin(supernova)
    cmb = ((om + ol - 1.0) / 0.03) ** 2 + ((om - 0.3) / 0.25) ** 2
    return {f"{config}_Riess1998_OmegaContours": pd.DataFrame([{
        "OmegaM": omega_m, "OmegaLambda": omega_lambda, "DeltaChi2": (grid - np.nanmin(grid)).astype(np.float32),
        "Config": config,
        "Name": "Riess1998", "Variable": "Omega"}]) for config, grid in (("SN", supernova), ("CMB", cmb))}


GENERATORS = {"F06": firas, "F08": hubble_1929, "F09": supernova_hubble_diagram, "F10": omega_contours}
