"""Early-20th-century physics and astronomy: F19 (Geiger-Marsden), F20
(Moseley), F21 (Leavitt) and F22 (Hertzsprung-Russell diagram).

Sources and the "Data" recipes are in docs/design/research.md, Part 3.
"""

import numpy as np
import pandas as pd

import models
from _common import rng_for, stored_fit


def geiger_marsden():
    """F19: alpha scattering counts vs deflection angle.

    Source: H. Geiger and E. Marsden, Phil. Mag. Ser. 6, 25, 604 (1913).

    From the paper: gold and silver foils, angles between 15 and 150
    degrees, N sin^4(phi/2) about constant (Rutherford 1911). The count
    table was not transcribed (scan is image-only), so all counts are
    (unverified) and synthetic.
    Synthetic: eleven angles, N = A / sin^4(phi/2) with A = 26 for gold
    (N(150) = 30; the pure law then gives 9e4 at 15 degrees, not the 1.4e5
    the research recipe quotes, so the recipe's two anchors cannot both
    hold), A x (47/79)^2 for silver (equal atoms per area), Poisson
    counts. The stored fits are fitted to these counts.

    Rows: ``Foil`` (Gold, Silver, and the fitted law of each), ``Type``
    (Data, Model), x ``Angle`` (degrees), y ``Counts``, ``CountsSin4`` =
    N sin^4(phi/2).
    """
    rng = rng_for("F19")
    angle = np.array([15, 22.5, 30, 37.5, 45, 60, 75, 105, 120, 135, 150])
    sin4 = np.sin(np.radians(angle) / 2) ** 4
    curve = np.linspace(10, 160, 151)
    rows = []
    for foil, a in (("Gold", 26.0), ("Silver", 26.0 * (47 / 79) ** 2)):
        counts = rng.poisson(models.rutherford(angle, a)).astype(float)
        error = np.sqrt(np.maximum(counts, 1))
        fit = stored_fit(models.rutherford, angle, counts, error, [a], ["$A$"], "Rutherford",
                         formats=[".2f"], formula=r"$A / \sin^4(\phi/2)$")
        rows.append({"Angle": angle, "Counts": counts, "CountsError": error, "CountsSin4": counts * sin4,
                     "CountsSin4Error": error * sin4, "Foil": foil, "Type": "Data", **fit})
        rows.append({"Angle": curve, "Counts": models.rutherford(curve, fit["Params"][0]),
                     "Foil": f"{foil}, $A/\\sin^4(\\phi/2)$", "Type": "Model"})
    return {"GeigerMarsden": pd.DataFrame(rows)}


ELEMENTS = {
    13: "Al", 14: "Si", 17: "Cl", 19: "K", 20: "Ca", 22: "Ti", 23: "V", 24: "Cr", 25: "Mn", 26: "Fe", 27: "Co",
    28: "Ni", 29: "Cu", 30: "Zn", 39: "Y", 40: "Zr", 41: "Nb", 42: "Mo", 44: "Ru", 45: "Rh", 46: "Pd", 47: "Ag",
    50: "Sn", 51: "Sb", 57: "La", 58: "Ce", 59: "Pr", 60: "Nd", 62: "Sm", 63: "Eu", 64: "Gd", 66: "Dy",
    67: "Ho", 68: "Er", 73: "Ta", 74: "W", 76: "Os", 77: "Ir", 78: "Pt", 79: "Au",
}


