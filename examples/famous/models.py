"""Model functions of the famous-plot datasets.

The generators use them to build the data, and the stored fits name them in
``FitFunction``, so plotipus must find them when it draws ``--fit``: this
module is listed under ``plugins`` in ``plotipus.toml`` and its ``setup``
registers it with :func:`plotipus.fits.register_module`.

Every function takes x first and then the parameters, as stored in
``Params``.
"""

import numpy as np
from scipy.special import comb, i0e, i1e, k0e, k1e

# Physical constants (CODATA 2018).
H_PLANCK = 6.62607015e-34  # J s
K_BOLTZMANN = 1.380649e-23  # J/K
C_LIGHT = 2.99792458e8  # m/s
C_KMS = 2.99792458e5  # km/s
G_KPC = 4.30091e-6  # kpc (km/s)^2 / M_sun
GEV2_TO_NB = 0.3893794e6  # (hbar c)^2 in nb GeV^2


def setup(registry):
    from plotipus import fits

    fits.register_module(__name__)


# --- F01: H -> gamma gamma ------------------------------------------------------

DIPHOTON_RANGE = (100.0, 160.0)


def diphoton_background(m, c0, c1, c2, c3, c4):
    """Fourth-order Bernstein polynomial on 100-160 GeV (events per bin)."""
    lo, hi = DIPHOTON_RANGE
    t = (np.asarray(m, dtype=float) - lo) / (hi - lo)
    coefficients = (c0, c1, c2, c3, c4)
    return sum(c * comb(4, k) * t**k * (1 - t) ** (4 - k) for k, c in enumerate(coefficients))


def diphoton_signal_plus_background(m, c0, c1, c2, c3, c4, n_signal, m_h, sigma, bin_width=2.0):
    """Bernstein background plus a Gaussian peak of ``n_signal`` events."""
    m = np.asarray(m, dtype=float)
    peak = n_signal * bin_width / (np.sqrt(2 * np.pi) * sigma) * np.exp(-0.5 * ((m - m_h) / sigma) ** 2)
    return diphoton_background(m, c0, c1, c2, c3, c4) + peak


# --- F06: CMB blackbody ---------------------------------------------------------


def planck_spectrum(wavenumber, temperature):
    """Blackbody intensity in MJy/sr at ``wavenumber`` in cm^-1."""
    nu = np.asarray(wavenumber, dtype=float) * 100 * C_LIGHT
    x = H_PLANCK * nu / (K_BOLTZMANN * temperature)
    intensity = 2 * H_PLANCK * nu**3 / C_LIGHT**2 / np.expm1(x)  # W m^-2 Hz^-1 sr^-1
    return intensity / 1e-20


# --- F08, F20, F21, F25: straight lines -------------------------------------------


def proportional(x, k):
    """y = k x (a line through the origin)."""
    return k * np.asarray(x, dtype=float)


def straight_line(x, slope, intercept):
    return slope * np.asarray(x, dtype=float) + intercept


# --- F09, F10: luminosity distance --------------------------------------------------


def distance_modulus(z, omega_m, omega_lambda, h0=65.0):
    """m - M for a Friedmann-Lemaitre universe with matter and Lambda.

    Returns NaN where the model has no big bang (E(z)^2 <= 0 below z) or
    no positive distance."""
    z = np.atleast_1d(np.asarray(z, dtype=float))
    omega_k = 1 - omega_m - omega_lambda
    grid = np.linspace(0, z.max(), 400)
    e2 = omega_m * (1 + grid) ** 3 + omega_k * (1 + grid) ** 2 + omega_lambda
    if np.any(e2 <= 0):
        return np.full_like(z, np.nan)
    inverse_e = 1 / np.sqrt(e2)
    chi = np.concatenate([[0], np.cumsum((inverse_e[1:] + inverse_e[:-1]) / 2 * np.diff(grid))])
    chi = np.interp(z, grid, chi)
    if omega_k > 1e-8:
        transverse = np.sinh(np.sqrt(omega_k) * chi) / np.sqrt(omega_k)
    elif omega_k < -1e-8:
        transverse = np.sin(np.sqrt(-omega_k) * chi) / np.sqrt(-omega_k)
    else:
        transverse = chi
    if np.any(transverse <= 0):  # recollapsed before z: no distance
        return np.full_like(z, np.nan)
    luminosity_distance = (1 + z) * C_KMS / h0 * transverse  # Mpc
    return 5 * np.log10(luminosity_distance) + 25


