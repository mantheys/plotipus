import numpy as np
import pandas as pd
import pytest
from matplotlib.collections import PolyCollection
from matplotlib.colors import to_hex
from matplotlib.container import ErrorbarContainer
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



def test_lower_ratio_with_empty_reference_bin(make_project, spectra):
    """A ratio to an empty bin is undefined there, not for the whole series."""
    from matplotlib.patches import StepPatch

    counts = spectra["Counts"].iloc[0].copy()
    counts[3] = 0.0
    spectra.at[0, "Counts"] = counts
    figures = _capture()
    run(make_project, spectra, "--hue", "Sample", "--select", "Stage", "-s", "Raw", "--plot_type", "step",
        "--lower", "ratio")
    lower = figures[-1].axes[1]
    steps = [patch for patch in lower.patches if isinstance(patch, StepPatch)]
    assert steps and all(np.isnan(patch.get_data().values[3]) for patch in steps)
    assert all(np.isfinite(np.delete(patch.get_data().values, 3)).all() for patch in steps)

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


# --- Error display (T07) --------------------------------------------------------------


@pytest.fixture
def limits():
    mass = np.linspace(110, 600, 20)
    median = 0.6 + 0.002 * (mass - 110)
    return pd.DataFrame([{"Mass": mass, "Limit": median, "LimitError": 0.3 * median, "Kind": "expected", "Variable": "L"},
                         {"Mass": mass, "Limit": median * 1.1, "Kind": "observed", "Variable": "L"}])


def _bands(ax):
    return [c for c in ax.collections if isinstance(c, PolyCollection) and len(c.get_paths())]


def _errorbars(ax):
    return [c for c in ax.containers if isinstance(c, ErrorbarContainer)]


def test_bands_without_plot_type(make_project, limits):
    make_project({"Limits": limits})
    figures = _capture()
    line.main(["--datafile", "Limits", "-x", "Mass", "-y", "Limit", "--hue", "Kind", "--errory", "--errory_type", "bands",
               "--logy"])
    ax = figures[0].axes[0]
    assert not _errorbars(ax)
    bands = _bands(ax)
    assert len(bands) == 1
    expected = next(l for l in ax.get_lines() if l.get_label() == "expected")
    assert to_hex(bands[0].get_facecolor()[0]) == to_hex(expected.get_color())
    assert bands[0].get_alpha() == pytest.approx(0.2)
    assert len(bands[0].get_edgecolor()) == 0 or bands[0].get_edgecolor()[0][3] == 0


def test_band_default_for_line_and_step(make_project, spectra):
    for plot_type in ("line", "step"):
        figures = _capture()
        run(make_project, spectra, "--hue", "Sample", "--select", "Stage", "-s", "Raw", "--errory",
            "--plot_type", plot_type)
        ax = figures[0].axes[0]
        assert len(_bands(ax)) == 3 and not _errorbars(ax)


def test_step_band_covers_the_bins(make_project, spectra):
    figures = _capture()
    run(make_project, spectra, "--hue", "Sample", "--select", "Stage", "-s", "Raw", "--errory", "--plot_type", "step")
    xs = _bands(figures[0].axes[0])[0].get_paths()[0].vertices[:, 0]
    assert xs.min() == pytest.approx(0.0) and xs.max() == pytest.approx(10.0)


def test_bars_on_a_line_kept(make_project, spectra):
    figures = _capture()
    run(make_project, spectra, "--hue", "Sample", "--select", "Stage", "-s", "Raw", "--errory",
        "--errory_type", "bars", "--plot_type", "line")
    ax = figures[0].axes[0]
    containers = _errorbars(ax)
    assert len(containers) == 3 and not _bands(ax)
    assert containers[0].lines[0].get_linestyle() == "-"


def test_band_alpha_from_style(make_project, spectra, tmp_path):
    (tmp_path / "style.json").write_text('{"plot_settings": {"band_alpha": 0.35}}')
    make_project({"Spectra": spectra}, 'style = ["style.json"]\n')
    figures = _capture()
    line.main(["--datafile", "Spectra", "-x", "Energy", "-y", "Counts", "--hue", "Sample", "--select", "Stage",
               "-s", "Raw", "--errory", "--plot_type", "line"])
    assert [b.get_alpha() for b in _bands(figures[0].axes[0])] == [pytest.approx(0.35)] * 3


def _resolution_events():
    rng = np.random.default_rng(3)
    rows = []
    for sample in ("signal", "background"):
        true = rng.uniform(1, 30, 2000)
        reco = true * rng.normal(1, 0.1, true.size)
        rows.append({"TrueEnergy": true, "Resolution": (reco - true) / true, "Sample": sample, "Variable": "Energy"})
    return pd.DataFrame(rows)


@pytest.mark.parametrize("connect", [False, True])
def test_errorbar_points_not_joined(make_project, connect):
    make_project({"Events": _resolution_events()})
    figures = _capture()
    line.main(["--datafile", "Events", "-x", "TrueEnergy", "-y", "Resolution", "--hue", "Sample", "--binned",
               "--estimator", "mean", "--bins", "15", "--plot_type", "errorbar", *(["--connect"] if connect else [])])
    containers = _errorbars(figures[0].axes[0])
    assert len(containers) == 2
    assert {c.lines[0].get_linestyle() for c in containers} == ({"-"} if connect else {"None"})


