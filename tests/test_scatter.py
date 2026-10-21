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
