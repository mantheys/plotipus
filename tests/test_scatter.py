import numpy as np
import pandas as pd

from plotipus.kinds import scatter
from plotipus.legacy import translate

from _hcs_project import make_project


def _paired():
    rows = []
    for name, base in (("a", 90.0), ("b", 95.0)):
        for variable in ("Purity", "Completeness"):
            rows.append({"Name": name, "Variable": variable, "Values": np.arange(3.0),
                         "Counts": base + np.arange(3.0), "CountsError": np.ones(3)})
    return pd.DataFrame(rows)


def _points():
    return pd.DataFrame({"X": [[0.0, 1.0, 2.0]], "Y": [[1.0, 2.0, 3.0]], "Z": [[3.0, 2.0, 1.0]],
                         "E": [[1.0, 5.0, 10.0]], "PDG": [[11, 22, 11]]})


def test_scatter_paired(tmp_path, monkeypatch):
    out = make_project(tmp_path, monkeypatch, {"a_Eff": _paired()[lambda d: d.Name == "a"], "b_Eff": _paired()[lambda d: d.Name == "b"]})
    scatter.main(["--datafile", "Eff", "--names", "a", "b", "--x_from", "Variable=Purity",
                  "--y_from", "Variable=Completeness", "-x", "Values", "-y", "Counts", "--connect"])
    assert [p.name for p in out.glob("*.png")] == ["eff_a_b_values_counts_purity_vs_completeness_scatter.png"]


def test_scatter_points(tmp_path, monkeypatch):
    out = make_project(tmp_path, monkeypatch, {"Event": _points()})
    scatter.main(["--datafile", "Event", "-x", "X", "-y", "Y", "-z", "Z", "--hue", "PDG", "--sizeby", "E"])
    scatter.main(["--datafile", "Event", "-x", "X", "-y", "Y", "--colorby", "E", "--output_suffix", "c.png"])
    assert len(list(out.glob("*.png"))) == 2


def test_weighted_mean():
    value, error = scatter._weighted_mean(np.array([1.0, 3.0]), np.array([1.0, 1.0]))
    assert value == 2.0 and np.isclose(error, 1 / np.sqrt(2))


def test_scatter_legacy_translation():
    kind, args = translate(["scripts/script_compare_pareto.py", "--datafile", "D", "-v", "P", "C"])
    assert kind == "scatter" and args[args.index("--output_suffix") + 1] == "P_vs_C_pareto.png"


def test_points_of_the_selected_row_only_drawn_columns(make_project):
    """Array columns of other lengths (e.g. a histogram next to the samples) do not stop the explode,
    and --select picks the row before the first row per Config/Name is kept."""
    from plotipus import registry
    from plotipus.kinds import scatter

    frame = pd.DataFrame([
        {"Kind": "a", "X": np.arange(5.0), "Y": np.arange(5.0), "Hist": np.ones(3)},
        {"Kind": "b", "X": np.arange(7.0), "Y": -np.arange(7.0), "Hist": np.ones(2)},
    ])
    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    make_project({"Points": frame})
    scatter.main(["--datafile", "Points", "-x", "X", "-y", "Y", "--select", "Kind", "-s", "b"])
    offsets = np.vstack([c.get_offsets() for c in figures[-1].axes[0].collections if len(c.get_offsets())])
    assert len(offsets) == 7 and (offsets[:, 1] <= 0).all()


# --- --hue keeps every group (T05) -------------------------------------------------------


def _groups():
    rng = np.random.default_rng(3)
    return pd.DataFrame({"Group": ["A", "B", "C"], "Variable": "Ev",
                         "Xv": [rng.normal(m, 1, 50) for m in (0, 1, 2)],
                         "Yv": [rng.normal(m, 1, 50) for m in (0, 1, 2)]})


def _point_collections(ax):
    return [c for c in ax.collections if len(c.get_offsets())]


def test_scatter_hue_draws_every_group(make_project, capsys):
    from matplotlib.colors import to_hex

    from plotipus import registry

    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    make_project({"Ev": _groups()})
    scatter.main(["--datafile", "Ev", "-x", "Xv", "-y", "Yv", "--hue", "Group", "--marker_size", "2"])
    ax = figures[0].axes[0]
    collections = _point_collections(ax)
    assert len(collections) == 3 and all(len(c.get_offsets()) == 50 for c in collections)
    assert len({to_hex(c.get_facecolor()[0]) for c in collections}) == 3
    assert [t.get_text() for t in ax.get_legend().get_texts()] == ["A", "B", "C"]
    assert "--markerby not set" not in capsys.readouterr().out


def test_scatter_without_hue_keeps_first_row_and_warns(make_project, capsys):
    from plotipus import registry

    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    make_project({"Ev": _groups()})
    scatter.main(["--datafile", "Ev", "-x", "Xv", "-y", "Yv"])
    offsets = np.vstack([c.get_offsets() for c in _point_collections(figures[0].axes[0])])
    assert np.allclose(offsets[:, 0], _groups()["Xv"][0])  # the first row only
    out = " ".join(capsys.readouterr().out.split())
    assert "--markerby not set" in out and "differ in Group" in out


def test_explode_points_per_point_hue_is_not_a_row_key():
    frame = pd.DataFrame({"X": [[0.0, 1.0], [2.0]], "PDG": [[11, 22], [13]]})
    exploded = scatter.explode_points(frame, columns=["X", "PDG"], hue="PDG")
    assert exploded["PDG"].tolist() == [11, 22]  # one row kept, its per-point hue kept as a column


def test_size_legend_shows_round_plain_numbers():
    levels, labels = scatter._size_levels(5.0, 337.0, 4)
    assert labels == ["100", "200", "300"]
    assert list(levels) == [100.0, 200.0, 300.0]
    _, labels = scatter._size_levels(0.013, 0.087, 4)
    assert labels == ["0.02", "0.04", "0.06", "0.08"]
    assert all("e" not in label for label in labels)