def moseley():
    """F20: Moseley's law, sqrt(nu) vs atomic number.

    Source: H. G. J. Moseley, Phil. Mag. 26, 1024 (1913),
    doi:10.1080/14786441308635052 (page range unverified), and the 1914
    sequel.

    From the paper: straight lines of sqrt(nu) vs Z for the K alpha and
    L alpha series, and the gaps at Z = 43, 61 and 75. Formulas from the
    research recipe: sqrt(nu) = a (Z - 1) for K alpha with
    a = sqrt(3/4 R_inf c) = 4.967e7 Hz^1/2, and a (Z - 7.4) for L alpha with
    a = sqrt(5/36 R_inf c). The element list approximates the 1913-1914
    measurements (unverified).
    Synthetic: 0.3% scatter and errors. The stored straight-line fits are
    fitted to these values.

    Rows: ``Series`` (K alpha, L alpha and their fitted lines), ``Type``
    (Data, Fit), x ``AtomicNumber``, y ``SqrtFrequency`` in 1e8 Hz^1/2,
    ``Element`` symbols.
    """
    rng = rng_for("F20")
    rydberg = 3.2898419603e15  # R_inf c in Hz
    series = {
        r"K$\alpha$": ([z for z in ELEMENTS if z <= 47], np.sqrt(0.75 * rydberg), 1.0),
        r"L$\alpha$": ([z for z in ELEMENTS if z >= 40], np.sqrt(5 / 36 * rydberg), 7.4),
    }
    rows = []
    for name, (atomic_number, a, screening) in series.items():
        z = np.array(atomic_number, dtype=float)
        truth = a * (z - screening) / 1e8
        error = 0.003 * truth
        value = truth + rng.normal(0, error)
        fit = stored_fit(models.straight_line, z, value, error, [a / 1e8, -a * screening / 1e8],
                         ["slope", "intercept"], "Linear", formats=[".4f", ".3f"])
        rows.append({"AtomicNumber": z, "SqrtFrequency": value, "SqrtFrequencyError": error,
                     "Element": np.array([ELEMENTS[int(v)] for v in z]), "Series": name, "Type": "Data", **fit})
        # The fitted line, reaching past the axis range (Z 10-82) on both sides.
        line = np.array([0.0, 100.0])
        rows.append({"AtomicNumber": line, "SqrtFrequency": models.straight_line(line, *fit["Params"]),
                     "Series": f"{name} fit", "Type": "Fit"})
    return {"Moseley": pd.DataFrame(rows)}


def leavitt():
    """F21: Leavitt's period-luminosity relation for 25 SMC Cepheids.

    Source: H. S. Leavitt & E. C. Pickering, Harvard College Observatory
    Circular 173, 1-3 (1912).

    From the paper: 25 variables in the Small Magellanic Cloud, periods
    from about 1 to 127 days, magnitude at maximum and minimum vs log
    period, both linear. The table was not transcribed (values unverified).
    Synthetic (research fallback): m_max = -2.1 log P + 15.5 +- 0.2 and
    m_min about 1.2 mag fainter (slope illustrative, unverified). The
    stored fits are fitted to these values.

    Rows: ``Brightness`` (Maximum, Minimum and their fitted lines),
    ``Type`` (Data, Fit), x ``LogPeriod`` (also ``Period`` in days), y
    ``Magnitude``.
    """
    rng = rng_for("F21")
    log_period = np.sort(rng.uniform(0.1, 2.1, 25))
    maximum = -2.1 * log_period + 15.5 + rng.normal(0, 0.2, 25)
    minimum = maximum + 1.2 + rng.normal(0, 0.15, 25)
    rows = []
    for name, magnitude in (("Maximum", maximum), ("Minimum", minimum)):
        error = np.full(25, 0.2)
        fit = stored_fit(models.straight_line, log_period, magnitude, error, [-2, 15], ["slope", "intercept"],
                         "Linear", formats=[".2f", ".2f"])
        rows.append({"LogPeriod": log_period, "Period": 10**log_period, "Magnitude": magnitude,
                     "MagnitudeError": error, "Brightness": name, "Type": "Data", **fit})
        # The fitted line, reaching past the axis range (log P 0-2.2).
        line = np.array([-1.0, 3.0])
        rows.append({"LogPeriod": line, "Magnitude": models.straight_line(line, *fit["Params"]),
                     "Brightness": f"{name} fit", "Type": "Fit"})
    return {"Leavitt": pd.DataFrame(rows)}


