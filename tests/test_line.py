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


def test_by_config_one_mapped_config_split_by_hue(make_project, tmp_path):
    """Issue #1: one config with a config_color, split by --hue, draws each
    hue value in its own colour (--iterable_color_mapping wins)."""
    x = np.arange(0.5, 10, 1.0)
    frame = pd.DataFrame([{"Values": x, "Counts": k * np.ones_like(x), "Config": "hd", "Name": "n", "Signal": s}
                          for k, s in ((3, "Signal"), (2, "External"), (1, "Intrinsic"))])
    (tmp_path / "style.json").write_text('{"mappings": {"config_color": {"hd": "C3"}, '
                                         '"hue_colors": {"External": "#123456"}}}')
    make_project({"hd_n_Spec": frame}, 'style = ["style.json"]\n')
    figures = _capture()
    base = ["--datafile", "Spec", "--configs", "hd", "--names", "n", "-x", "Values", "-y", "Counts",
            "-i", "Signal", "--by_config", "--plot_type", "line"]
    line.main(base)
    line.main([*base, "--iterable_color_mapping", "hue_colors"])
    plain, mapped = (_line_colors(fig.axes[0]) for fig in figures)
    assert len(plain) == 3 and len({color for color, _ in plain.values()}) == 3
    assert len({color for color, _ in mapped.values()}) == 3
    assert "#123456" in {color for color, _ in mapped.values()}


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
    lower_colors = [to_hex(l.get_color()) for l in lower.get_lines() if l.get_linestyle() != "--"]
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
    # Entries follow the right-hand ends of the lines (B is twice A, C half of it).
    assert [t.get_text() for t in legends[0].get_texts()] == ["B", "A", "C"]
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


@pytest.mark.parametrize("argv, linestyle", [(["--plot_type", "errorbar"], "None"), (["--connect"], "-")])
def test_errorbars_on_points(make_project, spectra, argv, linestyle):
    figures = _capture()
    run(make_project, spectra, "--hue", "Sample", "--select", "Stage", "-s", "Raw", "--errory", *argv)
    containers = _errorbars(figures[0].axes[0])
    assert len(containers) == 3 and not _bands(figures[0].axes[0])
    assert {c.lines[0].get_linestyle() for c in containers} == {linestyle}
    assert all(c.has_yerr for c in containers)


def test_compared_binned_series_default_to_steps(make_project, spectra):
    """Without --plot_type, binned series compared among themselves are
    steps (with error bands); points are for data."""
    figures = _capture()
    run(make_project, spectra, "--hue", "Sample", "--select", "Stage", "-s", "Raw", "--errory")
    ax = figures[0].axes[0]
    assert not _errorbars(ax) and len(_bands(ax)) == 3


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


def test_stacked_binned_series_are_filled_histograms(make_project, spectra):
    """--stacked over binned x stacks filled steps; --bar_width keeps bars."""
    from matplotlib.patches import Rectangle, StepPatch

    figures = _capture()
    run(make_project, spectra, "--hue", "Sample", "--select", "Stage", "-s", "Raw", "--stacked")
    patches = figures[-1].axes[0].patches
    filled = [p for p in patches if isinstance(p, StepPatch) and p.get_fill()]
    assert len(filled) == 3 and np.allclose(filled[1].get_data().baseline, spectra["Counts"].iloc[0])
    run(make_project, spectra, "--hue", "Sample", "--select", "Stage", "-s", "Raw", "--stacked", "--bar_width", "auto")
    assert any(isinstance(p, Rectangle) for p in figures[-1].axes[0].patches)


# --- Stacked simulation with overlaid data (T18) ----------------------------------------


def _spectrum(total_error=False):
    """The repro Spectrum: Poisson data over two backgrounds and a peak."""
    rng = np.random.default_rng(0)
    m = np.arange(100.5, 160, 1.0)
    mc = {"bkg_a": 3000 * np.exp(-(m - 100) / 40), "bkg_b": 400 * np.exp(-(m - 100) / 25),
          "signal": 120 * np.exp(-0.5 * ((m - 125) / 1.6) ** 2)}
    data = rng.poisson(sum(mc.values())).astype(float)
    rows = [{"Mass": m, "Counts": c, "CountsError": np.sqrt(c), "Sample": s}
            for s, c in [("data", data), *mc.items()]]
    if total_error:
        for row in rows:
            row["TotalError"] = 0.05 * sum(mc.values())
    return pd.DataFrame(rows), data, mc


def _stack_run(make_project, frame, *argv):
    figures = _capture()
    make_project({"Spectrum": frame})
    line.main(["--datafile", "Spectrum", "-x", "Mass", "-y", "Counts", "--hue", "Sample", "--stacked", *argv])
    return figures[-1]


def test_stack_fill_overlay_band_and_ratio(make_project):
    """The control plot: filled stacked steps, data points on top, the hatched total band, data / total."""
    from matplotlib.patches import StepPatch

    frame, data, mc = _spectrum()
    fig = _stack_run(make_project, frame, "--plot_type", "fill", "--overlay", "data", "--stack_total_error",
                     "--lower", "ratio")
    upper, lower = fig.axes[:2]
    filled = [p for p in upper.patches if isinstance(p, StepPatch) and p.get_fill()]
    assert [p.get_label() for p in filled] == ["bkg_a", "bkg_b", "signal"]
    total = sum(mc.values())
    assert np.allclose(filled[-1].get_data().values, total)  # the top of the stack is the sum of the MC
    assert np.allclose(filled[1].get_data().baseline, mc["bkg_a"])
    assert all(to_hex(p.get_edgecolor()) != to_hex(p.get_facecolor()) for p in filled)  # a darker edge
    (points,) = [c for c in upper.containers if isinstance(c, ErrorbarContainer)]
    assert np.allclose(points.lines[0].get_ydata(), data)
    (band,) = [p for p in upper.patches if isinstance(p, StepPatch) and not p.get_fill()]
    error = np.sqrt(sum(np.square(np.sqrt(c)) for c in mc.values()))
    assert np.allclose(band.get_data().values, total + error) and np.allclose(band.get_data().baseline, total - error)
    (ratio,) = [c for c in lower.containers if isinstance(c, ErrorbarContainer)]
    assert np.allclose(ratio.lines[0].get_ydata(), data / total)
    labels = [t.get_text() for t in upper.get_legend().get_texts()]
    assert labels == ["data", "signal", "bkg_b", "bkg_a", band.get_label()]