@pytest.mark.parametrize("argv, linestyle", [([], "None"), (["--plot_type", "errorbar"], "None"),
                                             (["--connect"], "-")])
def test_errorbars_on_points(make_project, spectra, argv, linestyle):
    figures = _capture()
    run(make_project, spectra, "--hue", "Sample", "--select", "Stage", "-s", "Raw", "--errory", *argv)
    containers = _errorbars(figures[0].axes[0])
    assert len(containers) == 3 and not _bands(figures[0].axes[0])
    assert {c.lines[0].get_linestyle() for c in containers} == {linestyle}
    assert all(c.has_yerr for c in containers)


# --- Data against simulation (--data_hue) ---------------------------------------------


def _data_and_simulation():
    x = np.arange(0.5, 10, 1.0)
    background, signal = 100 * np.exp(-x / 4), 20 * np.exp(-0.5 * (x - 5) ** 2)
    data = np.round(background + signal)
    return pd.DataFrame([
        {"Energy": x, "Counts": data, "CountsError": np.sqrt(data), "Sample": "Data"},
        {"Energy": x, "Counts": background, "CountsError": 0.1 * np.sqrt(background), "Sample": "Background"},
        {"Energy": x, "Counts": signal, "CountsError": 0.1 * np.sqrt(signal), "Sample": "Signal"},
    ])


def test_data_hue_points_over_steps(make_project):
    from plotipus import style

    figures = _capture()
    run(make_project, _data_and_simulation(), "--hue", "Sample", "--data_hue", "Data", "--errory")
    ax = figures[-1].axes[0]
    (container,) = [c for c in ax.containers if isinstance(c, ErrorbarContainer)]
    assert to_hex(container.lines[0].get_color()) == to_hex(style.role("ink"))
    assert container.has_yerr
    labels = [text.get_text() for text in ax.get_legend().get_texts()]
    assert labels[0] == "Data"
    # The simulation keeps the palette's first colours: the data takes none of them.
    from plotipus.palettes import current_colors

    steps = [p for p in ax.patches if p.get_label() in ("Background", "Signal")]
    assert {to_hex(p.get_edgecolor()) for p in steps} == {to_hex(c) for c in current_colors()[:2]}


def test_data_hue_stacked_ratio(make_project):
    from matplotlib.patches import StepPatch

    frame = _data_and_simulation()
    figures = _capture()
    run(make_project, frame, "--hue", "Sample", "--data_hue", "Data", "--stacked", "--errory", "--lower", "ratio")
    upper, lower = figures[-1].axes[:2]
    filled = [p for p in upper.patches if isinstance(p, StepPatch) and p.get_fill()]
    assert len(filled) == 2  # background, then signal stacked on it
    assert np.allclose(filled[1].get_data().baseline, frame["Counts"].iloc[1])
    total = frame["Counts"].iloc[1] + frame["Counts"].iloc[2]
    (container,) = [c for c in lower.containers if isinstance(c, ErrorbarContainer)]
    assert np.allclose(container.lines[0].get_ydata(), frame["Counts"].iloc[0] / total)


def test_data_hue_by_config(make_project):
    """With --by_config, --data_hue names a config: drawn as ink points, first in the legend, not combined."""
    from plotipus import style

    x = np.arange(0.5, 10, 1.0)
    counts = {"data": np.round(50 * np.exp(-x / 3)), "mc": 50 * np.exp(-x / 3)}
    frames = {f"{c}_n_Spec": pd.DataFrame([{"Values": x, "Counts": y, "CountsError": np.sqrt(y + 1), "Config": c,
                                             "Name": "n"}]) for c, y in counts.items()}
    make_project(frames)
    figures = _capture()
    line.main(["--datafile", "Spec", "--configs", "data", "mc", "--names", "n", "-x", "Values", "-y", "Counts",
               "--by_config", "--data_hue", "data", "--combine_op", "sum"])
    ax = figures[-1].axes[0]
    (container,) = [c for c in ax.containers if isinstance(c, ErrorbarContainer)]
    assert to_hex(container.lines[0].get_color()) == to_hex(style.role("ink")) and container.has_yerr
    labels = [t.get_text() for t in ax.get_legend().get_texts()]
    assert labels[0].lower().startswith("data")
    # The combined series sums the simulation only: its peak is the simulation's, not data + simulation.
    peaks = {p.get_label(): p.get_path().vertices[:, 1].max() for p in ax.patches}
    assert np.isclose(peaks["Combined"], counts["mc"].max())


def test_stack_error_style(make_project, tmp_path):
    """plot_settings.stack_error sets the label, hatch and colour of the stacked simulation's error band."""
    from matplotlib.patches import StepPatch

    (tmp_path / "style.json").write_text(
        '{"plot_settings": {"stack_error": {"label": "MC stat.", "hatch": "xx", "color": "#ff0000"}}}')
    make_project({"Spectra": _data_and_simulation()}, 'style = ["style.json"]\n')
    figures = _capture()
    line.main(["--datafile", "Spectra", "-x", "Energy", "-y", "Counts", "--hue", "Sample", "--data_hue", "Data",
               "--stacked", "--errory"])
    ax = figures[-1].axes[0]
    (band,) = [p for p in ax.patches if isinstance(p, StepPatch) and not p.get_fill()]
    assert band.get_label() == "MC stat." and band.get_hatch() == "xx"
    assert to_hex(band.get_edgecolor()) == "#ff0000"
