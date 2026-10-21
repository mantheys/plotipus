"""Temporary plotipus project for the hist/cat/scatter tests."""

import pickle

import matplotlib

matplotlib.use("Agg")

import plotipus.project as project


def make_project(tmp_path, monkeypatch, frames):
    """Write ``frames`` ({name: DataFrame}) as pickles into a fresh project
    in ``tmp_path`` and make it the current one."""
    data = tmp_path / "input" / "data"
    data.mkdir(parents=True)
    (tmp_path / "plotipus.toml").write_text("[project]\n")
    for name, frame in frames.items():
        with open(data / f"{name}.pkl", "wb") as handle:
            pickle.dump(frame, handle)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(project, "_PROJECT", None)
    return tmp_path / "output" / "plots"