def test_stack_step_outlines(make_project):
    """B10a: --stacked --plot_type step stacks the outlines (each one's top, no closed bottom edge)."""
    from matplotlib.patches import StepPatch

    frame, _, mc = _spectrum()
    fig = _stack_run(make_project, frame[frame.Sample != "data"], "--plot_type", "step")
    outlines = [p for p in fig.axes[0].patches if isinstance(p, StepPatch)]
    assert [p.get_label() for p in outlines] == ["bkg_a", "bkg_b", "signal"]
    assert all(not p.get_fill() and p.get_data().baseline is None for p in outlines)
    assert np.allclose(outlines[1].get_data().values, mc["bkg_a"] + mc["bkg_b"])
    assert fig.axes[0].get_ylim()[0] == 0


def test_stack_line_areas_and_reverse(make_project):
    from matplotlib.collections import PolyCollection

    frame, _, mc = _spectrum()
    fig = _stack_run(make_project, frame[frame.Sample != "data"], "--plot_type", "line", "--stack_reverse")
    areas = [c for c in fig.axes[0].collections if isinstance(c, PolyCollection)]
    assert [a.get_label() for a in areas] == ["signal", "bkg_b", "bkg_a"]  # first series on top
    top = areas[-1].get_paths()[0].vertices[:, 1].max()
    assert np.isclose(top, sum(mc.values()).max())


def test_stack_total_error_column_and_overlay_last(make_project):
    from matplotlib.patches import StepPatch

    frame, _, mc = _spectrum(total_error=True)
    fig = _stack_run(make_project, frame, "--overlay", "data", "--stack_total_error_column", "TotalError",
                     "--overlay_legend", "last")
    ax = fig.axes[0]
    (band,) = [p for p in ax.patches if isinstance(p, StepPatch) and not p.get_fill()]
    total = sum(mc.values())
    assert np.allclose(band.get_data().values, 1.05 * total)
    labels = [t.get_text() for t in ax.get_legend().get_texts()]
    assert labels == ["signal", "bkg_b", "bkg_a", band.get_label(), "data"]


# --- Data and simulation conventions -----------------------------------------------------


def test_density_gives_unit_area(make_project, spectra):
    figures = _capture()
    run(make_project, spectra, "--hue", "Sample", "--select", "Stage", "-s", "Raw", "--plot_type", "line",
        "--density")
    ax = figures[0].axes[0]
    # Bins of unit width around the centres 0.5 .. 9.5: the area is the sum of y.
    areas = [np.sum(line.get_ydata()) for line in ax.get_lines() if line.get_label() in ("A", "B", "C")]
    assert len(areas) == 3 and np.allclose(areas, 1.0)
    assert ax.get_ylabel() == "Density"


def test_data_named_by_style_value(make_project, spectra):
    from matplotlib.colors import to_hex
    from matplotlib.container import ErrorbarContainer

    figures = _capture()
    run(make_project, spectra, "--hue", "Sample", "--style", "Stage", "--data_hue", "Raw", "--errory")
    ax = figures[0].axes[0]
    points = [c for c in ax.containers if isinstance(c, ErrorbarContainer)]
    steps = [p for p in ax.patches if type(p).__name__ in ("Polygon", "StepPatch")]
    assert len(points) == 3 and len(steps) == 3
    # Data points take their hue colour; the one simulation style stays solid.
    assert len({to_hex(c.lines[0].get_color()) for c in points}) == 3
    assert all(p.get_linestyle() in ("-", "solid", (0, None)) for p in steps)  # solid
    style_legend = [leg for leg in [ax.get_legend(), *[a for a in ax.artists]] if leg is not None
                    and "Stage" in leg.get_title().get_text()][0]
    handles = style_legend.legend_handles
    assert handles[0].get_marker() == "o" and handles[0].get_linestyle() == "None"
    assert [t.get_text() for t in style_legend.get_texts()] == ["Raw", "Smooth"]


def test_column_panel_of_data_is_points(make_project, spectra):
    from matplotlib.container import ErrorbarContainer

    figures = _capture()
    run(make_project, spectra, "--hue", "Sample", "--select", "Stage", "Sample", "-s", "Raw", "A",
        "--data_hue", "A", "--errory", "--lower", "column:Significance")
    lower = figures[0].axes[1]
    assert any(isinstance(c, ErrorbarContainer) for c in lower.containers)
    assert not [line for line in lower.get_lines() if line.get_linestyle() not in ("None", "")
                and len(line.get_xdata()) > 2]


# --- Example feedback: peaks, reference ratios, safe ratios, compact panels ----------------


def test_peak_normalises_each_series_to_one(make_project, spectra):
    figures = _capture()
    run(make_project, spectra, "--hue", "Sample", "--select", "Stage", "-s", "Raw", "--peak", "--plot_type", "line")
    ax = figures[0].axes[0]
    assert all(np.nanmax(l.get_ydata()) == pytest.approx(1.0) for l in ax.get_lines() if not l.get_label().startswith("_"))
    assert ax.get_ylabel() == "Normalised to 1"


def test_ratio_to_a_reference_is_a_line_with_points(make_project, spectra):
    figures = _capture()
    run(make_project, spectra, "--hue", "Sample", "--select", "Stage", "-s", "Raw", "--lower", "ratio",
        "--reference_value", "A")
    upper, lower = figures[0].axes[:2]
    colors = {p.get_label(): to_hex(p.get_edgecolor()) for p in upper.patches if not p.get_label().startswith("_")}
    flat = [l for l in lower.get_lines() if len(l.get_ydata()) == 2 and np.allclose(l.get_ydata(), 1.0)]
    assert [to_hex(l.get_color()) for l in flat] == [colors["A"]]  # the reference: a line at 1 in its colour
    assert len(_errorbars(lower)) == 2  # B and C as points


def test_count_ratio_edge_cases():
    from plotipus.lower import count_ratio

    values, error, beyond = count_ratio([0, 3, 0, 4], [0, 0, 2, 2], [0, 1.7, 0, 2], counts=True)
    assert np.isnan(values[0]) and not beyond[0]  # 0/0: no information
    assert np.isnan(values[1]) and beyond[1]  # data over an empty prediction: an arrow
    assert values[2] == 0 and error[1][2] == pytest.approx(1.841 / 2, rel=1e-3)  # no data: Garwood upper error
    assert values[3] == 2 and error[0][3] == error[1][3] == 1


