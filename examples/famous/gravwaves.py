"""F15: GW150914 strain in the two LIGO detectors, from the data behind the
paper's Fig. 1.

Sources and the "Data" recipe are in docs/design/research.md, Part 3.
"""

import numpy as np
import pandas as pd
from scipy.signal import fftconvolve, hilbert

from _common import DATA

GW = DATA / "gw150914"
DELAY = 0.0069  # L1 leads H1 by 6.9 ms (PRL 116, 061102, Fig. 1 caption)


def _series(kind, detector):
    """Time (s after 09:50:45 UTC) and strain (1e-21) of a LIGO Fig. 1 file."""
    time, strain = np.loadtxt(GW / f"fig1-{kind}-{detector}.txt", unpack=True)
    return time, strain


def _scalogram(time, values, frequencies, q=6.0):
    """Normalised Morlet amplitude |W(t, f)| (rows: frequencies)."""
    rate = 1 / np.median(np.diff(time))
    out = np.empty((frequencies.size, time.size))
    for i, f in enumerate(frequencies):
        width = q / (2 * np.pi * f)
        t = np.arange(-4 * width, 4 * width, 1 / rate)
        kernel = np.exp(-0.5 * (t / width) ** 2) * np.exp(2j * np.pi * f * t)
        out[i] = np.abs(fftconvolve(values, kernel / np.abs(kernel).sum(), mode="same"))
    return out / out.max()


def gw150914():
    """F15: GW150914 whitened strain, reconstructions, residuals and
    time-frequency maps for H1 and L1 (real data).

    Source: LIGO/Virgo, PRL 116, 061102 (2016), arXiv:1602.03837, Fig. 1;
    data: the files of that figure from GWOSC (data/gw150914,
    fetch_data.py).

    Real: the 35-350 Hz filtered strain of both detectors, the numerical
    relativity waveform projected on each, and the residuals, 0.25-0.46 s
    after 09:50:45 UTC at 16384 Hz, in units of 1e-21. The L1 panel also
    shows the H1 data shifted by 6.9 ms and inverted, as in the figure.
    Ours: the time-frequency maps (a Morlet transform of the filtered strain,
    32-512 Hz; the paper's maps use the unfiltered data) and the widths of
    the two 90% reconstruction bands (BBH templates, sine-Gaussian wavelets),
    which are not among the published files: 0.08 + 0.15 and 0.12 + 0.3
    times the waveform's envelope. The detector colours are (unverified).

    Datafiles: ``GW150914`` (rows ``Detector`` x ``Component``, panels by
    ``Variable``: Whitened strain, Reconstructed, Residual; the two 90%
    bands are rows of their own (``StrainError``) so that they can be
    drawn in grey, and the numerical relativity rows also carry them as
    ``StrainTemplate+``/``-`` and ``StrainWavelet+``/``-``) and
    ``GW150914Spectrogram`` (``Name`` H1/L1, grids ``Time``,
    ``FrequencyGrid``, ``Amplitude``).
    """
    rows, maps = [], []
    observed = {}
    for detector, code in (("H1", "H"), ("L1", "L")):
        time, strain = _series("observed", code)
        observed[detector] = (time, strain)
        waveform = np.interp(time, *_series("waveform", code))
        residual = np.interp(time, *_series("residual", code))
        envelope = np.abs(hilbert(waveform))
        envelope /= envelope.max()
        template = 0.08 + 0.15 * envelope
        wavelet = 0.12 + 0.3 * envelope
        rows += [
            {"Time": time, "Strain": strain, "Detector": detector, "Component": f"{detector} observed",
             "Variable": "Whitened strain"},
            {"Time": time, "Strain": waveform, "Detector": detector, "Component": "Reconstructed (wavelet)",
             "Variable": "Reconstructed", "StrainError": wavelet, "Width": 0.0},
            {"Time": time, "Strain": waveform, "Detector": detector, "Component": "Reconstructed (template)",
             "Variable": "Reconstructed", "StrainError": template, "Width": 0.0},
            {"Time": time, "Strain": waveform, "Detector": detector, "Component": "Numerical relativity",
             "Variable": "Reconstructed", "StrainTemplate+": template, "StrainTemplate-": template,
             "StrainWavelet+": wavelet, "StrainWavelet-": wavelet},
            {"Time": time, "Strain": residual, "Detector": detector, "Component": "Residual",
             "Variable": "Residual"},
        ]
        frequencies = np.geomspace(32, 512, 48)
        maps.append({"Time": time[::16], "FrequencyGrid": frequencies,
                     "Amplitude": _scalogram(time, strain, frequencies)[:, ::16], "Config": "GW150914",
                     "Name": detector})
    # The L1 panel also shows the H1 data shifted by 6.9 ms and inverted.
    time, strain = observed["H1"]
    rows.insert(6, {"Time": time, "Strain": -np.interp(time + DELAY, time, strain), "Detector": "L1",
                    "Component": "H1 observed (shifted, inverted)", "Variable": "Whitened strain"})
    return {"GW150914": pd.DataFrame(rows), "GW150914Spectrogram": pd.DataFrame(maps)}


GENERATORS = {"F15": gw150914}
