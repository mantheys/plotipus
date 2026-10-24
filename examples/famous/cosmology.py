"""Cosmology figures: F06 (COBE FIRAS), F08 (Hubble 1929), F09 (SN Ia Hubble
diagram) and F10 (Omega_M-Omega_Lambda contours).

Sources and the "Data" recipes are in docs/design/research.md, Part 3.
"""

import numpy as np
import pandas as pd

import models
from _common import rng_for, stored_fit


def firas():
    """F06: COBE FIRAS cosmic microwave background spectrum.

    Sources: Mather et al. 1994, ApJ 420, 439 (T = 2.726 +- 0.010 K);
    Fixsen et al. 1996, ApJ 473, 576 (Table 4 residuals).

    From the papers: the 43 frequencies from 2.27 to 21.33 cm^-1, a
    2.725 K blackbody, intensities in MJy/sr and residuals in kJy/sr.
    Synthetic: the 1 sigma uncertainties (8 + 0.004 (nu - 10)^4 kJy/sr, a
    smooth stand-in for Table 4) and the residuals drawn from them. The real
    table is public on NASA LAMBDA (firas_monopole_spec_v1.txt). The "x400"
    error bars of the widely reproduced figure are (unverified for the
    original); ``IntensityErrorX400`` holds them.

    Rows: ``Component`` (Data, Blackbody). The data row stores the fitted
    ``planck_spectrum`` and ``Residual`` (kJy/sr).
    """
    rng = rng_for("F06")
    wavenumber = np.linspace(2.27, 21.33, 43)
    sigma = 8 + 0.004 * (wavenumber - 10) ** 4  # kJy/sr
    residual = rng.normal(0, sigma)
    intensity = models.planck_spectrum(wavenumber, 2.725) + residual / 1000
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
        {"Distance": np.array([1.4]), "Velocity": np.array([745.0]), "Sample": "Mean of 22 nebulae",
         "Type": "Data"},
    ]
    return {"Hubble1929": pd.DataFrame(rows)}


COSMOLOGIES = {
    r"$\Omega_M$=0.24, $\Omega_\Lambda$=0.76": (0.24, 0.76),
    r"$\Omega_M$=0.20, $\Omega_\Lambda$=0": (0.20, 0.0),
    r"$\Omega_M$=1.00, $\Omega_\Lambda$=0": (1.00, 0.0),
}


def _supernovae():
    """The synthetic SN Ia sample shared by F09 and F10."""
    rng = rng_for("F09")
    z_near = np.sort(10 ** rng.uniform(np.log10(0.0085), np.log10(0.13), 27))
    z_far = np.sort(rng.uniform(0.3, 0.62, 15))
    z = np.concatenate([z_near, z_far, [0.97]])
    peculiar = 5 / np.log(10) * 400 / (models.C_KMS * z)
    sigma = np.sqrt(np.where(z < 0.15, 0.15, rng.uniform(0.2, 0.3, z.size)) ** 2 + peculiar**2)
    mu = models.distance_modulus(z, 0.28, 0.72) + rng.normal(0, sigma)
    return z, mu, sigma