def test_data_over_an_empty_prediction_draws_an_arrow(make_project):
    x = np.arange(0.5, 6, 1.0)
    frame = pd.DataFrame([{"X": x, "Y": np.array(y, dtype=float), "YError": np.sqrt(y), "Sample": s}
                          for s, y in (("Data", [0, 3, 4, 5, 0, 2]), ("Simulation", [0, 0, 4, 5, 2, 2]))])
    make_project({"D": frame})
    figures = _capture()
    line.main(["--datafile", "D", "-x", "X", "-y", "Y", "--hue", "Sample", "--data_hue", "Data", "--errory",
               "--lower", "ratio"])
    lower = figures[0].axes[1]
    arrows = [l for l in lower.get_lines() if l.get_marker() == "^"]
    assert len(arrows) == 1 and list(arrows[0].get_xdata()) == [1.5]


def test_several_panels_are_compact_by_default(make_project):
    x = np.arange(0.5, 10, 1.0)
    frame = pd.DataFrame([{"X": x, "Y": k * np.exp(-x / 3), "Part": p, "Sample": "S"}
                          for k, p in ((1, "a"), (5, "b"))])
    make_project({"P": frame})
    figures = _capture()
    base = ["--datafile", "P", "-x", "X", "-y", "Y", "--hue", "Sample", "--variable_column", "Part",
            "--variables", "a", "b", "--plot_type", "line"]
    line.main(base)
    line.main([*base, "--no-compact"])
    first, second = figures[0].axes[:2]
    assert first.get_ylim() == second.get_ylim() and second.get_ylabel() == ""
    first, second = figures[1].axes[:2]
    assert first.get_ylim() != second.get_ylim() and second.get_ylabel() != ""


def test_significance_is_a_step_with_its_spread(make_project):
    """S/sqrt(B) is an expectation: a step, with the band a measured
    significance would spread over (sqrt(1 + S/B), at least 1)."""
    x = np.arange(0.5, 10, 1.0)
    frame = pd.DataFrame([{"X": x, "Y": y, "YError": np.sqrt(y), "Sample": s}
                          for s, y in (("Background", 100 * np.ones_like(x)), ("Signal", 10 * np.exp(-(x - 5) ** 2)))])
    make_project({"G": frame})
    figures = _capture()
    line.main(["--datafile", "G", "-x", "X", "-y", "Y", "--hue", "Sample", "--stacked", "--errory", "--lower", "group",
               "--reference_group", "Signal", "--other_group", "Background", "--group_significance"])
    lower = figures[0].axes[1]
    assert not _errorbars(lower) and lower.patches  # a step outline
    band = _bands(lower)[0].get_paths()[0].vertices[:, 1]
    assert np.ptp(band) >= 2.0  # at least +-1 around zero far from the signal


def test_column_lower_panel_shows_the_data_column_only(make_project):
    x = np.arange(0.5, 6, 1.0)
    frame = pd.DataFrame([{"X": x, "Y": np.full_like(x, 5.0), "YError": np.ones_like(x), "Pull": np.full_like(x, p),
                           "Sample": s} for s, p in (("Data", 1.0), ("Simulation", -1.0))])
    make_project({"C": frame})
    figures = _capture()
    line.main(["--datafile", "C", "-x", "X", "-y", "Y", "--hue", "Sample", "--data_hue", "Data", "--errory",
               "--lower", "column:Pull"])
    lower = figures[0].axes[1]
    ys = np.concatenate([l.get_ydata() for l in lower.get_lines()] or [[]])
    assert len(_errorbars(lower)) == 1 and not np.any(np.isclose(ys, -1.0))


# --- per-series plot type (T21) ---------------------------------------------------------


@pytest.fixture
def models():
    x = np.linspace(0.1, 2.0, 8)
    rows = [{"Z": x, "Mu": 5 * np.log10(x) + 43, "MuError": 0.2 * np.ones_like(x), "Model": "data"}]
    for name, offset in (("LCDM", 0.0), ("Empty", -0.3), ("EdS", -0.6)):
        rows.append({"Z": x, "Mu": 5 * np.log10(x) + 43 + offset, "MuError": 0.05 * np.ones_like(x), "Model": name})
    return pd.DataFrame(rows)


def _series_artists(ax):
    points = [c for c in ax.containers if isinstance(c, ErrorbarContainer)]
    in_points = {id(c.lines[0]) for c in points}
    lines = [l for l in ax.get_lines() if id(l) not in in_points and not l.get_label().startswith("_")]
    return points, lines


def test_series_type_data_points_over_model_lines(make_project, models):
    figures = _capture()
    make_project({"Hubble": models})
    line.main(["--datafile", "Hubble", "-x", "Z", "-y", "Mu", "--hue", "Model", "--plot_type", "line",
               "--series_type", "data=errorbar"])
    ax = figures[0].axes[0]
    points, lines = _series_artists(ax)
    assert len(points) == 1 and len(lines) == 3
    (data,) = points
    assert np.allclose(data.lines[2][0].get_segments()[0][1][1] - data.lines[2][0].get_segments()[0][0][1], 0.4)
    assert data.lines[0].get_zorder() > max(l.get_zorder() for l in lines)  # on top
    assert to_hex(data.lines[0].get_color()) not in {to_hex(l.get_color()) for l in lines}  # its own colour


def test_series_type_overlay_value_is_ink(make_project, models):
    from plotipus import style

    figures = _capture()
    make_project({"Hubble": models})
    line.main(["--datafile", "Hubble", "-x", "Z", "-y", "Mu", "--hue", "Model", "--plot_type", "line",
               "--series_type", "data=errorbar", "--overlay", "data"])
    (data,), lines = _series_artists(figures[0].axes[0])
    assert to_hex(data.lines[0].get_color()) == to_hex(style.role("ink")) and len(lines) == 3


def test_series_type_from_style_mapping(make_project, models, tmp_path):
    (tmp_path / "style.json").write_text('{"mappings": {"series_types": {"data": "errorbar", "EdS": "step"}}}')
    figures = _capture()
    make_project({"Hubble": models}, 'style = ["style.json"]\n')
    line.main(["--datafile", "Hubble", "-x", "Z", "-y", "Mu", "--hue", "Model", "--plot_type", "line",
               "--series_type_mapping", "series_types", "--series_type", "EdS=line"])
    points, lines = _series_artists(figures[0].axes[0])
    assert len(points) == 1 and len(lines) == 3  # the command line wins: EdS stays a line


def test_series_type_rejects_unknown_type():
    with pytest.raises(SystemExit):
        line.parse(["--datafile", "X", "-y", "Y", "--series_type", "data=dots"])


