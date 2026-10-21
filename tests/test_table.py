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
