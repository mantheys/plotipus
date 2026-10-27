"""--text/--arrow/--region (every kind) and line --direct_labels (T22.8)."""

import numpy as np
import pandas as pd
import pytest
from matplotlib.colors import to_hex
from matplotlib.patches import Polygon
from matplotlib.text import Annotation

from plotipus.annotations import parse_region
from plotipus.kinds import line


def _capture():
    from plotipus import registry

    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    return figures


@pytest.fixture
def curves():
    x = np.linspace(0, 10, 21)
    return pd.DataFrame([{"X": x, "Y": scale * x, "Model": name}
                         for name, scale in (("low", 1.0), ("mid", 1.05), ("high", 3.0))])


def _draw(make_project, frame, *argv):
    make_project({"Curves": frame})
    figures = _capture()
    line.main(["--datafile", "Curves", "-x", "X", "-y", "Y", "--hue", "Model", "--plot_type", "line", *argv])
    return figures[0].axes[0]


def test_text_in_data_coordinates_with_arrow(make_project, curves):
    ax = _draw(make_project, curves, "--text", "2", "20", "peak", "--text", "0.1", "0.9", "corner",
               "--arrow", "8", "8", "--arrow", "nan", "nan", "--text_coords", "data", "axes", "--text_color", "red")
    texts = {t.get_text(): t for t in ax.texts}
    arrow = texts["peak"]
    assert isinstance(arrow, Annotation) and arrow.xy == (8.0, 8.0) and arrow.arrow_patch is not None
    assert to_hex(arrow.get_color()) == "#ff0000"
    corner = texts["corner"]
    assert not isinstance(corner, Annotation) and corner.get_transform() == ax.transAxes


def test_region_shades_without_widening_the_axes(make_project, curves):
    ax = _draw(make_project, curves, "--rangey", "0", "30", "--region", "0,20 5,40 -5,40", "--region",
               "6,0", "9,0", "9,5", "--region_hatch", "none", "//", "--region_label", "far", "near")
    assert ax.get_ylim() == (0, 30) and ax.get_xlim()[0] > -5
    polygons = [p for p in ax.patches if isinstance(p, Polygon)]
    assert len(polygons) == 3  # two fills and one hatch layer
    assert any(p.get_hatch() == "//" for p in polygons)
    assert {"far", "near"} <= {t.get_text() for t in ax.texts}
    assert all(p.get_zorder() < 1 for p in polygons)  # under the data


def test_parse_region():
    assert parse_region(["0,0 1,0", "1,1"]).tolist() == [[0, 0], [1, 0], [1, 1]]
    with pytest.raises(ValueError):
        parse_region(["0,0", "1,1"])
    with pytest.raises(ValueError):
        parse_region(["0;0", "1,1", "2,2"])


def test_direct_labels_at_line_ends_apart(make_project, curves):
    ax = _draw(make_project, curves, "--direct_labels")
    assert ax.get_legend() is None
    labels = {t.get_text(): t for t in ax.texts if isinstance(t, Annotation)}
    assert set(labels) == {"Low", "Mid", "High"} or set(labels) == {"low", "mid", "high"}
    low, mid = (labels.get(k) or labels.get(k.lower()) for k in ("Low", "Mid"))
    assert low.xy[0] == 10 and to_hex(low.get_color()) != to_hex(mid.get_color())
    # low and mid end 0.5 apart in y: their labels are pushed at least a line apart.
    gap = abs(low.xyann[1] - mid.xyann[1] + (ax.transData.transform(low.xy)[1] - ax.transData.transform(mid.xy)[1])
              * 72 / ax.figure.dpi)
    assert gap >= 1.2 * low.get_fontsize()


def test_direct_labels_at_maximum_and_at_x(make_project):
    x = np.linspace(0, 10, 101)
    frame = pd.DataFrame([{"X": x, "Y": peak * np.exp(-((x - 5) ** 2)), "Model": name}
                          for name, peak in (("two", 35.0), ("three", 30.0))])
    ax = _draw(make_project, frame, "--direct_labels", "max")
    labels = {t.get_text().lower(): t for t in ax.texts if isinstance(t, Annotation)}
    assert np.isclose(labels["two"].xy[0], 5) and np.isclose(labels["two"].xy[1], 35)
    assert labels["two"].get_ha() == "center" and labels["two"].get_va() == "bottom"
    ax = _draw(make_project, frame, "--direct_labels", "4")
    labels = {t.get_text().lower(): t for t in ax.texts if isinstance(t, Annotation)}
    assert np.isclose(labels["three"].xy[1], 30 * np.exp(-1), rtol=1e-3)


# --- ISO dates as x coordinates ------------------------------------------------------------


def test_dates_accepted_on_a_date_axis(make_project):
    import matplotlib.dates as mdates

    days = pd.date_range("2025-07-01", periods=40, freq="D").to_numpy()
    make_project({"Daily": pd.DataFrame([{"Day": days, "Gain": np.linspace(1, 2, 40), "Channel": "A"}])})
    figures = _capture()
    line.main(["--datafile", "Daily", "-x", "Day", "-y", "Gain", "--plot_type", "line",
               "--vertical", "2025-07-10", "--vertical_band", "2025-07-15", "2025-07-25",
               "--region", "2025-07-02,1.1 2025-07-05,1.1 2025-07-05,1.3", "--text", "2025-07-20", "1.5", "drift",
               "--arrow", "2025-07-28", "1.7", "--text_coords", "data"])
    ax = figures[0].axes[0]
    day = lambda text: mdates.date2num(np.datetime64(text))  # noqa: E731
    assert any(np.allclose(l.get_xdata(), day("2025-07-10")) for l in ax.get_lines())
    band = [p for p in ax.patches if type(p).__name__ == "Rectangle" and np.isclose(p.get_x(), day("2025-07-15"))]
    assert band and np.isclose(band[0].get_x() + band[0].get_width(), day("2025-07-25"))
    region = [p for p in ax.patches if isinstance(p, Polygon)]
    assert region and np.isclose(region[0].get_xy()[0][0], day("2025-07-02"))
    (drift,) = [t for t in ax.texts if t.get_text() == "drift"]
    assert np.isclose(drift.get_position()[0], day("2025-07-20")) and np.isclose(drift.xy[0], day("2025-07-28"))


def test_parse_coordinate():
    from plotipus.args import parse_coordinate

    assert parse_coordinate("2.5") == 2.5
    assert parse_coordinate("2025-07-15") == pytest.approx(20284.0)
    assert parse_coordinate("2025-07-15T12:00") == pytest.approx(20284.5)
    with pytest.raises(Exception):
        parse_coordinate("July")


def test_bad_region_point_still_warns(capsys):
    from plotipus.annotations import parse_region

    with pytest.raises(ValueError):
        parse_region(["July,1", "1,1", "2,2"])
