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
