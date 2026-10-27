import numpy as np
import pandas as pd
from matplotlib.legend import Legend

from plotipus.kinds import line
from plotipus.legacy import translate


def _fit_frame():
    x = np.linspace(-5, 5, 41)
    params = [10.0, 0.5, 1.2]
    y = 10.0 * np.exp(-0.5 * ((x - 0.5) / 1.2) ** 2) * (1 + 0.02 * np.sin(x))
    return pd.DataFrame([{
        "Values": x, "Counts": y, "CountsError": np.sqrt(np.abs(y)) + 0.1,
        "FitFunctionLabel": "Gaussian", "Params": params, "ParamsError": [0.3, 0.05, 0.04],
        "ParamsLabel": ["A", r"$\mu$", r"$\sigma$"], "ParamsUnit": ["", "cm", "cm"],
    }])


def test_fit_with_residual(make_project):
    out = make_project({"Fits": _fit_frame()})
    outputs = line.main(["--datafile", "Fits", "-x", "Values", "-y", "Counts", "--fit", "--lower", "residual",
                         "--chi2", "--errory", "--output_suffix", "fit.png"])
    assert outputs == ["fits_values_counts_error_fit.png"]
    assert (out / outputs[0]).exists()



def test_fit_subtitle_follows_the_medium(make_project):
    from plotipus import registry

    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    make_project({"Fits": _fit_frame()})
    for medium, keep, title in (("slides", [], "Gaussian Fit"), ("paper", [], ""), ("paper", ["--keep_title"],
                                                                                        "Gaussian Fit")):
        line.main(["--datafile", "Fits", "-x", "Values", "-y", "Counts", "--fit", "--medium", medium, *keep])
        assert figures[-1].axes[0].get_title() == title, (medium, keep)


def test_fit_with_pull(make_project):
    """--lower pull divides data - fit by the stored error instead of the fit."""
    from plotipus import registry

    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    make_project({"Fits": _fit_frame()})
    line.main(["--datafile", "Fits", "-x", "Values", "-y", "Counts", "--fit", "--lower", "pull"])
    lower = figures[-1].axes[1]
    frame = _fit_frame().iloc[0]
    a, mu, sigma = frame["Params"]
    expected = (frame["Counts"] - a * np.exp(-0.5 * ((frame["Values"] - mu) / sigma) ** 2)) / frame["CountsError"]
    assert lower.get_ylabel() == "Pull"
    assert np.allclose(lower.lines[0].get_ydata(), expected)

def _capture():
    from plotipus import registry

    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    return figures


def test_fit_residual_and_pull_panels(make_project):
    """Two --lower entries give two lower panels, each with its own label and range."""
    figures = _capture()
    make_project({"Fits": _fit_frame()})
    line.main(["--datafile", "Fits", "-x", "Values", "-y", "Counts", "--fit", "--errory",
               "--lower", "residual", "--lower", "pull"])
    _, residual, pull = figures[-1].axes
    # (a style may append the axis offset, e.g. "Residual (x10^-2)")
    assert residual.get_ylabel().startswith("Residual") and pull.get_ylabel().startswith("Pull")
    assert [t.get_text() for t in residual.texts] == [r"(Data $-$ Fit) / Fit"]
    values = pull.lines[0].get_ydata()
    limit = max(3.0, 1.2 * np.nanmax(np.abs(values)))
    assert np.allclose(pull.get_ylim(), (-limit, limit))
    assert sorted(round(abs(p.get_y()), 6) for p in pull.patches) == [1, 2]  # the +-1 and +-2 bands
    assert any(t.get_text() == r"(Data $-$ Fit) / $\sigma$" for t in pull.texts)


def test_fit_residual_masks_the_tails(make_project):
    """Bins where the fit is below 1e-3 of its maximum are not drawn as residuals."""
    figures = _capture()
    make_project({"Fits": _fit_frame()})
    line.main(["--datafile", "Fits", "-x", "Values", "-y", "Counts", "--fit", "--lower", "residual"])
    frame = _fit_frame().iloc[0]
    a, mu, sigma = frame["Params"]
    fit = a * np.exp(-0.5 * ((frame["Values"] - mu) / sigma) ** 2)
    drawn = figures[-1].axes[1].lines[0].get_ydata()
    tails = fit < 1e-3 * fit.max()
    assert tails.any() and np.isnan(drawn[tails]).all()
    assert np.allclose(drawn[~tails], ((frame["Counts"] - fit) / fit)[~tails])


def test_fit_pull_without_errors_warns_and_draws_nothing(make_project, capsys):
    figures = _capture()
    make_project({"Fits": _fit_frame().drop(columns="CountsError")})
    line.main(["--datafile", "Fits", "-x", "Values", "-y", "Counts", "--fit", "--lower", "pull"])
    assert not figures[-1].axes[1].collections and len(figures[-1].axes[1].lines) == 1  # only the zero line
    assert "--lower pull needs the CountsError column" in " ".join(capsys.readouterr().out.split())


def test_fit_without_lower(make_project):
    out = make_project({"Fits": _fit_frame()})
    outputs = line.main(["--datafile", "Fits", "-x", "Values", "-y", "Counts", "--fit", "--no-fit_errors",
                         "--max_fit_params", "2"])
    assert (out / outputs[0]).exists()


