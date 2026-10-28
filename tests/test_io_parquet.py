import argparse
import pickle

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("pyarrow")

import plotipus
from plotipus.io import import_data, read_frame, write_parquet_frame
from plotipus.legacy import kind_module


def ns(**kwargs):
    defaults = dict(datafile=None, path=None, configs=None, names=None, variables=None, select=None,
                    save_values=None, remove_value=None, iterable=None, debug=False)
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def spectra():
    x = np.arange(0.5, 10, 1.0)
    return pd.DataFrame([
        {"Energy": x, "Counts": 100 * np.exp(-x / s), "Sample": name, "Weight": w, "Variable": "Energy"}
        for name, s, w in (("signal", 3.0, 1.0), ("background", 6.0, 0.5))
    ])


def test_round_trip_keeps_arrays_scalars_and_2d_cells(tmp_path):
    frame = spectra()
    frame["Grid"] = [np.arange(6.0).reshape(2, 3), np.ones((4, 2))]
    path = tmp_path / "Spectra.parquet"
    write_parquet_frame(frame, path)
    loaded = read_frame(path)

    assert list(loaded["Sample"]) == ["signal", "background"]
    assert loaded["Weight"].tolist() == [1.0, 0.5]
    for got, want in zip(loaded["Counts"], frame["Counts"]):
        assert isinstance(got, np.ndarray) and got.dtype == float
        np.testing.assert_allclose(got, want)
    assert loaded["Grid"][0].shape == (2, 3) and loaded["Grid"][1].shape == (4, 2)
    np.testing.assert_array_equal(loaded["Grid"][0], frame["Grid"][0])
    # the writer does not touch the caller's frame
    assert frame["Grid"][0].shape == (2, 3)


def test_datafile_found_as_parquet(make_project):
    make_project({})
    write_parquet_frame(spectra(), "input/data/Spectra.parquet")
    df = import_data(ns(datafile=["Spectra"]))
    assert len(df) == 2
    assert df["_Source"].iloc[0].endswith("Spectra.parquet")
    assert len(import_data(ns(datafile=["input/data/Spectra.parquet"]))) == 2


def test_pickle_wins_over_parquet_of_the_same_name(make_project):
    make_project({"Spectra": spectra().iloc[:1]})
    write_parquet_frame(spectra(), "input/data/Spectra.parquet")
    assert len(import_data(ns(datafile=["Spectra"]))) == 1


def test_config_name_files_as_parquet(make_project):
    make_project({})
    for config in ("small", "large"):
        write_parquet_frame(spectra().assign(Config=config), f"input/data/{config}_signal_Spectra.parquet")
    df = import_data(ns(datafile=["Spectra"], configs=["small", "large"], names=["signal"]))
    assert sorted(df["Config"].unique()) == ["large", "small"]


@pytest.mark.parametrize("kind, frame, argv", [
    ("line", spectra(), ["-x", "Energy", "-y", "Counts", "--hue", "Sample"]),
    ("map", pd.DataFrame([{"XGrid": np.linspace(0, 1, 5), "YGrid": np.linspace(0, 2, 4),
                           "ZGrid": np.add.outer(np.linspace(0, 2, 4), np.linspace(0, 1, 5)), "Variable": "Map"}]),
     ["-x", "XGrid", "-y", "YGrid", "-z", "ZGrid"]),
])
def test_figure_from_parquet_matches_pickle(make_project, kind, frame, argv):
    out = make_project({"Data": frame})
    (name,) = kind_module(kind).main(["--datafile", "Data", *argv])
    from_pickle = (out / name).read_bytes()
    (out / name).unlink()
    (out.parent.parent / "input" / "data" / "Data.pkl").unlink()
    write_parquet_frame(frame, "input/data/Data.parquet")
    assert kind_module(kind).main(["--datafile", "Data", *argv]) == [name]
    assert (out / name).read_bytes() == from_pickle


def test_load_frame_reads_both_formats(tmp_path):
    frame = spectra()
    with open(tmp_path / "a.pkl", "wb") as handle:
        pickle.dump(frame, handle)
    plotipus.save_frame(frame, tmp_path / "a.parquet")
    for name in ("a.pkl", "a.parquet"):
        np.testing.assert_allclose(plotipus.load_frame(tmp_path / name)["Counts"][1], frame["Counts"][1])
