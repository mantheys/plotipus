import pickle

import numpy as np
import pandas as pd
import pytest

from plotipus import project, registry
from plotipus.kinds import table


@pytest.fixture
def tmp_project(tmp_path, monkeypatch):
    (tmp_path / "plotipus.toml").write_text('[project]\ndata_root = "data"\n')
    (tmp_path / "data").mkdir()
    monkeypatch.chdir(tmp_path)
    project.load_project(reload=True)
    yield tmp_path
    project.set_project(None)


def write(tmp, name, frame):
    with open(tmp / "data" / f"{name}.pkl", "wb") as handle:
        pickle.dump(frame, handle)


def frame():
    rows = []
    for config in ("hd_a", "vd_b"):
        for variable, value in (("Purity", [0.9, 0.8]), ("Completeness", [0.5, 0.7])):
            rows.append({"Config": config, "Name": "sig", "Variable": variable,
                         "Values": np.array(value), "ValuesError": np.array([0.01, 0.02])})
    return pd.DataFrame(rows)


def run(tmp, *argv):
    table.main(["-o", str(tmp / "out"), *argv])
    return sorted((tmp / "out").iterdir())


def test_mean_with_error(tmp_project):
    for config in ("hd_a", "vd_b"):
        write(tmp_project, f"{config}_sig_Eff", frame()[lambda d: d.Config == config])
    files = run(tmp_project, "--datafile", "Eff", "--configs", "hd_a", "vd_b", "--names", "sig",
                "-y", "Values", "--variables", "Purity", "Completeness", "--html")
    names = [f.name for f in files]
    assert names == ["eff_hd_a_vd_b_sig_values_purity_completeness_mean_table.html",
                     "eff_hd_a_vd_b_sig_values_purity_completeness_mean_table.tex"]
    text = files[1].read_text()
    assert "0.85 ± 0.01" in text and "0.60 ± 0.01" in text
    assert "\\begin{tabular}" in text and "Purity" in text


def test_row_group_and_agg_sum(tmp_project):
    write(tmp_project, "hd_a_sig_Eff", frame()[lambda d: d.Config == "hd_a"])
    files = run(tmp_project, "--datafile", "Eff", "--configs", "hd_a", "--names", "sig", "-y", "Values",
                "--variables", "Purity", "--agg", "sum", "--no_error", "--bare",
                "--derive_column", "Geometry=prefix:Config:upper", "--row_group", "Geometry")
    text = files[0].read_text()
    assert files[0].name.endswith("_sum_table_tabular.tex")
    assert "HD" in text and "1.70" in text and "\\begin{table" not in text


def test_add_column_hook(tmp_project):
    write(tmp_project, "hd_a_sig_Eff", frame()[lambda d: d.Config == "hd_a"])

    def doubled(df, args, column):
        df[column] = df["Values"].map(lambda v: np.asarray(v) * 2)
        return df

    registry.table_columns["doubled"] = doubled
    try:
        files = run(tmp_project, "--datafile", "Eff", "--configs", "hd_a", "--names", "sig", "-y", "Twice",
                    "--variables", "Purity", "--add_column", "doubled=Twice", "--output_name", "t.tex")
    finally:
        registry.table_columns.pop("doubled")
    assert files[0].name == "t.tex"
    assert "1.70" in files[0].read_text()


def test_legacy_translation():
    tokens = table.LEGACY["script_aggregate_table"](["--operation", "sum", "--note", "x", "-y", "V"])
    assert tokens[:2] == ["--agg", "sum"] and "--note" not in tokens
    assert "--row_group" in tokens


def test_clopper_pearson(tmp_project):
    # Percent efficiencies with their pass counts: 100% must not print a symmetric error past the bound.
    rows = [{"Config": "hd_a", "Name": "sig", "Variable": variable, "Values": np.array([50, 100]),
             "Counts": np.array([passed, passed]), "Efficiency": np.array([100 * passed / total] * 2),
             "EfficiencyError": np.array([1.0, 1.0])}
            for variable, passed, total in (("Z", 12974, 12974), ("X", 9140, 10739))]
    write(tmp_project, "hd_a_sig_Eff", pd.DataFrame(rows))
    files = run(tmp_project, "--datafile", "Eff", "--configs", "hd_a", "--names", "sig", "-x", "Values",
                "--rangex", "90", "110", "-y", "Efficiency", "--variables", "X", "Z", "--bare",
                "--clopper_pearson", "Counts")
    text = files[0].read_text()
    assert "$100.00^{+0.00}_{-0.01}$" in text
    assert "$85.1^{+0.3}_{-0.4}$" in text and "±" not in text


# --- T22.11: statistics and fit-parameter tables ------------------------------------------


def _anscombe():
    x = np.array([10.0, 8, 13, 9, 11, 14, 6, 4, 12, 7, 5])
    y1 = np.array([8.04, 6.95, 7.58, 8.81, 8.33, 9.96, 7.24, 4.26, 10.84, 4.82, 5.68])
    y2 = np.array([9.14, 8.14, 8.74, 8.77, 9.26, 8.10, 6.13, 3.10, 9.13, 7.26, 4.74])
    return pd.DataFrame([
        {"X": x, "Y": y1, "Dataset": "I", "Params": [0.5, 3.0], "ParamsError": [0.118, 1.12],
         "ParamsLabel": ["slope", "intercept"], "ParamsFormat": [".3f", ".2f"]},
        {"X": x, "Y": y2, "Dataset": "II", "Params": [0.5, 3.0], "ParamsError": [0.118, 1.13],
         "ParamsLabel": ["slope", "intercept"], "ParamsFormat": [".3f", ".2f"]},
    ])