MAIN_SEQUENCE = np.array([(-0.1, 0.8), (0.0, 1.3), (0.3, 2.5), (0.5, 3.4), (0.82, 4.67), (1.0, 5.5), (1.5, 7.3),
                          (2.0, 8.8), (2.5, 10.3), (3.0, 11.7), (3.5, 12.8), (4.0, 13.8), (4.6, 14.6)])
GIANT_BRANCH = np.array([(0.75, 3.7), (1.0, 3.6), (1.05, 2.5), (1.2, 1.2), (1.5, -0.4), (2.0, -1.8)])


def hertzsprung_russell(n_stars=80_000):
    """F22: Hertzsprung-Russell diagram, M_G vs BP - RP.

    Sources: H. N. Russell, Nature 93, 252 (1914); Gaia Collaboration,
    Babusiaux et al., A&A 616, A10 (2018), arXiv:1804.09378.

    From the papers: the axes (absolute G magnitude, inverted, vs BP - RP)
    and the populations: main sequence, giant branch, red clump and white
    dwarf sequence. The real diagram is a Gaia archive query (research.md).
    Synthetic: every star. A main-sequence locus through (BP-RP, M_G)
    anchors including the Sun (0.82, 4.67), 0.15 mag width and 25%
    unresolved binaries (up to 0.75 mag brighter); a giant branch from the
    subgiants to M_G = -1.8; a red clump at (1.2, 0.5); white dwarfs from
    (-0.4, 10.2) to (1.2, 15). Fractions 86/5/4/5% of 80,000 stars.

    One row with per-star arrays ``BPRP``, ``MG`` and ``Population`` (an
    index into ``PopulationNames``).
    """
    rng = rng_for("F22")
    counts = rng.multinomial(n_stars, [0.86, 0.05, 0.04, 0.05])

    n = counts[0]
    colour = np.where(rng.random(n) < 0.35, rng.normal(0.9, 0.3, n), rng.normal(2.2, 0.7, n)).clip(-0.1, 4.6)
    magnitude = np.interp(colour, *MAIN_SEQUENCE.T) + rng.normal(0, 0.15, n)
    magnitude -= np.where(rng.random(n) < 0.25, 0.75 * np.sqrt(rng.random(n)), 0)
    populations = {"Main sequence": (colour, magnitude)}

    t = rng.random(counts[1]) ** 2
    position = t * (len(GIANT_BRANCH) - 1)
    populations["Giant branch"] = (
        np.interp(position, np.arange(len(GIANT_BRANCH)), GIANT_BRANCH[:, 0]) + rng.normal(0, 0.05, counts[1]),
        np.interp(position, np.arange(len(GIANT_BRANCH)), GIANT_BRANCH[:, 1]) + rng.normal(0, 0.15, counts[1]))
    populations["Red clump"] = (rng.normal(1.2, 0.05, counts[2]), rng.normal(0.5, 0.15, counts[2]))
    t = rng.random(counts[3]) ** 0.7
    populations["White dwarfs"] = (-0.4 + 1.6 * t + rng.normal(0, 0.05, counts[3]),
                                   10.2 + 4.8 * t + rng.normal(0, 0.25, counts[3]))
    colour = np.concatenate([c for c, _ in populations.values()]).astype(np.float32)
    magnitude = np.concatenate([m for _, m in populations.values()]).astype(np.float32)
    population = np.repeat(np.arange(len(populations), dtype=np.int8), [len(c) for c, _ in populations.values()])
    return {"HRDiagram": pd.DataFrame([{"BPRP": colour, "MG": magnitude, "Population": population,
                                        "PopulationNames": list(populations), "Config": "Synthetic",
                                        "Name": "Solar neighbourhood"}])}


GENERATORS = {"F19": geiger_marsden, "F20": moseley, "F21": leavitt, "F22": hertzsprung_russell}
