import pickle

import matplotlib

matplotlib.use("Agg")

import pytest

import plotipus.project as project
from plotipus import registry, style


@pytest.fixture
def make_project(tmp_path, monkeypatch):
    """Factory: write ``{name: DataFrame}`` as pickles into a fresh project in
    ``tmp_path`` (optional extra plotipus.toml text) and make it current.
    Returns the default plot output directory."""

    def _make(frames, config=""):
        data = tmp_path / "input" / "data"
        data.mkdir(parents=True, exist_ok=True)
        (tmp_path / "plotipus.toml").write_text("[project]\n" + config)
        for name, frame in frames.items():
            with open(data / f"{name}.pkl", "wb") as handle:
                pickle.dump(frame, handle)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(project, "_PROJECT", None)
        return tmp_path / "output" / "plots"

    yield _make
    style.reset()
    for hooks in (registry.resolvers, registry.post_load_hooks, registry.post_concat_hooks,
                  registry.arguments, registry.figure_hooks):
        hooks.clear()
    registry.label_hooks.clear()
    registry.color_hooks.clear()
    registry.config_label = None