def test_error_scale_multiplies_drawn_errors_only(make_project, models):
    figures = _capture()
    make_project({"Hubble": models})
    line.main(["--datafile", "Hubble", "-x", "Z", "-y", "Mu", "--hue", "Model", "--plot_type", "line",
               "--series_type", "data=errorbar", "--error_scale", "10", "--lower", "ratio"])
    ax = figures[0].axes[0]
    (data,), _ = _series_artists(ax)
    segments = data.lines[2][0].get_segments()
    half = np.array([(s[1][1] - s[0][1]) / 2 for s in segments])
    assert np.allclose(half, 10 * 0.2)
    assert np.allclose(data.lines[0].get_ydata(), models["Mu"].iloc[0])  # values unscaled
    labels = [t.get_text() for t in ax.get_legend().get_texts()]
    assert sum(t.endswith("(errors $\\times$10)") for t in labels) == 1


def test_error_scale_skips_series_without_errors(make_project, models):
    models["MuError"] = [models["MuError"].iloc[0]] + [np.full(8, np.nan)] * 3
    figures = _capture()
    make_project({"Hubble": models})
    line.main(["--datafile", "Hubble", "-x", "Z", "-y", "Mu", "--hue", "Model", "--plot_type", "line", "--errory",
               "--overlay", "data", "--error_scale", "10"])
    labels = [t.get_text() for t in figures[0].axes[0].get_legend().get_texts()]
    # Mathtext: the serif fonts of paper have no × glyph.
    assert labels[0] == "data (errors $\\times$10)" and not any("times" in t for t in labels[1:])


def test_shift_peak_aligns_the_maxima_on_the_reference(make_project):
    x = np.arange(0.5, 10, 1.0)
    frame = pd.DataFrame([{"X": x, "Y": np.exp(-0.5 * (x - c) ** 2) + 0.01, "YError": 0.01 * np.ones_like(x),
                           "Sample": s} for s, c in (("Ref", 4.5), ("Other", 6.5))])
    make_project({"S": frame})
    figures = _capture()
    base = ["--datafile", "S", "-x", "X", "-y", "Y", "--hue", "Sample", "--errory", "--shift", "peak",
            "--reference_value", "Ref"]
    line.main([*base, "--plot_type", "line"])
    line.main([*base, "--lower", "ratio"])
    peaks = {l.get_label(): l.get_xdata()[np.nanargmax(l.get_ydata())] for l in figures[0].axes[0].get_lines()
             if not l.get_label().startswith("_")}
    assert peaks == {"Ref": 4.5, "Other": 4.5}
    (points,) = _errorbars(figures[1].axes[1])
    assert points.has_yerr  # the ratio carries both series' errors


def test_empty_bins_agree_in_a_data_ratio(make_project):
    x = np.arange(0.5, 6, 1.0)
    frame = pd.DataFrame([{"X": x, "Y": np.array(y, dtype=float), "YError": np.sqrt(y), "Sample": s}
                          for s, y in (("Data", [0, 0, 4, 5, 3, 2]), ("Simulation", [0, 0, 4, 5, 2, 2]))])
    make_project({"E": frame})
    figures = _capture()
    line.main(["--datafile", "E", "-x", "X", "-y", "Y", "--hue", "Sample", "--data_hue", "Data", "--errory",
               "--lower", "ratio"])
    lower = figures[0].axes[1]
    (empty,) = [l for l in lower.get_lines() if l.get_marker() == "o" and l.get_markerfacecolor() == "none"]
    assert list(empty.get_xdata()) == [0.5, 1.5] and list(empty.get_ydata()) == [1, 1]


def test_column_lower_panel_has_a_reference_line(make_project):
    x = np.arange(0.5, 6, 1.0)
    frame = pd.DataFrame([{"X": x, "Y": np.full_like(x, 5.0), "YError": np.ones_like(x), "Pull": np.full_like(x, 1.0),
                           "Sample": "Data"}])
    make_project({"C": frame})
    figures = _capture()
    base = ["--datafile", "C", "-x", "X", "-y", "Y", "--hue", "Sample", "--data_hue", "Data", "--lower", "column:Pull"]
    line.main(base)
    line.main([*base, "--no_lower_reference"])
    flat = [[l for l in fig.axes[1].get_lines() if l.get_linestyle() == "--" and np.allclose(l.get_ydata(), 0)]
            for fig in figures]
    assert len(flat[0]) == 1 and not flat[1]


# --- per-series markers, x errors from bin edges (T21b) -------------------------------


def _legend_handles(ax):
    legend = ax.get_legend()
    return {t.get_text(): h for t, h in zip(legend.get_texts(), legend.legend_handles)}


def test_series_marker_shapes_and_legend(make_project, models):
    from plotipus import style

    figures = _capture()
    make_project({"Hubble": models})
    line.main(["--datafile", "Hubble", "-x", "Z", "-y", "Mu", "--hue", "Model", "--plot_type", "line",
               "--series_type", "data=errorbar", "--series_marker", "data=o_open", "LCDM=s", "EdS=x:14"])
    ax = figures[0].axes[0]
    (data,), lines = _series_artists(ax)
    point = data.lines[0]
    assert point.get_marker() == "o" and to_hex(point.get_markerfacecolor()) == to_hex(style.role("paper"))
    assert to_hex(point.get_markeredgecolor()) == to_hex(point.get_color())
    by_label = {l.get_label(): l for l in lines}
    assert by_label["LCDM"].get_marker() == "s" and by_label["LCDM"].get_linestyle() == "-"  # a line with markers
    assert by_label["EdS"].get_marker() == "x" and by_label["EdS"].get_markersize() == 14
    assert by_label["Empty"].get_marker() in ("None", "", None)
    handles = _legend_handles(ax)
    assert handles["LCDM"].get_marker() == "s" and handles["EdS"].get_marker() == "x"
    from matplotlib.lines import Line2D

    hollow = [l for l in ax.get_legend().findobj(Line2D) if l.get_marker() == "o"]  # the error-bar entry
    assert len(hollow) == 1 and to_hex(hollow[0].get_markerfacecolor()) == to_hex(style.role("paper"))


def test_series_marker_from_style_mapping_on_overlay_points(make_project, models, tmp_path):
    (tmp_path / "style.json").write_text('{"mappings": {"markers": {"data": "D"}}}')
    figures = _capture()
    make_project({"Hubble": models}, 'style = ["style.json"]\n')
    line.main(["--datafile", "Hubble", "-x", "Z", "-y", "Mu", "--hue", "Model", "--plot_type", "line",
               "--overlay", "data", "--series_marker_mapping", "markers"])
    (data,), _ = _series_artists(figures[0].axes[0])
    assert data.lines[0].get_marker() == "D"