def supernova_hubble_diagram():
    """F09: SN Ia Hubble diagram with three cosmologies.

    Sources: Riess et al., AJ 116, 1009 (1998), astro-ph/9805201, Fig. 4;
    Perlmutter et al., ApJ 517, 565 (1999).

    From the paper: the log z axis (0.01-1), the three cosmologies
    (Omega_M, Omega_Lambda) = (0.24, 0.76), (0.20, 0), (1.00, 0), the lower
    panel Delta(m - M) relative to (0.20, 0), the open symbol for SN 1997ck
    (z = 0.97), 27 nearby SNe (research.md) and 16 high-z ones (as recalled
    from the abstract, unverified).
    Synthetic: the redshifts (0.0085-0.13 and 0.3-0.62, as in Fig. 4), the
    distances (true cosmology Omega_M = 0.28,
    Omega_Lambda = 0.72, H0 = 65 km/s/Mpc) and the errors (0.15 mag nearby,
    0.2-0.3 mag high-z, plus 400 km/s peculiar velocities). The real
    distances are public (Union2.1, or Riess Tables 5, 6, 10).

    Rows: ``Series`` (Nearby SNe, High-z SNe, SN 1997ck and the three
    cosmologies), ``Type`` (Data, Model). ``DeltaMu`` is m - M minus the
    (0.20, 0) model.
    """
    z, mu, sigma = _supernovae()
    reference = models.distance_modulus(z, 0.20, 0.0)
    rows = []
    for series, index in (("Nearby SNe", z < 0.15), ("High-z SNe", (z > 0.15) & (z < 0.95)), ("SN 1997ck", z > 0.95)):
        rows.append({"Redshift": z[index], "DistanceModulus": mu[index], "DistanceModulusError": sigma[index],
                     "DeltaMu": mu[index] - reference[index], "DeltaMuError": sigma[index],
                     "Series": series, "Type": "Data"})
    curve = np.logspace(np.log10(0.005), np.log10(1.5), 200)
    curve_reference = models.distance_modulus(curve, 0.20, 0.0)
    for series, (omega_m, omega_lambda) in COSMOLOGIES.items():
        model = models.distance_modulus(curve, omega_m, omega_lambda)
        rows.append({"Redshift": curve, "DistanceModulus": model, "DeltaMu": model - curve_reference,
                     "Series": series, "Type": "Model"})
    return {"SupernovaHubble": pd.DataFrame(rows)}


def omega_contours():
    """F10: Omega_M-Omega_Lambda confidence regions.

    Sources: Riess et al. 1998, Fig. 6; Perlmutter et al. 1999, Fig. 7.

    From the papers: the axes (Omega_M 0-2.5, Omega_Lambda -1-3) and the
    2-dof levels Delta chi^2 = 2.30, 6.18, 11.83.
    Synthetic: the SN Delta chi^2 is computed from the F09 sample with H0
    marginalised analytically (chi^2 = A - B^2/C); grid points without a
    big bang are NaN. The CMB row is an illustrative ellipse narrow along
    Omega_M + Omega_Lambda = 1 (sigma 0.03 across, 0.25 along, centred on
    0.3/0.7).

    Datafiles ``{config}_{name}_OmegaContours`` (config Riess1998, names
    SN and CMB), one row each with the grid columns ``OmegaM``,
    ``OmegaLambda`` and ``DeltaChi2`` (shape len(OmegaLambda) x
    len(OmegaM)).
    """
    z, mu, sigma = _supernovae()
    omega_m = np.linspace(0, 2.5, 51)
    omega_lambda = np.linspace(-1, 3, 81)
    weight = 1 / sigma**2
    supernova = np.full((omega_lambda.size, omega_m.size), np.nan)
    for i, ol in enumerate(omega_lambda):
        for j, om in enumerate(omega_m):
            model = models.distance_modulus(z, om, ol)
            if np.isnan(model).any():
                continue
            delta = mu - model
            supernova[i, j] = np.sum(delta**2 * weight) - np.sum(delta * weight) ** 2 / np.sum(weight)
    supernova -= np.nanmin(supernova)
    om, ol = np.meshgrid(omega_m, omega_lambda)
    cmb = ((om + ol - 1.0) / 0.03) ** 2 + ((om - 0.3) / 0.25) ** 2
    return {f"Riess1998_{name}_OmegaContours": pd.DataFrame([{
        "OmegaM": omega_m, "OmegaLambda": omega_lambda, "DeltaChi2": grid - np.nanmin(grid), "Config": "Riess1998",
        "Name": name, "Variable": "Omega"}]) for name, grid in (("SN", supernova), ("CMB", cmb))}


GENERATORS = {"F06": firas, "F08": hubble_1929, "F09": supernova_hubble_diagram, "F10": omega_contours}
