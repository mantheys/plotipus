import numpy as np
import pandas as pd

from plotipus.kinds import line
from plotipus.legacy import translate


def _waveform():
    t = np.arange(0, 200.0, 2.0)
    return pd.DataFrame([{
        "Time": t, "Amplitude": np.exp(-((t - 80) / 15) ** 2), "Variable": "raw",
        "PhotonTime": np.array([70.0, 82.0, 95.0]), "PhotonArea": np.array([1.0, 2.0, 1.0]),
        "PhotonStart": np.array([68.0, 80.0, 93.0]), "PhotonEnd": np.array([72.0, 85.0, 97.0]),
    }])


def test_events_scatter(make_project):
    out = make_project({"Wave": _waveform()})
    outputs = line.main(["--datafile", "Wave", "-x", "Time", "-y", "Amplitude", "--lower", "events:Photon",
                         "--events_range", "--events_guides", "--series_label", "Raw"])
    assert outputs == ["Wave_data_Photon_scatter_line_scatter_panel.png"]
    assert (out / outputs[0]).exists()


def test_events_hist_without_lower(make_project):
    out = make_project({"Wave": _waveform()})
    outputs = line.main(["--datafile", "Wave", "-x", "Time", "-y", "Amplitude", "--lower", "events:Photon",
                         "--events_style", "hist", "--events_density", "--no_lower_plot", "-v", "raw"])
    assert outputs == ["Wave_data_Photon_raw_hist_line_scatter_panel.png"]
    assert (out / outputs[0]).exists()


def test_legacy_line2scatter_translation():
    kind, args = translate(["scripts/script_comapre_line2scatter.py", "--datafile", "W", "--lower_series", "Photon",
                            "--lower_show_range_bars", "--line_label", "Raw"])
    assert kind == "line"
    assert "events:Photon" in args and "--events_range" in args
    assert args[args.index("--series_label") + 1] == "Raw"
    assert args[args.index("-x") + 1] == "TimeNS"
