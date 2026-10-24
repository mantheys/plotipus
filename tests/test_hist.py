import numpy as np
import pandas as pd

from plotipus.kinds import hist
from plotipus.legacy import translate

from _hcs_project import make_project


def _frame():
    rng = np.random.default_rng(1)
    return pd.DataFrame({
        "Sample": ["a", "b"],
        "Variable": ["E", "E"],
        "True": [rng.normal(10, 1, 500), rng.normal(12, 1, 500)],
        "Reco": [rng.normal(10, 1, 500), rng.normal(12, 1, 500)],
    })


def test_hist_single_and_combined(tmp_path, monkeypatch):
    out = make_project(tmp_path, monkeypatch, {"Energies": _frame()})
    hist.main(["--datafile", "Energies", "-x", "True", "--hue", "Sample", "--bins", "20"])
    hist.main(["--datafile", "Energies", "-x", "True", "Reco", "--hist_combine", "relative",
               "--hue", "Sample", "--density", "-v", "E", "--panel_vertical", "0"])
    names = sorted(p.name for p in out.glob("*.png"))
    assert names == ["energies_e_sample_relative_hist.png", "energies_sample_hist.png"], names


def test_hist_combine_values():
    class Args:
        x = ["a", "b"]
        hist_combine = "subtract"

    frame = pd.DataFrame({"a": [np.array([3.0, 5.0])], "b": [np.array([1.0, 1.0])]})
    assert np.allclose(hist.combined_values(frame, Args), [2.0, 4.0])


def test_hist_legacy_translation():
    kind, args = translate(["scripts/script_compare_hist1d.py", "--datafile", "D", "-x", "A", "-i", "C", "--labely", "Counts"])
    assert kind == "hist"
    assert "--hist_combine" in args and args[args.index("--output_suffix") + 1] == "hist1d.png"


def test_plugin_argument_and_figure_hook(tmp_path, monkeypatch):
    from plotipus import registry

    seen = []
    registry.add_argument("--stamp", type=str, default=None)
    registry.add_figure_hook(lambda fig, args: seen.append((len(fig.axes), args.stamp)))
    try:
        out = make_project(tmp_path, monkeypatch, {"Energies": _frame()})
        hist.main(["--datafile", "Energies", "-x", "True", "--hue", "Sample", "--stamp", "Preliminary"])
    finally:
        registry.arguments.clear()
        registry.figure_hooks.clear()
    assert seen == [(1, "Preliminary")]
    assert (out / "energies_sample_hist.png").is_file()


# --- Edges, range, overflow and legend (T04) ---------------------------------------------


def _capture():
    from plotipus import registry

    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    return figures


def _stairs(ax):
    from matplotlib.patches import StepPatch

    return [p for p in ax.patches if isinstance(p, StepPatch)]


def test_hist_flat_outline_spans_all_edges(make_project):
    x = np.random.default_rng(2).uniform(0, 10, 20000)
    make_project({"Flat": pd.DataFrame({"E": [x]})})
    figures = _capture()
    hist.main(["--datafile", "Flat", "-x", "E", "--bins", "10"])
    ax = figures[0].axes[0]
    (step,) = _stairs(ax)
    edges = step.get_data().edges
    assert len(edges) == 11
    assert edges[0] == x.min() and edges[-1] == x.max()
    assert np.allclose(np.diff(edges), np.diff(edges)[0])  # outer bins at full width
    assert ax.get_xlim() == (edges[0], edges[-1])
    assert step.get_data().values.sum() == len(x)
    assert ax.get_legend() is None  # no legend for a single series without --hue
    assert ax.get_legend_handles_labels()[1] == []  # and no "None" label


def test_hist_range_spans_every_hue(make_project):
    make_project({"Ev": pd.DataFrame({"Group": ["A", "B"], "X": [np.linspace(0, 1, 100), np.linspace(5, 9, 100)]})})
    figures = _capture()
    hist.main(["--datafile", "Ev", "-x", "X", "--hue", "Group", "--bins", "9"])
    ax = figures[0].axes[0]
    steps = _stairs(ax)
    assert [s.get_label() for s in steps] == ["A", "B"]
    for step in steps:
        assert np.array_equal(step.get_data().edges, steps[0].get_data().edges)  # same edges for every hue
        assert step.get_data().values.sum() == 100  # nothing clipped
    assert steps[0].get_data().edges[[0, -1]].tolist() == [0.0, 9.0]
    assert ax.get_legend() is not None
    assert [t.get_text() for t in ax.get_legend().get_texts()] == ["A", "B"]


def test_hist_flow_show_and_hint(make_project, capsys):
    x = np.array([-5.0, -1.0, 0.5, 1.5, 2.5, 3.5, 7.0, 8.0, 9.0])
    make_project({"D": pd.DataFrame({"X": [x]})})
    figures = _capture()
    hist.main(["--datafile", "D", "-x", "X", "--bins", "4", "--rangex", "0", "4"])
    hist.main(["--datafile", "D", "-x", "X", "--bins", "4", "--rangex", "0", "4", "--flow", "show"])
    hist.main(["--datafile", "D", "-x", "X", "--bins", "4", "--rangex", "0", "4", "--flow", "hint"])
    assert _stairs(figures[0].axes[0])[0].get_data().values.tolist() == [1, 1, 1, 1]
    assert _stairs(figures[1].axes[0])[0].get_data().values.tolist() == [3, 1, 1, 4]  # 2 under, 3 over
    hints = figures[2].axes[0].get_lines()
    assert sorted(line.get_marker() for line in hints) == ["<", ">"]
    assert "5 of 9 entries" in capsys.readouterr().out


def test_hist_flow_show_density_normalises_drawn_counts():
    counts, under, over = hist.histogram(np.array([-1.0, 0.5, 1.5, 3.0]), np.array([0.0, 1.0, 2.0]),
                                         density=True, flow="show")
    assert (under, over) == (1.0, 1.0)
    assert np.isclose(np.sum(counts * 1.0), 1.0) and np.allclose(counts, [0.5, 0.5])