def test_stats_table_of_arrays(tmp_project, capsys):
    write(tmp_project, "Anscombe", _anscombe())
    name = table.main(["--datafile", "Anscombe", "-x", "X", "-y", "Y", "--row_name", "Dataset",
                       "--stats", "mean", "var", "corr", "line", "n", "--table_env", "none"])
    out = capsys.readouterr().out
    assert "Mean X" in out and "Var Y" in out and "Corr" in out
    text = next(tmp_project.rglob("*stats*tabular.tex")).read_text()
    assert "I & 9.00 & 7.50 & 11.00 & 4.13 & 0.82 & $Y = 0.50\\,X + 3.00$ & 11" in text
    assert "II & 9.00 & 7.50 & 11.00 & 4.13 & 0.82" in text


def test_fit_params_table(tmp_project):
    write(tmp_project, "Anscombe", _anscombe())
    table.main(["--datafile", "Anscombe", "-y", "Y", "--row_name", "Dataset", "--fit_params", "--table_env", "none"])
    text = next(tmp_project.rglob("*fit_params*tabular.tex")).read_text()
    assert "slope & intercept" in text
    assert "I & $0.500 \\pm 0.118$ & $3.00 \\pm 1.12$" in text


def test_agg_median(tmp_project):
    rows = [{"Config": "a", "Name": "n", "Variable": "V", "Value": v, "ValueError": 0.1} for v in (1.0, 2.0, 10.0)]
    write(tmp_project, "Agg", pd.DataFrame(rows))
    table.main(["--datafile", "Agg", "-y", "Value", "--variables", "V", "--agg", "median", "--no_error",
                "--table_env", "none"])
    text = next(tmp_project.rglob("*median*tabular.tex")).read_text()
    assert "2.00" in text


# --- Cut flow (T22.11) ----------------------------------------------------------------


def _cutflow():
    """Two samples through three nested stages: counts per bin, with Poisson errors for the signal only."""
    rows = []
    for sample, counts in (("signal", ([60, 40], [50, 30], [30, 15])), ("background", ([500, 500], [200, 100], [20, 5]))):
        for stage, values in zip(("Trigger", "Isolation", "Final"), counts):
            row = {"Sample": sample, "Stage": stage, "Counts": np.array(values, dtype=float)}
            if sample == "signal":
                row["CountsError"] = np.sqrt(np.array(values, dtype=float))
            rows.append(row)
    return pd.DataFrame(rows)


def test_cutflow_events_and_efficiencies(tmp_project):
    """J5: one row per stage; per sample the events with their error, and the efficiencies relative to
    the previous stage and to the first, as Clopper-Pearson intervals of the counts in percent."""
    from plotipus.intervals import clopper_pearson

    write(tmp_project, "Yields", _cutflow())
    table.main(["--datafile", "Yields", "-y", "Counts", "--hue", "Sample", "--variable_name", "Stage", "--cutflow",
                "--table_env", "none"])
    text = next(tmp_project.rglob("*cutflow*tabular.tex")).read_text()
    lines = text.splitlines()
    assert "\\multicolumn{3}{c}{signal} & \\multicolumn{3}{c}{background}" in text
    assert "Events & Rel. eff. (\\%) & Cum. eff. (\\%)" in text  # the percent sign escaped for LaTeX
    trigger, isolation, final = (next(l for l in lines if l.startswith(s)) for s in ("Trigger", "Isolation", "Final"))
    assert "100 ± 10" in trigger and trigger.count("---") == 4  # no efficiency for the first stage
    # Signal, final stage: 45 of 80 (relative), 45 of 100 (cumulative).
    from plotipus.format import format_with_interval

    low, high = clopper_pearson(45, 80)
    assert format_with_interval(56.25, 100 * low, 100 * high) == final.split(" & ")[2]
    low, high = clopper_pearson(45, 100)
    assert format_with_interval(45.0, 100 * low, 100 * high) == final.split(" & ")[3]
    # Background has no error column: the Garwood interval of its integer counts.
    assert "$300^{+" in isolation


def test_cutflow_stage_order_and_one_sample(tmp_project):
    """--variables picks and orders the stages; without --hue the columns have one level."""
    write(tmp_project, "Yields", _cutflow()[lambda d: d.Sample == "signal"])
    table.main(["--datafile", "Yields", "-y", "Counts", "--variable_name", "Stage", "--variables", "Trigger", "Final",
                "--cutflow", "--table_env", "none"])
    text = next(tmp_project.rglob("*cutflow*tabular.tex")).read_text()
    rows = [l.split(" & ")[0] for l in text.splitlines() if " & " in l]
    assert rows == ["Stage", "Trigger", "Final"]
    assert "\\multicolumn" not in text
    from plotipus.format import format_with_interval
    from plotipus.intervals import clopper_pearson

    low, high = clopper_pearson(45, 100)
    final = next(l for l in text.splitlines() if l.startswith("Final"))
    assert final.split(" & ")[2] == format_with_interval(45.0, 100 * low, 100 * high)  # relative to Trigger


def test_cutflow_non_integer_yields_warn_and_use_binomial_errors(tmp_project, capsys):
    frame = _cutflow()
    frame["Counts"] = frame["Counts"].map(lambda a: a * 0.5 + 0.25)
    write(tmp_project, "Yields", frame)
    table.main(["--datafile", "Yields", "-y", "Counts", "--hue", "Sample", "--variable_name", "Stage", "--cutflow",
                "--table_env", "none"])
    assert "not integer counts" in capsys.readouterr().out
