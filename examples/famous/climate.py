"""Climate figures: F13 (Keeling curve) and F14 (the MBH99 "hockey stick").

Sources and the "Data" recipes are in docs/design/research.md, Part 3.
"""

import numpy as np
import pandas as pd

from _common import rng_for

# Approximate Mauna Loa seasonal cycle, Jan-Dec, ppm (recalled, unverified).
CYCLE = np.array([0.0, 0.7, 1.4, 2.6, 3.1, 2.4, 0.8, -1.3, -3.0, -3.2, -1.9, -0.7])
CYCLE = CYCLE - CYCLE.mean()


def keeling_curve():
    """F13: Mauna Loa monthly mean CO2.

    Source: NOAA GML, Trends in Atmospheric CO2, co2_mm_mlo.csv (columns
    year, month, decimal date, average, deseasonalized, ndays, sdev, unc).

    From the data file: the span (1958-03 to 2026-09), the first value
    (315.71 ppm), the latest (426.07 ppm), and the monthly average plus
    deseasonalised series.
    Synthetic: a quadratic trend through those end points, a monthly
    seasonal cycle (about 6 ppm peak to peak, maximum in May, minimum in
    September-October; values recalled, unverified), AR(1) noise
    of 0.2 ppm and the 0.1-0.4 ppm uncertainties. No interpolated (flagged)
    months.

    Rows: ``Series`` (Monthly mean, Deseasonalized), x ``DecimalDate``,
    y ``CO2``. The monthly row also has per-month arrays ``MonthOfYear``
    and ``Detrended`` for the seasonal-cycle inset (``--binned``).
    """
    rng = rng_for("F13")
    n_months = (2026 - 1958) * 12 + 7
    month = (np.arange(n_months) + 2) % 12 + 1
    date = 1958 + (np.arange(n_months) + 2 + 0.5) / 12
    years = date - 1958
    trend = 313.35 + 0.75 * years + 0.01314 * years**2
    seasonal = np.interp(date - np.floor(date), (np.arange(14) - 0.5) / 12, np.r_[CYCLE[-1], CYCLE, CYCLE[0]])
    noise = np.zeros(n_months)
    for i in range(1, n_months):
        noise[i] = 0.6 * noise[i - 1] + rng.normal(0, 0.16)
    deseasonalized = trend + noise
    average = deseasonalized + seasonal
    uncertainty = np.clip(0.4 - 0.004 * years, 0.1, None)
    rows = [
        {"DecimalDate": date, "CO2": average, "CO2Error": uncertainty, "Series": "Monthly mean",
         "MonthOfYear": month, "Detrended": average - deseasonalized},
        {"DecimalDate": date, "CO2": deseasonalized, "Series": "Deseasonalized"},
    ]
    return {"Keeling": pd.DataFrame(rows)}


def hockey_stick():
    """F14: Northern Hemisphere temperature reconstruction, AD 1000-1980.

    Source: M. E. Mann, R. S. Bradley, M. K. Hughes, GRL 26(6), 759-762
    (1999) (DOI 10.1029/1999GL900070, unverified).

    From the paper: the span (reconstruction 1000-1980, instrumental
    1902-1998), a slow cooling then a sharp 20th-century rise, the
    uncertainty growing back in time; Fig. 3(a) and its caption: two
    standard error limits (shaded), a 40-year smoothed reconstruction, a
    linear trend over AD 1000-1850, the calibration-period (1902-1980) mean
    and the 1998 instrumental value (about +0.8 deg C).
    Synthetic: every value. Trend -0.02 - 0.00025 (t - 1000) to 1900, then
    +0.0055/yr; AR(1) noise (0.07); five volcanic dips; sigma 0.25 before
    1400, 0.2 to 1600, 0.18 to 1850, 0.12 after; an instrumental series
    with the 1998 peak. The real series is public (NOAA paleo study 6276).

    Rows: ``Series`` (Reconstruction, 40-year smoothed, Instrumental,
    Linear trend), x ``Year``, y ``Anomaly`` (deg C, relative to
    1902-1980). ``AnomalyError`` is two standard errors.
    """
    rng = rng_for("F14")
    year = np.arange(1000, 1981)
    trend = np.where(year < 1900, -0.02 - 0.00025 * (year - 1000), -0.245 + 0.0055 * (year - 1900))
    noise = np.zeros(year.size)
    for i in range(1, year.size):
        noise[i] = 0.5 * noise[i - 1] + rng.normal(0, 0.07)
    for eruption in (1258, 1453, 1600, 1815, 1883):
        noise -= 0.35 * np.exp(-np.clip(year - eruption, 0, None) / 2.0) * (year >= eruption)
    reconstruction = trend + noise
    sigma = np.select([year < 1400, year < 1600, year < 1850], [0.25, 0.2, 0.18], 0.12)
    smoothed = pd.Series(reconstruction).rolling(40, center=True, min_periods=20).mean().to_numpy()

    instrumental_year = np.arange(1902, 1999)
    instrumental = (np.where(instrumental_year < 1940, -0.25 + 0.008 * (instrumental_year - 1902),
                             np.where(instrumental_year < 1975, 0.05 - 0.002 * (instrumental_year - 1940),
                                      -0.05 + 0.02 * (instrumental_year - 1975)))
                    + 0.3 * (instrumental_year == 1998) + rng.normal(0, 0.09, instrumental_year.size))
    reference = instrumental[instrumental_year <= 1980].mean()
    early = year <= 1850
    slope, intercept = np.polyfit(year[early], reconstruction[early], 1)
    rows = [
        {"Year": year, "Anomaly": reconstruction, "AnomalyError": 2 * sigma, "Series": "Reconstruction", "Width": 0.8},
        {"Year": year, "Anomaly": smoothed, "Series": "40-year smoothed", "Width": 2.5},
        {"Year": instrumental_year, "Anomaly": instrumental - reference, "Series": "Instrumental", "Width": 0.8},
        {"Year": year[early], "Anomaly": slope * year[early] + intercept, "Series": "Linear trend", "Width": 1.5},
    ]
    return {"HockeyStick": pd.DataFrame(rows)}


GENERATORS = {"F13": keeling_curve, "F14": hockey_stick}
