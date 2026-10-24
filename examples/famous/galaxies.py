"""Galaxy rotation curves: F11 (Rubin, Ford & Thonnard 1980) and F12 (NGC 3198
disk-halo decomposition).

Sources and the "Data" recipes are in docs/design/research.md, Part 3.
"""

import numpy as np
import pandas as pd

import models
from _common import rng_for

SIZE_CLASSES = ((12.0, "$R_{max}$ < 12 kpc"), (35.0, "12-35 kpc"), (np.inf, "$R_{max}$ > 35 kpc"))


def rubin_rotation_curves():
    """F11: flat rotation curves of 21 Sc galaxies.

    Source: V. C. Rubin, W. K. Ford Jr., N. Thonnard, ApJ 238, 471 (1980),
    "Rotational properties of 21 Sc galaxies with a large range of
    luminosities and radii, from NGC 4605 (R = 4 kpc) to UGC 2885
    (R = 122 kpc)".

    From the paper: 21 galaxies, outermost radii from 4 kpc (NGC 4605) to
    122 kpc (UGC 2885), velocities rising to about 125 km/s by 5 kpc and
    then flat or slowly rising, H0 = 50. The other 19 names are not used
    (labelled Sc 02-Sc 20). The figure layout is (unverified).
    Synthetic: V(R) = V_flat (1 - exp(-R/R_t)) + slope R, with V_flat
    150-300 km/s growing with R_max, R_t 1-3 kpc, a small outer slope, and
    10 km/s errors; the Keplerian comparison V = 250 km/s sqrt(5 kpc / R).

    Rows: ``Galaxy`` (21 data rows and Keplerian), ``Type`` (Data, Model),
    ``Variable`` (three R_max classes, for --variables panels).
    """
    rng = rng_for("F11")
    r_max = np.exp(np.linspace(np.log(4), np.log(122), 21))
    fraction = np.log(r_max / 4) / np.log(122 / 4)
    names = ["NGC 4605"] + [f"Sc {i:02d}" for i in range(2, 21)] + ["UGC 2885"]
    rows = []
    for name, outer, f in zip(names, r_max, fraction):
        v_flat = 150 + 150 * f + rng.normal(0, 10)
        r_turn = 1 + 2 * f + rng.uniform(-0.3, 0.3)
        slope = rng.uniform(0, 20 / outer)
        radius = np.sort(rng.uniform(0.3, outer, rng.integers(12, 26)))
        radius[-1] = outer
        velocity = v_flat * (1 - np.exp(-radius / r_turn)) + slope * radius + rng.normal(0, 10, radius.size)
        size = next(label for limit, label in SIZE_CLASSES if outer < limit)
        rows.append({"Radius": radius, "Velocity": velocity, "VelocityError": np.full(radius.size, 10.0),
                     "Galaxy": name, "Type": "Data", "RMax": outer, "Variable": size})
    radius = np.linspace(5, 122, 200)
    rows.append({"Radius": radius, "Velocity": 250 * np.sqrt(5 / radius), "Galaxy": "Keplerian", "Type": "Model"})
    return {"RotationCurves": pd.DataFrame(rows)}


def ngc3198():
    """F12: NGC 3198 rotation curve with disk, gas and halo components.

    Source: T. S. van Albada, J. N. Bahcall, K. Begeman, R. Sancisi,
    ApJ 295, 305 (1985) (citation seen only through citing papers).

    From the paper (via secondary sources): the HI curve to about 30 kpc,
    flat at about 150 km/s, the exponential disk with h = 2.68 kpc, the
    isothermal halo. Formulas: Freeman's exponential disk and the
    pseudo-isothermal sphere of the research recipe; total = quadrature
    sum. The line styles of the 1985 figure are (unverified).
    Synthetic: the disk normalisation (peak 120 km/s), the gas disk
    (h = 10 kpc, peak 25 km/s), the halo (r_c = 7 kpc, V_inf = 157 km/s),
    the radii (1-29.5 kpc every 1.5 kpc), the 3-6 km/s errors and noise.

    Rows: ``Component`` (Data, Disk, Gas, Halo, Total).
    """
    rng = rng_for("F12")
    curve = np.linspace(0.2, 32, 300)

    def scaled_disk(radius, h, peak):
        shape = models.exponential_disk_velocity(curve, 1e8, h)
        return models.exponential_disk_velocity(radius, 1e8 * (peak / shape.max()) ** 2, h)

    rc, v_inf = 7.0, 157.0
    rho0 = v_inf**2 / (4 * np.pi * models.G_KPC * rc**2)

    def components(radius):
        disk = scaled_disk(radius, 2.68, 120.0)
        gas = scaled_disk(radius, 10.0, 25.0)
        halo = models.isothermal_halo_velocity(radius, rho0, rc)
        return {"Disk": disk, "Gas": gas, "Halo": halo, "Total": np.sqrt(disk**2 + gas**2 + halo**2)}

    radius = np.arange(1, 30, 1.5)
    error = 3 + 0.1 * radius
    velocity = components(radius)["Total"] + rng.normal(0, error)
    rows = [{"Radius": radius, "Velocity": velocity, "VelocityError": error, "Component": "Data"}]
    rows += [{"Radius": curve, "Velocity": values, "Component": name} for name, values in components(curve).items()]
    return {"NGC3198": pd.DataFrame(rows)}


GENERATORS = {"F11": rubin_rotation_curves, "F12": ngc3198}
