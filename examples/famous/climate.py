"""Climate figures: F13 (Keeling curve) and F14 (the MBH99 "hockey stick"), both
from NOAA's public records.

Sources and the "Data" recipes are in docs/design/research.md, Part 3.
"""

import numpy as np
import pandas as pd

from _common import DATA


def keeling_curve():
    """F13: Mauna Loa monthly mean CO2 (real data).

    Source: NOAA GML, Trends in Atmospheric CO2, co2_mm_mlo.csv (Dr. Xin Lan,
    NOAA/GML, and Dr. Ralph Keeling, Scripps Institution of Oceanography).

    Real: the monthly averages and deseasonalised values from March 1958
    (data/co2_mm_mlo.csv, fetch_data.py), with the monthly uncertainty where
    NOAA gives one (``unc`` < 0 marks months without it, which are kept).

    Rows: ``Series`` (Monthly mean, Deseasonalized), x ``DecimalDate``,
    y ``CO2``. The monthly row also has per-month arrays ``MonthOfYear``
    and ``Detrended`` (average - deseasonalised) for the seasonal cycle.
    """
    table = pd.read_csv(DATA / "co2_mm_mlo.csv", comment="#")
    date, average, deseasonalized = (table[c].to_numpy() for c in ("decimal date", "average", "deseasonalized"))
    uncertainty = table["unc"].to_numpy(dtype=float, copy=True)
    uncertainty[uncertainty < 0] = np.nan
    rows = [
        {"DecimalDate": date, "CO2": average, "CO2Error": uncertainty, "Series": "Monthly mean",
         "MonthOfYear": table["month"].to_numpy(), "Detrended": average - deseasonalized},
        {"DecimalDate": date, "CO2": deseasonalized, "Series": "Deseasonalized"},
    ]
    return {"Keeling": pd.DataFrame(rows)}


def hockey_stick():
    """F14: Northern Hemisphere temperature reconstruction, AD 1000-1980 (real data).

    Source: M. E. Mann, R. S. Bradley, M. K. Hughes, GRL 26(6), 759-762
    (1999) (DOI 10.1029/1999GL900070, unverified); data: NOAA NCEI
    Paleoclimatology, mann99-nhem-noaa.txt.

    Real (data/mann99-nhem-noaa.txt, fetch_data.py): the annual
    reconstruction 1000-1980, its two standard errors, and the instrumental
    record 1902-1998 (anomalies from the 1902-1980 mean; +0.78 deg C in
    1998), as in Fig. 3(a) and its caption.
    Ours: the 40-year running mean and the linear trend over 1000-1850.

    Rows: ``Series`` (Reconstruction, 40-year smoothed, Instrumental,
    Linear trend), x ``Year``, y ``Anomaly`` (deg C). ``AnomalyError`` is
    two standard errors.
    """
    table = pd.read_csv(DATA / "mann99-nhem-noaa.txt", sep="\t", comment="#", na_values=[-999])
    reconstructed = table.dropna(subset=["nhem_recon"])
    instrumental = table.dropna(subset=["nhem_raw"])
    year = reconstructed["age_CE"].to_numpy()
    reconstruction = reconstructed["nhem_recon"].to_numpy()
    smoothed = pd.Series(reconstruction).rolling(40, center=True, min_periods=20).mean().to_numpy()
    early = year <= 1850
    slope, intercept = np.polyfit(year[early], reconstruction[early], 1)
    rows = [
        {"Year": year, "Anomaly": reconstruction, "AnomalyError": reconstructed["nhem_2se"].to_numpy(),
         "Series": "Reconstruction", "Width": 0.8},
        {"Year": year, "Anomaly": smoothed, "Series": "40-year smoothed", "Width": 2.5},
        {"Year": instrumental["age_CE"].to_numpy(), "Anomaly": instrumental["nhem_raw"].to_numpy(),
         "Series": "Instrumental", "Width": 0.8},
        {"Year": year[early], "Anomaly": slope * year[early] + intercept, "Series": "Linear trend", "Width": 1.5},
    ]
    return {"HockeyStick": pd.DataFrame(rows)}


GENERATORS = {"F13": keeling_curve, "F14": hockey_stick}
