import numpy as np
import pandas as pd

from plotipus.kinds import map as map_kind
from plotipus.legacy import translate


def _points():
    rng = np.random.default_rng(0)
    x = rng.normal(size=500)
    return pd.DataFrame([{"Variable": "a", "X": x, "Y": x + rng.normal(scale=0.3, size=500)}])


def _maps():
    xs, ys = np.linspace(0, 1, 30), np.linspace(0, 2, 40)
    xx, yy = np.meshgrid(xs, ys)
    rows = []
    for config, (cx, cy) in {"one": (0.4, 1.0), "two": (0.6, 1.1)}.items():
        chi2 = ((xx - cx) / 0.1) ** 2 + ((yy - cy) / 0.2) ** 2
        rows.append({"Config": config, "Name": "s", "Variable": "p", "XGrid": xs, "YGrid": ys, "ZGrid": chi2})
    return pd.DataFrame(rows)


def test_hist2d_points(make_project):
    out = make_project({"Points": _points()})
    map_kind.main(["--datafile", "Points", "-x", "X", "-y", "Y", "--diagonal", "--norm", "vertical"])
    assert [p.name for p in out.iterdir()] == ["points_x_y_hist2d.png"]


def test_integer_bins_and_normalisation():
    assert np.allclose(map_kind.integer_bin_edges(0, 2), [-0.5, 0.5, 1.5, 2.5])
    h = np.array([[1.0, 3.0], [0.0, 0.0]])
    assert np.allclose(map_kind.normalize_hist2d(h, "vertical"), [[0.25, 0.75], [0.0, 0.0]])
    assert np.isclose(map_kind.normalize_hist2d(h, "global").sum(), 1)


def test_image_mode(make_project):
    grid = _maps().iloc[:1].rename(columns={"ZGrid": "Z"})
    out = make_project({"Grid": grid})
    map_kind.main(["--datafile", "Grid", "-x", "XGrid", "-y", "YGrid", "-z", "Z", "--logz", "--output_suffix", "img.png"])
    assert len(list(out.iterdir())) == 1


def test_contours_combined_with_palette(make_project):
    out = make_project({"one_s_Maps": _maps()[:1], "two_s_Maps": _maps()[1:]})
    map_kind.main([
        "--datafile", "Maps", "--configs", "one", "two", "--names", "s", "-x", "XGrid", "-y", "YGrid",
        "-z", "ZGrid", "--contour", "--combine_op", "squared_sum", "--fill_contours", "--combined_color", "cycle",
        "--contour_smoothing_sigma", "1", "--filename_select", "fill_contours",
    ])
    names = [p.name for p in out.iterdir()]
    assert names == ["maps_one_two_s_xgrid_ygrid_zgrid_squared_sum_fill_contours_contour.png"]


def test_palette_from_style_mapping():
    from plotipus import style

    style.configure(mappings={"bands": ["red", "rgb(0,0,255)"]})
    try:
        assert map_kind.band_hues("bands", 3)[:2] == ["red", (0.0, 0.0, 1.0)]
        assert map_kind.band_hues("black", 2) == ["black", "black"]
    finally:
        style.reset()


def test_legacy_contour_translation():
    kind, argv = translate(["scripts/script_compare_contour.py", "--datafile", "M", "-x", "a", "-y", "b", "-z", "c",
                            "--operation", "squared_sum", "--combined_color", "dune"])
    assert kind == "map"
    assert argv[argv.index("--combine_op") + 1] == "squared_sum"
    assert argv[argv.index("--combined_color") + 1] == "cycle"
    assert "--contour" in argv and argv[-1] == "contour.png"
