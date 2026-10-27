"""plotipus's sequential colour maps: ordered by lightness, the styles' default."""

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pytest

from plotipus import colormaps, style


@pytest.mark.parametrize("name, rising", [("plotipus", False), ("plotipus_r", True), ("plotipus_dark", True)])
def test_lightness_is_monotonic(name, rising):
    """CIELAB L* changes by the same step along the whole map: it reads in greyscale and for colour-vision
    deficiencies, which keep lightness."""
    rgb = matplotlib.colormaps[name](np.linspace(0, 1, 256))[:, :3]
    steps = np.diff(colormaps.srgb_to_lab(rgb)[:, 0])
    assert np.all(steps > 0) if rising else np.all(steps < 0)
    assert steps.max() - steps.min() < 0.01  # linear in L*


def test_light_end_is_a_tint_not_white():
    lab = colormaps.srgb_to_lab(matplotlib.colormaps["plotipus"](0.0)[:3])
    assert 90 < lab[0] < 99 and np.hypot(lab[1], lab[2]) > 10  # masked (white) bins stay distinguishable


def test_srgb_lab_round_trip():
    rgb = np.array([[0.25, 0.56, 0.85], [1.0, 1.0, 1.0], [0.0, 0.0, 0.0]])
    assert np.allclose(colormaps.lab_to_srgb(colormaps.srgb_to_lab(rgb)), rgb, atol=1e-6)
    assert colormaps.srgb_to_lab([1.0, 1.0, 1.0])[0] == pytest.approx(100, abs=1e-3)


def test_default_image_cmap_per_style():
    try:
        style.reset()
        assert plt.rcParams["image.cmap"] == "plotipus"
        style.apply_layers(style.name_layers("plotipus", "slides", "dark"))
        assert plt.rcParams["image.cmap"] == "plotipus_dark"
        style.restore(style.base_state())
        style.apply_layers(style.name_layers("plotipus", "slides", "light", "dune"))
        assert plt.rcParams["image.cmap"] == "cividis"  # an experiment keeps its own
    finally:
        style.reset()