def test_residual_lower_panel_on_series(make_project):
    """--lower residual on ordinary series evaluates each row's stored model."""
    out = make_project({"Fits": _fit_frame().assign(Sample="A")})
    outputs = line.main(["--datafile", "Fits", "-x", "Values", "-y", "Counts", "--hue", "Sample",
                         "--plot_type", "line", "--lower", "residual"])
    assert (out / outputs[0]).exists()


def test_legacy_fit_translation():
    kind, args = translate(["scripts/script_line_fit.py", "--datafile", "Fits", "--chi", "--no-fit_errors",
                            "--bottom_labely", "Res"])
    assert kind == "line"
    assert {"--fit", "--chi2", "--no-fit_errors", "--lower_labely"} <= set(args)
    assert args[args.index("-y") + 1] == "Density"


def _signal_background_frame():
    x = np.linspace(100, 160, 30)
    params = [80.0, 125.0, 2.0, 1e4, 30.0]
    y = 80.0 * np.exp(-0.5 * ((x - 125) / 2) ** 2) + 1e4 * np.exp(-x / 30)
    return pd.DataFrame([{
        "Mass": x, "Counts": y, "CountsError": np.sqrt(y), "Sample": "Data",
        "FitFunction": "gaussian_plus_exponential", "FitFunctionLabel": "Signal + background",
        "Params": params, "ParamsError": [10.0, 0.4, 0.4, 1e3, 1.0],
        "ParamsLabel": ["A", "m", "s", "B", "t"],
        "FitComponents": {"Signal": ["gaussian", [0, 1, 2]], "Background": ["exponential", [3, 4]]},
    }])


def test_fit_components_as_data(make_project):
    """--fit --data_hue: ink data points, the fit and its dashed components, and the parameters in a legend."""
    from matplotlib.colors import to_hex
    from matplotlib.container import ErrorbarContainer

    from plotipus import registry, style

    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    make_project({"Fits": _signal_background_frame()})
    line.main(["--datafile", "Fits", "-x", "Mass", "-y", "Counts", "--hue", "Sample", "--fit", "--data_hue", "Data",
               "--chi2"])
    ax = figures[-1].axes[0]
    (container,) = [c for c in ax.containers if isinstance(c, ErrorbarContainer)]
    assert to_hex(container.lines[0].get_color()) == to_hex(style.role("ink"))
    lines = {l.get_label(): l for l in ax.lines if not l.get_label().startswith("_")}
    assert {"Fit", "Signal", "Background"} <= set(lines)
    assert lines["Signal"].get_linestyle() == "--"
    assert np.allclose(lines["Fit"].get_ydata(), lines["Signal"].get_ydata() + lines["Background"].get_ydata())
    legends = [a for a in ax.get_children() if isinstance(a, Legend)]
    entries = [[t.get_text() for t in legend.get_texts()] for legend in legends]
    assert ["Data", "Fit", "Signal", "Background"] in entries
    parameters = next(e for e in entries if e[0].startswith("A ="))
    assert parameters[-1].startswith(r"$\chi^2$/ndof")
    assert not ax.texts  # no fixed text box


def test_fit_parameter_box_at_position(make_project):
    from plotipus import registry

    figures = []
    registry.add_figure_hook(lambda fig, args: figures.append(fig))
    make_project({"Fits": _fit_frame()})
    line.main(["--datafile", "Fits", "-x", "Values", "-y", "Counts", "--fit", "--fitlegendposition", "0.6", "0.9"])
    texts = [t.get_text() for t in figures[-1].axes[0].texts]
    assert texts[0] == "Fit Parameters:" and texts[1].startswith("A = ")


def test_residual_against_a_fit_component(make_project):
    """--lower residual:COMPONENT: data minus the background, with the signal (fit minus background) over it."""
    figures = _capture()
    frame = _signal_background_frame()
    make_project({"Fits": frame})
    line.main(["--datafile", "Fits", "-x", "Mass", "-y", "Counts", "--hue", "Sample", "--fit", "--data_hue", "Data",
               "--errory", "--lower", "residual:Back"])
    lower = figures[-1].axes[1]
    x = frame["Mass"].iloc[0]
    background = 1e4 * np.exp(-x / 30)
    points = [l for l in lower.lines if l.get_marker() not in (None, "None", "")]
    assert np.allclose(points[0].get_ydata(), frame["Counts"].iloc[0] - background)
    curve = max(lower.lines, key=lambda l: len(l.get_xdata()))
    assert np.isclose(np.max(curve.get_ydata()), 80.0, rtol=1e-3)  # the signal peak
    assert "Background" in lower.texts[0].get_text()


def test_residual_against_a_missing_component_warns(make_project, capsys):
    make_project({"Fits": _signal_background_frame()})
    line.main(["--datafile", "Fits", "-x", "Mass", "-y", "Counts", "--hue", "Sample", "--fit", "--lower",
               "residual:Nope"])
    assert "no such fit component" in capsys.readouterr().out


def test_parse_residual_component():
    from plotipus.lower import parse_lower

    spec = parse_lower("residual:Bkg (4th order polynomial)")
    assert (spec.kind, spec.name, spec.component) == ("operation", "residual", "Bkg (4th order polynomial)")
    assert parse_lower("residual").component is None
