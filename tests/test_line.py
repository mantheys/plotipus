import numpy as np
import pandas as pd
import pytest

from plotipus.kinds import line
from plotipus.legacy import translate


@pytest.fixture
def spectra():
    x = np.arange(0.5, 10, 1.0)
    rows = []
    for sample, scale in (("A", 1.0), ("B", 2.0), ("C", 0.5)):
        for stage in ("Raw", "Smooth"):
            rows.append({"Energy": x, "Counts": scale * np.exp(-x / 3), "CountsError": 0.1 * np.ones_like(x),
                         "Sample": sample, "Stage": stage, "Variable": "E", "Significance": scale * np.ones_like(x)})
    return pd.DataFrame(rows)


def run(make_project, frame, *argv):
    out = make_project({"Spectra": frame})
    outputs = line.main(["--datafile", "Spectra", "-x", "Energy", "-y", "Counts", *argv])
    return out, outputs


def test_hue_and_style(make_project, spectra):
    out, outputs = run(make_project, spectra, "--hue", "Sample", "--style", "Stage", "--plot_type", "step")
    assert outputs == ["spectra_energy_counts_sample_line.png"]
    assert (out / outputs[0]).exists()


def test_lower_ratio_and_column(make_project, spectra):
    out, outputs = run(make_project, spectra, "--hue", "Sample", "--select", "Stage", "-s", "Raw",
                       "--lower", "ratio", "--lower", "column:Significance", "--plot_type", "line")
    assert len(outputs) == 1 and (out / outputs[0]).exists()
    assert "ratio" in outputs[0]


def test_group_significance(make_project, spectra):
    out, outputs = run(make_project, spectra, "--hue", "Sample", "--select", "Stage", "-s", "Raw", "--lower", "group",
                       "--reference_group", "A", "--other_group", "B", "C", "--group_significance", "--stacked")
    assert outputs[0].endswith("stacked_line.png")


def test_sum_and_merge(make_project, spectra):
    out, outputs = run(make_project, spectra, "--hue", "Sample", "--select", "Stage", "-s", "Raw",
                       "--sum_iterables", "B", "C", "--sum_label", "Background", "--plot_type", "line")
    assert (out / outputs[0]).exists()
    out, outputs = run(make_project, spectra, "--hue", "Sample", "--merge_iterables", "B,C=BC", "--plot_type", "line",
                       "--output_suffix", "merged")
    assert outputs[0].endswith("merged.png")


def test_by_config(make_project):
    x = np.arange(5.0)
    frame = pd.DataFrame([{"Values": x, "Counts": x * k, "Config": c, "Name": "n"} for k, c in ((1, "a"), (2, "b"))])
    out = make_project({"a_n_Spec": frame[frame.Config == "a"], "b_n_Spec": frame[frame.Config == "b"]})
    outputs = line.main(["--datafile", "Spec", "--configs", "a", "b", "--names", "n", "-x", "Values", "-y", "Counts",
                         "--by_config", "--combine_op", "sum"])
    assert (out / outputs[0]).exists()


def test_legacy_line_operation_translation(make_project):
    make_project({})
    kind, args = translate(["scripts/script_compare_line_operation.py", "--datafile", "D", "-x", "E", "-y", "C",
                            "-i", "H", "--lower_series_data", "S", "--bottom_labely", "Sig", "--stacked"])
    assert kind == "line"
    assert args[args.index("--lower") + 1] == "column:S"
    assert "--lower_labely" in args and "--plot_type" not in args
    assert args[args.index("--output_suffix") + 1] == "stacked_line_operation.png"
