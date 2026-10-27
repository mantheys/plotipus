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
    assert any("×10" in t for t in labels) and sum("×10" in t for t in labels) == 1


def test_error_scale_skips_series_without_errors(make_project, models):
    models["MuError"] = [models["MuError"].iloc[0]] + [np.full(8, np.nan)] * 3
    figures = _capture()
    make_project({"Hubble": models})
    line.main(["--datafile", "Hubble", "-x", "Z", "-y", "Mu", "--hue", "Model", "--plot_type", "line", "--errory",
               "--overlay", "data", "--error_scale", "10"])
    labels = [t.get_text() for t in figures[0].axes[0].get_legend().get_texts()]
    assert labels[0] == "data (errors ×10)" and not any("×" in t for t in labels[1:])


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
