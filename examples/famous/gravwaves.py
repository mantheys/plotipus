"""F15: GW150914 strain in the two LIGO detectors.

Sources and the "Data" recipe are in docs/design/research.md, Part 3.
"""

import numpy as np
import pandas as pd
from scipy.signal import fftconvolve

from _common import rng_for

SAMPLE_RATE = 4096.0
T_SUN = 4.925491e-6  # G M_sun / c^3 in s


def _bandpass(values, low=35.0, high=350.0):
    spectrum = np.fft.rfft(values)
    frequency = np.fft.rfftfreq(values.size, 1 / SAMPLE_RATE)
    spectrum[(frequency < low) | (frequency > high)] = 0
    return np.fft.irfft(spectrum, values.size)


def _chirp(time, t_merger, chirp_mass=30.0, f_merger=150.0, f_ring=250.0, damping=0.004):
    """Leading-order inspiral (f ~ tau^-3/8, amplitude ~ f^2/3) up to
    ``f_merger``, then a ringdown at ``f_ring`` decaying with ``damping``;
    peak amplitude 1. Returns (strain, envelope, frequency)."""
    tau = np.clip(t_merger - time, 1e-6, None)
    frequency = (5 / (256 * tau)) ** 0.375 * (chirp_mass * T_SUN) ** -0.625 / np.pi
    t_peak = time[np.argmax(frequency >= f_merger)]
    after = time >= t_peak
    frequency[after] = f_ring - (f_ring - f_merger) * np.exp(-(time[after] - t_peak) / 0.0015)
    envelope = (frequency / f_merger) ** (2 / 3)
    envelope[after] = np.exp(-(time[after] - t_peak) / damping)
    phase = 2 * np.pi * np.cumsum(frequency) / SAMPLE_RATE
    return envelope * np.cos(phase), envelope, frequency


def _scalogram(time, values, frequencies, q=6.0):
    """Normalised Morlet amplitude |W(t, f)| (rows: frequencies)."""
    out = np.empty((frequencies.size, time.size))
    for i, f in enumerate(frequencies):
        width = q / (2 * np.pi * f)
        t = np.arange(-4 * width, 4 * width, 1 / SAMPLE_RATE)
        kernel = np.exp(-0.5 * (t / width) ** 2) * np.exp(2j * np.pi * f * t)
        out[i] = np.abs(fftconvolve(values, kernel / np.abs(kernel).sum(), mode="same"))
    return out / out.max()


def gw150914():
    """F15: GW150914 whitened strain, reconstructions, residuals and
    time-frequency maps for H1 and L1.

    Source: LIGO/Virgo, PRL 116, 061102 (2016), arXiv:1602.03837, Fig. 1.

    From the paper: the layout (H1 and L1 columns; strain, reconstruction,
    residual and time-frequency rows), the 0.25-0.46 s window after
    09:50:45 UTC, the 35-350 Hz band-pass, strain in units of 1e-21, L1
    leading H1 by 6.9 ms with the H1 signal inverted, the 32-512 Hz
    log-frequency map, and the two 90% reconstructions (BBH templates,
    sine-Gaussian wavelets). The detector colours are (unverified).
    Synthetic: the waveform (leading-order chirp with a chirp mass of
    30 M_sun, merger at 150 Hz, ringdown at 250 Hz, peak strain 1e-21),
    the noise (white, band-passed, sigma 0.12e-21), and the 90% band widths.
    The real filtered series are public (LIGO DCC G1600204, GWOSC).

    Datafiles: ``GW150914`` (rows ``Detector`` x ``Component``, panels by
    ``Variable``: Whitened strain, Reconstructed, Residual; the two 90%
    bands are rows of their own (``StrainError``) so that they can be
    drawn in grey, and the numerical relativity rows also carry them as
    ``StrainTemplate+``/``-`` and ``StrainWavelet+``/``-``) and
    ``GW150914Spectrogram`` (``Name`` H1/L1, grids ``Time``,
    ``FrequencyGrid``, ``Amplitude``).
    """
    rng = rng_for("F15")
    full = np.arange(0.0, 1.0, 1 / SAMPLE_RATE)
    window = (full >= 0.25) & (full < 0.46)
    time = full[window]
    delay = 0.0069
    hanford, envelope, _ = _chirp(full, 0.425)
    shifted = -np.interp(full + delay, full, hanford)
    signals = {"H1": hanford, "L1": 0.9 * shifted}

    rows, maps = [], []
    observed = {}
    for detector, signal in signals.items():
        noise = _bandpass(rng.normal(size=full.size))
        noisy = signal + 0.12 * noise / noise.std()
        observed[detector] = noisy
        envelope_detector = envelope if detector == "H1" else np.interp(full + delay, full, envelope)
        template = 0.08 + 0.15 * envelope_detector[window]
        wavelet = 0.12 + 0.3 * envelope_detector[window]
        rows += [
            {"Time": time, "Strain": noisy[window], "Detector": detector, "Component": f"{detector} observed",
             "Variable": "Whitened strain"},
            {"Time": time, "Strain": signal[window], "Detector": detector, "Component": "Reconstructed (wavelet)",
             "Variable": "Reconstructed", "StrainError": wavelet},
            {"Time": time, "Strain": signal[window], "Detector": detector, "Component": "Reconstructed (template)",
             "Variable": "Reconstructed", "StrainError": template},
            {"Time": time, "Strain": signal[window], "Detector": detector, "Component": "Numerical relativity",
             "Variable": "Reconstructed", "StrainTemplate+": template, "StrainTemplate-": template,
             "StrainWavelet+": wavelet, "StrainWavelet-": wavelet},
            {"Time": time, "Strain": noisy[window] - signal[window], "Detector": detector, "Component": "Residual",
             "Variable": "Residual"},
        ]
        frequencies = np.geomspace(32, 512, 48)
        amplitude = _scalogram(full, noisy, frequencies)[:, window][:, ::4]
        maps.append({"Time": time[::4], "FrequencyGrid": frequencies, "Amplitude": amplitude,
                     "Config": "GW150914", "Name": detector})
    # The L1 panel also shows the H1 data shifted by 6.9 ms and inverted.
    rows.insert(6, {"Time": time, "Strain": -np.interp(full + delay, full, observed["H1"])[window], "Detector": "L1",
                    "Component": "H1 observed (shifted, inverted)", "Variable": "Whitened strain"})
    return {"GW150914": pd.DataFrame(rows), "GW150914Spectrogram": pd.DataFrame(maps)}


GENERATORS = {"F15": gw150914}
