"""Galaxy rotation curves: F11 (Rubin, Ford & Thonnard 1980) and F12 (NGC 3198
disk-halo decomposition), both from the SPARC database.

Sources and the "Data" recipes are in docs/design/research.md, Part 3.
"""

import re

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

import models
from _common import DATA

SPARC = DATA / "sparc"
SIZE_CLASSES = ((12.0, "$R_{max}$ < 12 kpc"), (35.0, "12-35 kpc"), (np.inf, "$R_{max}$ > 35 kpc"))
# SPARC's disk mass-to-light ratio at 3.6 microns (Lelli, McGaugh & Schombert 2016).
DISK_ML = 0.5


def _rotmod(galaxy):
    """Radius, observed velocity, its error, and the gas and disk velocities
    (M/L = 1) of a SPARC rotation-curve file."""
    radius, velocity, error, gas, disk, _, _, _ = np.loadtxt(SPARC / f"{galaxy}_rotmod.dat", unpack=True)
    return radius, velocity, error, gas, disk


def _name(galaxy):
    """SPARC's 'NGC0801' as 'NGC 801'."""
    match = re.match(r"(NGC|UGC|ESO|IC|DDO)0*(\d.*)", galaxy)
    return f"{match.group(1)} {match.group(2)}" if match else galaxy


def rubin_rotation_curves():
    """F11: flat rotation curves of 21 spiral galaxies (real data).

    Source: V. C. Rubin, W. K. Ford Jr., N. Thonnard, ApJ 238, 471 (1980),
    "Rotational properties of 21 Sc galaxies with a large range of
    luminosities and radii, from NGC 4605 (R = 4 kpc) to UGC 2885
    (R = 122 kpc)"; data: SPARC, Lelli, McGaugh & Schombert, AJ 152, 157
    (2016).

    From the paper: 21 galaxies with flat or slowly rising curves, none
    falling in Keplerian fashion. The figure layout is (unverified).
    Real: the SPARC HI/H-alpha rotation curves (data/sparc, fetch_data.py)
    of 21 galaxies: the three of Rubin's in SPARC (NGC 801, NGC 2998,
    UGC 2885) and 18 quality-1 SBc-Scd galaxies spread in flat velocity
    (Rubin's optical curves themselves are not in a public table).
    Ours: the Keplerian comparison V = 250 km/s sqrt(5 kpc / R).

    Rows: ``Galaxy`` (21 data rows and Keplerian), ``Type`` (Data, Model),
    ``Variable`` (three R_max classes, for --variables panels).
    """
    galaxies = sorted((path.name.split("_")[0] for path in SPARC.glob("*_rotmod.dat")), key=lambda g: g != "NGC3198")
    rows = []
    for galaxy in galaxies:
        if galaxy == "NGC3198":
            continue
        radius, velocity, error, _, _ = _rotmod(galaxy)
        size = next(label for limit, label in SIZE_CLASSES if radius.max() < limit)
        rows.append({"Radius": radius, "Velocity": velocity, "VelocityError": error, "Galaxy": _name(galaxy),
                     "Type": "Data", "RMax": radius.max(), "Variable": size})
    rows.sort(key=lambda row: row["RMax"])
    radius = np.linspace(5, 125, 200)
    rows.append({"Radius": radius, "Velocity": 250 * np.sqrt(5 / radius), "Galaxy": "Keplerian", "Type": "Model"})
    return {"RotationCurves": pd.DataFrame(rows)}


def ngc3198():
    """F12: NGC 3198 rotation curve with disk, gas and halo components (real data).

    Source: T. S. van Albada, J. N. Bahcall, K. Begeman, R. Sancisi,
    ApJ 295, 305 (1985) (citation seen only through citing papers); data:
    SPARC, Lelli, McGaugh & Schombert, AJ 152, 157 (2016).

    From the paper (via secondary sources): the HI curve to about 30 kpc,
    flat at about 150 km/s, decomposed into an exponential disk, the gas and
    an isothermal halo; total = quadrature sum. The line styles of the 1985
    figure are (unverified).
    Real: the SPARC curve of NGC 3198 (D = 13.8 Mpc; data/sparc): the
    observed velocities and errors, and the gas and stellar-disk
    contributions (the disk scaled to SPARC's M/L = 0.5 at 3.6 microns).
    Ours: the pseudo-isothermal halo (``isothermal_halo_velocity``) fitted to
    what the disk and gas leave, and the total.

    Rows: ``Component`` (Data, Disk, Gas, Halo, Total).
    """
    radius, velocity, error, gas, disk = _rotmod("NGC3198")
    baryons = DISK_ML * disk**2 + gas * np.abs(gas)

    def total(r, rho0, rc):
        return np.sqrt(np.interp(r, radius, baryons) + models.isothermal_halo_velocity(r, rho0, rc) ** 2)

    (rho0, rc), _ = curve_fit(total, radius, velocity, p0=[3e7, 5.0], sigma=error, absolute_sigma=True,
                              bounds=([0, 0.1], [1e10, 50]))
    curve = np.linspace(radius.min(), radius.max(), 300)
    rows = [
        {"Radius": radius, "Velocity": velocity, "VelocityError": error, "Component": "Data"},
        {"Radius": radius, "Velocity": np.sqrt(DISK_ML) * disk, "Component": "Disk"},
        {"Radius": radius, "Velocity": gas, "Component": "Gas"},
        {"Radius": curve, "Velocity": models.isothermal_halo_velocity(curve, rho0, rc), "Component": "Halo"},
        {"Radius": curve, "Velocity": total(curve, rho0, rc), "Component": "Total"},
    ]
    return {"NGC3198": pd.DataFrame(rows)}


GENERATORS = {"F11": rubin_rotation_curves, "F12": ngc3198}
