import numpy as np
import pandas as pd

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