def distance_modulus_grid(z, omega_m, omega_lambda, h0=65.0, steps=300):
    """:func:`distance_modulus` for many cosmologies at once: rows follow the
    ``omega_m``/``omega_lambda`` arrays, columns ``z``; NaN rows have no big
    bang or no positive distance."""
    z = np.asarray(z, dtype=float)
    omega_m, omega_lambda = np.asarray(omega_m, dtype=float)[:, None], np.asarray(omega_lambda, dtype=float)[:, None]
    omega_k = 1 - omega_m - omega_lambda
    grid = np.linspace(0, z.max(), steps)
    e2 = omega_m * (1 + grid) ** 3 + omega_k * (1 + grid) ** 2 + omega_lambda
    valid = np.all(e2 > 0, axis=1)
    inverse_e = 1 / np.sqrt(np.where(e2 > 0, e2, np.nan))
    chi = np.concatenate([np.zeros((len(e2), 1)), np.cumsum((inverse_e[:, 1:] + inverse_e[:, :-1]) / 2
                                                              * np.diff(grid), axis=1)], axis=1)
    # Linear interpolation of every row at the same redshifts.
    index = np.clip(np.searchsorted(grid, z) - 1, 0, steps - 2)
    share = (z - grid[index]) / (grid[index + 1] - grid[index])
    chi = chi[:, index] * (1 - share) + chi[:, index + 1] * share
    root = np.sqrt(np.abs(omega_k))
    with np.errstate(invalid="ignore", divide="ignore"):
        transverse = np.where(omega_k > 1e-8, np.sinh(root * chi) / np.where(root > 0, root, 1),
                              np.where(omega_k < -1e-8, np.sin(root * chi) / np.where(root > 0, root, 1), chi))
        valid &= np.all(transverse > 0, axis=1)
        modulus = 5 * np.log10((1 + z) * C_KMS / h0 * transverse) + 25
    modulus[~valid] = np.nan
    return modulus


# --- F12: disk and halo rotation curves ----------------------------------------------


def exponential_disk_velocity(r, sigma0, h):
    """Freeman (1970) circular velocity of a thin exponential disk.

    V^2 = 4 pi G Sigma0 h y^2 [I0 K0 - I1 K1](y), y = R / 2h; Sigma0 in
    M_sun/kpc^2, h and R in kpc, V in km/s."""
    y = np.asarray(r, dtype=float) / (2 * h)
    # The exponentially scaled Bessel functions keep large y finite.
    bessel = i0e(y) * k0e(y) - i1e(y) * k1e(y)
    return np.sqrt(np.clip(4 * np.pi * G_KPC * sigma0 * h * y**2 * bessel, 0, None))


def isothermal_halo_velocity(r, rho0, rc):
    """Pseudo-isothermal sphere: V^2 = 4 pi G rho0 rc^2 [1 - (rc/R) atan(R/rc)]."""
    r = np.asarray(r, dtype=float)
    return np.sqrt(4 * np.pi * G_KPC * rho0 * rc**2 * (1 - rc / r * np.arctan(r / rc)))


# --- F16: reactor antineutrino survival -----------------------------------------------


def survival_probability(l_over_e, delta_m2, sin2_2theta):
    """Two-flavour survival probability at L/E in km/MeV (Delta m^2 in eV^2)."""
    return 1 - sin2_2theta * np.sin(1.267 * delta_m2 * 1e3 * np.asarray(l_over_e, dtype=float)) ** 2


# --- F17: Z lineshape -----------------------------------------------------------------


def z_lineshape(sqrt_s, m_z, gamma_z, gamma_ee, gamma_had):
    """Born-level hadronic cross section in nb (relativistic Breit-Wigner
    with s-dependent width, Phys. Rept. 427 eq. 1.40)."""
    s = np.asarray(sqrt_s, dtype=float) ** 2
    sigma0 = 12 * np.pi / m_z**2 * gamma_ee * gamma_had / gamma_z**2 * GEV2_TO_NB
    return sigma0 * s * gamma_z**2 / ((s - m_z**2) ** 2 + s**2 * gamma_z**2 / m_z**2)


def z_lineshape_isr(sqrt_s, m_z, gamma_z, gamma_ee, gamma_had):
    """:func:`z_lineshape` convolved with the leading-log initial-state
    radiation radiator H(z) = beta (1-z)^(beta-1) (1 + 3 beta / 4)."""
    sqrt_s = np.atleast_1d(np.asarray(sqrt_s, dtype=float))
    electron_mass = 0.51099895e-3
    beta = 2 / 137.036 / np.pi * (2 * np.log(sqrt_s / electron_mass) - 1)
    # u = (1-z)^beta turns the integrable singularity at z = 1 into a flat
    # integrand; the radiated fraction is cut at 1 - z = 0.75.
    u = (np.arange(4000) + 0.5) / 4000
    out = np.empty_like(sqrt_s)
    for i, (energy, b) in enumerate(zip(sqrt_s, beta)):
        x = u * 0.75**b
        z = 1 - x ** (1 / b)
        born = z_lineshape(energy * np.sqrt(z), m_z, gamma_z, gamma_ee, gamma_had)
        out[i] = (1 + 0.75 * b) * 0.75**b * born.mean()
    return out


# --- F19: Rutherford scattering ----------------------------------------------------------


def rutherford(angle_deg, a):
    """N(phi) = A / sin^4(phi / 2), phi in degrees."""
    return a / np.sin(np.radians(np.asarray(angle_deg, dtype=float)) / 2) ** 4