@pytest.mark.parametrize("spec", ["data=dots", "data=o_open:big", "data"])
def test_series_marker_rejects_bad_specs(spec):
    with pytest.raises(SystemExit):
        line.parse(["--datafile", "X", "-y", "Y", "--series_marker", spec])


def test_x_errors_from_bin_edge_columns(make_project):
    x = np.array([1.0, 3.0, 7.0])
    low, high = np.array([0.0, 2.0, 4.0]), np.array([2.0, 4.0, 12.0])  # unequal bins, x not centred
    frame = pd.DataFrame([{"X": x, "Y": np.array([1.0, 2.0, 3.0]), "YError": np.full(3, 0.1), "Low": low,
                           "High": high, "S": "data"},
                          {"X": x, "Y": np.array([1.1, 2.1, 2.9]), "S": "model"}])
    make_project({"E": frame})
    figures = _capture()
    line.main(["--datafile", "E", "-x", "X", "-y", "Y", "--hue", "S", "--overlay", "data", "--plot_type", "line",
               "--errorx_column", "Low", "High"])
    (data,), _ = _series_artists(figures[0].axes[0])
    assert data.has_xerr
    segments = [s for c in data.lines[2] for s in c.get_segments() if np.isclose(s[0][1], s[1][1])]
    spans = sorted((s[0][0], s[1][0]) for s in segments)
    assert np.allclose(spans, list(zip(low, high)))

    figures.clear()
    frame["Half"] = [np.array([1.0, 1.0, 4.0]), None]
    make_project({"E": frame})
    line.main(["--datafile", "E", "-x", "X", "-y", "Y", "--hue", "S", "--overlay", "data", "--plot_type", "line",
               "--errorx_column", "Half"])
    (data,), _ = _series_artists(figures[0].axes[0])
    segments = [s for c in data.lines[2] for s in c.get_segments() if np.isclose(s[0][1], s[1][1])]
    assert np.allclose(sorted(s[1][0] - s[0][0] for s in segments), [2.0, 2.0, 8.0])


def test_comparable_linewidths_follow_the_hue_when_hue_is_style(make_project, models):
    figures = _capture()
    make_project({"Hubble": models})
    line.main(["--datafile", "Hubble", "-x", "Z", "-y", "Mu", "--hue", "Model", "--style", "Model",
               "--plot_type", "line", "--comparable_linewidths", "1", "2", "3", "4"])
    widths = {l.get_label(): l.get_linewidth() for l in figures[0].axes[0].get_lines()
              if not l.get_label().startswith("_")}
    assert widths == {"data": 1, "LCDM": 2, "Empty": 3, "EdS": 4}


def test_short_line_styles_parse_as_values():
    args = line.parse(["--datafile", "X", "-y", "Y", "--comparable_linestyles", "solid", "--", "-.", ":",
                       "--plot_style", "--", "--logy"])
    assert args.comparable_linestyles == ["solid", "dashed", "dashdot", ":"]
    assert args.plot_style == "dashed" and args.logy


def test_shifted_steps_keep_box_legend_entries(make_project):
    """Steps with empty bins (stairs) show the same legend box as the others."""
    from matplotlib.patches import Rectangle

    x = np.arange(0.5, 10, 1.0)
    frame = pd.DataFrame([{"X": x, "Y": np.exp(-0.5 * (x - c) ** 2) + 0.01, "Sample": s}
                          for s, c in (("Ref", 4.5), ("Other", 6.5))])
    make_project({"S": frame})
    figures = _capture()
    line.main(["--datafile", "S", "-x", "X", "-y", "Y", "--hue", "Sample", "--shift", "peak", "--reference_value", "Ref"])
    handles = figures[0].axes[0].get_legend().legend_handles
    assert len(handles) == 2 and all(isinstance(h, Rectangle) for h in handles)


# --- T20: nested bands, sigma and Delta chi2 lines ----------------------------------


@pytest.fixture
def expected_limits():
    mass = np.linspace(110, 150, 9)
    expected = 0.5 + 0.01 * (mass - 110)
    return pd.DataFrame([
        {"Mass": mass, "MuLimit": expected * 1.2, "Limit": "Observed"},
        {"Mass": mass, "MuLimit": expected, "Limit": "Expected",
         "MuLimit1Sigma+": 0.2 * expected, "MuLimit1Sigma-": 0.15 * expected,
         "MuLimit2Sigma+": 0.5 * expected, "MuLimit2Sigma-": 0.3 * expected},
    ])


def _opaque_bands(ax):
    return [c for c in ax.collections if isinstance(c, PolyCollection) and c.get_alpha() in (None, 1.0)]


def test_brazil_bands_nested_with_legend(make_project, expected_limits):
    from plotipus.plot import BRAZIL_COLORS

    figures = _capture()
    make_project({"Limit": expected_limits})
    line.main(["--datafile", "Limit", "-x", "Mass", "-y", "MuLimit", "--hue", "Limit", "--plot_type", "line",
               "--errory", "--errory_column", "MuLimit1Sigma", "MuLimit2Sigma", "--band_colors", "brazil"])
    ax = figures[0].axes[0]
    bands = _opaque_bands(ax)
    assert len(bands) == 2
    by_color = {to_hex(b.get_facecolor()[0]): b for b in bands}
    inner, outer = by_color[BRAZIL_COLORS[0]], by_color[BRAZIL_COLORS[1]]
    assert inner.get_zorder() > outer.get_zorder()  # +-1 sigma on top
    assert all(b.get_zorder() < l.get_zorder() for b in bands for l in ax.get_lines())  # under the lines
    # The outer band reaches 0.5 x expected above the curve at the first point (asymmetric C+/C- sizes).
    assert np.isclose(outer.get_paths()[0].vertices[:, 1].max(), 1.5 * (0.5 + 0.4))
    labels = [t.get_text() for t in ax.get_legend().get_texts()]
    assert "Expected $\\pm1\\sigma$" in labels and "$\\pm2\\sigma$" in labels
    assert labels.index("Expected $\\pm1\\sigma$") < labels.index("$\\pm2\\sigma$")


