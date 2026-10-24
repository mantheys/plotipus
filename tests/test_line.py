import numpy as np
import pandas as pd
import pytest
from matplotlib.colors import to_hex
from matplotlib.legend import Legend

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


# --- Colours (T01) -------------------------------------------------------------------


def _capture():
    from plotipus import registry

    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    return figures


def _line_colors(ax):
    return {line.get_label(): (to_hex(line.get_color()), line.get_linestyle())
            for line in ax.get_lines() if not line.get_label().startswith("_")}


def test_by_config_distinct_colours_and_config_color(make_project, tmp_path):
    x = np.arange(0.5, 10, 1.0)
    frames = {f"{c}_signal_Efficiency": pd.DataFrame([{"Values": x, "Efficiency": k * np.ones_like(x), "Config": c,
                                                       "Name": "signal"}])
              for k, c in ((80, "small"), (90, "large"))}
    (tmp_path / "style.json").write_text('{"mappings": {"config_color": {"small": "C3", "large": "C4"}}}')
    make_project(frames, 'style = ["style.json"]\n')
    figures = _capture()
    line.main(["--datafile", "Efficiency", "--configs", "small", "large", "--names", "signal", "-x", "Values",
               "-y", "Efficiency", "--by_config", "--plot_type", "line", "--combine_op", "mean",
               "--combined_label", "Average"])
    colors = [to_hex(l.get_color()) for l in figures[0].axes[0].get_lines() if not l.get_label().startswith("_")]
    assert len(colors) == 3 and len(set(colors)) == 3
    assert colors[:2] == [to_hex("C3"), to_hex("C4")]


def test_many_hues_repeat_colours_with_a_warning(make_project, capsys):
    x = np.linspace(0, 10, 20)
    frame = pd.DataFrame([{"X": x, "Y": np.sin(x + i), "Run": f"run{i:02d}"} for i in range(12)])
    make_project({"ManyHue": frame})
    figures = _capture()
    line.main(["--datafile", "ManyHue", "-x", "X", "-y", "Y", "--hue", "Run", "--plot_type", "line"])
    pairs = _line_colors(figures[0].axes[0])
    assert len(pairs) == 12 and len({color for color, _ in pairs.values()}) == 10
    assert pairs["run10"] == pairs["run00"]
    assert {linestyle for _, linestyle in pairs.values()} == {"-"}
    assert capsys.readouterr().out.count("More categories") == 1


def test_palette_option(make_project, spectra):
    figures = _capture()
    run(make_project, spectra, "--hue", "Sample", "--select", "Stage", "-s", "Raw", "--plot_type", "line",
        "--palette", "okabe-ito")
    assert to_hex(figures[0].axes[0].get_lines()[0].get_color()) == "#e69f00"


def test_mapped_colour_not_reused(make_project, spectra, tmp_path):
    (tmp_path / "style.json").write_text('{"mappings": {"samples": {"C": "C0"}}}')
    out = make_project({"Spectra": spectra}, 'style = ["style.json"]\n')
    figures = _capture()
    line.main(["--datafile", "Spectra", "-x", "Energy", "-y", "Counts", "--hue", "Sample", "--select", "Stage",
               "-s", "Raw", "--plot_type", "line", "--hue_color_mapping", "samples"])
    colors = _line_colors(figures[0].axes[0])
    assert colors["C"][0] == to_hex("C0")
    assert to_hex("C0") not in {colors["A"][0], colors["B"][0]}


def test_same_colour_in_upper_and_lower_panels(make_project, spectra):
    figures = _capture()
    run(make_project, spectra, "--hue", "Sample", "--select", "Stage", "-s", "Raw", "--plot_type", "line",
        "--lower", "column:Significance")
    upper, lower = figures[0].axes[:2]
    upper_colors = [to_hex(l.get_color()) for l in upper.get_lines() if not l.get_label().startswith("_")]
    lower_colors = [to_hex(l.get_color()) for l in lower.get_lines()]
    assert len(set(upper_colors)) == 3
    assert lower_colors == upper_colors


def test_hue_and_style_on_one_column_draw_one_legend(make_project, spectra):
    figures = _capture()
    run(make_project, spectra, "--hue", "Sample", "--style", "Sample", "--select", "Stage", "-s", "Raw",
        "--plot_type", "line")
    ax = figures[0].axes[0]
    legends = [a for a in ax.get_children() if isinstance(a, Legend)]
    assert len(legends) == 1
    handles = legends[0].legend_handles
    assert [t.get_text() for t in legends[0].get_texts()] == ["A", "B", "C"]
    assert len({h.get_linestyle() for h in handles}) == 3
    assert len({to_hex(h.get_color()) for h in handles}) == 3


def test_hue_and_style_on_one_column_past_the_palette(make_project):
    x = np.linspace(0, 10, 20)
    frame = pd.DataFrame([{"X": x, "Y": np.sin(x + i), "Run": f"run{i:02d}"} for i in range(12)])
    make_project({"ManyHue": frame})
    figures = _capture()
    line.main(["--datafile", "ManyHue", "-x", "X", "-y", "Y", "--hue", "Run", "--style", "Run", "--plot_type", "line"])
    pairs = _line_colors(figures[0].axes[0])
    assert len(pairs) == 12 and len(set(pairs.values())) == 12