def test_band_labels_and_graded_colors(make_project, expected_limits):
    from plotipus import style

    figures = _capture()
    make_project({"Limit": expected_limits})
    line.main(["--datafile", "Limit", "-x", "Mass", "-y", "MuLimit", "--hue", "Limit", "--plot_type", "line",
               "--errory", "--errory_column", "MuLimit1Sigma", "MuLimit2Sigma", "--band_labels", "68%", "95%"])
    ax = figures[0].axes[0]
    colors = sorted(to_hex(b.get_facecolor()[0]) for b in _opaque_bands(ax))
    muted, paper = style.role("muted"), style.role("paper")
    assert colors == sorted(style._mix(muted, paper, share) for share in (0.45, 0.2))  # an "expected" series
    labels = [t.get_text() for t in ax.get_legend().get_texts()]
    assert "68%" in labels and "95%" in labels


def test_single_errory_column_keeps_translucent_band(make_project, spectra):
    figures = _capture()
    run(make_project, spectra, "--hue", "Sample", "--select", "Stage", "-s", "Raw", "--plot_type", "line",
        "--errory", "--errory_column", "CountsError")
    ax = figures[0].axes[0]
    bands = [c for c in ax.collections if isinstance(c, PolyCollection)]
    assert len(bands) == 3 and all(b.get_alpha() < 1 for b in bands)
    assert all(not b.get_label() or b.get_label().startswith("_") for b in bands)


def test_sigma_lines_at_one_sided_pvalues(make_project, spectra):
    figures = _capture()
    run(make_project, spectra, "--select", "Sample", "-s", "A", "--select", "Stage", "-s", "Raw",
        "--plot_type", "line", "--logy", "--sigma_lines", "1", "2", "3")
    ax = figures[0].axes[0]
    levels = sorted(l.get_ydata()[0] for l in ax.get_lines() if l.get_linestyle() == "--")
    assert np.allclose(levels, [0.00135, 0.02275, 0.1587], rtol=1e-3)
    texts = {t.get_text(): t for t in ax.texts}
    assert {"1$\\sigma$", "2$\\sigma$", "3$\\sigma$"} <= set(texts)
    assert all(t.xy[0] > 0.9 and t.get_ha() == "right" for t in texts.values())


def test_delta_chi2_and_cl_lines():
    from plotipus.plot import delta_chi2_lines

    values, labels = delta_chi2_lines([1, 4, 2.3])
    assert values == [1, 4, 2.3] and labels[:2] == ["1$\\sigma$", "2$\\sigma$"] and "2.3" in labels[2]
    values, labels = delta_chi2_lines(levels=[68.27, 95.45])
    assert np.allclose(values, [1, 4], atol=1e-3) and labels == ["68.27% CL", "95.45% CL"]
    values, _ = delta_chi2_lines(levels=[68.27], dof=2)
    assert np.isclose(values[0], 2.30, atol=0.01)


@pytest.mark.parametrize("pos, ha, x", [(None, "right", 0.98), ("left", "left", 0.02)])
def test_horizontal_labels_on_one_side(make_project, spectra, pos, ha, x):
    figures = _capture()
    run(make_project, spectra, "--select", "Sample", "-s", "A", "--select", "Stage", "-s", "Raw",
        "--plot_type", "line", "--horizontal", "0.2", "0.6", "--horizontal_label", "low", "high",
        *(["--horizontal_label_pos", pos] if pos else []))
    texts = [t for t in figures[0].axes[0].texts if t.get_text() in ("low", "high")]
    assert len(texts) == 2
    assert all(t.get_ha() == ha and np.isclose(t.xy[0], x) and t.get_va() == "bottom" for t in texts)


def test_sigma_lines_dotted_with_labels_outside(make_project, spectra):
    figures = _capture()
    run(make_project, spectra, "--select", "Sample", "-s", "A", "--select", "Stage", "-s", "Raw",
        "--plot_type", "line", "--logy", "--sigma_lines", "1", "2", "--sigma_line_style", "dotted",
        "--sigma_line_color", "red", "--horizontal_label_pos", "outside")
    ax = figures[0].axes[0]
    lines = [l for l in ax.get_lines() if l.get_linestyle() == ":"]
    assert len(lines) == 2 and all(to_hex(l.get_color()) == "#ff0000" for l in lines)
    texts = [t for t in ax.texts if t.get_text() in ("1$\\sigma$", "2$\\sigma$")]
    assert len(texts) == 2 and all(t.xy[0] == 1.0 and t.get_ha() == "left" for t in texts)
    assert all(to_hex(t.get_color()) == "#ff0000" for t in texts)


# --- T22.15: --reference by hue value ---------------------------------------------------


@pytest.mark.parametrize("reference, value, index", [("2", None, 2), ("B", "B", 0), ("B", "C", 0)])
def test_reference_takes_index_or_hue_value(reference, value, index):
    argv = ["--datafile", "X", "-y", "Y", "--reference", reference]
    args = line.parse(argv + (["--reference_value", value] if value else []))
    assert args.reference == index and args.reference_value == (value or (None if reference == "2" else reference))


def test_reference_by_hue_value_in_ratio(make_project, spectra):
    figures = _capture()
    run(make_project, spectra, "--hue", "Sample", "--select", "Stage", "-s", "Raw", "--plot_type", "line",
        "--lower", "ratio", "--reference", "B")
    lower = figures[0].axes[1]
    ratios = {line.get_label(): line.get_ydata() for line in lower.get_lines()}
    assert np.allclose(ratios["A / B"], 0.5) and np.allclose(ratios["C / B"], 0.25)


# --- T22.5: --hue_cmap -------------------------------------------------------------------


def test_hue_cmap_ordered_values_and_colorbar(make_project, spectra):
    import matplotlib

    figures = _capture()
    run(make_project, spectra, "--hue", "Sample", "--select", "Stage", "-s", "Raw", "--plot_type", "line",
        "--hue_cmap", "plasma")
    fig = figures[0]
    ax = fig.axes[0]
    cmap = matplotlib.colormaps["plasma"]
    colors = {l.get_label(): to_hex(l.get_color()) for l in ax.get_lines() if not l.get_label().startswith("_")}
    assert len(set(colors.values())) == 3
    assert colors["A"] == to_hex(cmap(0.0)) and colors["C"] == to_hex(cmap(1.0))  # the ends of the map, in order
    assert ax.get_legend() is None
    (cbar,) = [a for a in fig.axes if hasattr(a, "_colorbar")]
    assert [t.get_text() for t in cbar.get_yticklabels()] == ["A", "B", "C"]


def test_hue_cmap_keeps_mapped_colours_and_style_legend(make_project, spectra, tmp_path):
    (tmp_path / "style.json").write_text('{"mappings": {"sample_colors": {"C": "black"}}}')
    figures = _capture()
    make_project({"Spectra": spectra}, 'style = ["style.json"]\n')
    line.main(["--datafile", "Spectra", "-x", "Energy", "-y", "Counts", "--hue", "Sample", "--style", "Stage",
               "--plot_type", "line", "--hue_cmap", "viridis", "--iterable_color_mapping", "sample_colors"])
    fig = figures[0]
    ax = fig.axes[0]
    colors = {to_hex(l.get_color()) for l in ax.get_lines() if l.get_label() == "C"}
    assert colors == {"#000000"}
    (cbar,) = [a for a in fig.axes if hasattr(a, "_colorbar")]
    assert [t.get_text() for t in cbar.get_yticklabels()] == ["A", "B"]
    legends = [a for a in ax.get_children() if isinstance(a, Legend)]
    assert legends and all("A" not in [t.get_text() for t in leg.get_texts()] for leg in legends)


def test_hue_cmap_rejects_unknown_map():
    with pytest.raises(SystemExit):
        line.parse(["--datafile", "X", "-y", "Y", "--hue_cmap", "notamap"])


# --- T22.12: bar lower panels ----------------------------------------------------------------


def test_column_lower_panel_as_bars(make_project):
    from matplotlib.patches import Rectangle

    p = np.linspace(0.05, 0.95, 10)
    frame = pd.DataFrame([{"Predicted": p, "Observed": p ** 1.2, "Count": np.arange(10.0) + 1, "Model": "clf"}])
    make_project({"Calib": frame})
    figures = _capture()
    line.main(["--datafile", "Calib", "-x", "Predicted", "-y", "Observed", "--hue", "Model", "--plot_type", "line",
               "--lower", "column:Count", "--lower_plot_type", "bar"])
    lower = figures[0].axes[1]
    bars = [r for r in lower.patches if isinstance(r, Rectangle) and r.get_height() > 0]
    assert len(bars) == 10
    assert np.allclose([b.get_width() for b in bars], 0.08)  # 80% of the 0.1 spacing
    assert np.allclose([b.get_height() for b in bars], np.arange(10.0) + 1)
    assert lower.get_xlim()[0] > -0.1 and lower.get_xlim()[1] < 1.1


# --- T22.10: smoothing and dates ---------------------------------------------------------------


def test_smooth_draws_raw_faint_and_smoothed_line(make_project):
    from plotipus.transforms import smooth

    x = np.arange(50.0)
    y = np.sin(x / 8) + np.where(x % 2, 0.5, -0.5)
    make_project({"Noisy": pd.DataFrame([{"X": x, "Y": y, "Run": "r1"}])})
    figures = _capture()
    line.main(["--datafile", "Noisy", "-x", "X", "-y", "Y", "--hue", "Run", "--plot_type", "line", "--smooth", "4",
               "--single_legend"])
    ax = figures[0].axes[0]
    raw = [l for l in ax.lines if l.get_alpha() is not None and l.get_alpha() < 1]
    smoothed = [l for l in ax.lines if l.get_label() == "r1"]
    assert len(raw) == 1 and np.allclose(raw[0].get_ydata(), y)
    assert len(smoothed) == 1 and np.allclose(smoothed[0].get_ydata(), smooth(y, 4))
    assert [t.get_text() for t in ax.get_legend().get_texts()] == ["r1"]


def test_smooth_kinds():
    from plotipus.transforms import smooth

    y = np.array([0.0, 2, 0, 2, 0, 2, 0])
    assert np.allclose(smooth(y, 3)[1:-1], [2 / 3, 4 / 3, 2 / 3, 4 / 3, 2 / 3])
    quadratic = np.arange(9.0) ** 2
    assert np.allclose(smooth(quadratic, 5, "savgol"), quadratic)  # a quadratic filter keeps a parabola
    assert np.isnan(smooth(np.array([1.0, np.nan, 3.0]), 2)[1])


def test_dates_on_x_get_concise_ticks(make_project):
    import matplotlib.dates as mdates

    days = pd.date_range("2024-01-01", periods=60, freq="D").to_numpy()
    make_project({"Daily": pd.DataFrame([{"Day": days, "Load": np.arange(60.0)}])})
    figures = _capture()
    line.main(["--datafile", "Daily", "-x", "Day", "-y", "Load", "--plot_type", "line"])
    ax = figures[0].axes[0]
    assert isinstance(ax.xaxis.get_major_formatter(), mdates.ConciseDateFormatter)
    assert np.isclose(ax.lines[0].get_xdata()[0], mdates.date2num(np.datetime64("2024-01-01")))


# --- T22.6: panel grids, facets and shared axes --------------------------------------------


@pytest.fixture
def quartet():
    x = np.arange(1.0, 6.0)
    rows = []
    for name, scale in (("I", 1.0), ("II", 2.0), ("III", 3.0), ("IV", 4.0)):
        for weighting in ("Raw", "Weighted"):
            for detector in ("H1", "L1"):
                rows.append({"X": x, "Y": scale * x * (2 if weighting == "Weighted" else 1), "Variable": name,
                             "Weighting": weighting, "Detector": detector, "Ratio": np.ones_like(x)})
    return pd.DataFrame(rows)


def _grid(make_project, frame, *argv):
    make_project({"Quartet": frame})
    figures = _capture()
    line.main(["--datafile", "Quartet", "-x", "X", "-y", "Y", "--plot_type", "line", *argv])
    return figures[0]


def _labels_shown(ax, axis):
    return any(t.get_visible() and t.get_text() for t in getattr(ax, f"get_{axis}ticklabels")())


def test_variables_grid_shares_outer_labels(make_project, quartet):
    fig = _grid(make_project, quartet, "--select", "Weighting", "Detector", "-s", "Raw", "H1",
                "--variables", "I", "II", "III", "IV", "--panel_grid", "2", "2")
    a, b, c, d = fig.axes[:4]
    fig.canvas.draw()
    assert a.get_shared_x_axes().joined(a, c) and a.get_shared_y_axes().joined(a, b)
    assert not _labels_shown(a, "x") and _labels_shown(c, "x")
    assert not _labels_shown(b, "y") and _labels_shown(a, "y")
    assert a.get_xlabel() == "" and c.get_xlabel() == "X" and b.get_ylabel() == ""


def test_facet_rows_with_lower_panels_and_per_row_settings(make_project, quartet):
    fig = _grid(make_project, quartet, "--select", "Variable", "Detector", "-s", "I", "H1", "--facet_row",
                "Weighting", "--lower", "column:Ratio", "--panel_labely", "Events", "Weights", "--panel_rangey",
                "0", "10", "0", "20", "--panel_lower_labely", "R1", "R2", "--panel_lower_rangey", "0", "2", "0", "3")
    top, top_lower, bottom, bottom_lower = fig.axes[:4]
    assert top.get_position().y0 > bottom.get_position().y1  # stacked rows
    assert top.get_ylim() == (0, 10) and bottom.get_ylim() == (0, 20)
    assert top_lower.get_ylim() == (0, 2) and bottom_lower.get_ylim() == (0, 3)
    assert (top.get_ylabel(), bottom.get_ylabel()) == ("Events", "Weights")
    assert (top_lower.get_ylabel(), bottom_lower.get_ylabel()) == ("R1", "R2")
    assert top.get_shared_x_axes().joined(top, bottom_lower)
    assert top_lower.get_xlabel() == "" and bottom_lower.get_xlabel() == "X"
    assert np.allclose(bottom.get_lines()[0].get_ydata(), 2 * np.arange(1.0, 6.0))  # the Weighted rows


def test_facet_col_with_variables_rows(make_project, quartet):
    fig = _grid(make_project, quartet, "--select", "Weighting", "-s", "Raw", "--variables", "I", "II", "III",
                "--facet_col", "Detector", "--variable_label_map", '{"H1": "Hanford"}')
    panels = fig.axes[:6]
    assert [ax.get_title() for ax in panels[:2]] == ["Hanford", "L1"]
    assert all(ax.get_title() == "" for ax in panels[2:])
    row_labels = [t.get_text() for ax in panels for t in ax.texts]
    assert row_labels == ["I", "II", "III"]  # right of the last column
    assert np.allclose(panels[3].get_lines()[0].get_ydata(), 2 * np.arange(1.0, 6.0))  # II, L1
    assert panels[0].get_shared_y_axes().joined(panels[0], panels[1])
    assert not panels[0].get_shared_y_axes().joined(panels[0], panels[2])


# --- T22.7: insets -----------------------------------------------------------------------


@pytest.fixture
def selections():
    x = np.arange(0.5, 20, 1.0)
    rows = []
    for selection, scale in (("All", 1.0), ("Tight", 0.25)):
        for sample, shape in (("Data", 1.0), ("Bkg", 0.9)):
            rows.append({"X": x, "Y": scale * shape * (10 + x), "Sample": sample, "Selection": selection,
                         "Month": np.arange(20) % 12 + 1})
    return pd.DataFrame(rows)


def _main_and_inset(fig):
    main = fig.axes[0]
    insets = [a for a in main.child_axes if getattr(a, "_plotipus_inset", False)]
    return main, insets


def test_zoom_inset_redraws_the_panel(make_project, selections):
    make_project({"Sel": selections})
    figures = _capture()
    line.main(["--datafile", "Sel", "-x", "X", "-y", "Y", "--hue", "Sample", "--select", "Selection", "-s", "All",
               "--plot_type", "line", "--labelx", "Mass", "--inset", "5", "10", "0", "25"])
    main, (inset,) = _main_and_inset(figures[0])
    assert inset.get_xlim() == (5, 10) and inset.get_ylim() == (0, 25)
    assert len(inset.get_lines()) == len(main.get_lines()) == 2
    assert inset.get_legend() is None and inset.get_xlabel() == "Mass"
    assert any("Inset" in type(a).__name__ or (type(a).__name__ == "Rectangle" and a in main.patches)
               for a in main.get_children())  # the zoom frame


def test_inset_args_draw_another_selection(make_project, selections):
    make_project({"Sel": selections})
    figures = _capture()
    line.main(["--datafile", "Sel", "-x", "X", "-y", "Y", "--hue", "Sample", "--select", "Selection", "-s", "All",
               "--plot_type", "line", "--rangey", "0", "40", "--lower", "ratio",
               "--inset_args", "--select Selection -s Tight", "--inset_pos", "0.1", "0.5", "0.3", "0.3"])
    fig = figures[0]
    main, (inset,) = _main_and_inset(fig)
    ys = sorted(line.get_ydata()[0] for line in inset.get_lines())
    assert np.allclose(ys, [0.25 * 0.9 * 10.5, 0.25 * 10.5])  # the Tight rows only
    assert inset.get_ylim() != (0, 40)  # the main range does not carry over
    assert len(fig.axes) == 2  # main + its ratio panel; the inset has none
    x0, y0, w, h = inset.get_position().bounds
    m = main.get_position()
    assert np.isclose(x0, m.x0 + 0.1 * m.width) and np.isclose(w, 0.3 * m.width)


def test_inset_of_a_binned_estimator(make_project, selections):
    make_project({"Sel": selections})
    figures = _capture()
    line.main(["--datafile", "Sel", "-x", "X", "-y", "Y", "--hue", "Sample", "--select", "Selection", "-s", "All",
               "--plot_type", "line", "--inset_args", "-x Month --select Sample Selection -s Data All --binned "
               "--estimator mean --bins 13"])
    _, (inset,) = _main_and_inset(figures[0])
    assert inset.get_lines() and inset.get_xlim()[1] <= 13.5


def test_band_only_series_has_a_band_in_the_legend(make_project):
    """A series drawn without a line (width 0) shows its band in the legend, with or without --band_colors."""
    from plotipus import style

    x = np.linspace(110, 150, 9)
    frame = pd.DataFrame([
        {"Mass": x, "P0": 1e-3 * np.ones_like(x), "Hypothesis": "Expected"},
        {"Mass": x, "P0": 1e-3 * np.ones_like(x), "Hypothesis": "Band", "Width": 0.0,
         "P0Error+": 5e-4 * np.ones_like(x), "P0Error-": 5e-4 * np.ones_like(x)},
    ])
    make_project({"P0": frame})
    figures = _capture()
    line.main(["--datafile", "P0", "-x", "Mass", "-y", "P0", "--hue", "Hypothesis", "--linewidth_column", "Width",
               "--plot_type", "line", "--errory", "--errory_type", "bands"])
    legend = figures[0].axes[0].get_legend()
    handles = dict(zip([t.get_text() for t in legend.get_texts()], legend.legend_handles))
    band = handles["Band"]
    assert not hasattr(band, "get_linewidth") or type(band).__name__ != "Line2D"
    alpha = band.get_alpha() if band.get_alpha() is not None else band.get_facecolor()[3]
    assert alpha == pytest.approx(style.band_alpha)  # the translucent band, as drawn
